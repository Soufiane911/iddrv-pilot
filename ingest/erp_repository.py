"""Transactional persistence. Caller owns commit, allowing jobs and data to commit together."""
from datetime import datetime
import hashlib
import json
from uuid import UUID

from psycopg2.extras import Json, RealDictCursor

from .erp_models import ERPDeclaration, ImportCommitResult


class ERPConflict(ValueError):
    """The preview no longer describes current database state."""


def lock_site(cursor, site_id):
    """Serialize ERP work and hold the site's lifecycle row lock.

    The row lock is deliberate: archiving takes the same lock before disabling
    sources/connections, so an ERP preview or commit cannot cross the archive
    boundary between its checks and its writes.
    """
    cursor.execute('SELECT pg_advisory_xact_lock(1347568467, %s)', (site_id,))
    cursor.execute('SELECT status FROM sites WHERE id=%s FOR UPDATE', (site_id,))
    site = cursor.fetchone()
    if site is None:
        raise ERPConflict('site_not_found')
    status = site['status'] if isinstance(site, dict) else site[0]
    if status == 'archived':
        raise ERPConflict('site_archived')


def persist_declarations(conn, *, site_id: int, passport_id: UUID, declarations: list[ERPDeclaration], recorded_at: datetime) -> ImportCommitResult:
    result = ImportCommitResult()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        lock_site(cur, site_id)
        cur.execute('SELECT status FROM sites WHERE id=%s', (site_id,))
        site = cur.fetchone()
        if not site:
            raise ERPConflict('site_not_found')
        if site['status'] == 'archived':
            raise ERPConflict('site_archived')
        seen = set()
        order_observations = {}
        for declaration in declarations:
            cur.execute('SELECT id,status FROM machines WHERE site_id=%s AND erp_ref=%s', (site_id, declaration.machine_ref))
            machine = cur.fetchone()
            if machine is None:
                raise ValueError('machine_creation_not_confirmed')
            if machine.get('status', 'active') == 'archived':
                raise ERPConflict('machine_archived')
            machine_id = machine['id']
            cur.execute(
                '''INSERT INTO work_orders(site_id,order_number,order_number_normalized,created_by)
                   VALUES (%s,%s,lower(btrim(%s)),%s)
                   ON CONFLICT (site_id,order_number_normalized) DO NOTHING''',
                (site_id, declaration.order_ref, declaration.order_ref, 'erp-import'),
            )
            cur.execute(
                'SELECT id FROM work_orders WHERE site_id=%s AND order_number_normalized=lower(btrim(%s)) FOR UPDATE',
                (site_id, declaration.order_ref),
            )
            work_order = cur.fetchone()
            cur.execute(
                '''INSERT INTO work_order_allocations(site_id,work_order_id,machine_id,created_by)
                   VALUES (%s,%s,%s,%s) ON CONFLICT (site_id,work_order_id,machine_id) DO NOTHING''',
                (site_id, work_order['id'], machine_id, 'erp-import'),
            )
            key = declaration.key(site_id, machine_id)
            if key in seen:
                raise ValueError('duplicate_declaration_key')
            seen.add(key)
            cur.execute('''INSERT INTO production_orders (site_id,id,machine_id,started_at,erp_good_parts,erp_scrap_count)
                           VALUES (%s,%s,NULL,%s,NULL,NULL) ON CONFLICT(site_id,id) DO NOTHING''',
                        (site_id, declaration.order_ref, declaration.shift_started_at))
            cur.execute('''INSERT INTO erp_declarations(site_id,machine_id,production_order_id,declaration_key)
                           VALUES (%s,%s,%s,%s) ON CONFLICT(site_id,declaration_key) DO NOTHING''',
                        (site_id, machine_id, declaration.order_ref, key))
            cur.execute('''SELECT d.id,d.superseded_by,r.revision_number,r.content_hash,r.id AS revision_id
                           FROM erp_declarations d LEFT JOIN erp_declaration_revisions r ON r.id=d.current_revision_id
                           WHERE d.site_id=%s AND d.declaration_key=%s FOR UPDATE OF d''', (site_id, key))
            current = cur.fetchone()
            content_hash = declaration.fingerprint()
            cur.execute('SELECT 1 FROM erp_declaration_revisions WHERE declaration_id=%s AND content_hash=%s', (current['id'], content_hash))
            if cur.fetchone():
                result.unchanged += 1
                continue
            if current['superseded_by']:
                raise ERPConflict('declaration_superseded')
            values = declaration.values()
            columns = ['site_id','declaration_id','production_order_id','revision_number','passport_id','recorded_at',
                       'sheet_name','source_row','shift_started_at','shift_number','order_type','tool_ref','product_ref',
                       'production_started_at','production_ended_at','bounds_origin','calendar_version',
                       'produced_parts','good_parts','scrap_parts','cycle_count','cavities_actual','declared_scrap_rate',
                       'declared_trs','available_hours','total_stop_hours','running_hours','opening_hours','cycle_time_s','raw_data','warnings','content_hash','estimated_bounds']
            values.update(site_id=site_id, production_order_id=declaration.order_ref, declaration_id=current['id'], revision_number=(current['revision_number'] or 0) + 1,
                          passport_id=str(passport_id), recorded_at=recorded_at, estimated_bounds=Json(sorted(declaration.estimated_bounds)), raw_data=Json(declaration.raw_data), warnings=Json(declaration.warnings), content_hash=content_hash)
            cur.execute(f"INSERT INTO erp_declaration_revisions ({','.join(columns)}) VALUES ({','.join(['%s'] * len(columns))}) RETURNING id",
                        [values[column] for column in columns])
            revision_id = cur.fetchone()['id']
            cur.execute('UPDATE erp_declarations SET current_revision_id=%s WHERE site_id=%s AND id=%s', (revision_id, site_id, current['id']))
            if current['revision_number']:
                result.revised += 1
            else:
                result.created += 1
            result.awaiting_context += declaration.production_ended_at is None
            observations = {field: values[field] for field in declaration.provided_order_fields if field != 'order_status_effective_at'}
            if observations:
                effective_at = declaration.order_status_effective_at
                observation_hash = hashlib.sha256(json.dumps([effective_at.isoformat() if effective_at else None, observations, key, content_hash], sort_keys=True).encode()).hexdigest()
                group_key = (declaration.order_ref, effective_at, json.dumps(observations, sort_keys=True))
                if group_key in order_observations:
                    cur.execute('INSERT INTO production_order_observation_sources VALUES(%s,%s) ON CONFLICT DO NOTHING', (order_observations[group_key], revision_id))
                    continue
                cur.execute('''INSERT INTO production_order_revisions(site_id,production_order_id,passport_id,declaration_revision_id,
                               effective_at,recorded_at,values,content_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                               ON CONFLICT(site_id,production_order_id,content_hash) DO NOTHING RETURNING id''',
                            (site_id, declaration.order_ref, str(passport_id), revision_id, effective_at, recorded_at, Json(observations), observation_hash))
                observation_id = cur.fetchone()['id']
                order_observations[group_key] = observation_id
                cur.execute('INSERT INTO production_order_observation_sources VALUES(%s,%s) ON CONFLICT DO NOTHING', (observation_id, revision_id))
        # ERP confirmation is a valid reconciliation trigger too: receipts
        # may have arrived before either the OF or its press line existed.
        from backend.app.source_repository import replay_pending_receipts_in_transaction
        replay_pending_receipts_in_transaction(cur, site_id=site_id)
    return result

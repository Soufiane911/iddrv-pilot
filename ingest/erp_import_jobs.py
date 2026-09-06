"""Preview planning and durable approved imports, shared by API and watcher."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID
import hashlib

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from .erp_models import ERPRowIssue, ImportCommitResult
from .erp_reader import MAPPING, ORDER_FIELDS, local_datetime, normalize, read_trs_declarations
from .erp_repository import ERPConflict, lock_site, persist_declarations
from .runtime_config import worker_database_url


def current_calendar(cur, site_id):
    cur.execute('SELECT * FROM site_shift_calendars WHERE site_id=%s ORDER BY version DESC LIMIT 1', (site_id,))
    value = cur.fetchone()
    return dict(value) if value else None


def apply_calendar(declaration, calendar):
    if declaration.production_ended_at or not calendar:
        return
    from zoneinfo import ZoneInfo
    local = declaration.shift_started_at.astimezone(ZoneInfo(calendar['timezone']))
    if local.date() < calendar['valid_from'] or (calendar['valid_to'] and local.date() > calendar['valid_to']):
        return
    shift = next((shift for shift in calendar['shifts'] if shift['number'] == declaration.shift_number), None)
    if not shift or local.strftime('%H:%M') != shift['start'][:5]:
        return
    start_time = datetime.strptime(shift['start'][:5], '%H:%M').time()
    end_time = datetime.strptime(shift['end'][:5], '%H:%M').time()
    end_date = local.date() + timedelta(days=end_time <= start_time)
    try:
        end = local_datetime(datetime.combine(end_date, end_time), calendar['timezone'])
    except ValueError:
        return
    if end <= (declaration.production_started_at or declaration.shift_started_at):
        return
    if declaration.production_started_at is None:
        declaration.production_started_at = declaration.shift_started_at
        declaration.estimated_bounds.add('production_started_at')
    declaration.production_ended_at = end
    declaration.estimated_bounds.add('production_ended_at')
    declaration.bounds_origin = 'calendar'
    declaration.calendar_version = calendar['version']


def validate_order_observations(result):
    """Conflicting values need a source effective date, never row/UUID ordering."""
    groups = {}
    for declaration in result.declarations:
        groups.setdefault(declaration.order_ref, []).append(declaration)
    for rows in groups.values():
        for field in ('order_status', 'order_target_quantity', 'coverage_complete'):
            observed = [row for row in rows if field in row.provided_order_fields]
            conflict = any(getattr(a, field) != getattr(b, field) and
                (a.order_status_effective_at is None or b.order_status_effective_at is None or
                 a.order_status_effective_at == b.order_status_effective_at)
                for i,a in enumerate(observed) for b in observed[i+1:])
            if conflict:
                result.issues.append(ERPRowIssue(observed[0].source_row, 'order_observations_conflict', field,
                    'Contexte OF contradictoire : fournir des dates effectives distinctes pour ordonner les observations.'))


def read_request(cur, request, choices):
    cur.execute('SELECT timezone FROM sites WHERE id=%s', (request['site_id'],))
    site = cur.fetchone()
    if not site:
        raise ValueError('site_not_found')
    path = Path(request['raw_path'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != request['file_hash']:
        raise ERPConflict('source_file_changed')
    result = read_trs_declarations(path, source_timezone=site['timezone'], sheet_name=choices.get('sheet_name'))
    calendar = current_calendar(cur, request['site_id'])
    for declaration in result.declarations:
        confirmed = set(choices.get('confirmed_order_fields', []))
        declaration.provided_order_fields &= confirmed
        for field in ORDER_FIELDS - declaration.provided_order_fields:
            setattr(declaration, field, None)
        if declaration.order_ref in choices.get('complete_order_refs', []):
            declaration.coverage_complete = True
            declaration.provided_order_fields.add('coverage_complete')
        apply_calendar(declaration, calendar)
    validate_order_observations(result)
    return result, calendar


def build_preview(cur, request, choices):
    # caller holds the per-site lock so this snapshot is internally consistent.
    result, calendar = read_request(cur, request, choices)
    cur.execute("SELECT id,erp_ref FROM machines WHERE site_id=%s AND status <> 'archived'", (request['site_id'],))
    machines = {row['erp_ref']: row['id'] for row in cur.fetchall()}
    cur.execute('''SELECT d.id,d.declaration_key,d.machine_id,d.production_order_id,d.superseded_by,
                          r.revision_number,r.content_hash,r.shift_started_at,r.shift_number
                   FROM erp_declarations d JOIN erp_declaration_revisions r ON r.id=d.current_revision_id
                   WHERE d.site_id=%s''', (request['site_id'],))
    rows = [dict(row) for row in cur.fetchall()]
    current = {row['declaration_key']: row for row in rows}
    items, snapshot, new_machines = [], {}, set()
    counts = {'created': 0, 'revised': 0, 'unchanged': 0}
    for declaration in result.declarations:
        machine_id = machines.get(declaration.machine_ref)
        key = declaration.key(request['site_id'], machine_id) if machine_id is not None else None
        existing = current.get(key)
        historical_replay = False
        if existing and (existing['superseded_by'] or existing['content_hash'] != declaration.fingerprint()):
            cur.execute('SELECT 1 FROM erp_declaration_revisions WHERE declaration_id=%s AND content_hash=%s', (existing['id'], declaration.fingerprint()))
            historical_replay = cur.fetchone() is not None
            if existing['superseded_by'] and not historical_replay:
                result.issues.append(ERPRowIssue(declaration.source_row, 'identity_superseded', None, 'Cette identité a été remplacée. Utilisez l’identité courante.'))
        state = 'unchanged' if historical_replay or (existing and existing['content_hash'] == declaration.fingerprint()) else 'revised' if existing else 'created'
        counts[state] += 1
        if machine_id is None:
            new_machines.add(declaration.machine_ref)
        snapshot[str(declaration.source_row)] = {'key': key, 'revision': existing['revision_number'] if existing else None,
                                                'id': str(existing['id']) if existing else None}
        candidates = [row for row in rows if not row['superseded_by'] and row['machine_id'] == machine_id
                      and row['production_order_id'] == declaration.order_ref
                      and row['shift_started_at'] == declaration.shift_started_at and not existing]
        items.append({'source_row': declaration.source_row, 'machine_ref': declaration.machine_ref, 'order_ref': declaration.order_ref,
                      'shift_started_at': declaration.shift_started_at.isoformat(), 'shift_number': declaration.shift_number,
                      'produced_parts': declaration.produced_parts, 'good_parts': declaration.good_parts, 'scrap_parts': declaration.scrap_parts,
                      'cycle_count': declaration.cycle_count, 'warnings': declaration.warnings, 'bounds_origin': declaration.bounds_origin,
                      'production_ended_at': declaration.production_ended_at.isoformat() if declaration.production_ended_at else None,
                      'order_target_quantity': declaration.order_target_quantity, 'order_status': declaration.order_status,
                      'change': state, 'historical_replay': historical_replay, 'declaration_id': str(existing['id']) if existing else None,
                      'revision': existing['revision_number'] if existing else None,
                      'identity_candidates': [{'declaration_id': str(row['id']), 'expected_revision': row['revision_number']} for row in candidates]})
    # Raw rows are never included in the public preview (they can contain names).
    return {'items': items, 'counts': counts, 'issues': [asdict(issue) for issue in result.issues],
            'sheet_name': result.sheet_name, 'sheets': result.sheets, 'header_row': result.header_row,
            'new_machine_refs': sorted(new_machines), 'calendar_version': calendar['version'] if calendar else None,
            'snapshot': snapshot, 'choices': choices,
            'order_fields_available': sorted({field for declaration in result.declarations
                                              for field in ORDER_FIELDS if any(MAPPING.get(normalize(header)) == field for header in declaration.raw_data)})}


def validate_replacements(cur, site_id, preview, replacements):
    seen, source_rows = set(), set()
    for replacement in replacements:
        value = str(replacement['declaration_id'])
        if value in seen or replacement['source_row'] in source_rows:
            raise ERPConflict('duplicate_replacement')
        seen.add(value)
        source_rows.add(replacement['source_row'])
        source = next((row for row in preview['items'] if row['source_row'] == replacement['source_row']), None)
        if source is None or source['change'] != 'created':
            raise ERPConflict('replacement_requires_new_identity')
        cur.execute('''SELECT d.production_order_id,d.superseded_by,r.revision_number FROM erp_declarations d
                       JOIN erp_declaration_revisions r ON r.id=d.current_revision_id WHERE d.site_id=%s AND d.id=%s''', (site_id, value))
        old = cur.fetchone()
        if not old or old['superseded_by'] or old['revision_number'] != replacement['expected_revision']:
            raise ERPConflict('replacement_stale_or_unavailable')


def create_passport(cur, request, count):
    cur.execute('''INSERT INTO import_passports(site_id,file_name,file_hash,file_path_raw,parser_type,brand_detected,
                   encoding_detected,row_count_total,row_count_accepted,status,metadata)
                   VALUES (%s,%s,%s,%s,'erp_declarations','erp','xlsx',%s,%s,'completed',%s)
                   ON CONFLICT (site_id,file_hash) WHERE file_hash IS NOT NULL DO UPDATE SET status='completed'
                   RETURNING id''', (request['site_id'], request['original_name'], request['file_hash'], request['raw_path'], count, count,
                                    Json({'grain': 'team_order_declaration', 'import_request_id': str(request['id'])})))
    return cur.fetchone()['id']


def commit_request(conn, request):
    site_id = request['site_id']
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        lock_site(cur, site_id)
        choices = request['choices']
        preview = request['preview']
        latest = build_preview(cur, request, choices)
        if latest['calendar_version'] != preview['calendar_version'] or latest['snapshot'] != preview['snapshot'] or latest['new_machine_refs'] != preview['new_machine_refs']:
            raise ERPConflict('preview_stale')
        if any(issue['severity'] == 'error' for issue in latest['issues']) or not latest['items']:
            raise ValueError('preview_has_errors')
        replacements = choices.get('replacements', [])
        validate_replacements(cur, site_id, preview, replacements)
        new_ids = []
        for ref in latest['new_machine_refs']:
            if ref not in choices.get('create_machine_refs', []):
                raise ValueError('machine_creation_not_confirmed')
            cur.execute('SELECT status FROM sites WHERE id=%s FOR SHARE', (site_id,))
            site = cur.fetchone()
            if not site or site['status'] == 'archived':
                raise ERPConflict('site_archived')
            cur.execute('INSERT INTO machines(site_id,erp_ref,name) VALUES (%s,%s,%s) RETURNING id', (site_id, ref, f'Presse {ref}'))
            new_ids.append(cur.fetchone()['id'])
        result, _ = read_request(cur, request, choices)
        passport_id = create_passport(cur, request, len(result.declarations))
        now = datetime.now(timezone.utc)
        from .context_repository import site_periods, reconcile_changes
        old_periods = site_periods(conn, site_id, now)
        committed = persist_declarations(conn, site_id=site_id, passport_id=passport_id, declarations=result.declarations, recorded_at=now)
        committed.new_machine_ids = new_ids
        for replacement in replacements:
            declaration = next(item for item in result.declarations if item.source_row == replacement['source_row'])
            cur.execute('SELECT id FROM machines WHERE site_id=%s AND erp_ref=%s', (site_id, declaration.machine_ref))
            key = declaration.key(site_id, cur.fetchone()['id'])
            cur.execute('SELECT id FROM erp_declarations WHERE site_id=%s AND declaration_key=%s', (site_id, key))
            new_id = cur.fetchone()['id']
            cur.execute('UPDATE erp_declarations SET superseded_by=%s,superseded_recorded_at=%s WHERE site_id=%s AND id=%s',
                        (new_id, now, site_id, str(replacement['declaration_id'])))
        reconcile_changes(conn, site_id, old_periods, now)
        cur.execute("UPDATE erp_import_requests SET state='completed',passport_id=%s,result=%s,completed_at=%s,public_error=NULL WHERE id=%s", (passport_id, Json(asdict(committed)), now, str(request['id'])))
    return committed


def process_approved_erp_import(import_id: UUID, *, database_url: str | None = None) -> ImportCommitResult:
    conn = psycopg2.connect(database_url or worker_database_url())
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Transaction-level lock means a crash leaves the queued job claimable.
                cur.execute('SELECT * FROM erp_import_requests WHERE id=%s FOR UPDATE SKIP LOCKED', (str(import_id),))
                request = cur.fetchone()
                if not request:
                    raise ERPConflict('job_busy_or_missing')
                if request['state'] == 'completed':
                    return ImportCommitResult(**request['result'])
                if request['state'] not in {'queued', 'processing'}:
                    raise ERPConflict('job_not_queued')
                cur.execute("UPDATE erp_import_requests SET state='processing' WHERE id=%s", (str(import_id),))
            return commit_request(conn, request)
    except Exception as error:
        conn.rollback()
        # Do not expose exception text, workbook cells or filesystem paths.
        if str(error) not in {'job_busy_or_missing', 'job_not_queued'}:
            with conn, conn.cursor() as cur:
                public_error = 'site_archived' if str(error) == 'site_archived' else 'preview_stale' if isinstance(error, ERPConflict) else 'import_processing_failed'
                cur.execute("UPDATE erp_import_requests SET state='failed',public_error=%s WHERE id=%s AND state IN ('queued','processing')", (public_error, str(import_id)))
        raise
    finally:
        conn.close()


def process_pending_erp_imports(limit=10, *, database_url: str | None = None):
    from contextlib import closing
    with closing(psycopg2.connect(database_url or worker_database_url())) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM erp_import_requests WHERE state IN ('queued','processing') ORDER BY created_at LIMIT %s", (limit,))
        ids = [row[0] for row in cur.fetchall()]
    outcomes = []
    for import_id in ids:
        try:
            process_approved_erp_import(import_id, database_url=database_url)
            outcomes.append('erp_completed')
        except Exception:
            outcomes.append('erp_failed')
    return outcomes

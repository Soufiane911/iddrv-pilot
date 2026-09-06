"""One PostgreSQL transaction owns event identity, cycle, scoring job and offset."""
from datetime import datetime, timedelta
import hashlib
import json
import math
import os
from uuid import UUID

from psycopg2.extras import Json, RealDictCursor
from psycopg2 import sql

from .http_source import MEASUREMENTS, SourceError
from .models import CollectionResult, CyclePage


def _json_safe(value):
    # Invalid IEEE values cannot enter JSONB; preserve their literal spelling as rejection evidence.
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def store_page(conn, *, connection_id: UUID, page: CyclePage, received_at: datetime) -> CollectionResult:
    inserted = duplicates = rejected = conflicts = 0
    inserted_dates = []
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Use the same lock order as ERP and archive transactions:
            # advisory site lock first, then the lifecycle row lock. Acquiring
            # the row first would deadlock with lock_site().
            cur.execute('SELECT site_id FROM machine_connections WHERE id=%s', (str(connection_id),))
            source = cur.fetchone()
            if not source:
                raise SourceError('connection_not_found')
            from ingest.erp_repository import ERPConflict, lock_site
            try:
                lock_site(cur, source['site_id'])
            except ERPConflict as exc:
                raise SourceError(str(exc)) from None
            cur.execute('SELECT * FROM machine_connections WHERE id=%s FOR UPDATE', (str(connection_id),))
            connection = cur.fetchone()
            if not connection or page.machine_id != connection['external_machine_id']:
                raise SourceError('machine_identity_mismatch')
            cur.execute('SELECT status FROM machines WHERE id=%s AND site_id=%s FOR SHARE', (connection['machine_id'], connection['site_id']))
            machine = cur.fetchone()
            if not machine:
                raise SourceError('machine_not_found')
            if machine['status'] == 'archived':
                raise SourceError('machine_archived')
            cur.execute('SELECT * FROM machine_stream_offsets WHERE connection_id=%s FOR UPDATE', (str(connection_id),))
            offset = cur.fetchone()
            if offset and offset['stream_id'] != page.stream_id:
                raise SourceError('stream_changed', state='gap_detected')
            sequence = offset['last_sequence'] if offset else None
            # A stale/replayed page may only contain known identities, never move an offset backward.
            stale = offset is not None and page.after != offset['cursor']
            for item in page.items:
                digest = hashlib.sha256(json.dumps(item.raw, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
                cur.execute('SELECT id,payload_hash FROM machine_source_events WHERE connection_id=%s AND stream_id=%s AND event_id=%s',
                            (str(connection_id), page.stream_id, item.event_id))
                existing = cur.fetchone()
                if existing:
                    if existing['payload_hash'] == digest:
                        duplicates += 1
                    else:
                        conflicts += 1
                        cur.execute('UPDATE machine_source_events SET conflict_count=conflict_count+1,last_conflict_at=%s WHERE id=%s', (received_at, existing['id']))
                    continue
                if stale or sequence is not None and item.sequence <= sequence:
                    raise SourceError('sequence_not_progressive')
                cur.execute('''INSERT INTO machine_source_events(connection_id,site_id,machine_id,stream_id,event_id,sequence,cycle_ended_at,received_at,payload_hash,payload,status,rejection_reason)
                            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                            (str(connection_id), connection['site_id'], connection['machine_id'], page.stream_id, item.event_id, item.sequence,
                             item.cycle_ended_at, received_at, digest, Json(_json_safe(item.raw)), 'rejected' if item.rejection_reason else 'accepted', item.rejection_reason))
                event_id = cur.fetchone()['id']
                sequence = item.sequence
                if item.rejection_reason:
                    rejected += 1
                    continue
                fields = {'time': item.cycle_ended_at, 'machine_id': connection['machine_id'], 'source_event_id': event_id,
                          'cycle_counter': item.cycle_counter, 'production_order_id': None, 'good_parts': None, 'scrap_flag': None,
                          'part_quality_status': None, 'link_confidence': None, 'raw_data': Json(_json_safe(item.raw))}
                fields.update({column: item.measurements[key] for key, (column, _) in MEASUREMENTS.items() if key in item.measurements})
                cur.execute(sql.SQL('INSERT INTO machine_cycles ({}) VALUES ({})').format(
                    sql.SQL(',').join(map(sql.Identifier, fields)), sql.SQL(',').join(sql.Placeholder() for _ in fields)), list(fields.values()))
                cur.execute('''INSERT INTO hdt_scoring_jobs(event_id,machine_id,site_id,model_version,mode,calculation_revision)
                            VALUES(%s,%s,%s,%s,'live',1)''',
                            (event_id, connection['machine_id'], connection['site_id'], os.getenv('TELEMETRY_MODEL_VERSION', 'hdt-process-drift-iforest-v1')))
                inserted += 1
                inserted_dates.append(item.cycle_ended_at)
            stale = stale or (offset is not None and bool(page.items) and inserted + rejected == 0)
            cursor = offset['cursor'] if stale else page.next_cursor
            if not stale:
                if offset and page.items and cursor == offset['cursor'] and inserted + rejected > 0:
                    raise SourceError('cursor_not_progressive')
                if offset and not page.items and cursor != offset['cursor']:
                    raise SourceError('cursor_not_progressive')
                cur.execute('''INSERT INTO machine_stream_offsets(connection_id,stream_id,cursor,last_sequence,committed_at)
                              VALUES(%s,%s,%s,%s,%s) ON CONFLICT(connection_id) DO UPDATE SET cursor=EXCLUDED.cursor,last_sequence=EXCLUDED.last_sequence,committed_at=EXCLUDED.committed_at''',
                            (str(connection_id), page.stream_id, cursor, sequence, received_at))
            if inserted_dates:
                from ingest.context_repository import reconcile_period
                # Reception and context reconciliation already hold the site
                # lock acquired before any event was written.
                cur.execute('SELECT clock_timestamp() AS known_at')
                context_known_at = cur.fetchone()['known_at']
                reconcile_period(conn, site_id=connection['site_id'], machine_id=connection['machine_id'],
                    start=min(inserted_dates), end=max(inserted_dates)+timedelta(microseconds=1), known_at=context_known_at)
            last_cycle = max(inserted_dates) if inserted_dates else None
            cur.execute('''UPDATE machine_connections SET last_response_at=%s,last_success_at=%s,
                        last_cycle_at=CASE WHEN %s::timestamptz IS NULL THEN last_cycle_at ELSE GREATEST(last_cycle_at,%s::timestamptz) END,
                        state=%s,public_error=%s,failure_count=0,next_poll_at=%s + (CASE WHEN %s THEN 0 ELSE poll_interval_s END)*interval '1 second',updated_at=%s WHERE id=%s''',
                        (received_at, received_at, last_cycle, last_cycle, 'contract_error' if conflicts else 'collecting',
                         'event_content_conflict' if conflicts else None, received_at, page.has_more, received_at, str(connection_id)))
    return CollectionResult(inserted, duplicates, rejected, cursor, inserted, conflicts, 'contract_error' if conflicts else 'collecting')

"""API persistence for uploads, previews, calendars and controlled machine creation."""
from psycopg2.extras import Json, RealDictCursor

from ingest.erp_import_jobs import build_preview, current_calendar, validate_replacements
from ingest.erp_repository import ERPConflict, lock_site
from .db import get_connection


def get_request(import_id):
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT * FROM erp_import_requests WHERE id=%s', (str(import_id),))
        row = cur.fetchone()
        return dict(row) if row else None


def public_request(request):
    return {key: request.get(key) for key in ('id', 'site_id', 'original_name', 'state', 'preview_version', 'passport_id', 'created_at', 'confirmed_at', 'completed_at', 'result', 'public_error')}


def public_preview(request):
    preview = {key: value for key, value in request.get('preview', {}).items() if key != 'snapshot'}
    empty = {'items': [], 'counts': {'created': 0, 'revised': 0, 'unchanged': 0},
             'issues': [], 'sheets': [], 'sheet_name': '', 'header_row': 0,
             'new_machine_refs': [], 'order_fields_available': [], 'calendar_version': None, 'choices': {}}
    return {**empty, **public_request(request), **preview}


def create_request(*, site_id, creator_id, raw_path, original_name, file_hash):
    with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        lock_site(cur, site_id)
        cur.execute('''INSERT INTO erp_import_requests(site_id,creator_id,raw_path,original_name,file_hash,state)
                       VALUES (%s,%s,%s,%s,%s,'uploaded') RETURNING *''',
                    (site_id, creator_id, raw_path, original_name, file_hash))
        return public_request(dict(cur.fetchone()))


def list_requests(site_id):
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT * FROM erp_import_requests WHERE site_id=%s ORDER BY created_at DESC LIMIT 100', (site_id,))
        return [public_request(dict(row)) for row in cur.fetchall()]


def _preview_request(import_id, *, refresh=False, choices=None):
    with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Lock request before site, matching worker/confirmation lock order.
        cur.execute('SELECT * FROM erp_import_requests WHERE id=%s FOR UPDATE', (str(import_id),))
        row = cur.fetchone()
        if row is None:
            raise ERPConflict('import_not_found')
        request = dict(row)
        lock_site(cur, request['site_id'])
        if request['state'] in {'queued', 'processing', 'completed'}:
            return public_preview(request)
        if request['preview_version'] and not refresh:
            return public_preview(request)
        chosen = choices if choices is not None else request['choices']
        cur.execute("UPDATE erp_import_requests SET state='profiling' WHERE id=%s", (str(import_id),))
        preview = build_preview(cur, request, chosen)
        cur.execute('''UPDATE erp_import_requests SET state='preview_ready',preview_version=preview_version+1,
                       choices=%s,preview=%s,public_error=NULL WHERE id=%s RETURNING *''', (Json(chosen), Json(preview), str(import_id)))
        return public_preview(dict(cur.fetchone()))


def preview_request(import_id, *, refresh=False, choices=None):
    try:
        return _preview_request(import_id, refresh=refresh, choices=choices)
    except ERPConflict:
        # Do not mutate a request after an archive race.
        raise
    except Exception:
        # The workbook stays in raw storage; only a public failure code is stored.
        with get_connection() as conn, conn, conn.cursor() as cur:
            cur.execute("UPDATE erp_import_requests SET state='failed',public_error='xlsx_preview_failed' WHERE id=%s AND state NOT IN ('queued','processing','completed')", (str(import_id),))
        raise


def confirm_request(import_id, payload):
    with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT * FROM erp_import_requests WHERE id=%s FOR UPDATE', (str(import_id),))
        row = cur.fetchone()
        if row is None:
            raise ERPConflict('import_not_found')
        request = dict(row)
        lock_site(cur, request['site_id'])
        if payload['preview_version'] != request['preview_version']:
            raise ERPConflict('preview_stale')
        if request['state'] in {'queued', 'processing', 'completed'}:
            return public_request(request)
        if request['state'] != 'preview_ready':
            raise ERPConflict('preview_required')
        preview = request['preview']
        latest = build_preview(cur, request, request['choices'])
        if any(latest[key] != preview[key] for key in ('snapshot', 'calendar_version', 'new_machine_refs')):
            raise ERPConflict('preview_stale')
        if any(issue['severity'] == 'error' for issue in preview['issues']) or not preview['items']:
            raise ERPConflict('preview_has_errors')
        if set(payload['create_machine_refs']) != set(preview['new_machine_refs']):
            raise ERPConflict('machine_creation_not_confirmed')
        validate_replacements(cur, request['site_id'], preview, payload['replacements'])
        resolved = {item['source_row'] for item in payload['replacements']} | set(payload.get('new_identity_rows', []))
        if any(item['identity_candidates'] and item['source_row'] not in resolved for item in preview['items']):
            raise ERPConflict('identity_resolution_required')
        choices = {**request['choices'], 'create_machine_refs': payload['create_machine_refs'], 'replacements': payload['replacements'], 'new_identity_rows': payload.get('new_identity_rows', [])}
        cur.execute("UPDATE erp_import_requests SET state='queued',choices=%s,confirmed_at=now(),public_error=NULL WHERE id=%s RETURNING *", (Json(choices), str(import_id)))
        return public_request(dict(cur.fetchone()))


def get_calendar(site_id):
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        return current_calendar(cur, site_id)


def save_calendar(*, site_id, author_id, payload):
    with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        lock_site(cur, site_id)
        from datetime import datetime, timezone
        from ingest.context_repository import site_periods, reconcile_changes
        now = datetime.now(timezone.utc)
        old_periods = site_periods(conn, site_id, now)
        current = current_calendar(cur, site_id)
        version = current['version'] if current else 0
        if payload['expected_version'] != version:
            raise ERPConflict('calendar_stale')
        cur.execute('''INSERT INTO site_shift_calendars(site_id,version,valid_from,valid_to,timezone,shifts,author_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                    (site_id, version + 1, payload['valid_from'], payload.get('valid_to'), payload['timezone'], Json(payload['shifts']), author_id))
        saved = dict(cur.fetchone())
        reconcile_changes(conn, site_id, old_periods, max(now, saved['created_at']))
        return saved


def create_machine(*, site_id, erp_ref, name):
    with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        lock_site(cur, site_id)
        cur.execute('''INSERT INTO machines(site_id,erp_ref,name) VALUES (%s,%s,%s)
                       ON CONFLICT(site_id,erp_ref) DO NOTHING RETURNING id,site_id,erp_ref,name''', (site_id, erp_ref, name))
        value = cur.fetchone()
        return dict(value) if value else None

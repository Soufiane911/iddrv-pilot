"""Append-only context decisions; reconciliation never mutates cycles or predictions."""
from datetime import datetime, timezone
from psycopg2.extras import Json, RealDictCursor
from .context_models import CycleContext, DeclarationCandidate
from .context_matching import choose_context


def declaration_period(row, calendar):
    from .erp_import_jobs import apply_calendar
    from .erp_models import ERPDeclaration
    from .erp_reader import MAPPING, normalize
    start, end = row['production_started_at'], row['production_ended_at']
    if row['bounds_origin'] != 'calendar':
        return start, end, row['bounds_origin']
    estimated = row.get('estimated_bounds')
    if estimated is None:
        # Older revisions have source cells, but no SQL provenance column.
        explicit = {MAPPING.get(normalize(key)) for key, value in row['raw_data'].items() if value is not None and str(value).strip()}
        estimated = [key for key in ('production_started_at','production_ended_at') if key not in explicit]
    declaration = ERPDeclaration(machine_ref='', order_ref=row['production_order_id'], shift_started_at=row['shift_started_at'],
        shift_number=row['shift_number'], production_started_at=None if 'production_started_at' in estimated else start,
        production_ended_at=None if 'production_ended_at' in estimated else end)
    apply_calendar(declaration, calendar)
    return declaration.production_started_at, declaration.production_ended_at, declaration.bounds_origin


def candidates_at(cur, site_id, machine_id, known_at):
    cur.execute('SELECT * FROM site_shift_calendars WHERE site_id=%s AND created_at<=%s ORDER BY version DESC LIMIT 1', (site_id,known_at))
    calendar = cur.fetchone()
    cur.execute('''SELECT DISTINCT ON(d.id) r.*,d.machine_id FROM erp_declarations d
        JOIN erp_declaration_revisions r ON r.declaration_id=d.id AND r.site_id=d.site_id
        WHERE d.site_id=%s AND d.machine_id=%s AND r.recorded_at<=%s
        AND (d.superseded_by IS NULL OR d.superseded_recorded_at>%s)
        ORDER BY d.id,r.recorded_at DESC,r.revision_number DESC''', (site_id,machine_id,known_at,known_at))
    rows = [dict(row) for row in cur.fetchall()]
    candidates = []
    for row in rows:
        start,end,origin = declaration_period(row, calendar)
        if start is not None and end is not None:
            candidates.append(DeclarationCandidate(str(row['declaration_id']),str(row['id']),site_id,machine_id,
                row['production_order_id'], start,end,origin))
    return candidates, rows


def reconcile_period(conn, *, site_id, machine_id, start, end, known_at):
    count = 0
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Shared by calendar/import/collector to serialize competing successor writes.
        cur.execute('SELECT pg_advisory_xact_lock(1347568467,%s)', (site_id,))
        candidates,_ = candidates_at(cur,site_id,machine_id,known_at)
        cur.execute('''SELECT c.time,c.source_event_id,c.context_cycle_id FROM machine_cycles c JOIN machines m ON m.id=c.machine_id
                       WHERE m.site_id=%s AND c.machine_id=%s AND c.time>=%s AND c.time<%s ORDER BY c.time''', (site_id,machine_id,start,end))
        cycles = cur.fetchall()
        for cycle in cycles:
            cycle_key = str(cycle['source_event_id']) if cycle['source_event_id'] else 'legacy:' + str(cycle['context_cycle_id'])
            decision = choose_context(CycleContext(site_id,machine_id,cycle['time']),candidates)
            revisions = sorted(c.revision_id for c in candidates if c.id in decision.candidate_ids)
            cur.execute('''SELECT * FROM cycle_context_links WHERE site_id=%s AND machine_id=%s AND cycle_time=%s AND cycle_key=%s
                           ORDER BY created_at DESC LIMIT 1''', (site_id,machine_id,cycle['time'],cycle_key))
            previous = cur.fetchone()
            if previous and previous['status']==decision.status and previous['candidate_revision_ids']==revisions:
                continue
            cur.execute('''INSERT INTO cycle_context_links(site_id,machine_id,cycle_time,source_event_id,declaration_id,revision_id,
                status,candidate_ids,candidate_revision_ids,confidence,created_at,supersedes_id,cycle_key)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (site_id,machine_id,cycle['time'],cycle['source_event_id'],decision.declaration_id,decision.revision_id,
                 decision.status,Json(decision.candidate_ids),Json(revisions),decision.confidence,known_at,previous['id'] if previous else None,cycle_key))
            count += 1
    return count


def site_periods(conn, site_id, known_at):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT id FROM machines WHERE site_id=%s',(site_id,))
        machines = [r['id'] for r in cur.fetchall()]
        return [(m,c.start,c.end) for m in machines for c in candidates_at(cur,site_id,m,known_at)[0]]


def reconcile_changes(conn, site_id, old_periods, known_at):
    # Union includes old machines and periods of replaced declarations.
    periods = old_periods + site_periods(conn,site_id,known_at)
    by_machine = {}
    for machine,start,end in periods:
        by_machine.setdefault(machine,[]).append((start,end))
    count = 0
    for machine, intervals in by_machine.items():
        # Merge overlapping intervals, without manufacturing coverage across pauses.
        merged = []
        for start,end in sorted(set(intervals)):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0],max(end,merged[-1][1]))
            else:
                merged.append((start,end))
        for start,end in merged:
            count += reconcile_period(conn,site_id=site_id,machine_id=machine,start=start,end=end,known_at=known_at)
    return count

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extras import RealDictCursor
from ingest.context_repository import candidates_at
from ..db import get_connection
from ..security import Identity, get_current_identity
from ..order_repository import get_order_summary
from .machine_connections import authorized_machine

router = APIRouter(prefix='/api/v1/machines',tags=['production-context'])


def time_bounds(start, end, known_at):
    known_at = known_at or datetime.now(timezone.utc)
    end = end or known_at
    start = start or end-timedelta(hours=24)
    if any(value.tzinfo is None for value in (start,end,known_at)):
        raise HTTPException(422,'timezone_required')
    if start>=end or end-start>timedelta(days=31):
        raise HTTPException(422,'period_must_be_positive_and_at_most_31_days')
    return start,end,known_at


def context_history(conn, *, site_id, machine_id, start, end, known_at, limit=500):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        candidates, declarations = candidates_at(cur,site_id,machine_id,known_at)
        cur.execute('''SELECT c.time,c.source_event_id,coalesce(c.source_event_id::text,'legacy:'||c.context_cycle_id::text) AS cycle_key,l.id AS link_id,l.status,l.declaration_id,l.revision_id,
            l.candidate_ids,l.candidate_revision_ids,l.confidence,l.created_at,l.supersedes_id
            FROM machine_cycles c JOIN machines m ON m.id=c.machine_id
            LEFT JOIN machine_source_events e ON e.id=c.source_event_id AND e.site_id=m.site_id
            LEFT JOIN LATERAL (SELECT * FROM cycle_context_links l WHERE l.site_id=m.site_id AND l.machine_id=c.machine_id
                AND l.cycle_time=c.time AND l.cycle_key=coalesce(c.source_event_id::text,'legacy:'||c.context_cycle_id::text) AND l.created_at<=%s ORDER BY l.created_at DESC LIMIT 1) l ON true
            WHERE m.site_id=%s AND c.machine_id=%s AND c.time>=%s AND c.time<%s
            AND (c.source_event_id IS NULL OR e.received_at<=%s) ORDER BY c.time LIMIT %s''',
            (known_at,site_id,machine_id,start,end,known_at,limit+1))
        links = [dict(row) for row in cur.fetchall()]
    for link in links:
        link['status'] = link['status'] or 'awaiting_erp'
        link['historical_knowledge'] = 'verified' if link['source_event_id'] else 'unverifiable'
    periods = {c.revision_id:c for c in candidates}
    selected = []
    for declaration in declarations:
        c = periods.get(str(declaration['id']))
        if c and not (c.start < end and c.end > start):
            continue
        safe = {key:declaration[key] for key in ('id','declaration_id','production_order_id','revision_number','recorded_at',
            'produced_parts','good_parts','scrap_parts','cycle_count','warnings','shift_number','shift_started_at','passport_id')}
        safe.update(production_started_at=c.start if c else None,production_ended_at=c.end if c else None,
            bounds_origin=c.bounds_source if c else 'awaiting_context')
        selected.append(safe)
    return {'items':links[:limit],'truncated':len(links)>limit,'declarations':selected,'known_at':known_at,
            'coverage':{'returned_cycles':min(len(links),limit),'declarations':len(selected),
                        'unknown_bounds':sum(str(d['id']) not in periods for d in declarations)}}


@router.get('/{machine_id}/production-context')
def read(machine_id:int, from_:datetime|None=Query(None,alias='from'), to:datetime|None=None,
         known_at:datetime|None=None, limit:int=Query(500,ge=1,le=5000), identity:Identity=Depends(get_current_identity)):
    machine = authorized_machine(machine_id,identity)
    start,end,known = time_bounds(from_,to,known_at)
    with get_connection() as conn:
        result = context_history(conn,site_id=machine['site_id'],machine_id=machine_id,start=start,end=end,known_at=known,limit=limit)
    result['orders'] = [get_order_summary(site_id=machine['site_id'],order_ref=ref,known_at=known)
        for ref in sorted({d['production_order_id'] for d in result['declarations']})]
    return result

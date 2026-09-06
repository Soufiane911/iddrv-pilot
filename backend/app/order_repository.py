"""Order totals across every machine and team, with knowledge-time provenance."""
from datetime import datetime

from psycopg2.extras import RealDictCursor

from .db import get_connection


def summarize_order(order_ref, declarations, observations):
    context, history = {}, []
    for observation in observations:
        values = observation['values']
        context.update(values)
        if 'order_status' in values:
            history.append({**observation, 'status': values['order_status']})
    known = [row['good_parts'] for row in declarations if row.get('good_parts') is not None]
    complete = bool(declarations) and len(known) == len(declarations) and context.get('coverage_complete') is True and not any(row.get('warnings') for row in declarations)
    periods = [{'declaration_id':row.get('declaration_id'), 'revision_id':row.get('id'), 'machine_id':row.get('machine_id'),
                'start':row.get('production_started_at'), 'end':row.get('production_ended_at'), 'bounds_origin':row.get('bounds_origin')}
               for row in declarations]
    starts = [period['start'] for period in periods if period['start'] is not None]
    ends = [period['end'] for period in periods if period['end'] is not None]
    target = context.get('order_target_quantity')
    good = sum(known) if known else None
    return {'order_ref': order_ref, 'order_target_quantity': target, 'order_status': context.get('order_status'),
            'good_parts_net': good, 'remaining_quantity': max(0, target - good) if complete and target is not None else None,
            'coverage': {'complete': complete, 'history_confirmed': context.get('coverage_complete') is True,
                         'warnings': sum(bool(row.get('warnings')) for row in declarations), 'declarations': len(declarations), 'quality_known': len(known),
                         'quality_fraction': len(known) / len(declarations) if declarations else None,
                         'periods': periods, 'start': min(starts) if starts else None, 'end':max(ends) if ends else None},
            'status_history': history, 'source': 'erp_declaration_revisions'}


def get_order_summary(*, site_id: int, order_ref: str, known_at: datetime) -> dict:
    if known_at.tzinfo is None:
        raise ValueError('known_at_timezone_required')
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''SELECT d.id,d.machine_id,r.* FROM erp_declarations d
                       JOIN LATERAL (SELECT * FROM erp_declaration_revisions r WHERE r.declaration_id=d.id
                                     AND r.recorded_at<=%s ORDER BY r.revision_number DESC LIMIT 1) r ON true
                       WHERE d.site_id=%s AND d.production_order_id=%s
                       AND (d.superseded_recorded_at IS NULL OR d.superseded_recorded_at>%s)''',
                    (known_at, site_id, order_ref, known_at))
        declarations = [dict(row) for row in cur.fetchall()]
        from ingest.context_repository import declaration_period
        cur.execute('SELECT * FROM site_shift_calendars WHERE site_id=%s AND created_at<=%s ORDER BY version DESC LIMIT 1',(site_id,known_at))
        calendar = cur.fetchone()
        for declaration in declarations:
            start,end,origin = declaration_period(declaration,calendar)
            declaration.update(production_started_at=start,production_ended_at=end,bounds_origin=origin)
        cur.execute('''SELECT id,effective_at,recorded_at,passport_id,values FROM production_order_revisions
                       WHERE site_id=%s AND production_order_id=%s AND recorded_at<=%s AND (effective_at IS NULL OR effective_at<=%s)
                       ORDER BY COALESCE(effective_at,recorded_at),recorded_at,id''', (site_id, order_ref, known_at, known_at))
        observations = [dict(row) for row in cur.fetchall()]
        result = summarize_order(order_ref, declarations, observations)
        if not declarations:
            cur.execute('''SELECT erp_good_parts,erp_scrap_count,target_quantity FROM production_orders
                           WHERE site_id=%s AND id=%s AND NOT EXISTS (
                              SELECT 1 FROM erp_declarations d WHERE d.site_id=production_orders.site_id AND d.production_order_id=production_orders.id)''', (site_id, order_ref))
            legacy = cur.fetchone()
            if legacy:
                result.update(source='legacy', legacy=dict(legacy), historical_knowledge='unverifiable')
    return {**result, 'site_id': site_id, 'known_at': known_at}

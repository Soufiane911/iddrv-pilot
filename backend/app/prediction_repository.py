"""Production-time and knowledge-time bounded access to immutable HDT results."""
from psycopg2.extras import RealDictCursor
from .db import get_connection


def prediction_history(*, site_id, machine_id, start, end, known_at, limit=500):
    with get_connection() as conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''SELECT p.*,ep.incident_id FROM hdt_predictions p
            LEFT JOIN process_drift_episode_predictions ep ON ep.prediction_id=p.id AND ep.site_id=p.site_id AND ep.machine_id=p.machine_id
            WHERE p.site_id=%s AND p.machine_id=%s AND p.evaluated_through>=%s AND p.evaluated_through<%s AND p.scored_at<=%s
            ORDER BY p.evaluated_through DESC,p.scored_at DESC LIMIT %s''',(site_id,machine_id,start,end,known_at,limit+1))
        rows = [dict(row) for row in cur.fetchall()]
    return {'items':rows[:limit], 'truncated':len(rows)>limit, 'known_at':known_at}

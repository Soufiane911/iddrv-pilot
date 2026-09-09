"""Explicit read-only extraction, credentials never serialized."""
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .window import validate_window

SQL_DIR = Path(__file__).resolve().parents[1] / 'sql'


def extract(connection, site_id, from_utc, to_utc, limit=1000):
    if type(site_id) is not int or site_id < 1 or type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError('invalid_scope')
    start, end = validate_window(from_utc, to_utc)
    query = (SQL_DIR / 'cycles.sql').read_text()
    params = {'site_id': site_id, 'from_utc': start, 'to_utc': end, 'limit': limit + 1}
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute(query, params)
            columns = [c.name for c in cursor.description]
            rows = [dict(zip(columns, r)) for r in cursor.fetchall()]
            if len(rows) > limit:
                raise ValueError('row_limit')
            cursor.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + query, params)
            plan = cursor.fetchone()[0]
    return {'version': 1, 'source_id': 'synthetic-timescale' , 'classification': 'synthetic_projection',
            'collected_at_utc': datetime.now(timezone.utc).isoformat(), 'rows': rows,
            'count': len(rows), 'query_sha256': hashlib.sha256(query.encode()).hexdigest(), 'plan': plan}

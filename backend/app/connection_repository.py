"""Configuration boundary: public metadata only, secret values stay in deployment."""
from psycopg2.extras import RealDictCursor, Json
from .db import get_connection

PUBLIC_COLUMNS = 'id,site_id,machine_id,base_url,external_machine_id,secret_ref,poll_interval_s,enabled,mapping_profile,state,public_error,last_test_at,last_test_result,last_response_at,last_success_at,last_cycle_at,next_poll_at'


class ConnectionConflict(ValueError):
    pass


def local_machine(machine_id):
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT id,site_id FROM machines WHERE id=%s', (machine_id,))
        return cur.fetchone()


def get_connection_config(machine_id):
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f'SELECT {PUBLIC_COLUMNS} FROM machine_connections WHERE machine_id=%s', (machine_id,))
        return cur.fetchone()


def save_connection(machine, payload):
    with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT id,base_url,external_machine_id,state FROM machine_connections WHERE machine_id=%s FOR UPDATE', (machine['id'],))
        current = cur.fetchone()
        if current:
            cur.execute('SELECT pg_try_advisory_xact_lock(hashtextextended(%s,14)) AS locked', (str(current['id']),))
            if not cur.fetchone()['locked']:
                raise ConnectionConflict('collection_busy')
            if (current['base_url'], current['external_machine_id']) != (payload['base_url'], payload['external_machine_id']):
                cur.execute('SELECT 1 FROM machine_stream_offsets WHERE connection_id=%s', (current['id'],))
                if cur.fetchone():
                    raise ConnectionConflict('source_identity_locked')
            if payload['enabled'] and current['state'] in ('gap_detected', 'contract_error'):
                raise ConnectionConflict('continuity_review_required')
        cur.execute(f'''INSERT INTO machine_connections(site_id,machine_id,base_url,external_machine_id,secret_ref,poll_interval_s,enabled,mapping_profile,state)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(machine_id) DO UPDATE SET
                    base_url=EXCLUDED.base_url,external_machine_id=EXCLUDED.external_machine_id,secret_ref=EXCLUDED.secret_ref,
                    poll_interval_s=EXCLUDED.poll_interval_s,enabled=EXCLUDED.enabled,mapping_profile=EXCLUDED.mapping_profile,
                    state=CASE WHEN machine_connections.state IN ('gap_detected','contract_error') THEN machine_connections.state ELSE EXCLUDED.state END,
                    next_poll_at=now(),updated_at=now() RETURNING {PUBLIC_COLUMNS}''',
                    (machine['site_id'], machine['id'], payload['base_url'], payload['external_machine_id'], payload['secret_ref'],
                     payload['poll_interval_s'], payload['enabled'], payload['mapping_profile'], 'configured' if payload['enabled'] else 'disabled'))
        return cur.fetchone()


def record_test(machine_id, result):
    with get_connection() as conn, conn, conn.cursor() as cur:
        cur.execute('UPDATE machine_connections SET last_test_at=now(),last_test_result=%s WHERE machine_id=%s', (Json(result), machine_id))

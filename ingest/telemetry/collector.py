"""Autonomous poller; restart with the committed offset, independently of HDT."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from pathlib import Path
import random
import time
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor

from .http_source import ApiCycleSource, SourceError, configured_client
from .models import CollectionResult
from .repository import store_page

SUSPENDED = ('access_error', 'configuration_error', 'gap_detected', 'contract_error')


def connect():
    url = os.getenv('WORKER_DATABASE_URL')
    if not url:
        raise RuntimeError('WORKER_DATABASE_URL is required for collection')
    return psycopg2.connect(url, connect_timeout=3)


def collect_once(connection_id: UUID) -> CollectionResult:
    conn = connect()
    locked = False
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(hashtextextended(%s, 14))', (str(connection_id),))
            locked = cur.fetchone()[0]
        conn.commit()
        if not locked:
            return CollectionResult(state='busy')
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT * FROM machine_connections WHERE id=%s', (str(connection_id),))
            connection = cur.fetchone()
            if not connection or not connection['enabled'] or connection['state'] in SUSPENDED or connection['next_poll_at'] > datetime.now(timezone.utc):
                conn.commit()
                return CollectionResult(state='idle')
            cur.execute('SELECT * FROM machine_stream_offsets WHERE connection_id=%s', (str(connection_id),))
            offset = cur.fetchone()
        conn.commit()
        page_received = False
        try:
            with configured_client(connection['base_url'], connection['secret_ref']) as client:
                page = ApiCycleSource(client).fetch_page(connection['external_machine_id'], after=offset['cursor'] if offset else None)
            page_received = True
            return store_page(conn, connection_id=connection_id, page=page, received_at=datetime.now(timezone.utc))
        except SourceError as exc:
            conn.rollback()
            attempts = connection['failure_count'] + 1
            delay = exc.retry_after or min(30, 2 ** min(attempts, 5) + random.uniform(0, .2))
            with conn:
                with conn.cursor() as cur:
                    cur.execute('''UPDATE machine_connections SET state=%s,public_error=%s,failure_count=%s,
                                next_poll_at=now()+%s*interval '1 second',updated_at=now(),
                                last_response_at=CASE WHEN %s THEN last_response_at ELSE now() END WHERE id=%s''',
                                (exc.state, exc.code, attempts, delay, not (exc.response_received or page_received), str(connection_id)))
            return CollectionResult(cursor=offset['cursor'] if offset else None, state=exc.state)
    finally:
        # Session locks survive commits, but release on close even after process failure.
        conn.close()


def due_connections():
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute('''SELECT id FROM machine_connections WHERE enabled AND state IN ('configured','collecting','retrying') AND next_poll_at<=now() ORDER BY next_poll_at LIMIT 64''')
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def heartbeat_is_fresh():
    path = Path(os.getenv('COLLECTOR_HEARTBEAT_PATH', '/tmp/iddrv-collector-heartbeat'))
    return path.exists() and time.time() - path.stat().st_mtime < 90


def main():
    heartbeat = Path(os.getenv('COLLECTOR_HEARTBEAT_PATH', '/tmp/iddrv-collector-heartbeat'))
    with ThreadPoolExecutor(max_workers=8) as pool:
        while True:
            try:
                for result in pool.map(collect_once, due_connections()):
                    pass
                heartbeat.touch()
            except (psycopg2.Error, OSError, ValueError):
                # Public fixed message only: DB/HTTP exceptions can include credentials.
                print('Collector dependency failure; retrying.', flush=True)
            time.sleep(.25)


if __name__ == '__main__':
    main()

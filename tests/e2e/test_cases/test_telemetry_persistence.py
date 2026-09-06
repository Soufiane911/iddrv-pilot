"""Non-destructive standalone process proof; run with --noconftest.

This suite intentionally does not use the legacy E2E clean_db/clean_redis harness.
TELEMETRY_TEST_DATABASE_URL must explicitly point at the dedicated iddrv_test DB.
"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4
from urllib.parse import urlparse

import httpx
import psycopg2
import pytest


def eventually(check, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(.1)
    raise AssertionError('Expected process state not reached within deadline')


def test_collection_continues_without_browser_and_restart_has_no_duplicates(tmp_path):
    url = os.getenv('TELEMETRY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Dedicated TELEMETRY_TEST_DATABASE_URL not supplied')
    assert urlparse(url).hostname == 'db' and urlparse(url).path == '/iddrv_test'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    origin = f'http://127.0.0.1:{port}'
    env = {**os.environ, 'PRESS_FIXTURE_DB': str(tmp_path/'source.sqlite'), 'WORKER_DATABASE_URL': url,
           'TELEMETRY_ALLOWED_ORIGINS': origin, 'TELEMETRY_ALLOW_HTTP': 'true',
           'COLLECTOR_HEARTBEAT_PATH': str(tmp_path/'heartbeat'), 'PRESS_FIXTURE_CONTROL_TOKEN': 'synthetic-telemetry-control-only'}
    source = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'tests.fixtures.press_api.app:app', '--host', '127.0.0.1', '--port', str(port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    worker = None
    connection = None
    conn = psycopg2.connect(url)
    client = httpx.Client(base_url=origin, timeout=1, headers={'X-Test-Control-Token': env['PRESS_FIXTURE_CONTROL_TOKEN']})
    try:
        def ready():
            try:
                return client.get('/v1/machines/606/status').status_code == 200
            except httpx.HTTPError:
                return False
        eventually(ready)
        with conn, conn.cursor() as cur:
            cur.execute('INSERT INTO sites(name) VALUES(%s) RETURNING id', ('telemetry-process-' + uuid4().hex,))
            site = cur.fetchone()[0]
            cur.execute("INSERT INTO machines(site_id,erp_ref) VALUES(%s,'606') RETURNING id", (site,))
            machine = cur.fetchone()[0]
            cur.execute("INSERT INTO machine_connections(site_id,machine_id,base_url,external_machine_id,enabled,state) VALUES(%s,%s,%s,'606',true,'configured') RETURNING id", (site,machine,origin))
            connection = cur.fetchone()[0]
        def count():
            with conn, conn.cursor() as cur:
                cur.execute('SELECT count(*) FROM machine_cycles WHERE machine_id=%s', (machine,))
                return cur.fetchone()[0]
        def state():
            with conn, conn.cursor() as cur:
                cur.execute('SELECT state FROM machine_connections WHERE id=%s', (connection,))
                return cur.fetchone()[0]
        def start():
            return subprocess.Popen([sys.executable, '-m', 'ingest.telemetry.collector'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        client.post('/__test/control', json={'emit': 1}).raise_for_status()
        worker = start()
        eventually(lambda: count() == 1)
        # No browser or product API process has been launched at any point.
        client.post('/__test/control', json={'emit': 2}).raise_for_status()
        eventually(lambda: count() == 3)
        worker.terminate(); worker.wait(timeout=5)
        client.post('/__test/control', json={'emit': 5}).raise_for_status()
        assert count() == 3
        worker = start()
        eventually(lambda: count() == 8)
        client.post('/__test/control', json={'error': 410}).raise_for_status()
        eventually(lambda: state() == 'gap_detected')
        assert count() == 8
        assert Path(env['COLLECTOR_HEARTBEAT_PATH']).exists()
        with conn, conn.cursor() as cur:
            cur.execute('SELECT count(*),count(DISTINCT event_id) FROM machine_source_events WHERE connection_id=%s', (connection,))
            assert cur.fetchone() == (8,8)
            cur.execute('SELECT count(*) FROM hdt_scoring_jobs WHERE machine_id=%s', (machine,))
            assert cur.fetchone()[0] == 8
        print('No browser/API: cycles 1 → 3; collector stopped: 3; restart: 8; distinct events/jobs: 8; retention: gap_detected, no jump.')
    finally:
        if worker and worker.poll() is None:
            worker.terminate(); worker.wait(timeout=5)
        source.terminate(); source.wait(timeout=5)
        client.close()
        if connection:
            conn.rollback()
            with conn, conn.cursor() as cur:
                cur.execute('UPDATE machine_connections SET enabled=false WHERE id=%s', (connection,))
        conn.close()

"""Real DB invariants. Dedicated iddrv_test only; never truncate shared tables."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import os
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import psycopg2
import pytest

from ingest.telemetry import collector
from ingest.telemetry.http_source import SourceError, validate_page
from ingest.telemetry.repository import store_page
from test_telemetry_contract import payload


@pytest.fixture
def database(monkeypatch):
    monkeypatch.setenv('HDT_RUNTIME_MODE', 'historical')
    url = os.getenv('TELEMETRY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Dedicated TELEMETRY_TEST_DATABASE_URL not supplied')
    target = urlparse(url)
    assert target.hostname in {'db', 'localhost', '127.0.0.1'} and target.path == '/iddrv_test'
    conn = psycopg2.connect(url)
    with conn, conn.cursor() as cur:
        cur.execute('INSERT INTO sites(name) VALUES(%s) RETURNING id', ('telemetry-test-' + uuid4().hex,))
        site = cur.fetchone()[0]
        cur.execute("INSERT INTO machines(site_id,erp_ref,name) VALUES(%s,'606','Synthetic press') RETURNING id", (site,))
        machine = cur.fetchone()[0]
        cur.execute("INSERT INTO machine_connections(site_id,machine_id,base_url,external_machine_id,enabled,state) VALUES(%s,%s,'http://machine.test','606',true,'configured') RETURNING id", (site, machine))
        connection = cur.fetchone()[0]
    monkeypatch.setattr(collector, 'connect', lambda: psycopg2.connect(url))
    yield conn, connection, machine, site
    # Retain all evidence; only disable this test's own connection.
    conn.rollback()
    with conn, conn.cursor() as cur:
        cur.execute('UPDATE machine_connections SET enabled=false WHERE id=%s', (connection,))
    conn.close()


def page(n=1, after=None):
    return replace(validate_page(payload(n), expected_machine_id='606', expected_stream_id=None), after=after)


def counts(conn, connection):
    with conn.cursor() as cur:
        cur.execute('''SELECT (SELECT count(*) FROM machine_source_events WHERE connection_id=%s),
                       (SELECT count(*) FROM machine_cycles c JOIN machine_source_events e ON e.id=c.source_event_id WHERE e.connection_id=%s),
                       (SELECT count(*) FROM hdt_scoring_jobs j JOIN machine_source_events e ON e.id=j.event_id WHERE e.connection_id=%s),
                       (SELECT cursor FROM machine_stream_offsets WHERE connection_id=%s)''', (connection,)*4)
        result = cur.fetchone()
    conn.commit()
    return result


def store(conn, connection, value):
    return store_page(conn, connection_id=connection, page=value, received_at=datetime.now(timezone.utc))


def due(conn, connection):
    with conn, conn.cursor() as cur:
        cur.execute("UPDATE machine_connections SET next_poll_at=now()-interval '1 second' WHERE id=%s", (connection,))


def source(monkeypatch, handler):
    monkeypatch.setattr(collector, 'configured_client', lambda *args: httpx.Client(base_url='http://machine.test', transport=httpx.MockTransport(handler)))


def test_atomic_dedupe_cycles_jobs_and_unknown_quality_without_erp(database):
    conn, connection, machine, site = database
    assert store(conn, connection, page()).inserted_cycles == 1
    assert store(conn, connection, page()).duplicates == 1
    assert counts(conn, connection) == (1, 1, 1, 'cursor-1')
    with conn.cursor() as cur:
        cur.execute('SELECT production_order_id,good_parts,scrap_flag,part_quality_status FROM machine_cycles WHERE machine_id=%s', (machine,))
        assert cur.fetchone() == (None, None, None, None)


class CrashConnection:
    def __init__(self, conn, after=False):
        self.conn, self.after = conn, after
    def cursor(self, **kwargs):
        return self.conn.cursor(**kwargs)
    def __enter__(self):
        self.conn.__enter__()
        return self
    def __exit__(self, *args):
        if self.after:
            self.conn.__exit__(*args)
        else:
            error = RuntimeError('synthetic crash before commit')
            self.conn.__exit__(RuntimeError, error, None)
        raise RuntimeError('synthetic crash after commit' if self.after else 'synthetic crash before commit')


def test_crash_before_commit_rolls_back_everything_then_replays(database):
    conn, connection, *_ = database
    with pytest.raises(RuntimeError, match='before commit'):
        store(CrashConnection(conn), connection, page())
    assert counts(conn, connection) == (0, 0, 0, None)
    assert store(conn, connection, page()).inserted_cycles == 1


def test_crash_after_commit_resumes_at_committed_cursor(database, monkeypatch):
    conn, connection, *_ = database
    with pytest.raises(RuntimeError, match='after commit'):
        store(CrashConnection(conn, after=True), connection, page())
    assert counts(conn, connection) == (1, 1, 1, 'cursor-1')
    due(conn, connection)
    def handler(request):
        assert request.url.params['after'] == 'cursor-1'
        return httpx.Response(200, json={**payload(), 'items': []})
    source(monkeypatch, handler)
    assert collector.collect_once(connection).new_scoring_jobs == 0
    assert counts(conn, connection) == (1, 1, 1, 'cursor-1')


def test_rejections_do_not_lose_valid_neighbors_and_conflict_preserves_first(database):
    conn, connection, *_ = database
    p = payload(2)
    p['items'][0]['measurements']['cycle_time_s'] = float('nan')
    parsed = validate_page(p, expected_machine_id='606', expected_stream_id=None)
    result = store(conn, connection, parsed)
    assert (result.rejected_events, result.inserted_cycles) == (1, 1)
    p['items'][1]['measurements']['cycle_time_s'] = 13
    conflict = store(conn, connection, validate_page(p, expected_machine_id='606', expected_stream_id=None))
    assert conflict.conflicts == 1
    assert counts(conn, connection) == (2, 1, 1, 'cursor-2')
    with conn.cursor() as cur:
        cur.execute("SELECT payload->'measurements'->>'cycle_time_s',conflict_count FROM machine_source_events WHERE connection_id=%s AND event_id='stream-A:2'", (connection,))
        assert cur.fetchone() == ('12.0', 1)


def test_shared_lock_prevents_concurrent_http_consumption(database, monkeypatch):
    conn, connection, *_ = database
    with conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_lock(hashtextextended(%s,14))', (str(connection),))
    conn.commit()
    source(monkeypatch, lambda r: pytest.fail('lock held: no HTTP request allowed'))
    assert collector.collect_once(connection).state == 'busy'
    with conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_unlock(hashtextextended(%s,14))', (str(connection),))
    conn.commit()


def test_outage_recovers_five_retained_cycles_and_410_never_skips(database, monkeypatch):
    conn, connection, *_ = database
    source(monkeypatch, lambda r: httpx.Response(503))
    assert collector.collect_once(connection).state == 'retrying'
    assert counts(conn, connection) == (0, 0, 0, None)
    source(monkeypatch, lambda r: httpx.Response(200, json=payload(5)))
    due(conn, connection)
    assert collector.collect_once(connection).inserted_cycles == 5
    source(monkeypatch, lambda r: httpx.Response(410, json={'error': 'cursor_expired'}))
    due(conn, connection)
    assert collector.collect_once(connection).state == 'gap_detected'
    assert counts(conn, connection) == (5, 5, 5, 'cursor-5')
    source(monkeypatch, lambda r: pytest.fail('gap must suspend automatically'))
    due(conn, connection)
    assert collector.collect_once(connection).state == 'idle'


def test_pagination_late_cycle_and_hardware_reset(database, monkeypatch):
    conn, connection, machine, _ = database
    data = payload(103)
    data['items'][-1].update(cycle_counter=0, cycle_ended_at='2026-09-04T08:00:12+02:00')
    def handler(request):
        after = request.url.params.get('after')
        if after is None:
            return httpx.Response(200, json={**data, 'items': data['items'][:100], 'has_more': True, 'next_cursor': 'cursor-100'})
        assert after == 'cursor-100'
        return httpx.Response(200, json={**data, 'items': data['items'][100:]})
    source(monkeypatch, handler)
    assert collector.collect_once(connection).inserted_cycles == 100
    assert collector.collect_once(connection).inserted_cycles == 3
    assert counts(conn, connection) == (103, 103, 103, 'cursor-103')
    with conn.cursor() as cur:
        cur.execute('SELECT cycle_counter FROM machine_cycles WHERE machine_id=%s ORDER BY time LIMIT 1', (machine,))
        assert cur.fetchone()[0] == 0


def test_stream_reset_suspends_and_cross_site_journal_is_rejected(database):
    conn, connection, machine, site = database
    store(conn, connection, page())
    with pytest.raises(SourceError, match='stream_changed'):
        store(conn, connection, replace(page(), stream_id='new-stream'))
    assert counts(conn, connection) == (1, 1, 1, 'cursor-1')
    with pytest.raises(psycopg2.IntegrityError), conn, conn.cursor() as cur:
        cur.execute("INSERT INTO hdt_scoring_jobs(event_id,machine_id,site_id,model_version) SELECT id,%s,1,'wrong-site' FROM machine_source_events WHERE connection_id=%s", (machine, connection))


def test_configuration_persists_with_server_scope_and_locked_source_identity(database, monkeypatch):
    from backend.app import connection_repository as configs
    from backend.app import db
    conn, connection, machine, site = database
    url = os.environ['TELEMETRY_TEST_DATABASE_URL']
    monkeypatch.setattr(db, 'connect', lambda: psycopg2.connect(url))
    body = {'base_url': 'http://machine.test', 'external_machine_id': '606', 'secret_ref': 'PRESS', 'poll_interval_s': 3, 'enabled': False, 'mapping_profile': 'iddrv-cycle-v1'}
    saved = configs.save_connection({'id': machine, 'site_id': site}, body)
    assert saved['site_id'] == site and saved['enabled'] is False
    assert configs.get_connection_config(machine)['secret_ref'] == 'PRESS'
    store(conn, connection, page())
    with pytest.raises(configs.ConnectionConflict, match='source_identity_locked'):
        configs.save_connection({'id': machine, 'site_id': site}, {**body, 'external_machine_id': '607'})
    with conn, conn.cursor() as cur:
        cur.execute("UPDATE machine_connections SET state='gap_detected' WHERE id=%s", (connection,))
    configs.save_connection({'id': machine, 'site_id': site}, body)
    with pytest.raises(configs.ConnectionConflict, match='continuity_review_required'):
        configs.save_connection({'id': machine, 'site_id': site}, {**body, 'enabled': True})


def test_invalid_page_leaves_offset_unchanged_and_records_response(database, monkeypatch):
    conn, connection, *_ = database
    p = payload()
    p['items'][0]['machine_id'] = 'other'
    source(monkeypatch, lambda r: httpx.Response(200, json=p))
    assert collector.collect_once(connection).state == 'contract_error'
    assert counts(conn, connection) == (0,0,0,None)
    with conn.cursor() as cur:
        cur.execute('SELECT last_response_at,last_cycle_at FROM machine_connections WHERE id=%s', (connection,))
        response_at, cycle_at = cur.fetchone()
        assert response_at is not None and cycle_at is None


def test_conflict_cannot_move_last_cycle_time(database):
    conn, connection, *_ = database
    store(conn, connection, page())
    p = payload()
    p['items'][0]['cycle_ended_at'] = '2035-09-05T08:00:12+02:00'
    result = store(conn, connection, validate_page(p, expected_machine_id='606', expected_stream_id=None))
    assert result.conflicts == 1
    with conn.cursor() as cur:
        cur.execute('SELECT last_cycle_at FROM machine_connections WHERE id=%s', (connection,))
        assert cur.fetchone()[0].year == 2026


def test_contract_example_1529_is_stored_once_without_erp(database):
    conn, connection, machine, _ = database
    p = payload()
    p['items'][0].update(event_id='stream-A:1529', sequence=1529, cycle_counter=1529)
    p['next_cursor'] = 'cursor-1529'
    parsed = validate_page(p, expected_machine_id='606', expected_stream_id=None)
    store(conn, connection, parsed)
    assert store(conn, connection, parsed).duplicates == 1
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM machine_source_events WHERE connection_id=%s AND stream_id='stream-A' AND event_id='stream-A:1529'", (connection,))
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM machine_cycles c JOIN machine_source_events e ON e.id=c.source_event_id WHERE e.connection_id=%s AND e.event_id='stream-A:1529' AND c.production_order_id IS NULL", (connection,))
        assert cur.fetchone()[0] == 1


def test_huge_measurement_commits_rejection_neighbor_job_and_cursor(database, monkeypatch):
    from decimal import Decimal
    conn, connection, machine, _ = database
    p = payload(2)
    p['items'][0]['measurements']['cycle_time_s'] = 10**400
    p['items'][1]['measurements']['cycle_time_s'] = 9999.995
    source(monkeypatch, lambda r: httpx.Response(200, json=p))
    result = collector.collect_once(connection)
    assert (result.rejected_events, result.inserted_cycles, result.new_scoring_jobs, result.cursor) == (1, 1, 1, 'cursor-2')
    assert counts(conn, connection) == (2, 1, 1, 'cursor-2')
    with conn.cursor() as cur:
        cur.execute("SELECT status,rejection_reason,payload->'measurements'->>'cycle_time_s' FROM machine_source_events WHERE connection_id=%s ORDER BY sequence", (connection,))
        assert cur.fetchall() == [('rejected', 'measurement_invalid', str(10**400)), ('accepted', None, '9999.995')]
        cur.execute('SELECT cycle_time_s FROM machine_cycles WHERE machine_id=%s', (machine,))
        assert cur.fetchone()[0] == Decimal('9999.995')
    conn.commit()
    due(conn, connection)
    def resumed(request):
        assert request.url.params['after'] == 'cursor-2'
        return httpx.Response(200, json={**p, 'items': []})
    source(monkeypatch, resumed)
    assert collector.collect_once(connection).new_scoring_jobs == 0
    assert counts(conn, connection) == (2, 1, 1, 'cursor-2')

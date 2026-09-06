from datetime import date, datetime, timezone
from ingest.erp_models import ERPDeclaration
from ingest.erp_import_jobs import apply_calendar


def test_calendar_crosses_midnight_and_does_not_use_available_hours():
    declaration = ERPDeclaration('606', '000012', datetime(2026, 9, 5, 19, tzinfo=timezone.utc), 4, available_hours=2)
    calendar = {'version': 2, 'valid_from': date(2026, 1, 1), 'valid_to': None, 'timezone': 'Europe/Paris', 'shifts': [{'number': 4, 'start': '21:00', 'end': '05:00'}]}
    apply_calendar(declaration, calendar)
    assert declaration.production_ended_at == datetime(2026, 9, 6, 3, tzinfo=timezone.utc)
    assert declaration.bounds_origin == 'calendar' and declaration.calendar_version == 2


def test_without_calendar_period_stays_unknown_and_fingerprint_ignores_position():
    declaration = ERPDeclaration('606', '000012', datetime(2026, 9, 5, 19, tzinfo=timezone.utc), 4, available_hours=8)
    apply_calendar(declaration, None)
    assert declaration.production_ended_at is None
    value = declaration.fingerprint()
    declaration.source_row = 100
    declaration.sheet_name = 'Other'
    assert declaration.fingerprint() == value
    declaration.good_parts = 0
    assert declaration.fingerprint() != value


# PostgreSQL scenarios are opt-in and never truncate any table.
import os
from contextlib import contextmanager
from uuid import uuid4
from urllib.parse import urlparse
import pytest


@pytest.fixture
def erp_db(monkeypatch):
    import psycopg2
    from psycopg2.extras import RealDictCursor
    url = os.getenv('ERP_TEST_DATABASE_URL')
    if not url:
        pytest.skip('ERP_TEST_DATABASE_URL dedicated PostgreSQL not supplied')
    parsed = urlparse(url)
    assert parsed.hostname in {'db', 'localhost', '127.0.0.1'} and parsed.path == '/iddrv_test'
    conn = psycopg2.connect(url)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("INSERT INTO sites(name,timezone) VALUES (%s,'Europe/Paris') RETURNING id", (f'ERP synthetic {uuid4()}',))
        site_id = cur.fetchone()['id']
        cur.execute("INSERT INTO machines(site_id,erp_ref,name) VALUES (%s,'606','Synthetic press')", (site_id,))
        cur.execute("INSERT INTO import_passports(site_id,file_name,status) VALUES (%s,'synthetic.xlsx','completed') RETURNING id", (site_id,))
        passport = cur.fetchone()['id']
    # Summary reads this same uncommitted transaction; no data escapes the fixture.
    @contextmanager
    def connection(): yield conn
    monkeypatch.setattr('backend.app.order_repository.get_connection', connection)
    try:
        yield conn, site_id, passport
    finally:
        conn.rollback()
        conn.close()


def test_persistent_order_lifecycle_and_old_export_replay(erp_db):
    from copy import deepcopy
    from datetime import timedelta
    from ingest.erp_repository import persist_declarations
    from backend.app.order_repository import get_order_summary
    conn, site, passport = erp_db
    at = datetime(2026, 9, 5, tzinfo=timezone.utc)
    first = ERPDeclaration('606', '000012', at, 1, produced_parts=6000, good_parts=6000, scrap_parts=0,
                           order_target_quantity=10000, order_status='open', coverage_complete=True,
                           provided_order_fields={'order_target_quantity','order_status','coverage_complete'})
    original = deepcopy(first)
    def persist(declarations, days):
        return persist_declarations(conn, site_id=site, passport_id=passport, declarations=declarations, recorded_at=at + timedelta(days=days))
    def summary(days):
        return get_order_summary(site_id=site, order_ref='000012', known_at=at + timedelta(days=days))
    assert persist([first], 0).created == 1
    assert summary(0)['remaining_quantity'] == 4000
    second = ERPDeclaration('606', '000012', at + timedelta(hours=8), 2, good_parts=4000)
    assert persist([second], 1).created == 1
    assert summary(1)['remaining_quantity'] == 0
    assert summary(1)['order_status'] == 'open'
    second.order_status = 'closed'
    second.order_status_effective_at = at + timedelta(days=2)
    second.provided_order_fields = {'order_status', 'order_status_effective_at'}
    assert persist([second], 2).revised == 1
    assert summary(2)['order_status'] == 'closed'
    first.good_parts, first.scrap_parts, first.order_status = 5600, 400, 'reopened'
    first.order_status_effective_at = at + timedelta(days=3)
    first.order_status_reason = 'Synthetic defective lot'
    first.provided_order_fields |= {'order_status_effective_at', 'order_status_reason'}
    assert persist([first], 3).revised == 1
    assert summary(3)['good_parts_net'] == 9600
    assert summary(3)['remaining_quantity'] == 400
    assert summary(0)['good_parts_net'] == 6000
    third = ERPDeclaration('606', '000012', at + timedelta(days=4), 4, good_parts=400, order_status='closed', provided_order_fields={'order_status'})
    assert persist([third], 4).created == 1
    assert summary(4)['remaining_quantity'] == 0
    assert persist([original, second, third], 5).unchanged == 3
    assert summary(5)['good_parts_net'] == 10000
    with conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM production_orders WHERE site_id=%s AND id=%s', (site, '000012'))
        assert cur.fetchone()[0] == 1
        cur.execute('SELECT count(*) FROM erp_declarations WHERE site_id=%s', (site,))
        assert cur.fetchone()[0] == 3
        cur.execute('SELECT count(*) FROM erp_declaration_revisions WHERE site_id=%s', (site,))
        assert cur.fetchone()[0] == 5


def test_reader_to_storage_two_teams_replay_and_one_correction(erp_db, tmp_path):
    from test_erp_reader import workbook, row
    from ingest.erp_reader import read_trs_declarations
    from ingest.erp_repository import persist_declarations
    conn, site, passport = erp_db
    declarations = read_trs_declarations(workbook(tmp_path, [row(), row(**{'1': 2, '0': datetime(2026, 9, 5, 13)})]), source_timezone='Europe/Paris').declarations
    def persist():
        return persist_declarations(conn, site_id=site, passport_id=passport, declarations=declarations, recorded_at=datetime.now(timezone.utc))
    assert persist().created == 2
    assert persist().unchanged == 2
    declarations[0].scrap_parts = 48
    declarations[0].good_parts = 752
    assert persist().revised == 1
    with conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM erp_declarations WHERE site_id=%s', (site,))
        assert cur.fetchone()[0] == 2
        cur.execute('SELECT count(*) FROM erp_declaration_revisions WHERE site_id=%s', (site,))
        assert cur.fetchone()[0] == 3


def test_calendar_context_does_not_make_an_old_source_new():
    declaration = ERPDeclaration('606', '000012', datetime(2026, 9, 5, 19, tzinfo=timezone.utc), 4, good_parts=600)
    before = declaration.fingerprint()
    apply_calendar(declaration, {'version': 1, 'valid_from': date(2026, 1, 1), 'valid_to': None, 'timezone': 'Europe/Paris', 'shifts': [{'number': 4, 'start': '21:00', 'end': '05:00'}]})
    assert declaration.fingerprint() == before


def test_calendar_preserves_explicit_start_and_its_source_fingerprint():
    from copy import deepcopy
    shift = datetime(2026, 9, 5, 5, tzinfo=timezone.utc)
    start = datetime(2026, 9, 5, 7, tzinfo=timezone.utc)
    source = ERPDeclaration('606', 'same-order', shift, 1, production_started_at=start)
    original_hash = source.fingerprint()
    calendar = {'version': 1, 'valid_from': date(2026, 1, 1), 'valid_to': None,
                'timezone': 'UTC', 'shifts': [{'number': 1, 'start': '05:00', 'end': '13:00'}]}
    first = deepcopy(source)
    apply_calendar(first, calendar)
    assert first.production_started_at == start
    assert first.production_ended_at == datetime(2026, 9, 5, 13, tzinfo=timezone.utc)
    assert first.fingerprint() == original_hash
    revised_calendar = {**calendar, 'version': 2, 'shifts': [{'number': 1, 'start': '05:00', 'end': '14:00'}]}
    second = deepcopy(source)
    apply_calendar(second, revised_calendar)
    assert second.production_started_at == start
    assert second.production_ended_at.hour == 14
    assert second.fingerprint() == original_hash
    source.production_started_at = datetime(2026, 9, 5, 8, tzinfo=timezone.utc)
    apply_calendar(source, revised_calendar)
    assert source.fingerprint() != original_hash


def test_new_closure_without_effective_date_survives_reopening(erp_db):
    from datetime import timedelta
    from ingest.erp_repository import persist_declarations
    from backend.app.order_repository import get_order_summary
    conn, site, passport = erp_db
    at = datetime(2026, 9, 5, tzinfo=timezone.utc)
    versions = [ERPDeclaration('606', 'reclosed-order', at, 1, good_parts=quantity,
                              order_status=status, provided_order_fields={'order_status'})
                for quantity, status in [(100, 'closed'), (90, 'reopened'), (95, 'closed')]]
    for index, declaration in enumerate(versions):
        persist_declarations(conn, site_id=site, passport_id=passport, declarations=[declaration], recorded_at=at + timedelta(days=index))
        summary = get_order_summary(site_id=site, order_ref='reclosed-order', known_at=at + timedelta(days=index))
        assert summary['order_status'] == declaration.order_status
    assert [item['status'] for item in summary['status_history']] == ['closed', 'reopened', 'closed']
    assert all(item['effective_at'] is None for item in summary['status_history'])
    assert summary['good_parts_net'] == 95
    replay = persist_declarations(conn, site_id=site, passport_id=passport, declarations=[versions[0]], recorded_at=at + timedelta(days=3))
    assert replay.unchanged == 1
    assert get_order_summary(site_id=site, order_ref='reclosed-order', known_at=at + timedelta(days=3))['good_parts_net'] == 95


def test_source_start_correction_and_calendar_change_do_not_restore_old_version(erp_db):
    from copy import deepcopy
    from datetime import timedelta
    from ingest.erp_repository import persist_declarations
    conn, site, passport = erp_db
    at = datetime(2026, 9, 5, 5, tzinfo=timezone.utc)
    source = ERPDeclaration('606', 'start-correction', at, 1, good_parts=100,
                            production_started_at=at + timedelta(hours=2))
    calendar = {'version': 1, 'valid_from': date(2026, 1, 1), 'valid_to': None,
                'timezone': 'UTC', 'shifts': [{'number': 1, 'start': '05:00', 'end': '13:00'}]}
    initial = deepcopy(source)
    apply_calendar(initial, calendar)
    assert persist_declarations(conn, site_id=site, passport_id=passport, declarations=[initial], recorded_at=at).created == 1
    correction = deepcopy(source)
    correction.production_started_at += timedelta(hours=1)
    apply_calendar(correction, calendar)
    assert persist_declarations(conn, site_id=site, passport_id=passport, declarations=[correction], recorded_at=at + timedelta(days=1)).revised == 1
    replay = deepcopy(source)
    apply_calendar(replay, {**calendar, 'version': 2, 'shifts': [{'number': 1, 'start': '05:00', 'end': '14:00'}]})
    assert persist_declarations(conn, site_id=site, passport_id=passport, declarations=[replay], recorded_at=at + timedelta(days=2)).unchanged == 1
    with conn.cursor() as cur:
        cur.execute('''SELECT r.production_started_at,r.production_ended_at,r.revision_number FROM erp_declarations d
                       JOIN erp_declaration_revisions r ON r.id=d.current_revision_id WHERE d.site_id=%s AND d.production_order_id='start-correction' ''', (site,))
        start, end, version = cur.fetchone()
        assert start.hour == 8 and end.hour == 13 and version == 2

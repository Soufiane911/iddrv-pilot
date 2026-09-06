from datetime import datetime, timezone
from ingest.erp_models import ERPDeclaration, ERPReadResult
from ingest.erp_import_jobs import validate_order_observations


def test_conflicting_order_status_without_source_dates_blocks_preview():
    rows = [ERPDeclaration('606','OF1',datetime(2026,9,5,tzinfo=timezone.utc),i,
             order_status=status, provided_order_fields={'order_status'}, source_row=i)
            for i,status in [(1,'closed'),(2,'reopened')]]
    result = ERPReadResult(rows, [], 'Sheet', 1)
    validate_order_observations(result)
    assert [issue.code for issue in result.issues] == ['order_observations_conflict']
    assert result.issues[0].severity == 'error'
    rows[0].order_status_effective_at = datetime(2026,9,4,tzinfo=timezone.utc)
    rows[1].order_status_effective_at = datetime(2026,9,5,tzinfo=timezone.utc)
    result.issues.clear()
    validate_order_observations(result)
    assert result.issues == []

from contextlib import contextmanager
from datetime import timedelta, date
from psycopg2.extras import RealDictCursor, Json
from uuid import uuid4
from ingest.erp_repository import persist_declarations
from ingest.context_repository import reconcile_period, site_periods, reconcile_changes, candidates_at
from ingest.erp_import_jobs import apply_calendar
from test_hdt_scoring_worker import scoring_site, emit


def passport(conn,site):
    with conn,conn.cursor() as cur:
        cur.execute("INSERT INTO import_passports(site_id,file_name,parser_type,status) VALUES(%s,'synthetic.xlsx','erp_declarations','completed') RETURNING id",(site,))
        return cur.fetchone()[0]


def declaration(start, *, shift=1, good=45, order='OF1', end=None, status=None):
    return ERPDeclaration('606',order,start,shift,production_started_at=start,
        production_ended_at=end or start+timedelta(hours=8),bounds_origin='source',good_parts=good,
        scrap_parts=5,produced_parts=50,order_status=status,provided_order_fields={'order_status'} if status else set())


def test_delayed_context_correction_known_at_and_immutable_snapshot(scoring_site,monkeypatch):
    conn,url,site,machine,connection=scoring_site
    start=datetime(2026,9,5,5,tzinfo=timezone.utc)
    received=start+timedelta(minutes=1)
    emit(conn,connection,3,start=start,received=received)
    imported=datetime.now(timezone.utc)
    p=passport(conn,site)
    first=declaration(start)
    with conn:
        persist_declarations(conn,site_id=site,passport_id=p,declarations=[first],recorded_at=imported)
        reconcile_period(conn,site_id=site,machine_id=machine,start=start,end=start+timedelta(hours=8),known_at=imported)
    from backend.app.api.production_context import context_history
    def read(known): return context_history(conn,site_id=site,machine_id=machine,start=start,end=start+timedelta(hours=8),known_at=known)
    before=read(imported-timedelta(seconds=1)); original=read(imported)
    assert {x['status'] for x in before['items']}=={'awaiting_erp'}
    assert {x['status'] for x in original['items']}=={'matched'}
    with conn,conn.cursor() as cur:
        cur.execute("INSERT INTO incidents(site_id,machine_id,symptom,started_at,data_cutoff) VALUES(%s,%s,'Dérive à examiner',%s,%s) RETURNING id",(site,machine,start,imported))
        incident=cur.fetchone()[0]
    @contextmanager
    def database():
        import psycopg2
        c=psycopg2.connect(url)
        try: yield c
        finally: c.close()
    monkeypatch.setattr('backend.app.repositories.get_connection',database)
    from backend.app.repositories import persist_investigation,get_investigation
    from backend.app.diagnostics.models import Investigation
    run=persist_investigation(incident,Investigation({},[],[]),imported,context_snapshot=original)
    frozen=get_investigation(run,allowed_site_ids=(site,))
    first.production_started_at=start+timedelta(minutes=1)
    with conn:
        old=site_periods(conn,site,imported)
        persist_declarations(conn,site_id=site,passport_id=p,declarations=[first],recorded_at=imported+timedelta(hours=1))
        reconcile_changes(conn,site,old,imported+timedelta(hours=1))
    corrected=read(imported+timedelta(hours=1))
    assert {x['status'] for x in corrected['items']}=={'awaiting_erp'}
    assert original==read(imported)
    assert get_investigation(run,allowed_site_ids=(site,))==frozen
    assert get_investigation(run,allowed_site_ids=(site+10000,)) is None
    assert all(x['supersedes_id'] is not None for x in corrected['items'])


def test_calendar_reload_preserves_explicit_start_and_revises_old_period(scoring_site):
    conn,url,site,machine,connection=scoring_site
    start=datetime(2026,9,5,5,tzinfo=timezone.utc)
    p=passport(conn,site)
    with conn,conn.cursor() as cur:
        cur.execute("INSERT INTO users(email,password_hash,display_name) VALUES(%s,'none','Calendar test') RETURNING id",(uuid4().hex+'@example.test',)); user=cur.fetchone()[0]
        cur.execute("INSERT INTO site_shift_calendars(site_id,version,valid_from,timezone,shifts,author_id,created_at) VALUES(%s,1,'2026-01-01','UTC',%s,%s,%s)",(site,Json([{'number':1,'start':'05:00','end':'13:00'}]),user,start))
    source=ERPDeclaration('606','OF1',start,1,production_started_at=start+timedelta(hours=1))
    calendar={'timezone':'UTC','valid_from':date(2026,1,1),'valid_to':None,'shifts':[{'number':1,'start':'05:00','end':'13:00'}],'version':1}
    apply_calendar(source,calendar)
    assert source.estimated_bounds=={'production_ended_at'}
    with conn:
        persist_declarations(conn,site_id=site,passport_id=p,declarations=[source],recorded_at=start+timedelta(hours=8))
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        original=candidates_at(cur,site,machine,start+timedelta(hours=8))[0][0]
        assert original.start==start+timedelta(hours=1) and original.end==start+timedelta(hours=8)
    with conn,conn.cursor() as cur:
        cur.execute("INSERT INTO site_shift_calendars(site_id,version,valid_from,timezone,shifts,author_id,created_at) VALUES(%s,2,'2026-01-01','UTC',%s,%s,%s)",(site,Json([{'number':1,'start':'05:00','end':'14:00'}]),user,start+timedelta(hours=9)))
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        revised=candidates_at(cur,site,machine,start+timedelta(hours=9))[0][0]
        assert revised.start==original.start and revised.end==start+timedelta(hours=9)


def test_order_observations_deduplicate_inside_file_preserve_provenance(scoring_site):
    conn,url,site,machine,connection=scoring_site
    start=datetime(2026,9,5,5,tzinfo=timezone.utc); p=passport(conn,site)
    with conn:
        persist_declarations(conn,site_id=site,passport_id=p,recorded_at=start+timedelta(days=1),declarations=[declaration(start,status='closed'),declaration(start+timedelta(hours=8),shift=2,status='closed')])
    with conn,conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM production_order_revisions WHERE site_id=%s',(site,)); assert cur.fetchone()[0]==1
        cur.execute('SELECT count(*) FROM production_order_observation_sources s JOIN production_order_revisions r ON r.id=s.observation_id WHERE r.site_id=%s',(site,)); assert cur.fetchone()[0]==2


def test_same_timestamp_events_keep_distinct_context_chains(scoring_site):
    conn,url,site,machine,connection=scoring_site
    at=datetime(2026,9,5,5,tzinfo=timezone.utc)
    emit(conn,connection,1,start=at)
    emit(conn,connection,1,start=at,sequence=1,after='1')
    with conn,conn.cursor() as cur:
        cur.execute('SELECT source_event_id FROM cycle_context_links WHERE machine_id=%s',(machine,))
        assert len({row[0] for row in cur.fetchall()})==2
    p=passport(conn,site); known=datetime.now(timezone.utc)
    with conn:
        persist_declarations(conn,site_id=site,passport_id=p,declarations=[declaration(at)],recorded_at=known)
        reconcile_period(conn,site_id=site,machine_id=machine,start=at,end=at+timedelta(hours=8),known_at=known)
    from backend.app.api.production_context import context_history
    result=context_history(conn,site_id=site,machine_id=machine,start=at,end=at+timedelta(hours=8),known_at=known)
    assert len({row['link_id'] for row in result['items']})==2
    with conn,conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM cycle_context_links a JOIN cycle_context_links b ON a.supersedes_id=b.id WHERE a.machine_id=%s AND a.source_event_id<>b.source_event_id',(machine,))
        assert cur.fetchone()[0]==0


def test_replacement_reconciles_old_and_new_press_of_same_site(scoring_site):
    conn,url,site,machine,connection=scoring_site
    at=datetime(2026,9,5,5,tzinfo=timezone.utc); p=passport(conn,site)
    emit(conn,connection,1,start=at,received=at)
    with conn,conn.cursor() as cur:
        cur.execute("INSERT INTO machines(site_id,erp_ref) VALUES(%s,'607') RETURNING id",(site,)); other=cur.fetchone()[0]
        cur.execute("INSERT INTO machine_connections(site_id,machine_id,base_url,external_machine_id) VALUES(%s,%s,'http://other-synthetic','606') RETURNING id",(site,other)); second=cur.fetchone()[0]
    emit(conn,second,1,start=at,received=at)
    known=datetime.now(timezone.utc)
    with conn:
        persist_declarations(conn,site_id=site,passport_id=p,declarations=[declaration(at)],recorded_at=known)
        reconcile_changes(conn,site,[],known)
        old=site_periods(conn,site,known)
        replacement=declaration(at,shift=2); replacement.machine_ref='607'
        persist_declarations(conn,site_id=site,passport_id=p,declarations=[replacement],recorded_at=known+timedelta(hours=1))
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM erp_declarations WHERE site_id=%s AND machine_id=%s',(site,other)); replacement_id=cur.fetchone()[0]
            cur.execute('UPDATE erp_declarations SET superseded_by=%s,superseded_recorded_at=%s WHERE site_id=%s AND machine_id=%s',(replacement_id,known+timedelta(hours=1),site,machine))
        reconcile_changes(conn,site,old,known+timedelta(hours=1))
    with conn,conn.cursor() as cur:
        for press,status in [(machine,'awaiting_erp'),(other,'matched')]:
            cur.execute('SELECT status FROM cycle_context_links WHERE site_id=%s AND machine_id=%s ORDER BY created_at DESC LIMIT 1',(site,press))
            assert cur.fetchone()[0]==status


def test_legacy_calendar_provenance_derives_only_missing_bounds():
    from ingest.context_repository import declaration_period
    at=datetime(2026,9,5,5,tzinfo=timezone.utc)
    row={'production_order_id':'OF1','shift_started_at':at,'shift_number':1,'production_started_at':at+timedelta(hours=1),
         'production_ended_at':at+timedelta(hours=8),'bounds_origin':'calendar','estimated_bounds':None,
         'raw_data':{'Début Production':'2026-09-05T06:00:00Z'}}
    from ingest.erp_reader import MAPPING,normalize
    source_header=next(header for header,field in MAPPING.items() if field=='production_started_at')
    row['raw_data']={source_header:'2026-09-05T06:00:00Z'}
    calendar={'timezone':'UTC','valid_from':date(2026,1,1),'valid_to':None,'shifts':[{'number':1,'start':'05:00','end':'14:00'}],'version':2}
    start,end,origin=declaration_period(row,calendar)
    assert start==at+timedelta(hours=1) and end==at+timedelta(hours=9) and origin=='calendar'


def test_collector_uses_erp_committed_while_waiting_for_site_lock(scoring_site):
    import threading
    import time
    import psycopg2
    from concurrent.futures import ThreadPoolExecutor
    from ingest.erp_repository import lock_site
    conn,url,site,machine,connection=scoring_site
    at=datetime(2026,9,5,5,tzinfo=timezone.utc)
    p=passport(conn,site)
    collector=psycopg2.connect(url)
    received=datetime.now(timezone.utc)
    def collect():
        emit(collector,connection,1,start=at,received=received)
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            with conn.cursor() as cur:
                lock_site(cur,site)
                future=pool.submit(collect)
                deadline=time.monotonic()+5
                while True:
                    cur.execute("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE pid=%s AND locktype='advisory' AND NOT granted)",
                                (collector.get_backend_pid(),))
                    if cur.fetchone()[0]: break
                    assert time.monotonic()<deadline,'Collector did not reach the site lock'
                    time.sleep(.01)
                imported=datetime.now(timezone.utc)
                assert imported>received
                persist_declarations(conn,site_id=site,passport_id=p,declarations=[declaration(at)],recorded_at=imported)
                # Import cannot observe the collector transaction's not-yet-committed cycle.
                assert reconcile_period(conn,site_id=site,machine_id=machine,start=at,
                    end=at+timedelta(hours=8),known_at=imported)==0
            conn.commit()
            future.result(timeout=5)
            with conn,conn.cursor() as cur:
                cur.execute('SELECT received_at FROM machine_source_events WHERE machine_id=%s',(machine,))
                assert cur.fetchone()[0]==received
                cur.execute('SELECT status,created_at FROM cycle_context_links WHERE machine_id=%s',(machine,))
                status,known_at=cur.fetchone()
                assert status=='matched'
                assert known_at>=imported
        finally:
            conn.rollback()  # Release the advisory lock even if synchronization fails.
            collector.close()

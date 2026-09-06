from backend.app.services.process_drift import score_history

def test_live_scoring_waits_for_observations_without_loading_model():
    result = score_history([], artifact={}, mode='live')
    assert result.status == 'insufficient_history'
    assert result.input_count == 0
    assert result.score is None

from datetime import datetime, timedelta, timezone
from contextlib import closing
from uuid import uuid4
from urllib.parse import urlparse
import os
import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
from ml.process_drift import DRIFT_NUMERIC_FEATURES, MODEL_VERSION
from ingest.telemetry.models import CycleEnvelope, CyclePage
from ingest.telemetry.repository import store_page
from ingest.telemetry.scorer import claim_job, finish_job, score_pending_once
from backend.app.services.process_drift import ScoringOutcome


def history(n=20):
    return [dict(timestamp=(datetime(2026,9,5,tzinfo=timezone.utc)+timedelta(seconds=i*12)).isoformat(),
                 machine_erp_ref='606', **{key:float(i+1) for key in DRIFT_NUMERIC_FEATURES}) for i in range(n)]


def test_live_contract_19_20_missing_nonfinite_and_units(monkeypatch):
    import pandas as pd
    monkeypatch.setattr('backend.app.services.process_drift.predict',lambda a,f:pd.DataFrame([{
        'anomaly_score':.7,'threshold':.5,'model_version':MODEL_VERSION,'horizon_cycles':20}]))
    artifact={'models':{}}
    assert score_history(history(19),artifact=artifact,mode='live').status=='insufficient_history'
    result=score_history(history(),artifact=artifact,mode='live')
    assert result.status=='scored' and result.model_scope=='global'
    bad=history(); del bad[5]['peak_pressure_bar']
    assert score_history(bad,artifact=artifact,mode='live').status=='incompatible'
    bad=history(); bad[5]['energy_kwh']=float('nan')
    assert score_history(bad,artifact=artifact,mode='live').score is None
    bad=history(); bad[5]['units']={'cycle_time_s':'ms'}
    assert score_history(bad,artifact=artifact,mode='live').reason=='incompatible_units:cycle_time_s'


@pytest.fixture
def scoring_site():
    url=os.getenv('ERP_TEST_DATABASE_URL')
    if not url: pytest.skip('Dedicated ERP_TEST_DATABASE_URL not supplied')
    assert urlparse(url).hostname=='db' and urlparse(url).path=='/iddrv_test'
    conn=psycopg2.connect(url)
    with conn,conn.cursor() as cur:
        cur.execute('INSERT INTO sites(name) VALUES(%s) RETURNING id',('hdt-test-'+uuid4().hex,)); site=cur.fetchone()[0]
        cur.execute("INSERT INTO machines(site_id,erp_ref) VALUES(%s,'606') RETURNING id",(site,)); machine=cur.fetchone()[0]
        cur.execute("INSERT INTO machine_connections(site_id,machine_id,base_url,external_machine_id) VALUES(%s,%s,'http://synthetic','606') RETURNING id",(site,machine)); connection=cur.fetchone()[0]
    yield conn,url,site,machine,connection
    conn.close()


def emit(conn,connection,n,*,start=None,sequence=0,after=None,received=None,partial=False):
    start=start or datetime(2026,9,5,tzinfo=timezone.utc)
    received=received or datetime.now(timezone.utc)
    items=[]
    for i in range(n):
        seq=sequence+i+1
        ended=start+timedelta(seconds=i*12)
        measurements={k:float(i+1) for k in DRIFT_NUMERIC_FEATURES}
        if partial: measurements={'cycle_time_s':12.}
        raw={'event_id':str(seq),'sequence':seq,'machine_id':'606','cycle_ended_at':ended.isoformat(),'measurements':measurements}
        items.append(CycleEnvelope(str(seq),seq,raw,ended,seq,measurements))
    page=CyclePage('test',items,str(sequence+n),False,'606',after)
    store_page(conn,connection_id=connection,page=page,received_at=received)


def stub(cycles,mode):
    return ScoringOutcome('scored',model_version=MODEL_VERSION,model_scope='global',score=.7,threshold=.5,input_count=len(cycles))


def test_frozen_claim_recovery_and_atomic_idempotent_result(scoring_site):
    conn,url,site,machine,connection=scoring_site
    emit(conn,connection,20)
    with closing(psycopg2.connect(url)) as claim_conn:
        job=claim_job(claim_conn,machine_id=machine,lease_seconds=-1)
        frozen=job['input_event_ids']
        with closing(psycopg2.connect(url)) as competitor:
            assert claim_job(competitor,machine_id=machine) is None
    # Late arrival cannot enter the recovered job's already committed snapshot.
    emit(conn,connection,1,start=datetime(2026,9,4,tzinfo=timezone.utc),sequence=20,after='20')
    with closing(psycopg2.connect(url)) as resumed:
        # Recover the specific job before the newly arrived older anchor.
        with resumed,resumed.cursor() as cur:
            cur.execute("UPDATE hdt_scoring_jobs SET lease_until=now()+interval '1 day' WHERE machine_id=%s AND id<>%s",(machine,job['id']))
        retry=claim_job(resumed,machine_id=machine)
        assert retry['id']==job['id'] and retry['input_event_ids']==frozen and retry['calculation_revision']==1
        assert finish_job(resumed,retry,stub(retry['input_snapshot'],retry['mode']))
        assert not finish_job(resumed,retry,stub([],retry['mode']))
    with conn,conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM hdt_predictions WHERE machine_id=%s',(machine,)); assert cur.fetchone()[0]==1
        cur.execute('SELECT count(*) FROM incidents WHERE machine_id=%s',(machine,)); assert cur.fetchone()[0]==0
        cur.execute('SELECT count(*) FROM machine_cycles WHERE machine_id=%s',(machine,)); assert cur.fetchone()[0]==21


def test_timeout_retries_without_success_or_cycle_loss(scoring_site):
    conn,url,site,machine,connection=scoring_site
    emit(conn,connection,1)
    def timeout(*args): raise TimeoutError()
    assert score_pending_once(database_url=url,machine_id=machine,infer=timeout)==0
    with conn,conn.cursor() as cur:
        cur.execute('SELECT state,public_error,input_event_ids FROM hdt_scoring_jobs WHERE machine_id=%s',(machine,)); state,error,ids=cur.fetchone()
        assert state=='pending' and error=='scoring_retry_required' and len(ids)==1
        cur.execute('SELECT count(*) FROM machine_cycles WHERE machine_id=%s',(machine,)); assert cur.fetchone()[0]==1


def test_episode_first_high_five_low_and_replay(scoring_site):
    conn,url,site,machine,connection=scoring_site
    scores=[.2,.7,.8,.3,.3,.3,.3,.3]
    expected=[0,1,1,1,1,1,1,0]
    for i,score in enumerate(scores):
        emit(conn,connection,1,start=datetime.now(timezone.utc)-timedelta(seconds=1),sequence=i,after=str(i) if i else None)
        def infer(cycles,mode): return ScoringOutcome('scored',model_version=MODEL_VERSION,model_scope='global',score=score,threshold=.5,input_count=len(cycles))
        assert score_pending_once(database_url=url,machine_id=machine,infer=infer)==1
        with conn,conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM process_drift_episodes WHERE machine_id=%s AND closed_at IS NULL",(machine,))
            assert cur.fetchone()[0]==expected[i]
    assert score_pending_once(database_url=url,machine_id=machine,infer=stub)==0
    with conn,conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM incidents WHERE machine_id=%s',(machine,)); assert cur.fetchone()[0]==1


def test_source_event_composite_fk(scoring_site):
    conn,url,site,machine,connection=scoring_site
    emit(conn,connection,1)
    with conn,conn.cursor() as cur:
        cur.execute('SELECT id,cycle_ended_at FROM machine_source_events WHERE machine_id=%s',(machine,)); event,ended=cur.fetchone()
        cur.execute("INSERT INTO machines(site_id,erp_ref) VALUES(%s,'607') RETURNING id",(site,)); other=cur.fetchone()[0]
        for event_id,machine_id,at in [(str(uuid4()),machine,ended),(event,other,ended),(event,machine,ended+timedelta(seconds=1))]:
            cur.execute('SAVEPOINT invalid_event')
            with pytest.raises(psycopg2.IntegrityError):
                cur.execute('INSERT INTO machine_cycles(time,machine_id,source_event_id) VALUES(%s,%s,%s)',(at,machine_id,event_id))
            cur.execute('ROLLBACK TO SAVEPOINT invalid_event')


def test_model_unavailable_abstains_and_missing_breaks_normal_streak(scoring_site):
    assert score_history(history(),artifact={},mode='live').status=='model_unavailable'
    conn,url,site,machine,connection=scoring_site
    for i,score in enumerate([.7,.3,.3,None,.3,.3,.3,.3,.3]):
        emit(conn,connection,1,start=datetime.now(timezone.utc)-timedelta(seconds=1),sequence=i,after=str(i) if i else None)
        def infer(cycles,mode):
            if score is None: return ScoringOutcome('incompatible',reason='missing_feature',input_count=len(cycles))
            return ScoringOutcome('scored',model_version=MODEL_VERSION,model_scope='global',score=score,threshold=.5,input_count=len(cycles))
        assert score_pending_once(database_url=url,machine_id=machine,infer=infer)==1
        with conn,conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM process_drift_episodes WHERE machine_id=%s AND closed_at IS NULL',(machine,))
            assert cur.fetchone()[0]==(0 if i==8 else 1)


def test_failed_atomic_finish_and_explicit_recalculation(scoring_site,monkeypatch):
    conn,url,site,machine,connection=scoring_site
    emit(conn,connection,1)
    import ingest.telemetry.scorer as scorer
    original=scorer.update_episode
    def crash(*args): raise RuntimeError('crash-before-job-completion')
    monkeypatch.setattr(scorer,'update_episode',crash)
    assert score_pending_once(database_url=url,machine_id=machine,infer=stub)==0
    with conn,conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM hdt_predictions WHERE machine_id=%s',(machine,)); assert cur.fetchone()[0]==0
        cur.execute('UPDATE hdt_scoring_jobs SET lease_until=NULL WHERE machine_id=%s',(machine,))
    monkeypatch.setattr(scorer,'update_episode',original)
    assert score_pending_once(database_url=url,machine_id=machine,infer=stub)==1
    with conn,conn.cursor() as cur:
        cur.execute('SELECT id FROM hdt_predictions WHERE machine_id=%s',(machine,)); first=cur.fetchone()[0]
        scorer.request_recalculation(conn,site_id=site,prediction_id=first)
    assert score_pending_once(database_url=url,machine_id=machine,infer=stub)==1
    with conn,conn.cursor() as cur:
        cur.execute('SELECT calculation_revision,supersedes_id,mode FROM hdt_predictions WHERE machine_id=%s ORDER BY calculation_revision',(machine,))
        assert cur.fetchall()==[(1,None,'backfill'),(2,first,'backfill')]


def test_bounded_inference_does_not_spawn_for_warmup_or_partial_data(monkeypatch):
    from ingest.telemetry.scorer import infer_bounded
    def forbidden(*args): raise AssertionError('No inference process needed')
    monkeypatch.setattr('ingest.telemetry.scorer.multiprocessing.get_context',forbidden)
    assert infer_bounded(history(19),'live').status=='insufficient_history'
    partial=history(); del partial[4]['peak_pressure_bar']
    assert infer_bounded(partial,'live').status=='incompatible'


def test_recovered_frozen_live_job_becomes_backfill_after_newer_score(scoring_site):
    conn,url,site,machine,connection=scoring_site
    at=datetime.now(timezone.utc)-timedelta(seconds=2)
    emit(conn,connection,1,start=at)
    with closing(psycopg2.connect(url)) as crashed:
        original=claim_job(crashed,machine_id=machine)
        assert original['mode']=='live'
    # The older claim still has an active lease, so a newer anchor can progress.
    emit(conn,connection,1,start=at+timedelta(seconds=1),sequence=1,after='1')
    assert score_pending_once(database_url=url,machine_id=machine,infer=stub)==1
    with conn,conn.cursor() as cur:
        cur.execute('SELECT below_count,closed_at FROM process_drift_episodes WHERE machine_id=%s',(machine,))
        episode_before=cur.fetchone()
        cur.execute('SELECT count(*) FROM process_drift_episode_predictions WHERE machine_id=%s',(machine,))
        links_before=cur.fetchone()[0]
        cur.execute("UPDATE hdt_scoring_jobs SET lease_until=clock_timestamp()-interval '1 second' WHERE id=%s",(original['id'],))
    with closing(psycopg2.connect(url)) as resumed:
        retry=claim_job(resumed,machine_id=machine)
        assert retry['id']==original['id']
        assert retry['input_event_ids']==original['input_event_ids']
        assert retry['input_snapshot']==original['input_snapshot']
        assert retry['mode']=='backfill'
        assert finish_job(resumed,retry,ScoringOutcome('scored',model_version=MODEL_VERSION,
            model_scope='global',score=.2,threshold=.5,input_count=1))
    with conn,conn.cursor() as cur:
        cur.execute('SELECT below_count,closed_at FROM process_drift_episodes WHERE machine_id=%s',(machine,))
        assert cur.fetchone()==episode_before
        cur.execute('SELECT count(*) FROM process_drift_episode_predictions WHERE machine_id=%s',(machine,))
        assert cur.fetchone()[0]==links_before


def test_same_timestamp_jobs_follow_source_order_with_one_live_anchor(scoring_site):
    conn,url,site,machine,connection=scoring_site
    at=datetime.now(timezone.utc)-timedelta(seconds=1)
    received=datetime.now(timezone.utc)
    items=[]
    for sequence in (1,2,3):
        raw={'event_id':str(sequence),'sequence':sequence,'machine_id':'606','cycle_ended_at':at.isoformat(),
             'measurements':{'cycle_time_s':12.}}
        items.append(CycleEnvelope(str(sequence),sequence,raw,at,sequence,raw['measurements']))
    store_page(conn,connection_id=connection,page=CyclePage('test',items,'3',False,'606'),received_at=received)
    with conn,conn.cursor() as cur:
        # Deliberately invert job creation order: source sequence remains authoritative.
        cur.execute("""UPDATE hdt_scoring_jobs j SET created_at=e.received_at-e.sequence*interval '1 second'
            FROM machine_source_events e WHERE e.id=j.event_id AND j.machine_id=%s""",(machine,))
        cur.execute('SELECT id FROM machine_source_events WHERE machine_id=%s ORDER BY sequence',(machine,))
        expected_ids=[str(row[0]) for row in cur.fetchall()]
    for index,event_id in enumerate(expected_ids):
        with closing(psycopg2.connect(url)) as worker:
            job=claim_job(worker,machine_id=machine)
            assert str(job['event_id'])==event_id
            assert job['input_event_ids']==expected_ids[:index+1]
            assert job['mode']==('live' if index==2 else 'backfill')
            assert finish_job(worker,job,stub(job['input_snapshot'],job['mode']))
        with conn,conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM process_drift_episodes WHERE machine_id=%s',(machine,))
            assert cur.fetchone()[0]==(1 if index==2 else 0)
    with conn,conn.cursor() as cur:
        cur.execute('SELECT count(DISTINCT source_event_id) FROM cycle_context_links WHERE machine_id=%s',(machine,))
        assert cur.fetchone()[0]==3
        cur.execute('SELECT count(*) FROM process_drift_episode_predictions WHERE machine_id=%s',(machine,))
        assert cur.fetchone()[0]==1

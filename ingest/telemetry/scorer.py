"""Durable HDT jobs. A session advisory lock serializes each press across inference."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import multiprocessing
import os
from pathlib import Path
import time
from uuid import uuid4

import psycopg2
from psycopg2.extras import Json, RealDictCursor
from ingest.runtime_config import worker_database_url
from backend.app.services.process_drift import model_artifact, score_history


def _infer_child(pipe, cycles, mode):
    try:
        pipe.send(score_history(cycles, artifact=model_artifact, mode=mode))
    finally:
        pipe.close()


def infer_bounded(cycles, mode):
    # Sparse telemetry is a persisted abstention; it needs no subprocess/model.
    readiness = score_history(cycles,artifact={},mode=mode)
    if readiness.status in {'insufficient_history','incompatible'}:
        return readiness
    context = multiprocessing.get_context('spawn')
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_infer_child,args=(child,cycles,mode))
    process.start()
    child.close()
    try:
        if not parent.poll(float(os.getenv('HDT_INFERENCE_TIMEOUT_S','30'))):
            raise TimeoutError('model_timeout')
        return parent.recv()
    finally:
        if process.is_alive():
            process.terminate()
        process.join()
        parent.close()


def claim_job(conn, *, machine_id=None, lease_seconds=60):
    from ml.runtime_mode import historical_enabled
    if not historical_enabled():
        return None
    with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''SELECT j.id,j.machine_id FROM hdt_scoring_jobs j
            JOIN machine_source_events e ON e.id=j.event_id
            WHERE (j.state='pending' OR j.state='running' AND j.lease_until<now())
            AND (j.lease_until IS NULL OR j.lease_until<now()) AND (%s::int IS NULL OR j.machine_id=%s)
            ORDER BY e.cycle_ended_at,e.received_at,e.connection_id,e.stream_id,e.sequence,
                     j.calculation_revision,j.model_version,j.mode,j.id LIMIT 100''', (machine_id,machine_id))
        for candidate in cur.fetchall():
            cur.execute('SELECT pg_try_advisory_lock(1347568468,%s)', (candidate['machine_id'],))
            if not cur.fetchone()['pg_try_advisory_lock']:
                continue
            cur.execute('''SELECT j.*,e.cycle_ended_at,e.received_at,e.sequence AS anchor_sequence,e.connection_id,e.stream_id,m.erp_ref FROM hdt_scoring_jobs j
                JOIN machine_source_events e ON e.id=j.event_id JOIN machines m ON m.id=j.machine_id AND m.site_id=j.site_id
                WHERE j.id=%s AND (j.state='pending' OR j.state='running' AND j.lease_until<now())
                AND (j.lease_until IS NULL OR j.lease_until<now()) FOR UPDATE OF j SKIP LOCKED''',(candidate['id'],))
            job = cur.fetchone()
            if not job:
                cur.execute('SELECT pg_advisory_unlock(1347568468,%s)',(candidate['machine_id'],))
                continue
            job = dict(job)
            token = str(uuid4())
            if job['input_event_ids'] is None:
                input_known_at = job['received_at'] if job['calculation_revision']==1 else job['created_at']
                cur.execute('''SELECT id,payload,cycle_ended_at FROM machine_source_events
                    WHERE site_id=%s AND machine_id=%s AND status='accepted' AND cycle_ended_at<=%s
                    AND received_at<=%s AND (cycle_ended_at,received_at,connection_id,stream_id,sequence)<=(%s,%s,%s,%s,%s)
                    ORDER BY cycle_ended_at DESC,received_at DESC,connection_id DESC,stream_id DESC,sequence DESC LIMIT 20''',
                    (job['site_id'],job['machine_id'],job['cycle_ended_at'],input_known_at,job['cycle_ended_at'],job['received_at'],job['connection_id'],job['stream_id'],job['anchor_sequence']))
                inputs = list(reversed(cur.fetchall()))
                ids = [str(row['id']) for row in inputs]
                snapshot = [dict(row['payload'].get('measurements',{}),timestamp=row['cycle_ended_at'].isoformat(),
                                 machine_erp_ref=job['erp_ref'],units=row['payload'].get('units',{})) for row in inputs]
                cur.execute('UPDATE hdt_scoring_jobs SET input_event_ids=%s,input_snapshot=%s WHERE id=%s',
                            (Json(ids),Json(snapshot),job['id']))
                job.update(input_event_ids=ids,input_snapshot=snapshot)
            # Reclassify every claim, including a recovered frozen snapshot. The
            # unique source order selects one current event even at a tied date.
            # Across streams, reception and source identity provide a stable tie;
            # within one stream, sequence (never job creation/UUID) is authoritative.
            cur.execute("""SELECT id FROM machine_source_events
                WHERE site_id=%s AND machine_id=%s AND status='accepted'
                ORDER BY cycle_ended_at DESC,received_at DESC,connection_id DESC,stream_id DESC,sequence DESC LIMIT 1""",
                (job['site_id'],job['machine_id']))
            latest = cur.fetchone()
            now = datetime.now(timezone.utc)
            current = (latest is not None and latest['id']==job['event_id']
                       and job['calculation_revision']==1
                       and timedelta(0)<=now-job['cycle_ended_at']<=timedelta(seconds=90))
            if job['mode']=='live' and not current:
                cur.execute("UPDATE hdt_scoring_jobs SET mode='backfill' WHERE id=%s",(job['id'],))
                job['mode']='backfill'
            cur.execute('''UPDATE hdt_scoring_jobs SET state='running',claim_token=%s,attempts=attempts+1,
                lease_until=clock_timestamp()+%s*interval '1 second',started_at=coalesce(started_at,clock_timestamp()),updated_at=clock_timestamp()
                WHERE id=%s''',(token,lease_seconds,job['id']))
            job['claim_token'] = token
            return job
    return None


def update_episode(cur, prediction):
    if prediction['mode'] != 'live' or prediction['calculation_revision'] != 1:
        return
    site,machine = prediction['site_id'],prediction['machine_id']
    cur.execute('SELECT 1 FROM process_drift_episode_predictions WHERE prediction_id=%s',(prediction['id'],))
    if cur.fetchone():
        return
    cur.execute('SELECT * FROM process_drift_episodes WHERE site_id=%s AND machine_id=%s AND closed_at IS NULL FOR UPDATE',(site,machine))
    episode = cur.fetchone()
    scored = prediction['status']=='scored'
    high = scored and prediction['score'] >= prediction['threshold']
    if not episode and high:
        key = hashlib.sha256(('process_drift:'+str(prediction['id'])).encode()).hexdigest()
        cur.execute('''INSERT INTO incidents(site_id,machine_id,origin,symptom,started_at,data_cutoff,detection_key)
            VALUES(%s,%s,'process_drift','Dérive à examiner',%s,%s,%s)
            ON CONFLICT(detection_key) WHERE detection_key IS NOT NULL DO NOTHING RETURNING id''',
            (site,machine,prediction['evaluated_through'],prediction['scored_at'],key))
        incident = cur.fetchone()
        if not incident:
            return
        cur.execute('INSERT INTO process_drift_episodes(incident_id,site_id,machine_id) VALUES(%s,%s,%s) RETURNING *',(incident['id'],site,machine))
        episode = cur.fetchone()
    if not episode:
        return
    below = 0 if high or not scored else episode['below_count']+1
    closed = prediction['evaluated_through'] if below>=5 else None
    cur.execute('UPDATE process_drift_episodes SET below_count=%s,closed_at=%s WHERE incident_id=%s',(below,closed,episode['incident_id']))
    cur.execute('UPDATE incidents SET data_cutoff=%s WHERE id=%s AND site_id=%s AND machine_id=%s',
                (prediction['scored_at'],episode['incident_id'],site,machine))
    if closed:
        cur.execute("UPDATE incidents SET status='closed',ended_at=%s,data_cutoff=%s WHERE id=%s",(closed,prediction['scored_at'],episode['incident_id']))
    cur.execute('INSERT INTO process_drift_episode_predictions(prediction_id,incident_id,site_id,machine_id) VALUES(%s,%s,%s,%s)',
                (prediction['id'],episode['incident_id'],site,machine))


def finish_job(conn, job, outcome):
    from ml.runtime_mode import historical_enabled
    if not historical_enabled():
        return False
    with conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id FROM hdt_scoring_jobs WHERE id=%s AND claim_token=%s AND state='running' FOR UPDATE",(job['id'],job['claim_token']))
        if not cur.fetchone():
            return False
        if outcome.model_version and outcome.model_version != job['model_version']:
            raise ValueError('model_version_mismatch')
        cur.execute('''INSERT INTO hdt_predictions(job_id,event_id,site_id,machine_id,input_event_ids,model_version,model_scope,
            mode,calculation_revision,supersedes_id,status,score,threshold,signals,horizon_cycles,input_count,reason,evaluated_through,scored_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,clock_timestamp()) RETURNING *''',
            (job['id'],job['event_id'],job['site_id'],job['machine_id'],Json(job['input_event_ids']),job['model_version'],outcome.model_scope,
             job['mode'],job['calculation_revision'],job['supersedes_id'],outcome.status,outcome.score,outcome.threshold,Json(outcome.signals),
             outcome.horizon_cycles,outcome.input_count,outcome.reason,job['cycle_ended_at']))
        prediction = dict(cur.fetchone())
        update_episode(cur,prediction)
        cur.execute("UPDATE hdt_scoring_jobs SET state='completed',completed_at=clock_timestamp(),lease_until=NULL,public_error=NULL WHERE id=%s",(job['id'],))
    return True


def score_pending_once(*, database_url=None, machine_id=None, infer=None) -> int:
    from ml.runtime_mode import historical_enabled
    if not historical_enabled():
        return 0  # Explicitly suspended; queued historical identities are untouched.
    with closing(psycopg2.connect(database_url or worker_database_url())) as conn:
        job = claim_job(conn,machine_id=machine_id)
        if not job:
            return 0
        try:
            outcome = (infer or infer_bounded)(job['input_snapshot'],job['mode'])
            return int(finish_job(conn,job,outcome))
        except Exception:
            conn.rollback()
            with conn,conn.cursor() as cur:
                cur.execute("""UPDATE hdt_scoring_jobs SET state='pending',public_error='scoring_retry_required',
                    lease_until=clock_timestamp()+interval '30 seconds' WHERE id=%s AND claim_token=%s AND state='running'""",(job['id'],job['claim_token']))
            return 0
        finally:
            with conn,conn.cursor() as cur:
                cur.execute('SELECT pg_advisory_unlock(1347568468,%s)',(job['machine_id'],))


def request_recalculation(conn, *, site_id, prediction_id):
    """Explicit worker command. ERP reconciliation never calls this operation."""
    from ml.runtime_mode import historical_enabled
    if not historical_enabled():
        raise ValueError('historical_scoring_disabled')
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT * FROM hdt_predictions WHERE site_id=%s AND id=%s',(site_id,str(prediction_id)))
        previous = cur.fetchone()
        if not previous:
            raise ValueError('prediction_not_found')
        cur.execute('SELECT pg_advisory_xact_lock(1347568468,%s)',(previous['machine_id'],))
        cur.execute('SELECT coalesce(max(calculation_revision),0)+1 AS revision FROM hdt_scoring_jobs WHERE event_id=%s AND model_version=%s',
                    (previous['event_id'],previous['model_version']))
        revision = cur.fetchone()['revision']
        cur.execute("""INSERT INTO hdt_scoring_jobs(event_id,site_id,machine_id,model_version,mode,calculation_revision,supersedes_id)
            VALUES(%s,%s,%s,%s,'backfill',%s,%s) RETURNING id""",(previous['event_id'],site_id,previous['machine_id'],
            previous['model_version'],revision,previous['id']))
        return cur.fetchone()['id']


def heartbeat_is_fresh():
    path = Path(os.getenv('SCORER_HEARTBEAT_PATH','/tmp/iddrv-scorer-heartbeat'))
    return path.exists() and time.time()-path.stat().st_mtime<90


def main():
    from ml.runtime_mode import historical_enabled
    if not historical_enabled():
        import logging
        logging.getLogger(__name__).warning('Historical scorer suspended by HDT_RUNTIME_MODE; summary6 live is not connected')
    heartbeat = Path(os.getenv('SCORER_HEARTBEAT_PATH','/tmp/iddrv-scorer-heartbeat'))
    while True:
        try:
            completed = score_pending_once()
            heartbeat.touch()
            if not completed:
                time.sleep(1)
        except psycopg2.Error:
            time.sleep(2)

if __name__=='__main__':
    main()

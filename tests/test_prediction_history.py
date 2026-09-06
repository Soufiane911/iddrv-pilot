from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
import psycopg2
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.security import Identity,create_session_token
from backend.app.api import predictions, production_context
from ingest.telemetry.scorer import score_pending_once
from test_hdt_scoring_worker import scoring_site,emit,stub


def test_persisted_history_survives_connections_and_knowledge_filter(scoring_site,monkeypatch):
    conn,url,site,machine,connection=scoring_site
    emit(conn,connection,1)
    before=datetime.now(timezone.utc)
    assert score_pending_once(database_url=url,machine_id=machine,infer=stub)==1
    @contextmanager
    def database():
        with psycopg2.connect(url) as c: yield c
    monkeypatch.setattr('backend.app.prediction_repository.get_connection',database)
    from backend.app.prediction_repository import prediction_history
    kwargs=dict(site_id=site,machine_id=machine,start=datetime(2026,9,5,tzinfo=timezone.utc),end=datetime(2026,9,6,tzinfo=timezone.utc))
    assert prediction_history(**kwargs,known_at=before)['items']==[]
    rows=prediction_history(**kwargs,known_at=datetime.now(timezone.utc))['items']
    assert len(rows)==1 and rows[0]['mode']=='backfill'
    assert prediction_history(**(kwargs|{'site_id':site+10000}),known_at=datetime.now(timezone.utc))['items']==[]
    with conn,conn.cursor() as cur:
        cur.execute('SAVEPOINT immutable_prediction')
        with pytest.raises(psycopg2.Error,match='immutable_history'):
            cur.execute('UPDATE hdt_predictions SET score=0 WHERE id=%s',(rows[0]['id'],))
        cur.execute('ROLLBACK TO SAVEPOINT immutable_prediction')


def test_prediction_api_is_authenticated_scoped_and_bounded(monkeypatch):
    client=TestClient(app)
    assert client.get('/api/v1/machines/1/hdt-predictions').status_code==401
    token,_=create_session_token(Identity('u','test@example.test','Test','viewer',(1,)))
    headers={'Authorization':'Bearer '+token}
    monkeypatch.setattr('backend.app.api.machine_connections.local_machine',lambda _: {'id':1,'site_id':2})
    assert client.get('/api/v1/machines/1/hdt-predictions',headers=headers).status_code==404
    monkeypatch.setattr('backend.app.api.machine_connections.local_machine',lambda _: {'id':1,'site_id':1})
    assert client.get('/api/v1/machines/1/hdt-predictions?from=2026-01-01T00:00:00Z&to=2026-03-01T00:00:00Z',headers=headers).status_code==422
    assert client.get('/api/v1/machines/1/production-context?known_at=2026-01-01T00:00:00',headers=headers).status_code==422

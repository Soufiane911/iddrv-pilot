"""Standalone non-destructive acceptance: --noconftest, dedicated iddrv_test only."""
from contextlib import contextmanager
from datetime import datetime, timezone
import os
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import psycopg2
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.app.main import app
from backend.app.security import Identity,create_session_token
from backend.app.services.process_drift import model_artifact,score_history
from ingest.telemetry.http_source import ApiCycleSource
from ingest.telemetry.repository import store_page
from ingest.telemetry.scorer import score_pending_once
from ingest.erp_import_jobs import process_approved_erp_import


def test_100_real_scores_then_two_teams_and_correction(tmp_path,monkeypatch):
    url=os.getenv('ERP_TEST_DATABASE_URL')
    if not url: pytest.skip('Dedicated ERP_TEST_DATABASE_URL not supplied')
    assert urlparse(url).hostname=='db' and urlparse(url).path=='/iddrv_test'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    origin=f'http://127.0.0.1:{port}'
    token='synthetic-delayed-erp-only'
    env={**os.environ,'PRESS_FIXTURE_DB':str(tmp_path/'press.sqlite'),'PRESS_FIXTURE_CONTROL_TOKEN':token}
    source=subprocess.Popen([sys.executable,'-m','uvicorn','tests.fixtures.press_api.app:app','--host','127.0.0.1','--port',str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    conn=psycopg2.connect(url)
    try:
        with httpx.Client(base_url=origin,headers={'X-Test-Control-Token':token},timeout=2) as http:
            deadline=time.monotonic()+15
            while True:
                try:
                    if http.get('/v1/machines/606/status').status_code==200: break
                except httpx.HTTPError: pass
                assert time.monotonic()<deadline
                time.sleep(.1)
            assert http.post('/__test/control',json={'emit':100,'profile':'complete','start_at':'2026-09-05T12:50:00+02:00'}).status_code==200
            with conn,conn.cursor() as cur:
                cur.execute("INSERT INTO sites(name,timezone) VALUES(%s,'Europe/Paris') RETURNING id",('delayed-erp-'+uuid4().hex,)); site=cur.fetchone()[0]
                cur.execute("INSERT INTO machines(site_id,erp_ref) VALUES(%s,'606') RETURNING id",(site,)); machine=cur.fetchone()[0]
                cur.execute("INSERT INTO machine_connections(site_id,machine_id,base_url,external_machine_id) VALUES(%s,%s,%s,'606') RETURNING id",(site,machine,origin)); connection=cur.fetchone()[0]
                cur.execute("INSERT INTO users(email,password_hash,display_name) VALUES(%s,'none','ERP QA') RETURNING id",(uuid4().hex+'@example.test',)); user=str(cur.fetchone()[0])
            page=ApiCycleSource(http).fetch_page('606',after=None,limit=100)
            received=datetime.now(timezone.utc)
            assert store_page(conn,connection_id=connection,page=page,received_at=received).inserted_cycles==100
        def real(cycles,mode): return score_history(cycles,artifact=model_artifact,mode=mode)
        for _ in range(100):
            assert score_pending_once(database_url=url,machine_id=machine,infer=real)==1
        with conn,conn.cursor() as cur:
            cur.execute('SELECT id,score,status,input_event_ids,scored_at FROM hdt_predictions WHERE machine_id=%s ORDER BY evaluated_through',(machine,)); initial=cur.fetchall()
            assert len(initial)==100
            assert sum(row[2]=='scored' for row in initial)==81
            assert sum(row[2]=='insufficient_history' for row in initial)==19
            cur.execute('SELECT count(*) FROM incidents WHERE machine_id=%s',(machine,)); assert cur.fetchone()[0]==0
        @contextmanager
        def database():
            c=psycopg2.connect(url)
            try: yield c
            finally: c.close()
        for module in ('erp_import_repository','order_repository','connection_repository','prediction_repository','auth_repository'):
            monkeypatch.setattr('backend.app.'+module+'.get_connection',database)
        monkeypatch.setattr('backend.app.api.production_context.get_connection',database)
        monkeypatch.setattr('backend.app.api.erp_imports.UPLOAD_ROOT',tmp_path/'uploads')
        client=TestClient(app)
        session_id=str(uuid4())
        access,expires=create_session_token(Identity(user,'qa@example.test','QA','supervisor',(site,),session_id,site_roles=((site,'supervisor'),)))
        from backend.app.security import token_hash
        with conn,conn.cursor() as cur:
            cur.execute("INSERT INTO user_site_roles(user_id,site_id,role) VALUES(%s,%s,'supervisor')",(user,site))
            cur.execute('INSERT INTO sessions(id,user_id,token_hash,expires_at) VALUES(%s,%s,%s,%s)',(session_id,user,token_hash(access),expires))
        headers={'Authorization':'Bearer '+access}
        calendar={'expected_version':0,'valid_from':'2026-01-01','timezone':'Europe/Paris',
            'shifts':[{'number':1,'start':'05:00','end':'13:00'},{'number':2,'start':'13:00','end':'21:00'}]}
        response=client.put(f'/api/v1/sites/{site}/shift-calendar',headers=headers,json=calendar)
        assert response.status_code==200,response.text
        def import_teams(good):
            book=Workbook(); sheet=book.active
            sheet.append(['Début Equipe','Num Equipe','Réf. Machine','Réf OF','Type OF','Qté Pieces Fab.','Qté Pieces Bonnes','Total Rebuts','Nb Cycles'])
            sheet.append([datetime(2026,9,5,5),1,'606','000012','Production',50,good,50-good,50])
            sheet.append([datetime(2026,9,5,13),2,'606','000012','Production',50,48,2,50])
            path=tmp_path/'teams.xlsx'; book.save(path)
            response=client.post(f'/api/v1/sites/{site}/erp-imports',headers=headers,files={'file':('teams.xlsx',path.read_bytes())})
            assert response.status_code==202,response.text
            import_id=response.json()['id']
            preview=client.post(f'/api/v1/erp-imports/{import_id}/preview/refresh',headers=headers).json()
            assert not [i for i in preview['issues'] if i['severity']=='error'],preview
            response=client.post(f'/api/v1/erp-imports/{import_id}/confirm',headers=headers,json={'preview_version':preview['preview_version'],'create_machine_refs':[],'replacements':[]})
            assert response.status_code==202,response.text
            process_approved_erp_import(import_id,database_url=url)
        import_teams(45)
        params={'from':'2026-09-05T10:40:00Z','to':'2026-09-05T11:20:00Z'}
        response=client.get(f'/api/v1/machines/{machine}/production-context',headers=headers,params=params)
        assert response.status_code==200,response.text
        context=response.json()
        assert len(context['items'])==100 and {x['status'] for x in context['items']}=={'provisional'}
        by_revision={d['id']:d['shift_number'] for d in context['declarations']}
        assert [by_revision[x['revision_id']] for x in context['items']]==[1]*50+[2]*50
        assert datetime.fromisoformat(context['items'][50]['time'])==datetime(2026,9,5,11,tzinfo=timezone.utc)
        import_teams(42)
        corrected=client.get(f'/api/v1/machines/{machine}/production-context',headers=headers,params=params).json()
        assert sum(a['link_id']!=b['link_id'] for a,b in zip(context['items'],corrected['items']))==50
        assert corrected['orders'][0]['good_parts_net']==90
        with conn,conn.cursor() as cur:
            cur.execute('SELECT id,score,status,input_event_ids,scored_at FROM hdt_predictions WHERE machine_id=%s ORDER BY evaluated_through',(machine,)); assert cur.fetchall()==initial
            cur.execute('SELECT count(*),count(good_parts),count(scrap_flag) FROM machine_cycles WHERE machine_id=%s',(machine,)); assert cur.fetchone()==(100,0,0)
        print(f'100cycles; 81scores réels backfill/19warmup; ERP2équipes50+50; correction50liens; scores immuables; site={site} machine={machine}; réception={received.isoformat()}.')
    finally:
        conn.close()
        source.terminate(); source.wait(timeout=5)

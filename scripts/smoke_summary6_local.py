"""Real loopback HTTP/login + temporary DB smoke, never an existing stack.
Creates ONLY its uniquely named tmpfs container and removes ONLY that container.
Requires cached Timescale image, Docker and the exact approved Python environment.
"""
import os
import json
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import uuid

import httpx
import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def stop_server(server):
    if server is None:
        return
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=10)


def remove_owned_container(name, owner):
    inspected = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True)
    if inspected.returncode:
        return
    info = json.loads(inspected.stdout)[0]
    if info.get('Config', {}).get('Labels', {}).get('iddrv.summary6.smoke') != owner:
        raise RuntimeError('smoke_container_ownership_mismatch')
    subprocess.run(['docker', 'rm', '-f', info['Id']], check=True, stdout=subprocess.DEVNULL)


def run():
    # Fail before Docker/network for missing, corrupt or incompatible artifacts.
    os.environ['HDT_RUNTIME_MODE'] = 'summary6_replay'
    from backend.app.services.summary6 import current
    if not current()['replay_enabled']:
        raise RuntimeError('summary6_preflight_unavailable')
    owner = uuid.uuid4().hex
    name = 'iddrv-summary6-smoke-' + owner
    password = secrets.token_urlsafe(24)
    server = None
    attempted = False
    conn = None
    try:
        attempted = True
        subprocess.run(['docker', 'run', '-d', '--pull=never', '--name', name,
                        '--label', 'iddrv.summary6.smoke=' + owner,
                        '--tmpfs', '/var/lib/postgresql/data:rw', '-p', '127.0.0.1::5432',
                        '-e', 'POSTGRES_DB=summary6_smoke', '-e', 'POSTGRES_PASSWORD='+password,
                        'timescale/timescaledb:2.28.2-pg16'], check=True, capture_output=True)
        port = subprocess.check_output(['docker', 'port', name, '5432/tcp'], text=True).strip().split(':')[-1]
        database = f'postgresql://postgres:{password}@127.0.0.1:{port}/summary6_smoke'
        for _ in range(60):
            try:
                conn = psycopg2.connect(database); break
            except psycopg2.Error:
                time.sleep(.5)
        else:
            raise RuntimeError('temporary_database_not_ready')
        with conn:
            with conn.cursor() as cur:
                cur.execute((ROOT/'db/init.sql').read_text())
                for migration in sorted((ROOT/'db/migrations').glob('*.sql')):
                    cur.execute(migration.read_text())
                cur.execute("INSERT INTO sites(name) VALUES ('Summary6 synthetic smoke') RETURNING id")
                site = cur.fetchone()[0]
        os.environ.update(API_DATABASE_URL=database, APP_ENV='test', SESSION_SECRET=secrets.token_urlsafe(40),
                          SESSION_FAIL_OPEN='false', ALLOW_ANONYMOUS_READS='false',
                          REDIS_URL='redis://127.0.0.1:0/0', HDT_RUNTIME_MODE='summary6_replay')
        from backend.app.auth_repository import create_user
        create_user('summary6@example.test', password, 'Summary6 smoke', 'viewer', [site])
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); api_port = sock.getsockname()[1]
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app.main:app', '--workers', '1', '--host', '127.0.0.1', '--port', str(api_port)],
                                  cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with httpx.Client(base_url=f'http://127.0.0.1:{api_port}', timeout=30) as client:
            for _ in range(60):
                try:
                    if client.get('/live').status_code == 200: break
                except httpx.ConnectError:
                    pass
                time.sleep(.2)
            base = '/api/v1/process-drift/summary6'
            assert client.get(base+'/current').status_code == 401
            response = client.post('/api/v1/auth/login', json={'email': 'summary6@example.test', 'password': password})
            assert response.status_code == 200, response.text
            current = client.get(base+'/current').json()
            assert current['replay_enabled'], current
            assert client.get(base+f'/demo-datasets?site_id={site+10000}').status_code == 403
            datasets = client.get(base+f'/demo-datasets?site_id={site}').json()
            with conn.cursor() as cur:
                cur.execute('SELECT count(*) FROM incidents'); before = cur.fetchone()[0]
            for cutoff in (59, 79, 83, 84, 399):
                response = client.post(base+'/replay', json={'site_id': site, 'expected_package_id': current['loaded_package_id'],
                    'source': {'kind': 'demo_dataset', 'dataset_id': datasets['dataset_id'], 'lot_id': 'M1-R1-L15', 'through_cycle': cutoff}})
                assert response.status_code == 200, response.text
                result = response.json()
                assert result['input_count'] == cutoff+1
                assert result['latest']['status'] == ('abstained' if cutoff < 84 else 'available')
                print(cutoff, result['latest']['status'], result['latest']['decision_score'])
            with conn.cursor() as cur:
                cur.execute('SELECT count(*) FROM incidents'); assert cur.fetchone()[0] == before
            print('PASS real localhost HTTP / DB login / site isolation / approved package / cutoffs / no incident writes')
    finally:
        try:
            stop_server(server)
        finally:
            try:
                if conn is not None:
                    conn.close()
            finally:
                if attempted:
                    remove_owned_container(name, owner)


if __name__ == '__main__':
    run()

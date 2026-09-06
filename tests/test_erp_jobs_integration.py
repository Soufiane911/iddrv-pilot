"""Authenticated upload→preview→confirmation→worker on an explicitly isolated DB.

No truncation or production credentials. Each invocation creates a synthetic site.
"""
import os
from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4
from urllib.parse import urlparse

import pytest
import psycopg2
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import Identity, create_session_token
from backend.app.api import erp_imports
from ingest.erp_import_jobs import process_approved_erp_import
from test_erp_reader import workbook, row


@pytest.fixture
def job_site(monkeypatch, tmp_path):
    url = os.getenv('ERP_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Dedicated ERP_TEST_DATABASE_URL not supplied')
    parsed = urlparse(url)
    assert parsed.hostname in {'db', 'localhost', '127.0.0.1'} and parsed.path == '/iddrv_test'
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO sites(name,timezone) VALUES (%s,'Europe/Paris') RETURNING id", (f'Upload synthetic {uuid4()}',))
        site = cur.fetchone()[0]
        cur.execute("INSERT INTO users(email,password_hash,display_name) VALUES (%s,'unusable-test-hash','Synthetic') RETURNING id", (f'{uuid4()}@example.test',))
        user = str(cur.fetchone()[0])
        cur.execute("INSERT INTO user_site_roles(user_id,site_id,role) VALUES (%s,%s,'supervisor')", (user, site))
    @contextmanager
    def connection():
        conn = psycopg2.connect(url)
        try: yield conn
        finally: conn.close()
    monkeypatch.setattr('backend.app.erp_import_repository.get_connection', connection)
    monkeypatch.setattr('backend.app.order_repository.get_connection', connection)
    monkeypatch.setattr('ingest.erp_import_jobs.worker_database_url', lambda: url)
    monkeypatch.setattr(erp_imports, 'UPLOAD_ROOT', tmp_path / 'uploads')
    token, _ = create_session_token(Identity(user, 'test@example.test', 'Test', 'supervisor', (site,)))
    return site, {'Authorization': f'Bearer {token}'}, url


def test_two_uploads_correction_replay_and_calendar_conflict(job_site, tmp_path):
    site, headers, url = job_site
    client = TestClient(app)
    def upload(rows):
        path = workbook(tmp_path, rows)
        response = client.post(f'/api/v1/sites/{site}/erp-imports', headers=headers, files={'file': ('teams.xlsx', path.read_bytes())})
        assert response.status_code == 202, response.text
        return response.json()['id']
    def preview(import_id, refresh=False):
        response = client.get(f'/api/v1/erp-imports/{import_id}/preview', headers=headers)
        if refresh or response.json().get('preview_version') == 0:
            response = client.post(f'/api/v1/erp-imports/{import_id}/preview/refresh', headers=headers)
        assert response.status_code == 200, response.text
        return response.json()
    def confirm(import_id, data):
        return client.post(f'/api/v1/erp-imports/{import_id}/confirm', headers=headers, json={'preview_version': data['preview_version'], 'create_machine_refs': data['new_machine_refs'], 'replacements': []})
    first = upload([row(), row(**{'1': 2, '0': datetime(2026, 9, 5, 13)})])
    first_preview = preview(first)
    assert first_preview['new_machine_refs'] == ['606']
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM machines WHERE site_id=%s', (site,))
        assert cur.fetchone()[0] == 0
    assert confirm(first, first_preview).status_code == 202
    assert confirm(first, first_preview).json()['id'] == first
    committed = process_approved_erp_import(first)
    assert committed.created == 2 and len(committed.new_machine_ids) == 1
    assert process_approved_erp_import(first) == committed
    # A missing team in the next file is not deleted.
    second = upload([row(**{'6': 752, '7': 48})])
    second_preview = preview(second)
    assert second_preview['counts']['revised'] == 1
    assert confirm(second, second_preview).status_code == 202
    assert process_approved_erp_import(second).revised == 1
    replay = upload([row()])
    replay_preview = preview(replay)
    assert replay_preview['items'][0]['historical_replay'] is True
    assert replay_preview['counts']['unchanged'] == 1
    assert confirm(replay, replay_preview).status_code == 202
    assert process_approved_erp_import(replay).unchanged == 1
    pending = upload([row(**{'6': 744, '7': 56})])
    pending_preview = preview(pending)
    calendar = {'timezone': 'Europe/Paris', 'valid_from': '2026-01-01', 'expected_version': 0,
                'shifts': [{'number': 1, 'start': '05:00', 'end': '13:00'}]}
    assert client.put(f'/api/v1/sites/{site}/shift-calendar', headers=headers, json=calendar).status_code == 200
    assert confirm(pending, pending_preview).status_code == 409
    refreshed = preview(pending, True)
    assert refreshed['preview_version'] == 2 and refreshed['calendar_version'] == 1
    assert confirm(pending, refreshed).status_code == 202
    # A change after confirmation is checked again by the worker.
    calendar['expected_version'] = 1
    calendar['shifts'][0]['end'] = '14:00'
    assert client.put(f'/api/v1/sites/{site}/shift-calendar', headers=headers, json=calendar).status_code == 200
    from ingest.erp_repository import ERPConflict
    with pytest.raises(ERPConflict, match='preview_stale'):
        process_approved_erp_import(pending)
    assert preview(pending)['state'] == 'failed'
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM erp_declarations WHERE site_id=%s', (site,))
        assert cur.fetchone()[0] == 2
        cur.execute('SELECT count(*) FROM erp_declaration_revisions WHERE site_id=%s', (site,))
        assert cur.fetchone()[0] == 3
        cur.execute('SELECT count(*) FROM machines WHERE site_id=%s', (site,))
        assert cur.fetchone()[0] == 1


def test_explicit_identity_replacement_and_cross_site_rejection(job_site, tmp_path):
    from psycopg2.extras import RealDictCursor
    site, headers, url = job_site
    client = TestClient(app)
    def prepare(values):
        path = workbook(tmp_path, values)
        result = client.post(f'/api/v1/sites/{site}/erp-imports', headers=headers, files={'file': ('synthetic.xlsx', path.read_bytes())})
        assert result.status_code == 202
        import_id = result.json()['id']
        response = client.post(f'/api/v1/erp-imports/{import_id}/preview/refresh', headers=headers)
        assert response.status_code == 200, response.text
        return import_id, response.json()
    initial, initial_preview = prepare([row()])
    body = {'preview_version': 1, 'create_machine_refs': ['606'], 'replacements': []}
    assert client.post(f'/api/v1/erp-imports/{initial}/confirm', headers=headers, json=body).status_code == 202
    process_approved_erp_import(initial)
    changed, changed_preview = prepare([row(**{'4': 'Production corrigée'})])
    candidate = changed_preview['items'][0]['identity_candidates'][0]
    base = {'preview_version': 1, 'create_machine_refs': [], 'replacements': []}
    path = f'/api/v1/erp-imports/{changed}/confirm'
    assert client.post(path, headers=headers, json=base).status_code == 409
    replacement = {'source_row': 12, **candidate}
    for invalid in [
        [{**replacement, 'declaration_id': str(uuid4())}],
        [{**replacement, 'expected_revision': 99}],
        [replacement, replacement],
    ]:
        assert client.post(path, headers=headers, json={**base, 'replacements': invalid}).status_code == 409
    assert client.post(path, headers=headers, json={**base, 'replacements': [replacement]}).status_code == 202
    assert process_approved_erp_import(changed).created == 1
    with psycopg2.connect(url) as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT superseded_by,current_revision_id FROM erp_declarations WHERE site_id=%s AND id=%s', (site, candidate['declaration_id']))
        assert cur.fetchone()['superseded_by'] is not None
        cur.execute('SELECT count(*) FROM erp_declarations WHERE site_id=%s AND superseded_by IS NULL', (site,))
        assert cur.fetchone()['count'] == 1
        # Referential provenance must reject a declaration from another site/OF.
        cur.execute('SAVEPOINT provenance_test')
        cur.execute('SELECT id,passport_id,declaration_id FROM erp_declaration_revisions WHERE site_id=%s LIMIT 1', (site,))
        revision = cur.fetchone()
        with pytest.raises(psycopg2.IntegrityError):
            cur.execute('''INSERT INTO production_order_revisions(site_id,production_order_id,passport_id,declaration_revision_id,
                           recorded_at,values,content_hash) VALUES (%s,'WRONG-ORDER',%s,%s,now(),'{}','synthetic-invalid')''', (site, revision['passport_id'], revision['id']))
        cur.execute('ROLLBACK TO SAVEPOINT provenance_test')


@pytest.mark.parametrize('state', ['uploaded', 'profiling'])
def test_viewer_reads_unprofiled_request_without_database_mutation(job_site, tmp_path, state):
    site, writer_headers, url = job_site
    client = TestClient(app)
    path = workbook(tmp_path, [row()])
    response = client.post(f'/api/v1/sites/{site}/erp-imports', headers=writer_headers, files={'file': ('unprofiled.xlsx', path.read_bytes())})
    assert response.status_code == 202
    import_id = response.json()['id']
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute('UPDATE erp_import_requests SET state=%s WHERE id=%s', (state, import_id))
        cur.execute('SELECT state,preview_version,preview,choices FROM erp_import_requests WHERE id=%s', (import_id,))
        before = cur.fetchone()
    token, _ = create_session_token(Identity(str(uuid4()), 'viewer@example.test', 'Viewer', 'viewer', (site,)))
    viewer_headers = {'Authorization': f'Bearer {token}'}
    preview_path = f'/api/v1/erp-imports/{import_id}/preview'
    read = client.get(preview_path, headers=viewer_headers)
    assert read.status_code == 200
    assert read.json()['state'] == state and read.json()['preview_version'] == 0
    assert read.json()['items'] == []
    assert client.get(preview_path + '?refresh=true', headers=viewer_headers).status_code == 403
    assert client.post(preview_path + '/refresh', headers=viewer_headers).status_code == 403
    assert client.put(preview_path, headers=viewer_headers, json={}).status_code == 403
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute('SELECT state,preview_version,preview,choices FROM erp_import_requests WHERE id=%s', (import_id,))
        assert cur.fetchone() == before
    # A writer can explicitly prepare the same request.
    prepared = client.put(preview_path, headers=writer_headers, json={})
    assert prepared.status_code == 200
    assert prepared.json()['preview_version'] == 1

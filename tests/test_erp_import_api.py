from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
from openpyxl import Workbook
import pytest

from backend.app.main import app
from backend.app.api import erp_imports
from backend.app.security import Identity, create_session_token

client = TestClient(app)


def headers(role='analyst', site=1):
    token, _ = create_session_token(Identity(str(uuid4()), 'test@example.com', 'Test', role, (site,)))
    return {'Authorization': f'Bearer {token}'}


def xlsx():
    stream = BytesIO()
    Workbook().save(stream)
    return stream.getvalue()


def test_upload_requires_authentication_and_site_writer():
    assert client.post('/api/v1/sites/1/erp-imports', files={'file': ('test.xlsx', xlsx())}).status_code == 401
    assert client.post('/api/v1/sites/1/erp-imports', headers=headers('viewer'), files={'file': ('test.xlsx', xlsx())}).status_code == 403
    assert client.post('/api/v1/sites/2/erp-imports', headers=headers(), files={'file': ('test.xlsx', xlsx())}).status_code == 404


def test_upload_validates_actual_xlsx_and_limits(monkeypatch, tmp_path):
    monkeypatch.setattr(erp_imports, 'UPLOAD_ROOT', tmp_path)
    monkeypatch.setattr(erp_imports, 'create_request', lambda **kwargs: {'id': str(uuid4()), 'state': 'uploaded'})
    assert client.post('/api/v1/sites/1/erp-imports', headers=headers(), files={'file': ('test.csv', b'x')}).status_code == 415
    assert client.post('/api/v1/sites/1/erp-imports', headers=headers(), files={'file': ('test.xlsx', b'not a workbook')}).status_code == 415
    monkeypatch.setattr(erp_imports, 'MAX_COMPRESSED', 10)
    assert client.post('/api/v1/sites/1/erp-imports', headers=headers(), files={'file': ('test.xlsx', xlsx())}).status_code == 413
    assert not list(tmp_path.iterdir())


def test_preview_other_site_is_hidden(monkeypatch):
    monkeypatch.setattr(erp_imports, 'get_request', lambda value: {'site_id': 2})
    assert client.get(f'/api/v1/erp-imports/{uuid4()}/preview', headers=headers()).status_code == 404


def test_confirm_forbids_viewer_and_returns_conflict(monkeypatch):
    monkeypatch.setattr(erp_imports, 'get_request', lambda value: {'site_id': 1})
    body = {'preview_version': 1, 'create_machine_refs': [], 'replacements': []}
    path = f'/api/v1/erp-imports/{uuid4()}/confirm'
    assert client.post(path, headers=headers('viewer'), json=body).status_code == 403
    def conflict(*args, **kwargs):
        raise erp_imports.ERPConflict('preview_stale')
    monkeypatch.setattr(erp_imports, 'confirm_request', conflict)
    assert client.post(path, headers=headers(), json=body).status_code == 409


def test_expanded_archive_limit_is_checked_before_profiling(monkeypatch, tmp_path):
    monkeypatch.setattr(erp_imports, 'UPLOAD_ROOT', tmp_path)
    monkeypatch.setattr(erp_imports, 'MAX_EXPANDED', 10)
    response = client.post('/api/v1/sites/1/erp-imports', headers=headers(), files={'file': ('test.xlsx', xlsx())})
    assert response.status_code == 413
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('state,version', [('uploaded', 0), ('profiling', 0), ('preview_ready', 1)])
def test_viewer_preview_read_never_profiles_or_refreshes(monkeypatch, state, version):
    request = {'id': str(uuid4()), 'site_id': 1, 'state': state, 'preview_version': version,
               'preview': {'items': [], 'counts': {'created': 0, 'revised': 0, 'unchanged': 0}} if version else {}}
    monkeypatch.setattr(erp_imports, 'get_request', lambda value: request)
    def mutation(*args, **kwargs):
        pytest.fail('A viewer must never call the profiling writer')
    monkeypatch.setattr(erp_imports, 'preview_request', mutation)
    path = f"/api/v1/erp-imports/{request['id']}/preview"
    response = client.get(path, headers=headers('viewer'))
    assert response.status_code == 200
    assert response.json()['state'] == state
    assert response.json()['preview_version'] == version
    assert response.json()['items'] == []
    assert client.get(path + '?refresh=true', headers=headers('viewer')).status_code == 403
    assert client.put(path, headers=headers('viewer'), json={}).status_code == 403
    assert client.post(path + '/refresh', headers=headers('viewer')).status_code == 403


def test_preview_refresh_get_cannot_mutate_for_writer_either(monkeypatch):
    monkeypatch.setattr(erp_imports, 'get_request', lambda value: {'site_id': 1})
    assert client.get(f'/api/v1/erp-imports/{uuid4()}/preview?refresh=true', headers=headers()).status_code == 405

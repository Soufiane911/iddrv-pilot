import copy
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import app
from backend.app.security import Identity, create_session_token
from ml.hdt_registry import CATALOG_PATH, Catalog, load_catalog


def test_catalog_inventory_and_no_research_loading(monkeypatch):
    import joblib
    monkeypatch.setattr(joblib, 'load', lambda *a, **k: pytest.fail('catalog must not load pickles'))
    catalog = load_catalog()
    assert len(catalog.candidates) == 4
    assert [c.status for c in catalog.candidates] == ['executable', 'research_only', 'blocked', 'blocked']
    assert all(not c.artifact.artifact_packaged for c in catalog.candidates[1:])
    assert 'ABSENTE' in catalog.candidates[-1].scientific_status
    assert catalog.candidates[-1].evaluations[0].phase == 'development'
    root = Path(__file__).resolve().parents[1]
    for proof in [catalog.candidates[0].artifact, *catalog.candidates[0].evidence]:
        assert hashlib.sha256((root / proof.path).read_bytes()).hexdigest() == proof.sha256


@pytest.mark.parametrize('mutation', ['duplicate', 'no_default', 'two_defaults', 'status', 'sha', 'absolute', 'traversal', 'backslash', 'packaged', 'executable', 'identity_sha'])
def test_invalid_catalog_fails_closed(mutation):
    data = json.loads(CATALOG_PATH.read_text())
    candidate = data['candidates'][1]
    if mutation == 'duplicate': data['candidates'].append(copy.deepcopy(candidate))
    elif mutation == 'no_default': data['candidates'][0]['default'] = False
    elif mutation == 'two_defaults': candidate['default'] = True
    elif mutation == 'status': candidate['status'] = 'promoted'
    elif mutation == 'sha': candidate['artifact']['sha256'] = 'bad'
    elif mutation == 'absolute': candidate['artifact']['path'] = '/Users/private/model.joblib'
    elif mutation == 'traversal': candidate['evidence'][0]['path'] = 'output/../secret'
    elif mutation == 'backslash': candidate['evidence'][0]['path'] = 'output/secret\\file'
    elif mutation == 'packaged': candidate['artifact']['artifact_packaged'] = True
    elif mutation == 'executable': candidate['status'] = 'executable'
    elif mutation == 'identity_sha': candidate['artifact']['sha256'] = 'a' * 64
    with pytest.raises(ValidationError): Catalog.model_validate(data)


client = TestClient(app)
def headers(role):
    token, _ = create_session_token(Identity('u1', 'u@test', 'User', role, (1,), session_id='sid-1'))
    return {'Authorization': f'Bearer {token}'}


def test_catalog_authentication():
    assert client.get('/api/v1/process-drift/candidates').status_code == 401
    assert client.get('/api/v1/process-drift/candidates', headers={'Authorization': 'Bearer invalid'}).status_code == 401
    assert client.get('/api/v1/process-drift/candidates', headers=headers('unknown')).status_code == 401


@pytest.mark.parametrize('role', ['viewer', 'analyst', 'supervisor', 'admin'])
def test_catalog_authorized_roles(role, monkeypatch):
    from backend.app.api import process_drift
    monkeypatch.setattr(process_drift, '_model_artifact', lambda: pytest.fail('no runtime model access'))
    response = client.get('/api/v1/process-drift/candidates', headers=headers(role))
    assert response.status_code == 200
    assert response.json() == load_catalog().model_dump()
    assert '/Users/' not in response.text


def test_catalog_failure_does_not_leak_paths(monkeypatch):
    from backend.app.api import process_drift
    def fail(): raise ValueError('/Users/private/secret')
    monkeypatch.setattr(process_drift, 'load_catalog', fail)
    response = client.get('/api/v1/process-drift/candidates', headers=headers('viewer'))
    assert response.status_code == 503
    assert 'private' not in response.text

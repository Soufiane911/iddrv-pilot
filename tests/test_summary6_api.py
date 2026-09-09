"""TestClient contracts; auth session repository is stubbed, not a real DB smoke."""
import os
from unittest.mock import Mock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app.api.summary6 import router
from backend.app.api.process_drift import router as legacy
from backend.app.security import Identity, create_session_token
from backend.app.services import summary6 as service

PRODUCTION_DATA = service.DATA
PRODUCTION_DATA_PIN = service.MANIFEST_SHA


@pytest.fixture
def client(monkeypatch, summary6_data):
    monkeypatch.setenv('HDT_RUNTIME_MODE', 'summary6_replay')
    monkeypatch.setattr('backend.app.auth_repository.session_is_active', lambda *a: True)
    app = FastAPI()
    from backend.app.middleware import RequestContextMiddleware
    from backend.app.errors import validation_exception_handler, http_exception_handler, unhandled_exception_handler
    from fastapi import HTTPException
    from fastapi.exceptions import RequestValidationError
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(router)
    app.include_router(legacy)
    with TestClient(app) as c:
        yield c


def headers():
    token, _ = create_session_token(Identity('test', 'test@local', 'Test', 'viewer', (7,)))
    return {'Authorization': 'Bearer '+token}


def body(cutoff=84):
    return {'site_id': 7, 'expected_package_id': service.PACKAGE_ID,
            'source': {'kind': 'demo_dataset', 'dataset_id': 'synthetic-61007-l15-v1',
                       'lot_id': 'M1-R1-L15', 'through_cycle': cutoff}}


BASE = '/api/v1/process-drift/summary6'


def test_auth_site(client):
    for path in ['/current', '/demo-datasets?site_id=7']:
        assert client.get(BASE+path).status_code == 401
    assert client.post(BASE+'/replay', json=body()).status_code == 401
    assert client.get(BASE+'/demo-datasets?site_id=8', headers=headers()).status_code == 403
    b = body(); b['site_id'] = 8
    assert client.post(BASE+'/replay', json=b, headers=headers()).status_code == 403
    assert client.get(BASE+'/demo-datasets?site_id=7', headers=headers()).status_code == 200


@pytest.mark.parametrize('change', [lambda b: b.update(model_params={}), lambda b: b['source'].update(path='/tmp/a'),
    lambda b: b['source'].update(kind='provided_run'), lambda b: b['source'].update(through_cycle=400),
    lambda b: b['source'].update(through_cycle=True), lambda b: b.update(site_id='7')])
def test_strict(client, change):
    b = body(); change(b)
    assert client.post(BASE+'/replay', json=b, headers=headers()).status_code == 422


def test_unavailable_and_no_pickle(client, monkeypatch, tmp_path):
    (tmp_path/'manifest.json').write_text('{}')
    monkeypatch.setenv('SUMMARY6_PACKAGE_DIR', str(tmp_path))
    monkeypatch.setenv('SUMMARY6_MANIFEST_SHA256', '0'*64)
    loader = Mock(side_effect=AssertionError('must not deserialize'))
    monkeypatch.setattr('joblib.load', loader)
    r = client.post(BASE+'/replay', json=body(), headers=headers())
    assert r.status_code == 503 and str(tmp_path) not in r.text
    loader.assert_not_called()
    state = client.get(BASE+'/current', headers=headers()).json()
    assert state['loaded_package_id'] is None and not state['replay_enabled'] and not state['live_enabled']


def test_identity_and_profile(client, monkeypatch):
    monkeypatch.setattr(service, 'package', lambda: type('P', (), {'runtime_id': 'different'})())
    assert client.post(BASE+'/replay', json=body(), headers=headers()).status_code == 409
    monkeypatch.setenv('HDT_RUNTIME_MODE', 'historical')
    assert client.post(BASE+'/replay', json=body(), headers=headers()).status_code == 409


def test_historical_post_guard_and_rollback(client, monkeypatch):
    from backend.app.api import process_drift
    from types import SimpleNamespace
    scoring = Mock(return_value=SimpleNamespace(status='scored', model_version='hdt-process-drift-iforest-v1',
        score=0.1, threshold=0.5, horizon_cycles=20, signals=[]))
    monkeypatch.setattr('backend.app.services.process_drift.score_history', scoring)
    payload = {'site_id': 7, 'cycles': [{'timestamp': f'2025-01-01T00:0{i}:00Z', 'machine_erp_ref': '152'} for i in range(3)]}
    assert client.post('/api/v1/process-drift', json=payload, headers=headers()).status_code == 409
    scoring.assert_not_called()
    monkeypatch.setenv('HDT_RUNTIME_MODE', 'historical')
    assert client.post('/api/v1/process-drift', json=payload, headers=headers()).status_code == 200
    scoring.assert_called_once()


@pytest.mark.parametrize('mode', ['summary6_replay', None, 'unknown'])
def test_worker_suspended(monkeypatch, mode):
    from ingest.telemetry.scorer import score_pending_once, claim_job, request_recalculation
    if mode is None:
        monkeypatch.delenv('HDT_RUNTIME_MODE', raising=False)
    else:
        monkeypatch.setenv('HDT_RUNTIME_MODE', mode)
    assert score_pending_once(database_url='must-not-connect') == 0
    assert claim_job(None) is None
    from ingest.telemetry.scorer import finish_job
    assert finish_job(None, None, None) is False
    with pytest.raises(ValueError, match='historical_scoring_disabled'):
        request_recalculation(None, site_id=7, prediction_id='a')
    monkeypatch.delenv('HDT_RUNTIME_MODE', raising=False)
    from ml.runtime_mode import historical_enabled
    assert not historical_enabled()
    from ml.runtime_mode import runtime_mode
    assert runtime_mode() == 'disabled'


@pytest.fixture
def api_tiny(tmp_path):
    import numpy as np
    from sklearn.ensemble import IsolationForest
    from ml.summary6.registry import write_package
    from ml.summary6 import load_package, UNITS
    models, contexts = {}, []
    for machine in ('M1', 'M2', 'M3'):
        for recipe in ('R1', 'R2'):
            key = (machine, recipe)
            models[key] = IsolationForest(n_estimators=3, max_samples=16, random_state=42).fit(
                np.random.default_rng(42).normal(size=(32, 6)))
            contexts.append({'key': list(key), 'center': [10.0 * (j + 1) for j in range(len(UNITS))],
                             'scale': [1.0] * len(UNITS), 'threshold': 0.7})
    path = tmp_path / 'api-tiny-package'
    pin = write_package(path, models=models, contexts=contexts, source_sha256='tiny-synthetic',
                        scientific_status='TINY_SYNTHETIC_TEST_ONLY', provenance={})
    return load_package(path, expected_manifest_sha256=pin, allow_test_package=True), pin


def test_synthetic_package_prefixes(client, monkeypatch, api_tiny):
    """Real scorer and gzip/JSON parser with tiny test-only forest, not approval evidence."""
    loaded, pin = api_tiny
    monkeypatch.setattr(service, 'PACKAGE_ID', loaded.runtime_id)
    monkeypatch.setattr(service, 'package', lambda: loaded)
    monkeypatch.setenv('SUMMARY6_MANIFEST_SHA256', pin)
    previous = []
    for cutoff in (59, 79, 83, 84, 399):
        response = client.post(BASE + '/replay', json=body(cutoff), headers=headers())
        assert response.status_code == 200, response.text
        value = response.json()
        assert value['input_count'] == cutoff + 1
        assert value['series'][:len(previous)] == previous
        previous = value['series']
        assert value['latest']['status'] == ('abstained' if cutoff < 84 else 'available')
        assert value['signals'] == [] and value['live_enabled'] is False
    for lot in service.catalog()['lots']:
        payload = body(84)
        payload['source']['lot_id'] = lot['lot_id']
        response = client.post(BASE + '/replay', json=payload, headers=headers())
        assert response.status_code == 200
        assert response.json()['latest']['status'] == 'available'


def test_real_package_prefixes(client, monkeypatch):
    path = os.getenv('SUMMARY6_TEST_PACKAGE')
    if not path:
        pytest.skip('private package not configured')
    from pathlib import Path
    monkeypatch.setattr(service, 'DATA', Path(os.getenv('SUMMARY6_TEST_DATA_DIR', str(PRODUCTION_DATA))))
    monkeypatch.setattr(service, 'MANIFEST_SHA', PRODUCTION_DATA_PIN)
    monkeypatch.setenv('SUMMARY6_PACKAGE_DIR', path)
    monkeypatch.setenv('SUMMARY6_MANIFEST_SHA256', os.environ['SUMMARY6_TEST_MANIFEST_SHA256'])
    previous = []
    for cutoff in (59, 79, 83, 84, 399):
        r = client.post(BASE+'/replay', json=body(cutoff), headers=headers())
        assert r.status_code == 200, r.text
        value = r.json()
        assert value['input_count'] == cutoff+1
        assert value['package_id'] == service.PACKAGE_ID
        assert value['series'][:len(previous)] == previous
        previous = value['series']
        assert value['latest']['status'] == ('abstained' if cutoff < 84 else 'available')
        if cutoff < 84:
            assert value['latest']['alert'] is None
    for lot in service.catalog()['lots']:
        b = body(84); b['source']['lot_id'] = lot['lot_id']
        assert client.post(BASE+'/replay', json=b, headers=headers()).status_code == 200


def test_demo_whitelist(summary6_data):
    import gzip, json, hashlib
    from ml.summary6 import UNITS
    for lot in service.catalog()['lots']:
        raw = (service.DATA/(lot['lot_id']+'.jsonl.gz')).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == lot['sha256']
        records = [json.loads(line) for line in gzip.decompress(raw).splitlines()]
        assert [r['cycle']['cycle_counter'] for r in records] == list(range(400))
        for record in records:
            assert set(record) == {'timestamp', 'cycle'}
            assert set(record['cycle']) == {'source_id', 'machine_erp_ref', 'recipe_id', 'lot_id', 'cycle_counter', 'units', 'sensors'}
            assert record['cycle']['units'] == UNITS
            assert set(record['cycle']['sensors']) == set(UNITS)

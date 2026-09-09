from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import hdt_control as hdt_api
from backend.app.api import production_planning as planning_api
from backend.app.api.hdt_control import router as hdt_router
from backend.app.api.production_planning import router as planning_router
from backend.app import hdt_control_repository, planning_repository
from backend.app.security import Identity, create_session_token


def client_for(*routers):
    app = FastAPI()
    for router in routers:
        app.include_router(router)
    return TestClient(app)


def headers(role='supervisor', sites=(1,)):
    token, _ = create_session_token(Identity('actor-1', 'actor@test', 'Actor', role, sites))
    return {'Authorization': f'Bearer {token}'}


def test_hdt_control_contract_is_site_scoped_and_preserves_blocking_reasons(monkeypatch):
    machine = {'id': 10, 'site_id': 1, 'site_lifecycle_status': 'active', 'machine_lifecycle_status': 'active'}
    monkeypatch.setattr('backend.app.api.hdt_control.local_machine', lambda machine_id: machine if machine_id == 10 else None)
    monkeypatch.setattr(hdt_api, 'get_control', lambda machine_id: {
        'machine_id': machine_id, 'desired_state': 'active', 'effective_state': 'blocked',
        'blocking_reasons': ['source_not_ready', 'model_profile_not_enabled'], 'model_profile': None,
    })
    response = client_for(hdt_router).get('/api/v1/machines/10/hdt-control', headers=headers('viewer'))
    assert response.status_code == 200
    assert response.json()['blocking_reasons'] == ['source_not_ready', 'model_profile_not_enabled']
    assert client_for(hdt_router).get('/api/v1/machines/10/hdt-control', headers=headers('viewer', (2,))).status_code == 404


def test_hdt_write_requires_supervisor_or_admin(monkeypatch):
    monkeypatch.setattr('backend.app.api.hdt_control.local_machine', lambda _: {'id': 10, 'site_id': 1, 'site_lifecycle_status': 'active', 'machine_lifecycle_status': 'active'})
    called = False
    def forbidden(**kwargs):
        nonlocal called
        called = True
        return {}
    monkeypatch.setattr(hdt_api, 'set_control', forbidden)
    response = client_for(hdt_router).post('/api/v1/machines/10/hdt-control/stop', headers=headers('operator'))
    assert response.status_code == 403
    assert not called


def test_scrap_http_contract_rejects_bool_fraction_negative_and_accepts_zero_null(monkeypatch):
    work_order_id = uuid4()
    monkeypatch.setattr(planning_api.repository, 'get_work_order', lambda value: {'id': work_order_id, 'site_id': 1})
    saved = []
    monkeypatch.setattr(planning_api.repository, 'update_actual_scrap', lambda **kwargs: saved.append(kwargs) or {
        'site_id': 1, 'work_order_id': work_order_id, 'machine_id': 10,
        'actual_scrap_count': kwargs['actual_scrap_count'], 'comment': None, 'row_version': 2,
    })
    client = client_for(planning_router)
    base = {'machine_id': 10, 'row_version': 1}
    for value in (True, 1.5, -1):
        response = client.post(f'/api/v1/planning/work-orders/{work_order_id}/scrap', headers=headers('operator'), json={**base, 'actual_scrap_count': value})
        assert response.status_code == 422
    assert client.post(f'/api/v1/planning/work-orders/{work_order_id}/scrap', headers=headers('operator'), json={**base, 'actual_scrap_count': 0}).status_code == 200
    assert client.post(f'/api/v1/planning/work-orders/{work_order_id}/scrap', headers=headers('operator'), json={**base, 'actual_scrap_count': None}).status_code == 200
    assert [item['actual_scrap_count'] for item in saved] == [0, None]

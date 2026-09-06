from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api import machine_management
from test_erp_import_api import headers


def test_manual_machine_role_and_duplicate(monkeypatch):
    client = TestClient(app)
    body = {'workshop_code': 'AT-606', 'erp_ref': '606', 'name': 'Presse 606'}
    assert client.post('/api/v1/sites/1/machines', headers=headers('analyst'), json=body).status_code == 403
    monkeypatch.setattr(machine_management, 'create_machine', lambda **kwargs: None)
    assert client.post('/api/v1/sites/1/machines', headers=headers('supervisor'), json=body).status_code == 409


def test_machine_can_be_created_before_erp(monkeypatch):
    calls = []
    monkeypatch.setattr(
        machine_management,
        'create_machine',
        lambda **kwargs: calls.append(kwargs) or {
            'id': 12, 'site_id': 1, 'workshop_code': 'AT-12',
            'erp_ref': None, 'name': 'Presse 12', 'status': 'active',
        },
    )
    response = TestClient(app).post(
        '/api/v1/sites/1/machines', headers=headers('supervisor'),
        json={'workshop_code': 'AT-12', 'name': 'Presse 12'},
    )
    assert response.status_code == 201
    assert calls[0]['erp_ref'] is None
    assert TestClient(app).post(
        '/api/v1/sites/1/machines', headers=headers('supervisor'),
        json={'name': 'Sans code'},
    ).status_code == 422


def test_machine_patch_is_site_scoped_and_trims_identity(monkeypatch):
    calls = []
    monkeypatch.setattr(machine_management, 'machine_site_id', lambda machine_id: 1)
    monkeypatch.setattr(
        machine_management,
        'update_machine',
        lambda **kwargs: calls.append(kwargs) or {
            'id': kwargs['machine_id'], 'site_id': 1, 'workshop_code': 'AT-12',
            'erp_ref': 'ERP-12', 'name': 'Presse corrigée', 'status': 'active',
        },
    )
    response = TestClient(app).patch(
        '/api/v1/machines/12', headers=headers('supervisor'),
        json={'name': 'Presse corrigée', 'erp_ref': ' ERP-12 '},
    )
    assert response.status_code == 200
    assert calls[0]['erp_ref'] == 'ERP-12'


def test_machine_archive_has_rbac_and_stable_errors(monkeypatch):
    calls = []
    monkeypatch.setattr(machine_management, 'machine_site_id', lambda machine_id: 1)
    monkeypatch.setattr(machine_management, 'archive_machine', lambda machine_id: calls.append(machine_id))
    assert TestClient(app).post('/api/v1/machines/12/archive', headers=headers('analyst')).status_code == 403
    assert TestClient(app).post('/api/v1/machines/12/archive', headers=headers('supervisor')).status_code == 204
    assert calls == [12]


def test_calendar_validation_handles_team_four_and_invalid_zone():
    from backend.app.schemas import ShiftCalendarInput
    import pytest
    from pydantic import ValidationError
    value = ShiftCalendarInput(timezone='Europe/Paris', valid_from='2026-09-05', shifts=[{'number': 4, 'start': '21:00', 'end': '05:00'}])
    assert value.shifts[0].number == 4
    with pytest.raises(ValidationError):
        ShiftCalendarInput(timezone='invalid/zone', valid_from='2026-09-05', shifts=[])

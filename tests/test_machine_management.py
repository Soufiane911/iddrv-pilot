from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api import machine_management
from test_erp_import_api import headers


def test_manual_machine_role_and_duplicate(monkeypatch):
    client = TestClient(app)
    body = {'erp_ref': '606', 'name': 'Presse 606'}
    assert client.post('/api/v1/sites/1/machines', headers=headers('analyst'), json=body).status_code == 403
    monkeypatch.setattr(machine_management, 'create_machine', lambda **kwargs: None)
    assert client.post('/api/v1/sites/1/machines', headers=headers('supervisor'), json=body).status_code == 409


def test_calendar_validation_handles_team_four_and_invalid_zone():
    from backend.app.schemas import ShiftCalendarInput
    import pytest
    from pydantic import ValidationError
    value = ShiftCalendarInput(timezone='Europe/Paris', valid_from='2026-09-05', shifts=[{'number': 4, 'start': '21:00', 'end': '05:00'}])
    assert value.shifts[0].number == 4
    with pytest.raises(ValidationError):
        ShiftCalendarInput(timezone='invalid/zone', valid_from='2026-09-05', shifts=[])

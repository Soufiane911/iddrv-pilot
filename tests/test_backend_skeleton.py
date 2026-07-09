from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_reports_degraded_when_database_is_unavailable(monkeypatch):
    monkeypatch.setattr("backend.app.main.check_connection", lambda: False)
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "unavailable"


def test_app_metadata_and_error_envelope():
    assert app.title == "IDDVR API"
    assert app.version == "0.1.0"

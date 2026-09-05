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


def test_live_does_not_probe_dependencies():
    response = TestClient(app).get("/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_ready_reports_dependency_status(monkeypatch):
    monkeypatch.setattr("backend.app.main.check_connection", lambda: True)
    monkeypatch.setattr("backend.app.main.check_redis_connection", lambda: True)
    monkeypatch.setattr("backend.app.main.check_model_artifact", lambda: True)
    response = TestClient(app).get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["database"] == "ok"
    assert response.json()["redis"] == "ok"
    assert response.json()["model"] == "ok"


def test_ready_returns_503_when_dependency_is_unavailable(monkeypatch):
    monkeypatch.setattr("backend.app.main.check_connection", lambda: False)
    monkeypatch.setattr("backend.app.main.check_redis_connection", lambda: True)
    monkeypatch.setattr("backend.app.main.check_model_artifact", lambda: True)
    response = TestClient(app).get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["database"] == "unavailable"

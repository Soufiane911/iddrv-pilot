from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import Identity, create_session_token, hash_password, verify_password


client = TestClient(app)


def bearer(identity: Identity) -> dict[str, str]:
    token, _ = create_session_token(identity)
    return {"Authorization": f"Bearer {token}"}


def test_password_hash_is_argon2id_or_scrypt_and_verifies():
    encoded = hash_password("correct horse battery staple")
    assert encoded.startswith(("$argon2id$", "scrypt$"))
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_auth_me_uses_signed_server_identity():
    identity = Identity("u-1", "analyst@example.test", "Analyst", "analyst", (1,))
    response = client.get("/api/v1/auth/me", headers=bearer(identity))
    assert response.status_code == 200
    assert response.json()["role"] == "analyst"
    assert response.json()["site_ids"] == [1]


def test_viewer_cannot_start_investigation():
    identity = Identity("u-2", "viewer@example.test", "Viewer", "viewer", (1,))
    response = client.post("/api/v1/incidents/00000000-0000-0000-0000-000000000001/investigations", headers=bearer(identity))
    assert response.status_code == 403
    assert response.json()["error"]["message"] == "insufficient_role"


def test_site_scope_is_enforced_before_query(monkeypatch):
    monkeypatch.setattr("backend.app.api.sites.list_machines", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("query should not run")))
    identity = Identity("u-3", "viewer@example.test", "Viewer", "viewer", (2,))
    response = client.get("/api/v1/sites/1/machines", headers=bearer(identity))
    assert response.status_code == 404


def test_timeline_contract_is_bounded_and_uses_aggregates(monkeypatch):
    monkeypatch.setattr("backend.app.api.machines.get_machine", lambda machine_id: {"id": machine_id, "site_id": 1, "name": "Presse"})
    monkeypatch.setattr("backend.app.api.machines.timeline", lambda *args: [{
        "bucket": datetime(2025, 2, 1, tzinfo=timezone.utc), "cycle_count": 10,
        "avg_cycle_time_s": 3.2, "scrap_rate": 0.1, "avg_zone2_temperature_c": 200.0,
        "production_order_id": "OF-1",
    }])
    response = client.get("/api/v1/machines/7/timeline?from=2025-02-01T00:00:00Z&to=2025-02-01T01:00:00Z&bucket=hour")
    assert response.status_code == 200
    assert response.json()["items"][0]["cycle_count"] == 10
    assert "time" not in response.json()["items"][0]


def test_timeline_requires_historical_window():
    response = client.get("/api/v1/machines/7/timeline?bucket=hour")
    assert response.status_code == 422

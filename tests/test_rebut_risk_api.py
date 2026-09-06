from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import Identity, create_session_token


def _headers(identity: Identity) -> dict[str, str]:
    token, _ = create_session_token(identity)
    return {"Authorization": f"Bearer {token}"}


def _payload(site_id: int = 1) -> dict[str, object]:
    return {
        "site_id": site_id,
        "machine_erp_ref": "1003",
        "cycle_time_s": 30.0,
        "dosing_time_s": 7.2,
        "injection_time_s": 2.9,
        "cooling_time_s": 15.0,
        "cushion_mm": 4.5,
        "switchover_position_mm": 17.0,
        "switchover_pressure_bar": 165.0,
        "peak_pressure_bar": 840.0,
        "clamp_force_kn": 1450.0,
        "mold_temperature_c": 54.0,
        "barrel_temp_zone1_c": 203.0,
        "barrel_temp_zone2_c": 224.0,
        "barrel_temp_zone3_c": 214.0,
        "oil_temperature_c": 51.0,
        "energy_kwh": 1.0,
        "previous_scrap_flag": 0,
        "rolling_scrap_rate_20": 0.02,
    }


def test_scrap_risk_endpoint_returns_versioned_prediction():
    client = TestClient(app)
    identity = Identity("u1", "u@test", "User", "viewer", (1,), session_id="sid-1")
    response = client.post("/api/v1/scrap-risk", headers=_headers(identity), json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["model_version"] == "rebut-risk-logistic-v1"
    assert 0 <= body["risk_probability"] <= 1
    assert isinstance(body["predicted_scrap"], bool)
    assert 0 < body["threshold"] < 1


def test_scrap_risk_endpoint_enforces_site_scope():
    client = TestClient(app)
    identity = Identity("u1", "u@test", "User", "viewer", (2,), session_id="sid-1")
    response = client.post("/api/v1/scrap-risk", headers=_headers(identity), json=_payload(site_id=1))

    assert response.status_code == 404

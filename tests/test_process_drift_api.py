from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.api import process_drift
from backend.app.main import app
from backend.app.schemas import ProcessDriftRequest, ProcessDriftResponse
from backend.app.security import Identity, create_session_token


client = TestClient(app)


def _headers(identity: Identity) -> dict[str, str]:
    token, _ = create_session_token(identity)
    return {"Authorization": f"Bearer {token}"}


def _cycle(index: int, machine_erp_ref: str = "1003") -> dict[str, object]:
    return {
        "timestamp": (datetime(2025, 2, 17, tzinfo=timezone.utc) + timedelta(minutes=index)).isoformat(),
        "machine_erp_ref": machine_erp_ref,
        "cycle_time_s": 30.0 + index * 0.2,
        "dosing_time_s": 7.2 + index * 0.02,
        "injection_time_s": 2.9 + index * 0.03,
        "cooling_time_s": 15.0 + index * 0.1,
        "cushion_mm": 4.5 + index * 0.01,
        "switchover_position_mm": 17.0 + index * 0.02,
        "switchover_pressure_bar": 165.0 + index * 0.2,
        "peak_pressure_bar": 840.0 + index * 1.5,
        "clamp_force_kn": 1450.0 + index,
        "mold_temperature_c": 54.0 + index * 0.1,
        "barrel_temp_zone1_c": 203.0 + index * 0.1,
        "barrel_temp_zone2_c": 224.0 + index * 0.2,
        "barrel_temp_zone3_c": 214.0 + index * 0.1,
        "oil_temperature_c": 51.0 + index * 0.1,
        "energy_kwh": 1.0 + index * 0.01,
    }


def _payload(site_id: int = 1, machines: tuple[str, ...] = ("1003", "1003", "1003")) -> dict[str, object]:
    return {
        "site_id": site_id,
        "cycles": [_cycle(index, machine) for index, machine in enumerate(machines)],
    }


def _viewer(site_ids: tuple[int, ...] = (1,)) -> Identity:
    return Identity("u1", "u@test", "User", "viewer", site_ids, session_id="sid-1")


@pytest.fixture(autouse=True)
def _clear_process_drift_model_cache():
    process_drift._model_artifact.cache_clear()
    yield
    process_drift._model_artifact.cache_clear()


def test_process_drift_pydantic_contract():
    request = ProcessDriftRequest.model_validate(_payload())
    assert request.site_id == 1
    assert len(request.cycles) == 3
    assert request.cycles[0].machine_erp_ref == "1003"

    response = ProcessDriftResponse.model_validate(
        {
            "model_version": "hdt-process-drift-iforest-v1",
            "machine_erp_ref": "1003",
            "anomaly_score": 0.42,
            "predicted_instability_next_20_cycles": False,
            "threshold": 0.5,
            "horizon_cycles": 20,
            "signals": [{"feature": "cycle_time_s_volatility_20", "volatility": 0.1}],
        }
    )
    assert response.horizon_cycles == 20
    assert response.signals[0].volatility == 0.1

    with pytest.raises(ValidationError):
        ProcessDriftResponse.model_validate(
            {
                "model_version": "hdt-process-drift-iforest-v1",
                "machine_erp_ref": "1003",
                "anomaly_score": 0.42,
                "predicted_instability_next_20_cycles": False,
                "threshold": 0.5,
                "horizon_cycles": 20,
                "signals": [{"feature": "x", "volatility": 0.1}] * 4,
            }
        )


def test_process_drift_rejects_history_shorter_than_three_cycles():
    response = client.post(
        "/api/v1/process-drift",
        headers=_headers(_viewer()),
        json=_payload(machines=("1003", "1003")),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_process_drift_rejects_mixed_machine_history_at_pydantic_boundary():
    with pytest.raises(ValidationError, match="cycles must belong to a single machine"):
        ProcessDriftRequest.model_validate(
            _payload(machines=("1003", "1003", "152"))
        )


def test_process_drift_rejects_aggregate_history_without_raw_features():
    cycles = [{
        "timestamp": (datetime(2025, 2, 17, tzinfo=timezone.utc) + timedelta(minutes=index)).isoformat(),
        "machine_erp_ref": "1003",
    } for index in range(3)]
    response = client.post(
        "/api/v1/process-drift",
        headers=_headers(_viewer()),
        json={"site_id": 1, "cycles": cycles},
    )
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "process_drift_raw_features_missing"


def test_process_drift_returns_versioned_score_response():
    response = client.post(
        "/api/v1/process-drift",
        headers=_headers(_viewer()),
        json=_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    contract = ProcessDriftResponse.model_validate(body)
    assert contract.model_version == "hdt-process-drift-iforest-v1"
    assert contract.machine_erp_ref == "1003"
    assert contract.horizon_cycles == 20
    assert contract.anomaly_score >= 0
    assert contract.threshold >= 0
    assert len(contract.signals) <= 3
    assert all(signal.volatility >= 0 for signal in contract.signals)


def test_process_drift_returns_503_when_model_is_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("PROCESS_DRIFT_MODEL_PATH", str(tmp_path / "missing.joblib"))
    process_drift._model_artifact.cache_clear()

    response = client.post(
        "/api/v1/process-drift",
        headers=_headers(_viewer()),
        json=_payload(),
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "process_drift_model_unavailable"


def test_process_drift_requires_authentication():
    response = client.post("/api/v1/process-drift", json=_payload())

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "authentication_required"


def test_process_drift_enforces_site_isolation():
    response = client.post(
        "/api/v1/process-drift",
        headers=_headers(_viewer(site_ids=(2,))),
        json=_payload(site_id=1),
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "resource_not_found"

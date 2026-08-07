"""Contrat HTTP des cycles machine bruts.

Ces tests restent unitaires : la lecture des cycles est remplacée par un lecteur
mémoire afin de ne pas exiger PostgreSQL. Le lecteur ``raw_machine_cycles`` est
le seam attendu par l'implémentation de l'endpoint.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import AliasChoices, Field, create_model

from backend.app.main import app
from backend.app.security import Identity, create_session_token
from ml.process_drift import RAW_NUMERIC_FEATURES


client = TestClient(app)
MACHINE_ID = 7
SITE_ID = 1
AS_OF = datetime(2025, 2, 17, 12, 10, tzinfo=timezone.utc)
AS_OF_QUERY = AS_OF.isoformat().replace("+00:00", "Z")


def _headers(identity: Identity) -> dict[str, str]:
    token, _ = create_session_token(identity)
    return {"Authorization": f"Bearer {token}"}


def _machine(site_id: int = SITE_ID) -> dict[str, Any]:
    return {"id": MACHINE_ID, "site_id": site_id, "erp_ref": "1003", "name": "Presse 1003"}


def _cycle(index: int, *, at: datetime | None = None) -> dict[str, Any]:
    timestamp = at or (AS_OF - timedelta(minutes=index))
    values = {
        "cycle_time_s": 30.0 + index * 0.1,
        "dosing_time_s": 7.0 + index * 0.01,
        "injection_time_s": 2.8 + index * 0.01,
        "cooling_time_s": 15.0 + index * 0.1,
        "cushion_mm": 4.0 + index * 0.01,
        "switchover_position_mm": 17.0 + index * 0.02,
        "switchover_pressure_bar": 160.0 + index,
        "peak_pressure_bar": 840.0 + index,
        "clamp_force_kn": 1450.0 + index,
        "mold_temperature_c": 54.0 + index * 0.1,
        "barrel_temp_zone1_c": 203.0 + index * 0.1,
        "barrel_temp_zone2_c": 224.0 + index * 0.1,
        "barrel_temp_zone3_c": 214.0 + index * 0.1,
        "oil_temperature_c": 51.0 + index * 0.1,
        "energy_kwh": 1.0 + index * 0.01,
    }
    return {
        "time": timestamp.isoformat(),
        "machine_id": MACHINE_ID,
        "machine_erp_ref": "1003",
        **values,
    }


# The alias accepts the database-facing ``time`` name as well as ``timestamp``
# used by ProcessDriftCycle. The response must still contain every HDT input.
MachineCycleContract = create_model(
    "MachineCycleContract",
    timestamp=(datetime, Field(validation_alias=AliasChoices("timestamp", "time"))),
    machine_erp_ref=(str, Field(min_length=1)),
    **{name: (float | None, None) for name in RAW_NUMERIC_FEATURES},
)
MachineCyclesResponseContract = create_model(
    "MachineCyclesResponseContract",
    items=(list[MachineCycleContract], ...),
    next_cursor=(str | None, None),
)


def _items(response) -> list[dict[str, Any]]:
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, dict)
    assert "items" in body
    return body["items"]


def _install_memory_reader(monkeypatch, rows: list[dict[str, Any]], calls: list[dict[str, Any]]):
    """Install the DB-free repository seam under the likely import aliases."""

    def reader(*args, **kwargs):
        machine_id = kwargs.get("machine_id", args[0] if args else None)
        as_of = kwargs.get("as_of", kwargs.get("to", kwargs.get("end")))
        if as_of is None and len(args) > 1:
            as_of = args[1]
        limit = kwargs.get("limit", args[2] if len(args) > 2 else 20)
        calls.append({"machine_id": machine_id, "as_of": as_of, "limit": limit})
        cutoff = as_of if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
        selected = [row for row in rows if datetime.fromisoformat(row["time"]) <= cutoff]
        selected = sorted(selected, key=lambda row: row["time"])[:limit]
        return [
            {"timestamp": row["time"], **{key: value for key, value in row.items() if key not in {"time", "machine_id"}}}
            for row in selected
        ]

    # The first name is the contract seam. The aliases keep the tests useful if
    # the repository follows the existing list_* naming convention.
    for module_name in ("backend.app.api.machines", "backend.app.read_repositories"):
        for name in ("raw_machine_cycles", "raw_cycles", "list_machine_cycles", "machine_cycles"):
            monkeypatch.setattr(f"{module_name}.{name}", reader, raising=False)


def _install_machine(monkeypatch, value: dict[str, Any] | None):
    monkeypatch.setattr("backend.app.api.machines.get_machine", lambda machine_id: value, raising=False)


@pytest.fixture
def cycle_reader(monkeypatch):
    rows = [
        _cycle(3),
        _cycle(1),
        _cycle(2),
        _cycle(0, at=AS_OF + timedelta(minutes=1)),
    ]
    calls: list[dict[str, Any]] = []
    _install_machine(monkeypatch, _machine())
    _install_memory_reader(monkeypatch, rows, calls)
    return rows, calls


def test_machine_cycles_pydantic_contract_and_hdt_fields(cycle_reader):
    response = client.get(
        f"/api/v1/machines/{MACHINE_ID}/cycles?to={AS_OF_QUERY}&limit=3",
    )
    items = _items(response)
    contract = MachineCyclesResponseContract.model_validate(response.json())

    assert len(contract.items) == 3
    assert all(item.machine_erp_ref == "1003" for item in contract.items)
    for item in items:
        assert set(RAW_NUMERIC_FEATURES).issubset(item)


def test_machine_cycles_use_default_limit_and_are_chronological(cycle_reader):
    rows, calls = cycle_reader
    # More than the default window, with deliberately non-chronological input.
    rows.extend(_cycle(index + 10) for index in range(20))

    response = client.get(f"/api/v1/machines/{MACHINE_ID}/cycles?to={AS_OF_QUERY}")
    items = _items(response)

    assert len(items) == 20
    assert calls[-1]["as_of"] == AS_OF
    assert calls[-1]["limit"] == 20
    timestamps = [datetime.fromisoformat(item.get("time", item.get("timestamp"))) for item in items]
    assert timestamps == sorted(timestamps)
    assert all(timestamp <= AS_OF for timestamp in timestamps)


def test_machine_cycles_respect_requested_limit_and_ceiling(cycle_reader):
    response = client.get(f"/api/v1/machines/{MACHINE_ID}/cycles?to={AS_OF_QUERY}&limit=2")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2

    response = client.get(f"/api/v1/machines/{MACHINE_ID}/cycles?to={AS_OF_QUERY}&limit=101")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("query", ["limit=0", "limit=-1", "limit=not-a-number"])
def test_machine_cycles_reject_invalid_limits(cycle_reader, query):
    response = client.get(f"/api/v1/machines/{MACHINE_ID}/cycles?to={AS_OF_QUERY}&{query}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    "query, error_code",
    [
        (f"to={AS_OF_QUERY}&to=not-a-date", "validation_error"),
        ("to=2025-02-17T12:10:00", "http_error"),
        ("limit=20", "validation_error"),
    ],
)
def test_machine_cycles_reject_invalid_or_missing_window(cycle_reader, query, error_code):
    response = client.get(f"/api/v1/machines/{MACHINE_ID}/cycles?{query}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == error_code


def test_machine_cycles_return_404_for_unknown_machine(monkeypatch):
    _install_machine(monkeypatch, None)
    calls: list[dict[str, Any]] = []
    _install_memory_reader(monkeypatch, [], calls)

    response = client.get(f"/api/v1/machines/999/cycles?to={AS_OF_QUERY}")

    assert response.status_code == 404
    assert calls == []


def test_machine_cycles_enforce_site_isolation(monkeypatch):
    _install_machine(monkeypatch, _machine(site_id=2))
    calls: list[dict[str, Any]] = []
    _install_memory_reader(monkeypatch, [_cycle(1)], calls)
    identity = Identity("u-site-1", "viewer@example.test", "Viewer", "viewer", (1,))

    response = client.get(
        f"/api/v1/machines/{MACHINE_ID}/cycles?to={AS_OF_QUERY}",
        headers=_headers(identity),
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "resource_not_found"
    assert calls == []


def test_machine_cycles_never_use_ground_truth_json():
    """The route/repository boundary must remain independent of evaluation data."""
    from pathlib import Path

    sources = [
        Path("backend/app/api/machines.py").read_text(encoding="utf-8"),
        Path("backend/app/read_repositories.py").read_text(encoding="utf-8"),
    ]
    assert all("ground_truth.json" not in source for source in sources)

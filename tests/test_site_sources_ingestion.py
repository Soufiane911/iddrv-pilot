from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.api import cycle_ingestion
from backend.app.api.cycle_ingestion import CycleEventInput
from backend.app.source_repository import (
    EventPayloadConflict,
    SourceForbidden,
    _invalid_process_field,
    _raw_order_number,
    canonical_payload_hash,
    normalize_order_number,
)


def _client(monkeypatch):
    app = FastAPI()
    app.include_router(cycle_ingestion.router)
    return TestClient(app)


def _body(**changes):
    body = {
        "event_id": "evt-1",
        "external_machine_id": "press-a",
        "occurred_at": "2026-09-06T10:00:00Z",
        "of_number": "000042",
        "cycle_counter": 7,
        "process_parameters": {"cycle_time_s": 1.2},
    }
    body.update(changes)
    return body


def test_receipt_migration_upgrades_an_existing_table_idempotently():
    sql = open("db/migrations/021_site_sources_and_event_receipts.sql", encoding="utf-8").read()
    assert "CREATE TABLE IF NOT EXISTS cycle_event_receipts" in sql
    assert "ADD COLUMN IF NOT EXISTS source_id" in sql
    assert "ADD COLUMN IF NOT EXISTS occurred_at" in sql
    assert "cycle_event_receipts_source_site_fkey" in sql
    assert "cycle_event_receipts_source_event_key" in sql


def test_order_is_compared_without_destroying_leading_zeroes():
    value = CycleEventInput(**_body())
    assert value.work_order == "000042"
    assert normalize_order_number(" 000042 ") == "000042"
    assert normalize_order_number("42") != normalize_order_number("000042")


def test_client_cannot_choose_site_or_quality_defaults_are_invented():
    with pytest.raises(ValidationError):
        CycleEventInput(**_body(site_id=999))
    value = CycleEventInput(**_body())
    payload = value.model_dump()
    assert "good_parts" not in payload
    assert "scrap_flag" not in payload


def test_repository_keeps_raw_order_identity_and_rejects_invalid_process_values():
    payload = {'work_order': ' 000042 ', 'of_number': 'ignored'}
    assert _raw_order_number(payload) == ' 000042 '
    assert normalize_order_number(_raw_order_number(payload)) == '000042'
    assert _invalid_process_field({'process_parameters': {'cycle_time_s': 1.5}}) is None
    assert _invalid_process_field({'process_parameters': {'cycle_time_s': float('nan')}}) == 'cycle_time_s'


def test_payload_hash_is_canonical_but_detects_changes():
    assert canonical_payload_hash({"a": 1, "b": 2}) == canonical_payload_hash({"b": 2, "a": 1})
    assert canonical_payload_hash({"a": 1}) != canonical_payload_hash({"a": 2})


def test_invalid_gateway_credential_is_401(monkeypatch):
    client = _client(monkeypatch)
    response = client.post("/api/v1/ingestion/cycle-events", json=_body(), headers={"X-Source-ID": str(uuid4())})
    assert response.status_code == 401


def test_duplicate_and_payload_conflict_statuses(monkeypatch):
    source_id = uuid4()
    source = {"id": source_id, "site_id": 4, "kind": "gateway_push", "name": "gw", "status": "active"}
    monkeypatch.setattr(cycle_ingestion, "authenticate_source", lambda **_: source)
    responses = iter(
        [
            {"status_code": 201, "state": "materialized", "duplicate": False, "receipt": {"event_id": "evt-1", "source_id": source_id, "id": uuid4(), "pending_reason": None}},
            {"status_code": 200, "state": "materialized", "duplicate": True, "receipt": {"event_id": "evt-1", "source_id": source_id, "id": uuid4(), "pending_reason": None}},
        ]
    )
    monkeypatch.setattr(cycle_ingestion, "ingest_cycle_event", lambda **_: next(responses))
    client = _client(monkeypatch)
    headers = {"X-Source-ID": str(source_id), "X-Source-Credential": "one-time-secret"}
    assert client.post("/api/v1/ingestion/cycle-events", json=_body(), headers=headers).status_code == 201
    assert client.post("/api/v1/ingestion/cycle-events", json=_body(), headers=headers).status_code == 200


def test_reused_event_id_with_changed_payload_is_409(monkeypatch):
    source_id = uuid4()
    monkeypatch.setattr(
        cycle_ingestion,
        "authenticate_source",
        lambda **_: {"id": source_id, "site_id": 4, "kind": "gateway_push", "name": "gw", "status": "active"},
    )
    monkeypatch.setattr(
        cycle_ingestion,
        "ingest_cycle_event",
        lambda **_: (_ for _ in ()).throw(EventPayloadConflict("event_id_payload_mismatch")),
    )
    client = _client(monkeypatch)
    response = client.post(
        "/api/v1/ingestion/cycle-events",
        json=_body(cycle_counter=8),
        headers={"X-Source-ID": str(source_id), "X-Source-Credential": "one-time-secret"},
    )
    assert response.status_code == 409


def test_disabled_gateway_credential_is_403(monkeypatch):
    monkeypatch.setattr(
        cycle_ingestion,
        "authenticate_source",
        lambda **_: (_ for _ in ()).throw(SourceForbidden("source_not_active")),
    )
    client = _client(monkeypatch)
    response = client.post(
        "/api/v1/ingestion/cycle-events",
        json=_body(),
        headers={"X-Source-ID": str(uuid4()), "X-Source-Credential": "revoked"},
    )
    assert response.status_code == 403
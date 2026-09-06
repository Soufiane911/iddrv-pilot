"""Authenticated push endpoint for gateway cycle events."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from ..source_repository import (
    EventPayloadConflict,
    InvalidSourceCredential,
    SourceForbidden,
    authenticate_source,
    ingest_cycle_event,
)

router = APIRouter(prefix="/api/v1/ingestion", tags=["cycle-ingestion"])


class CycleEventInput(BaseModel):
    """Wire contract for one event from a site gateway.

    ``work_order`` is intentionally a string and is never stripped or cast to
    an integer.  Aliases are accepted for adapters, while the persisted raw
    payload keeps the supplied value and leading zeroes.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    event_id: str = Field(min_length=1, max_length=256)
    external_machine_id: str = Field(min_length=1, max_length=128)
    occurred_at: datetime = Field(validation_alias=AliasChoices("occurred_at", "timestamp", "cycle_at"))
    work_order: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        validation_alias=AliasChoices("work_order", "of_number", "production_order_id", "order_number", "of"),
    )
    cycle_counter: int | None = Field(default=None, ge=0)
    process_parameters: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("process_parameters", "parameters"),
    )


def _gateway_headers(request: Request) -> tuple[UUID, str]:
    source_value = request.headers.get("x-source-id") or request.headers.get("x-gateway-source-id")
    secret = (
        request.headers.get("x-source-credential")
        or request.headers.get("x-source-secret")
        or request.headers.get("x-gateway-secret")
    )
    if not secret:
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            secret = authorization[7:].strip()
    if not source_value or not secret:
        raise HTTPException(status_code=401, detail="source_credential_required")
    try:
        source_id = UUID(source_value)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid_source_credential") from None
    return source_id, secret


def _response(result: dict[str, Any]) -> JSONResponse:
    receipt = result["receipt"]
    body = {
        "event_id": receipt["event_id"],
        "source_id": receipt["source_id"],
        "receipt_id": receipt["id"],
        "state": result["state"],
        "materialized": result["state"] == "materialized",
        "duplicate": result["duplicate"],
        "pending_reason": receipt.get("pending_reason"),
    }
    return JSONResponse(status_code=result["status_code"], content=jsonable_encoder(body))


@router.post("/cycle-events")
def receive_cycle_event(payload: CycleEventInput, request: Request):
    source_id, secret = _gateway_headers(request)
    try:
        source = authenticate_source(source_id=source_id, secret=secret)
        result = ingest_cycle_event(
            source=source,
            # jsonable_encoder turns the datetime into its stable wire form;
            # no site_id is accepted from or forwarded from the client.
            payload=jsonable_encoder(payload.model_dump()),
        )
        return _response(result)
    except InvalidSourceCredential:
        raise HTTPException(status_code=401, detail="invalid_source_credential") from None
    except SourceForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except EventPayloadConflict:
        raise HTTPException(status_code=409, detail="event_id_payload_mismatch") from None

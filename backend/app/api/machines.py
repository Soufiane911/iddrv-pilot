from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from ..read_repositories import get_machine, machine_status, quality, raw_cycles, timeline
from ..repositories import list_incidents
from ..schemas import IncidentPage, Machine, MachineStatusResponse, QualityResponse, RawMachineCyclePage, TimelineResponse
from ..security import Identity, get_identity_optional, require_site


router = APIRouter(prefix="/api/v1/machines", tags=["supervision"])


def _machine_or_404(machine_id: int):
    value = get_machine(machine_id)
    if value is None:
        raise HTTPException(status_code=404, detail="machine_not_found")
    return value


@router.get("/{machine_id}", response_model=Machine)
def machine(machine_id: int, identity: Identity | None = Depends(get_identity_optional)):
    value = _machine_or_404(machine_id)
    if identity is not None:
        require_site(identity, int(value["site_id"]))
    return value


@router.get("/{machine_id}/status", response_model=MachineStatusResponse)
def status(
    machine_id: int,
    as_of: datetime | None = None,
    identity: Identity | None = Depends(get_identity_optional),
):
    value = _machine_or_404(machine_id)
    if identity is not None:
        require_site(identity, int(value["site_id"]))
    return machine_status(machine_id, as_of or datetime.now(timezone.utc))


@router.get("/{machine_id}/cycles", response_model=RawMachineCyclePage)
def machine_cycles(
    machine_id: int,
    to: datetime = Query(...),
    limit: int = Query(20, ge=1, le=100),
    identity: Identity | None = Depends(get_identity_optional),
):
    value = _machine_or_404(machine_id)
    if identity is not None:
        require_site(identity, int(value["site_id"]))
    if to.tzinfo is None or to.utcoffset() is None:
        raise HTTPException(status_code=422, detail="to_timezone_required")
    return {"items": raw_cycles(machine_id, to, limit), "next_cursor": None}


@router.get("/{machine_id}/timeline", response_model=TimelineResponse)
def machine_timeline(
    machine_id: int,
    from_: datetime = Query(..., alias="from"),
    to: datetime = Query(...),
    bucket: str = Query("hour"),
    identity: Identity | None = Depends(get_identity_optional),
):
    value = _machine_or_404(machine_id)
    if identity is not None:
        require_site(identity, int(value["site_id"]))
    if from_ >= to:
        raise HTTPException(status_code=422, detail="from must be before to")
    if bucket not in {"minute", "hour", "shift", "order"}:
        raise HTTPException(status_code=422, detail="invalid bucket")
    return {"machine_id": machine_id, "from": from_, "to": to, "bucket": bucket,
            "items": timeline(machine_id, from_, to, bucket)}


@router.get("/{machine_id}/quality", response_model=QualityResponse)
def machine_quality(
    machine_id: int,
    from_: datetime = Query(..., alias="from"),
    to: datetime = Query(...),
    identity: Identity | None = Depends(get_identity_optional),
):
    value = _machine_or_404(machine_id)
    if identity is not None:
        require_site(identity, int(value["site_id"]))
    if from_ >= to:
        raise HTTPException(status_code=422, detail="from must be before to")
    return quality(machine_id, from_, to)


@router.get("/{machine_id}/diagnostics", response_model=IncidentPage)
def machine_diagnostics(
    machine_id: int,
    as_of: datetime | None = None,
    identity: Identity | None = Depends(get_identity_optional),
):
    value = _machine_or_404(machine_id)
    if identity is not None:
        require_site(identity, int(value["site_id"]))
    rows = list_incidents(machine_id=machine_id, end=as_of)
    return {"items": rows, "next_cursor": None}

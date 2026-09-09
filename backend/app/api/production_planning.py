"""HTTP contract for the workshop's multi-press production planning."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
import re
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StrictInt, model_validator

from .. import planning_repository as repository
from ..security import Identity, get_current_identity, require_site, require_site_roles

router = APIRouter(prefix="/api/v1", tags=["production-planning"])


class PlanningSlotInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    starts_at: datetime = Field(
        validation_alias=AliasChoices("starts_at", "start_at", "planned_start", "planned_start_at", "start")
    )
    ends_at: datetime = Field(
        validation_alias=AliasChoices("ends_at", "end_at", "planned_end", "planned_end_at", "end")
    )
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def valid_period(self):
        if self.starts_at.tzinfo is None or self.starts_at.utcoffset() is None:
            raise ValueError("timezone_required")
        if self.ends_at.tzinfo is None or self.ends_at.utcoffset() is None:
            raise ValueError("timezone_required")
        if self.starts_at >= self.ends_at:
            raise ValueError("slot_period_must_be_positive")
        return self


class WorkOrderAllocationInput(PlanningSlotInput):
    machine_id: int = Field(gt=0)


class WorkOrderCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    order_number: str = Field(
        min_length=1,
        max_length=50,
        validation_alias=AliasChoices("order_number", "of_number", "production_order_id", "production_order_number"),
    )
    allocations: list[WorkOrderAllocationInput] = Field(
        min_length=1,
        validation_alias=AliasChoices("allocations", "assignments", "presses"),
    )
    note: str | None = Field(default=None, max_length=2000)


class AllocationCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    machine_id: int = Field(gt=0)
    slots: list[PlanningSlotInput] = Field(default_factory=list, max_length=100)


class SlotCreateInput(PlanningSlotInput):
    allocation_id: UUID


class SlotPatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    row_version: int = Field(ge=1)
    starts_at: datetime | None = Field(
        default=None, validation_alias=AliasChoices("starts_at", "start_at", "planned_start", "planned_start_at", "start")
    )
    ends_at: datetime | None = Field(
        default=None, validation_alias=AliasChoices("ends_at", "end_at", "planned_end", "planned_end_at", "end")
    )
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def valid_dates(self):
        for value in (self.starts_at, self.ends_at):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError("timezone_required")
        if self.starts_at is not None and self.ends_at is not None and self.starts_at >= self.ends_at:
            raise ValueError("slot_period_must_be_positive")
        return self


class ScrapInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # StrictInt deliberately distinguishes 0 from null and rejects bools and
    # fractional JSON numbers at the HTTP boundary.
    machine_id: StrictInt = Field(gt=0)
    actual_scrap_count: StrictInt | None = Field(default=None, ge=0)
    comment: str | None = Field(default=None, max_length=2000)
    row_version: StrictInt = Field(ge=1)


class SlotCancelInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_version: int = Field(ge=1)


def _error(exc: RuntimeError | ValueError) -> HTTPException:
    if isinstance(exc, repository.PlanningNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, repository.PlanningConflict):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


def _allocation_dict(value: WorkOrderAllocationInput) -> dict:
    return {
        "machine_id": value.machine_id,
        "starts_at": value.starts_at,
        "ends_at": value.ends_at,
        "note": value.note,
    }


def _slot_dict(value: PlanningSlotInput) -> dict:
    return {"starts_at": value.starts_at, "ends_at": value.ends_at, "note": value.note}


def _authorized_order(order_id: UUID, identity: Identity, write: bool = True) -> dict:
    order = repository.get_work_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="work_order_not_found")
    if write:
        require_site_roles(identity, int(order["site_id"]), "supervisor", "admin")
    else:
        require_site(identity, int(order["site_id"]))
    return order


def _authorized_allocation(allocation_id: UUID, identity: Identity, write: bool = True) -> dict:
    allocation = repository.get_allocation(allocation_id)
    if not allocation:
        raise HTTPException(status_code=404, detail="allocation_not_found")
    if write:
        require_site_roles(identity, int(allocation["site_id"]), "supervisor", "admin")
    else:
        require_site(identity, int(allocation["site_id"]))
    return allocation


def _authorized_slot(slot_id: UUID, identity: Identity, write: bool = True) -> dict:
    slot = repository.get_slot(slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="slot_not_found")
    if write:
        require_site_roles(identity, int(slot["site_id"]), "supervisor", "admin")
    else:
        require_site(identity, int(slot["site_id"]))
    return slot


@router.get("/sites/{site_id}/planning")
def read_planning(
    site_id: int,
    week_start: date | None = Query(None, description="Monday in the site's local timezone"),
    week: str | None = Query(None, pattern=r"^\d{4}-W\d{2}$"),
    identity: Identity = Depends(get_current_identity),
):
    require_site(identity, site_id)
    if week_start is None and week is not None:
        try:
            year, week_number = (int(value) for value in re.fullmatch(r"(\d{4})-W(\d{2})", week).groups())
            week_start = date.fromisocalendar(year, week_number, 1)
        except (AttributeError, ValueError):
            raise HTTPException(status_code=422, detail="week_invalid") from None
    if week_start is None:
        raise HTTPException(status_code=422, detail="week_start_required")
    try:
        return repository.list_planning_week(site_id=site_id, week_start=week_start)
    except (repository.PlanningNotFound, repository.PlanningConflict, repository.PlanningValidation) as exc:
        raise _error(exc) from None


@router.post("/sites/{site_id}/work-orders", status_code=201)
def create_work_order(
    site_id: int,
    payload: WorkOrderCreateInput,
    identity: Identity = Depends(get_current_identity),
):
    require_site_roles(identity, site_id, "supervisor", "admin")
    try:
        return repository.create_work_order(
            site_id=site_id,
            order_number=payload.order_number,
            note=payload.note,
            allocations=[_allocation_dict(value) for value in payload.allocations],
            actor_id=identity.user_id,
        )
    except (repository.PlanningNotFound, repository.PlanningConflict, repository.PlanningValidation) as exc:
        raise _error(exc) from None


@router.post("/work-orders/{work_order_id}/allocations", status_code=201)
def add_allocation(
    work_order_id: UUID,
    payload: AllocationCreateInput,
    identity: Identity = Depends(get_current_identity),
):
    _authorized_order(work_order_id, identity)
    try:
        return repository.create_allocation(
            work_order_id=work_order_id,
            machine_id=payload.machine_id,
            slots=[_slot_dict(value) for value in payload.slots],
            actor_id=identity.user_id,
        )
    except (repository.PlanningNotFound, repository.PlanningConflict, repository.PlanningValidation) as exc:
        raise _error(exc) from None


@router.post("/planning/slots", status_code=201)
def add_slot(payload: SlotCreateInput, identity: Identity = Depends(get_current_identity)):
    allocation = _authorized_allocation(payload.allocation_id, identity)
    try:
        # Reuse the allocation transaction so the site and press are taken
        # from the locked allocation rather than trusted from the request.
        return repository.create_slot(
            allocation_id=payload.allocation_id,
            site_id=int(allocation["site_id"]),
            machine_id=int(allocation["machine_id"]),
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            note=payload.note,
            actor_id=identity.user_id,
        )
    except (repository.PlanningNotFound, repository.PlanningConflict, repository.PlanningValidation) as exc:
        raise _error(exc) from None


@router.patch("/planning/slots/{slot_id}")
def edit_slot(
    slot_id: UUID,
    payload: SlotPatchInput,
    identity: Identity = Depends(get_current_identity),
):
    slot = _authorized_slot(slot_id, identity)
    try:
        return repository.update_slot(
            slot_id=slot_id,
            row_version=payload.row_version,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            note=payload.note,
            note_provided="note" in payload.model_fields_set,
            actor_id=identity.user_id,
        )
    except (repository.PlanningNotFound, repository.PlanningConflict, repository.PlanningValidation) as exc:
        raise _error(exc) from None


@router.post("/planning/work-orders/{work_order_id}/scrap")
def enter_scrap(work_order_id: UUID, payload: ScrapInput, identity: Identity = Depends(get_current_identity)):
    # Read authorization first: operators may enter actuals, while the
    # planning lifecycle remains supervisor/admin-only.
    order = _authorized_order(work_order_id, identity, write=False)
    if identity.role_for_site(int(order['site_id'])) not in ('operator', 'supervisor', 'admin'):
        raise HTTPException(status_code=403, detail='insufficient_role')
    try:
        return repository.update_actual_scrap(work_order_id=work_order_id, machine_id=payload.machine_id,
            actual_scrap_count=payload.actual_scrap_count, comment=payload.comment,
            row_version=payload.row_version, actor_id=identity.user_id)
    except (repository.PlanningNotFound, repository.PlanningConflict, repository.PlanningValidation) as exc:
        raise _error(exc) from None


@router.post("/planning/slots/{slot_id}/cancel")
def cancel_slot(
    slot_id: UUID,
    payload: SlotCancelInput,
    identity: Identity = Depends(get_current_identity),
):
    _authorized_slot(slot_id, identity)
    try:
        return repository.cancel_slot(slot_id=slot_id, row_version=payload.row_version, actor_id=identity.user_id)
    except (repository.PlanningNotFound, repository.PlanningConflict, repository.PlanningValidation) as exc:
        raise _error(exc) from None

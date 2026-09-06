from fastapi import APIRouter, Depends, HTTPException, Response

from ..schemas import MachineCreateInput, MachinePatchInput
from ..security import Identity, get_current_identity, require_site_roles
from ..site_repository import (
    MachineConflict,
    MachineNotFound,
    SiteConflict,
    SiteNotFound,
    archive_machine,
    create_machine,
    machine_site_id,
    update_machine,
)

# Full paths are used here so this router can expose both the Atelier create
# endpoint and the machine-scoped lifecycle endpoint without changing main.py.
router = APIRouter(tags=["topology"])


@router.post("/api/v1/sites/{site_id}/machines", status_code=201)
def add_machine(
    site_id: int,
    payload: MachineCreateInput,
    identity: Identity = Depends(get_current_identity),
):
    require_site_roles(identity, site_id, "supervisor", "admin")
    try:
        machine = create_machine(site_id=site_id, **payload.model_dump())
        # Keep the old repository contract usable for integrations that return
        # None instead of raising on an identity conflict.
        if machine is None:
            raise HTTPException(status_code=409, detail="machine_identity_already_exists")
        return machine
    except SiteNotFound:
        raise HTTPException(status_code=404, detail="site_not_found") from None
    except (SiteConflict, MachineConflict) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


def _patch_machine(machine_id: int, payload: MachinePatchInput):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="machine_patch_empty")
    try:
        return update_machine(machine_id=machine_id, **changes)
    except MachineNotFound:
        raise HTTPException(status_code=404, detail="machine_not_found") from None
    except (SiteConflict, MachineConflict) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.patch("/api/v1/machines/{machine_id}")
def patch_machine(
    machine_id: int,
    payload: MachinePatchInput,
    identity: Identity = Depends(get_current_identity),
):
    _check_machine_role(identity, machine_id)
    return _patch_machine(machine_id, payload)


@router.patch("/api/v1/sites/{site_id}/machines/{machine_id}")
def patch_site_machine(
    site_id: int,
    machine_id: int,
    payload: MachinePatchInput,
    identity: Identity = Depends(get_current_identity),
):
    _check_machine_role(identity, machine_id, expected_site_id=site_id)
    return _patch_machine(machine_id, payload)


def _check_machine_role(identity: Identity, machine_id: int, expected_site_id: int | None = None) -> None:
    try:
        actual_site_id = machine_site_id(machine_id)
    except MachineNotFound:
        raise HTTPException(status_code=404, detail="machine_not_found") from None
    if expected_site_id is not None and actual_site_id != expected_site_id:
        # Do not disclose a machine belonging to another tenant.
        raise HTTPException(status_code=404, detail="machine_not_found")
    if identity.is_admin:
        return
    require_site_roles(identity, actual_site_id, "supervisor", "admin")


@router.post("/api/v1/machines/{machine_id}/archive", status_code=204)
def archive(
    machine_id: int,
    identity: Identity = Depends(get_current_identity),
):
    """Archive a press while retaining its cycles, mappings and references."""
    _check_machine_role(identity, machine_id)
    try:
        archive_machine(machine_id)
    except MachineNotFound:
        raise HTTPException(status_code=404, detail="machine_not_found") from None
    except MachineConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return Response(status_code=204)


@router.post("/api/v1/sites/{site_id}/machines/{machine_id}/archive", status_code=204)
def archive_site_machine(
    site_id: int,
    machine_id: int,
    identity: Identity = Depends(get_current_identity),
):
    """Site-scoped alias used by the Atelier clients."""
    _check_machine_role(identity, machine_id, expected_site_id=site_id)
    try:
        archive_machine(machine_id)
    except MachineNotFound:
        raise HTTPException(status_code=404, detail="machine_not_found") from None
    except MachineConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return Response(status_code=204)

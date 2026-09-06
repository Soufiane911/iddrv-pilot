"""Administration API for site-owned gateway sources and detected identities."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from fastapi.encoders import jsonable_encoder

from ..security import Identity, get_current_identity, require_site_roles
from ..source_repository import (
    SourceConflict,
    SourceForbidden,
    SourceNotFound,
    create_source,
    detected_machines,
    list_sources,
    map_source_machine,
    rotate_source_credential,
    source_site,
)

router = APIRouter(tags=["site-sources"])


class SourceCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(default="Passerelle du site", min_length=1, max_length=120)


class SourceMachineMappingInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    external_machine_id: str = Field(min_length=1, max_length=128)
    machine_id: int = Field(ge=1)
    effective_at: datetime | None = None


def _source_site_or_404(source_id: UUID) -> int:
    try:
        return source_site(source_id)
    except SourceNotFound:
        raise HTTPException(status_code=404, detail="source_not_found") from None
    except SourceForbidden as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.get("/api/v1/sites/{site_id}/sources")
def read_sources(site_id: int, identity: Identity = Depends(get_current_identity)):
    require_site(identity, site_id)
    return {"items": jsonable_encoder(list_sources(site_id=site_id))}


@router.post("/api/v1/sites/{site_id}/sources", status_code=201)
def provision_source(
    site_id: int,
    payload: SourceCreateInput,
    identity: Identity = Depends(get_current_identity),
):
    require_site_roles(identity, site_id, "supervisor", "admin")
    try:
        return jsonable_encoder(create_source(site_id=site_id, name=payload.name))
    except SourceNotFound:
        raise HTTPException(status_code=404, detail="site_not_found") from None
    except SourceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/api/v1/sources/{source_id}/credentials", status_code=201)
def rotate_credential(source_id: UUID, identity: Identity = Depends(get_current_identity)):
    site_id = _source_site_or_404(source_id)
    require_site_roles(identity, site_id, "supervisor", "admin")
    try:
        return jsonable_encoder(rotate_source_credential(source_id=source_id))
    except SourceNotFound:
        raise HTTPException(status_code=404, detail="source_not_found") from None
    except SourceForbidden as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.post("/api/v1/sources/{source_id}/machine-mappings", status_code=201)
def create_machine_mapping(
    source_id: UUID,
    payload: SourceMachineMappingInput,
    identity: Identity = Depends(get_current_identity),
):
    site_id = _source_site_or_404(source_id)
    require_site_roles(identity, site_id, "supervisor", "admin")
    try:
        return jsonable_encoder(
            map_source_machine(
                source_id=source_id,
                external_machine_id=payload.external_machine_id,
                machine_id=payload.machine_id,
                effective_at=payload.effective_at,
            )
        )
    except SourceNotFound:
        raise HTTPException(status_code=404, detail="source_not_found") from None
    except SourceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/api/v1/sources/{source_id}/detected-machines")
def read_detected_machines(source_id: UUID, identity: Identity = Depends(get_current_identity)):
    site_id = _source_site_or_404(source_id)
    require_site_roles(identity, site_id, "viewer", "analyst", "supervisor", "admin")
    try:
        return {"items": jsonable_encoder(detected_machines(source_id=source_id))}
    except SourceNotFound:
        raise HTTPException(status_code=404, detail="source_not_found") from None

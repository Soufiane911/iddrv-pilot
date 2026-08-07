from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ..read_repositories import get_import, list_imports
from ..schemas import ImportJob, ImportPage
from ..security import Identity, get_identity_optional, require_site


router = APIRouter(prefix="/api/v1/imports", tags=["imports"])


@router.get("", response_model=ImportPage)
def imports(
    site_id: int | None = None,
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    identity: Identity | None = Depends(get_identity_optional),
):
    if identity is not None and site_id is not None:
        require_site(identity, site_id)
    allowed = None if identity is None or identity.anonymous else identity.site_ids
    items, next_value = list_imports(site_ids=allowed, site_id=site_id, limit=limit, cursor=cursor)
    return {"items": items, "next_cursor": next_value}


@router.get("/{import_id}", response_model=ImportJob)
def import_detail(import_id: UUID, identity: Identity | None = Depends(get_identity_optional)):
    value = get_import(import_id)
    if value is None:
        raise HTTPException(status_code=404, detail="import_not_found")
    if identity is not None:
        require_site(identity, int(value["site_id"]))
    return value

from fastapi import APIRouter, Depends, HTTPException, Query

from ..read_repositories import list_lines, list_machines, list_sites
from ..schemas import MachinePage, ProductionLinePage, Site, SitePage
from ..security import Identity, get_identity_optional, require_site


router = APIRouter(prefix="/api/v1/sites", tags=["topology"])


@router.get("", response_model=SitePage)
def sites(
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    identity: Identity | None = Depends(get_identity_optional),
):
    site_ids = None if identity is None or identity.anonymous else identity.site_ids
    items, next_value = list_sites(site_ids=site_ids, limit=limit, cursor=cursor)
    return {"items": items, "next_cursor": next_value}


@router.get("/{site_id}", response_model=Site)
def site(site_id: int, identity: Identity | None = Depends(get_identity_optional)):
    if identity is not None:
        require_site(identity, site_id)
    items, _ = list_sites(site_ids=(site_id,), limit=1)
    if not items:
        raise HTTPException(status_code=404, detail="site_not_found")
    return items[0]


@router.get("/{site_id}/lines", response_model=ProductionLinePage)
def lines(
    site_id: int,
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    identity: Identity | None = Depends(get_identity_optional),
):
    if identity is not None:
        require_site(identity, site_id)
    items, next_value = list_lines(site_id, limit=limit, cursor=cursor)
    return {"items": items, "next_cursor": next_value}


@router.get("/{site_id}/machines", response_model=MachinePage)
def machines(
    site_id: int,
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    identity: Identity | None = Depends(get_identity_optional),
):
    if identity is not None:
        require_site(identity, site_id)
    items, next_value = list_machines(site_id, limit=limit, cursor=cursor)
    return {"items": items, "next_cursor": next_value}

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ..repositories import get_investigation
from ..security import Identity, require_roles


router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])


@router.get("/{run_id}")
def investigation(
    run_id: UUID,
    identity: Identity = Depends(require_roles("viewer", "analyst", "supervisor", "admin")),
):
    value = get_investigation(run_id, allowed_site_ids=None if identity.is_admin else identity.site_ids)
    if value is None:
        raise HTTPException(status_code=404, detail="investigation_not_found")
    return value

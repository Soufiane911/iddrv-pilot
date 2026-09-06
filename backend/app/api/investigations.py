from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ..repositories import get_investigation
from ..security import Identity, get_current_identity


router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])


@router.get("/{run_id}")
def investigation(
    run_id: UUID,
    identity: Identity = Depends(get_current_identity),
):
    value = get_investigation(run_id, allowed_site_ids=identity.site_ids)
    if value is None:
        raise HTTPException(status_code=404, detail="investigation_not_found")
    return value

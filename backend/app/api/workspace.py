from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ..repositories import add_import_file, create_import_session, get_import_session, validate_import_session
from ..schemas import ImportFileRequest, ImportSession, ImportSessionRequest
from ..security import Identity, get_current_identity, require_site_roles

router = APIRouter(prefix="/api/v1", tags=["workspace"])


@router.post("/sites/{site_id}/import-sessions", response_model=ImportSession, status_code=201)
def create_session(site_id: int, payload: ImportSessionRequest, identity: Identity = Depends(get_current_identity)):
    require_site_roles(identity, site_id, "analyst", "supervisor", "admin")
    return create_import_session(site_id, payload.name, identity.user_id)


@router.get("/import-sessions/{session_id}", response_model=ImportSession)
def session_detail(session_id: UUID, identity: Identity = Depends(get_current_identity)):
    value = get_import_session(session_id)
    if value is None:
        raise HTTPException(status_code=404, detail="import_session_not_found")
    require_site_roles(identity, int(value["site_id"]), "viewer", "analyst", "supervisor", "admin")
    return value


@router.post("/import-sessions/{session_id}/files", response_model=ImportSession)
def register_file(session_id: UUID, payload: ImportFileRequest, identity: Identity = Depends(get_current_identity)):
    session = get_import_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="import_session_not_found")
    require_site_roles(identity, int(session["site_id"]), "analyst", "supervisor", "admin")
    add_import_file(session_id, payload.model_dump())
    return get_import_session(session_id)


@router.post("/import-sessions/{session_id}/validate", response_model=ImportSession)
def validate_session(session_id: UUID, identity: Identity = Depends(get_current_identity)):
    session = get_import_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="import_session_not_found")
    require_site_roles(identity, int(session["site_id"]), "analyst", "supervisor", "admin")
    try:
        return validate_import_session(session_id, identity.user_id)
    except ValueError as exc:
        if str(exc) == "import_session_not_profiled":
            raise HTTPException(status_code=409, detail="import_session_not_profiled") from None
        raise

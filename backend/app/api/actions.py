from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ..repositories import create_proposal, decide_proposal, get_incident, get_proposal, list_proposals
from ..schemas import ActionDecisionRequest, ActionDecisionResponse, ActionProposal, ActionRequest
from ..security import Identity, require_roles


router = APIRouter(prefix="/api/v1", tags=["actions"])


@router.get("/incidents/{incident_id}/actions", response_model=list[ActionProposal])
def actions(
    incident_id: UUID,
    identity: Identity = Depends(require_roles("viewer", "analyst", "supervisor", "admin")),
):
    allowed = None if identity.is_admin else identity.site_ids
    if get_incident(incident_id, allowed_site_ids=allowed) is None:
        raise HTTPException(status_code=404, detail="incident_not_found")
    return list_proposals(incident_id, allowed_site_ids=allowed)


@router.post("/incidents/{incident_id}/actions", response_model=ActionProposal, status_code=201)
def propose_action(
    incident_id: UUID,
    payload: ActionRequest,
    identity: Identity = Depends(require_roles("analyst", "supervisor", "admin")),
):
    allowed = None if identity.is_admin else identity.site_ids
    if get_incident(incident_id, allowed_site_ids=allowed) is None:
        raise HTTPException(status_code=404, detail="incident_not_found")
    return create_proposal(incident_id, payload.action_code, payload.label, payload.run_id)


@router.post("/actions/{action_id}/decision", response_model=ActionDecisionResponse)
def action_decision(
    action_id: UUID,
    payload: ActionDecisionRequest,
    identity: Identity = Depends(require_roles("supervisor", "admin")),
):
    if get_proposal(action_id, allowed_site_ids=None if identity.is_admin else identity.site_ids) is None:
        raise HTTPException(status_code=404, detail="action_not_found")
    result = decide_proposal(action_id, identity.user_id, payload.status, payload.reason)
    if result is None:
        raise HTTPException(status_code=404, detail="action_not_found")
    return result

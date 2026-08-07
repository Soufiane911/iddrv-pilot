from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ..repositories import create_proposal, decide_proposal, get_incident, get_investigation, get_proposal, list_proposals
from ..schemas import ActionDecisionRequest, ActionDecisionResponse, ActionProposal, ActionRequest
from ..security import Identity, get_current_identity, require_site_roles


router = APIRouter(prefix="/api/v1", tags=["actions"])


@router.get("/incidents/{incident_id}/actions", response_model=list[ActionProposal])
def actions(
    incident_id: UUID,
    identity: Identity = Depends(get_current_identity),
):
    incident = get_incident(incident_id, allowed_site_ids=identity.site_ids)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident_not_found")
    require_site_roles(identity, int(incident["site_id"]), "viewer", "analyst", "supervisor", "admin")
    return list_proposals(incident_id, allowed_site_ids=identity.site_ids)


@router.post("/incidents/{incident_id}/actions", response_model=ActionProposal, status_code=201)
def propose_action(
    incident_id: UUID,
    payload: ActionRequest,
    identity: Identity = Depends(get_current_identity),
):
    incident = get_incident(incident_id, allowed_site_ids=identity.site_ids)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident_not_found")
    require_site_roles(identity, int(incident["site_id"]), "analyst", "supervisor", "admin")
    if payload.run_id is not None:
        run = get_investigation(payload.run_id, allowed_site_ids=identity.site_ids)
        if run is None or str(run["incident_id"]) != str(incident_id):
            raise HTTPException(status_code=422, detail="investigation_incident_mismatch")
    proposal = create_proposal(incident_id, payload.action_code, payload.label, payload.run_id)
    if proposal is None:
        raise HTTPException(status_code=409, detail="action_already_decided")
    return proposal


@router.post("/actions/{action_id}/decision", response_model=ActionDecisionResponse)
def action_decision(
    action_id: UUID,
    payload: ActionDecisionRequest,
    identity: Identity = Depends(get_current_identity),
):
    proposal = get_proposal(action_id, allowed_site_ids=identity.site_ids)
    if proposal is None:
        raise HTTPException(status_code=404, detail="action_not_found")
    incident = get_incident(proposal["incident_id"], allowed_site_ids=identity.site_ids)
    if incident is None:
        raise HTTPException(status_code=404, detail="action_not_found")
    require_site_roles(identity, int(incident["site_id"]), "supervisor", "admin")
    result = decide_proposal(action_id, identity.user_id, payload.status, payload.reason)
    if result is None:
        raise HTTPException(status_code=409, detail="action_already_decided")
    return result

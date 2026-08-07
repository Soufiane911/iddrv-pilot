from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from ..repositories import list_incidents, get_incident, get_evidence, save_feedback, persist_investigation
from ..read_repositories import _cursor_offset, next_cursor
from ..schemas import Incident, IncidentPage, Evidence, FeedbackRequest, FeedbackResponse, InvestigationResponse
from ..security import Identity, get_identity_optional, require_roles, require_site, require_site_roles

router = APIRouter(prefix="/api/v1/incidents", tags=["investigations"])

@router.get("", response_model=IncidentPage)
def incidents(site_id: int | None = None, from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
              status: str | None = None, machine_id: int | None = None, cursor: str | None = None,
              limit: int = Query(100, ge=1, le=500), identity: Identity | None = Depends(get_identity_optional)):
    if from_ and to and from_ > to: raise HTTPException(422, detail="from must be before or equal to to")
    if status and status not in {"open","reviewed","closed"}: raise HTTPException(422, detail="invalid status")
    if identity is not None and site_id is not None:
        require_site(identity, site_id)
    allowed = None if identity is None or identity.anonymous else identity.site_ids
    rows = list_incidents(site_id, from_, to, status, machine_id=machine_id, allowed_site_ids=allowed,
                          limit=limit + 1, offset=_cursor_offset(cursor))
    offset = _cursor_offset(cursor)
    return {"items": rows[:limit], "next_cursor": next_cursor(offset, limit, len(rows))}

@router.get("/{incident_id}", response_model=Incident)
def incident(incident_id: UUID, identity: Identity | None = Depends(get_identity_optional)):
    allowed = None if identity is None or identity.anonymous else identity.site_ids
    value = get_incident(incident_id, allowed_site_ids=allowed)
    if value is None: raise HTTPException(404, detail="incident_not_found")
    return value

@router.get("/{incident_id}/evidence", response_model=list[Evidence])
def evidence(incident_id: UUID, identity: Identity | None = Depends(get_identity_optional)):
    allowed = None if identity is None or identity.anonymous else identity.site_ids
    if get_incident(incident_id, allowed_site_ids=allowed) is None: raise HTTPException(404, detail="incident_not_found")
    return get_evidence(incident_id)

@router.post("/{incident_id}/investigations", response_model=InvestigationResponse)
def investigate(incident_id: UUID, as_of: datetime | None = None,
                identity: Identity = Depends(require_roles("analyst", "supervisor", "admin"))):
    inc = get_incident(incident_id, allowed_site_ids=identity.site_ids)
    if inc is None: raise HTTPException(404, detail="incident_not_found")
    require_site_roles(identity, int(inc["site_id"]), "analyst", "supervisor", "admin")
    try:
        from ..diagnostics.engine import DeterministicInvestigator
        from ..diagnostics.postgres import PostgresDiagnosticRepository
        from ..diagnostics.models import InsufficientDataError
        engine = DeterministicInvestigator(
            PostgresDiagnosticRepository(),
            minimum_event_cycles=30,
            minimum_baseline_cycles=30,
            minimum_quality_checks=1,
            abstain_on_insufficient=True,
        )
    except ImportError:
        from ..metrics import record_investigation_outcome
        record_investigation_outcome("error")
        raise HTTPException(503, detail="diagnostic_engine_unavailable")
    if as_of is not None and as_of.utcoffset() is None:
        raise HTTPException(status_code=422, detail="as_of_timezone_required")
    effective_cutoff = min(as_of, inc["data_cutoff"]) if as_of is not None else inc["data_cutoff"]
    incident_end = min(inc.get("ended_at") or effective_cutoff, effective_cutoff)
    try:
        result = engine.investigate(
            machine_id=inc["machine_id"],
            machine_erp_ref=inc.get("machine_erp_ref"),
            production_order_id=inc.get("production_order_id"),
            started_at=inc["started_at"],
            ended_at=incident_end,
            as_of=effective_cutoff,
            defect_type=inc.get("defect_type") or "short_shot",
            incident_id=str(incident_id),
        )
    except InsufficientDataError as exc:
        from ..metrics import record_investigation_outcome
        record_investigation_outcome("insufficient_data")
        raise HTTPException(status_code=422, detail={"code": "insufficient_data", "message": str(exc)}) from exc
    run_id = persist_investigation(incident_id, result, effective_cutoff)
    from ..metrics import record_investigation_outcome
    record_investigation_outcome("succeeded")
    return {"incident": inc, "run_id": run_id, "hypotheses": [h.to_dict() for h in result.hypotheses], "evidence": [e.to_dict() for e in result.evidence]}

@router.post("/{incident_id}/feedback", response_model=FeedbackResponse, status_code=201)
def feedback(incident_id: UUID, payload: FeedbackRequest,
             identity: Identity = Depends(require_roles("analyst", "supervisor", "admin"))):
    inc = get_incident(incident_id, allowed_site_ids=identity.site_ids)
    if inc is None:
        raise HTTPException(404, detail="incident_not_found")
    require_site_roles(identity, int(inc["site_id"]), "analyst", "supervisor", "admin")
    return save_feedback(incident_id, payload.verdict, payload.comment)

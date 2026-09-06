from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from ..repositories import list_incidents, get_incident, get_evidence, save_feedback, persist_investigation
from ..read_repositories import InvalidCursor, _cursor_offset, next_cursor
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
    try:
        offset = _cursor_offset(cursor)
    except InvalidCursor as exc:
        raise HTTPException(status_code=422, detail="invalid pagination cursor") from exc
    rows = list_incidents(site_id, from_, to, status, machine_id=machine_id, allowed_site_ids=allowed,
                          limit=limit + 1, offset=offset)
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
    if as_of is not None and as_of.utcoffset() is None:
        raise HTTPException(status_code=422, detail="as_of_timezone_required")
    knowledge_at = as_of or (datetime.now(timezone.utc) if inc.get('origin') == 'process_drift' else inc['data_cutoff'])
    try:
        from ..diagnostics.engine import DeterministicInvestigator
        from ..diagnostics.postgres import PostgresDiagnosticRepository
        from ..diagnostics.models import InsufficientDataError
        repository = PostgresDiagnosticRepository(site_id=inc["site_id"],known_at=knowledge_at)
        engine = DeterministicInvestigator(
            repository,
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
    if inc.get('origin') == 'process_drift' and not list(repository.quality_checks(inc['machine_id'],inc['started_at'],incident_end)):
        raise HTTPException(422,'process_drift_quality_observations_required')
    try:
        result = engine.investigate(
            machine_id=inc["machine_id"],
            machine_erp_ref=inc.get("machine_erp_ref"),
            production_order_id=inc.get("production_order_id"),
            started_at=inc["started_at"],
            ended_at=incident_end,
            as_of=effective_cutoff,
            defect_type=inc.get("defect_type") or (None if inc.get("origin") == "process_drift" else "short_shot"),
            incident_id=str(incident_id),
        )
    except InsufficientDataError as exc:
        from ..metrics import record_investigation_outcome
        record_investigation_outcome("insufficient_data")
        raise HTTPException(status_code=422, detail={"code": "insufficient_data", "message": str(exc)}) from exc
    run_id = persist_investigation(incident_id, result, knowledge_at, context_snapshot=repository.context_snapshot)
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
    if payload.run_id is not None:
        from ..repositories import get_investigation
        run = get_investigation(payload.run_id,allowed_site_ids=identity.site_ids)
        if run is None or str(run['incident_id']) != str(incident_id):
            raise HTTPException(422,'feedback_run_mismatch')
    elif inc.get('origin') == 'process_drift':
        raise HTTPException(422,'feedback_run_required')
    return save_feedback(incident_id, payload.verdict, payload.comment, payload.run_id)

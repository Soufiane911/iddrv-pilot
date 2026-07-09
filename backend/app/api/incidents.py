from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from ..repositories import list_incidents, get_incident, get_evidence, save_feedback, persist_investigation
from ..schemas import Incident, Evidence, FeedbackRequest, FeedbackResponse, InvestigationResponse

router = APIRouter(prefix="/api/v1/incidents", tags=["investigations"])

@router.get("", response_model=list[Incident])
def incidents(site_id: int | None = None, from_: datetime | None = Query(None, alias="from"), to: datetime | None = None, status: str | None = None):
    if from_ and to and from_ > to: raise HTTPException(422, detail="from must be before or equal to to")
    if status and status not in {"open","reviewed","closed"}: raise HTTPException(422, detail="invalid status")
    return list_incidents(site_id, from_, to, status)

@router.get("/{incident_id}", response_model=Incident)
def incident(incident_id: UUID):
    value = get_incident(incident_id)
    if value is None: raise HTTPException(404, detail="incident_not_found")
    return value

@router.get("/{incident_id}/evidence", response_model=list[Evidence])
def evidence(incident_id: UUID):
    if get_incident(incident_id) is None: raise HTTPException(404, detail="incident_not_found")
    return get_evidence(incident_id)

@router.post("/{incident_id}/investigations", response_model=InvestigationResponse)
def investigate(incident_id: UUID, as_of: datetime | None = None):
    inc = get_incident(incident_id)
    if inc is None: raise HTTPException(404, detail="incident_not_found")
    # Diagnostic worker supplies this optional local engine; no LLM is used here.
    try:
        from ..diagnostics.engine import DiagnosticEngine
        from ..diagnostics.postgres import PostgresDiagnosticRepository
        engine = DiagnosticEngine(PostgresDiagnosticRepository())
    except ImportError:
        raise HTTPException(503, detail="diagnostic_engine_unavailable")
    result = engine.investigate(machine_id=inc["machine_id"], machine_erp_ref=inc.get("machine_erp_ref"), production_order_id=inc.get("production_order_id"), started_at=inc["started_at"], ended_at=inc.get("ended_at") or as_of or inc["data_cutoff"], defect_type=inc.get("defect_type") or "short_shot", incident_id=str(incident_id))
    run_id = persist_investigation(incident_id, result, as_of or inc["data_cutoff"])
    return {"incident": inc, "run_id": run_id, "hypotheses": [h.to_dict() for h in result.hypotheses], "evidence": [e.to_dict() for e in result.evidence]}

@router.post("/{incident_id}/feedback", response_model=FeedbackResponse, status_code=201)
def feedback(incident_id: UUID, payload: FeedbackRequest):
    if get_incident(incident_id) is None: raise HTTPException(404, detail="incident_not_found")
    return save_feedback(incident_id, payload.verdict, payload.comment)

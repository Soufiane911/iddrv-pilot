"""Stable API contracts for the v1 service skeleton.

Business endpoints are intentionally not implemented in G1. These models keep
the public wire format explicit for the frontend and future route work.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiError(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ApiError


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    database: Literal["ok", "unavailable"]


class Site(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    timezone: str = "UTC"


class ProductionLine(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    site_id: int
    name: str


class Machine(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    site_id: int | None = None
    line_id: int | None = None
    name: str
    status: Literal["running", "warning", "stopped", "offline"] | None = None


class MachineStatus(BaseModel):
    machine_id: int
    status: Literal["running", "warning", "stopped", "offline"]
    as_of: datetime
    freshness_s: float | None = None


class CursorPage[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


class TimelinePoint(BaseModel):
    timestamp: datetime
    value: float | None = None
    status: str | None = None

class Incident(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; site_id: int; machine_id: int; machine_erp_ref: str | None = None
    production_order_id: str | None = None
    status: Literal["open", "reviewed", "closed"]
    severity: Literal["low", "medium", "high", "critical"]
    symptom: str; defect_type: str | None = None
    started_at: datetime; ended_at: datetime | None = None; created_at: datetime
    data_cutoff: datetime; confidence: Literal["low", "medium", "high"] | None = None

class Evidence(BaseModel):
    id: UUID; source_kind: str; source_ref: str; metric: str
    window: dict[str, Any] = {}; observation: dict[str, Any]
    baseline: dict[str, Any] | None = None; delta: float | None = None
    supports: bool; excerpt: str | None = None

class Hypothesis(BaseModel):
    cause_code: str; label: str; confidence: float
    supporting_evidence_ids: list[UUID] = []; contradicting_evidence_ids: list[UUID] = []
    missing_data: list[Any] = []; next_check: str | None = None

class InvestigationResponse(BaseModel):
    incident: Incident
    run_id: UUID | None = None
    hypotheses: list[Hypothesis] = []
    evidence: list[Evidence] = []

class FeedbackRequest(BaseModel):
    verdict: str = Field(min_length=1, max_length=30)
    comment: str | None = Field(default=None, max_length=4000)

class FeedbackResponse(BaseModel):
    id: UUID; incident_id: UUID; verdict: str; comment: str | None = None

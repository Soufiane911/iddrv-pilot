"""Stable API contracts for the v1 service.

The API never exposes raw machine cycles. Time-series endpoints return bounded
aggregates whose shape is shared by the 2D and optional 3D clients.
"""

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    service: str
    version: str
    database: Literal["ok", "unavailable"]
    redis: Literal["ok", "unavailable"]
    model: Literal["ok", "unavailable"]


class Site(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    timezone: str = "UTC"
    machine_count: int | None = None
    open_incident_count: int | None = None
    last_import_at: datetime | None = None
    status: Literal["active", "archived"] = "active"


class SiteCreateInput(BaseModel):
    """Payload used to provision an empty production site."""

    name: str = Field(min_length=1, max_length=100)
    timezone: str = Field(default="Europe/Paris", min_length=1, max_length=50)


class ProductionLine(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    site_id: int
    name: str
    code: str | None = None
    machine_count: int | None = None


class Machine(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    site_id: int | None = None
    line_id: int | None = None
    workshop_code: str | None = None
    erp_ref: str | None = None
    name: str
    brand: str | None = None
    model: str | None = None
    status: Literal["running", "warning", "stopped", "offline"] | None = None
    lifecycle_status: Literal["active", "inactive", "archived"] = "active"
    as_of: datetime | None = None
    layout: dict[str, Any] | None = None


class MachineStatus(BaseModel):
    machine_id: int
    status: Literal["running", "warning", "stopped", "offline"]
    as_of: datetime
    freshness_s: float | None = None


class ScrapRiskRequest(BaseModel):
    site_id: int = Field(ge=1)
    machine_erp_ref: str = Field(min_length=1, max_length=50)
    cycle_time_s: float | None = None
    dosing_time_s: float | None = None
    injection_time_s: float | None = None
    cooling_time_s: float | None = None
    cushion_mm: float | None = None
    switchover_position_mm: float | None = None
    switchover_pressure_bar: float | None = None
    peak_pressure_bar: float | None = None
    clamp_force_kn: float | None = None
    mold_temperature_c: float | None = None
    barrel_temp_zone1_c: float | None = None
    barrel_temp_zone2_c: float | None = None
    barrel_temp_zone3_c: float | None = None
    oil_temperature_c: float | None = None
    energy_kwh: float | None = None
    previous_scrap_flag: int | None = Field(default=None, ge=0, le=1)
    rolling_scrap_rate_20: float | None = Field(default=None, ge=0, le=1)


class ScrapRiskResponse(BaseModel):
    model_version: str
    risk_probability: float = Field(ge=0, le=1)
    predicted_scrap: bool
    threshold: float = Field(gt=0, lt=1)


class ProcessDriftCycle(BaseModel):
    timestamp: datetime
    machine_erp_ref: str = Field(min_length=1, max_length=50)
    cycle_time_s: float | None = None
    dosing_time_s: float | None = None
    injection_time_s: float | None = None
    cooling_time_s: float | None = None
    cushion_mm: float | None = None
    switchover_position_mm: float | None = None
    switchover_pressure_bar: float | None = None
    peak_pressure_bar: float | None = None
    clamp_force_kn: float | None = None
    mold_temperature_c: float | None = None
    barrel_temp_zone1_c: float | None = None
    barrel_temp_zone2_c: float | None = None
    barrel_temp_zone3_c: float | None = None
    oil_temperature_c: float | None = None
    energy_kwh: float | None = None


class RawMachineCycle(ProcessDriftCycle):
    """One unaggregated machine cycle suitable for causal HDT history."""
    scrap_flag: bool | None = None
    good_parts: int | None = None


class RawMachineCyclePage(BaseModel):
    items: list[RawMachineCycle]
    next_cursor: str | None = None


class ProcessDriftRequest(BaseModel):
    site_id: int = Field(ge=1)
    cycles: list[ProcessDriftCycle] = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def validate_single_machine(self) -> "ProcessDriftRequest":
        machine_refs = {cycle.machine_erp_ref for cycle in self.cycles}
        if len(machine_refs) > 1:
            raise ValueError("cycles must belong to a single machine")
        return self


class ProcessDriftSignal(BaseModel):
    feature: str = Field(min_length=1)
    volatility: float = Field(ge=0)


class ProcessDriftResponse(BaseModel):
    model_version: str
    machine_erp_ref: str
    anomaly_score: float
    predicted_instability_next_20_cycles: bool
    threshold: float
    horizon_cycles: int = Field(gt=0)
    signals: list[ProcessDriftSignal] = Field(default_factory=list, max_length=3)


class CursorPage[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


class TimelinePoint(BaseModel):
    timestamp: datetime
    value: float | None = None
    status: str | None = None


class PageMeta(BaseModel):
    next_cursor: str | None = None


class SitePage(BaseModel):
    items: list[Site]
    next_cursor: str | None = None


class ProductionLinePage(BaseModel):
    items: list[ProductionLine]
    next_cursor: str | None = None


class MachineListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    site_id: int
    line_id: int | None = None
    workshop_code: str | None = None
    erp_ref: str | None = None
    name: str
    brand: str | None = None
    model: str | None = None
    status: Literal["running", "warning", "stopped", "offline"] | None = None
    lifecycle_status: Literal["active", "inactive", "archived"] = "active"
    as_of: datetime | None = None
    layout: dict[str, Any] | None = None


class MachinePage(BaseModel):
    items: list[MachineListItem]
    next_cursor: str | None = None


class MachineStatusResponse(BaseModel):
    machine_id: int
    status: Literal["running", "warning", "stopped", "offline"]
    as_of: datetime
    freshness_s: float | None = None
    last_cycle_at: datetime | None = None
    current_order_id: str | None = None
    cycle_count_24h: int = 0
    scrap_rate_24h: float | None = None
    data_quality_status: str | None = None


class TimelineAggregate(BaseModel):
    bucket: datetime
    cycle_count: int
    avg_cycle_time_s: float | None = None
    scrap_rate: float | None = None
    avg_zone2_temperature_c: float | None = None
    production_order_id: str | None = None


class TimelineResponse(BaseModel):
    machine_id: int
    from_: datetime = Field(alias="from")
    to: datetime
    bucket: Literal["minute", "hour", "shift", "order"]
    items: list[TimelineAggregate]

    model_config = ConfigDict(populate_by_name=True)


class QualityDefectSummary(BaseModel):
    defect_type: str
    count: int
    type: str | None = None


class QualityResponse(BaseModel):
    machine_id: int
    from_: datetime = Field(alias="from")
    to: datetime
    total_checks: int = 0
    total_defects: int = 0
    scrap_count: int | None = None
    scrap_rate: float | None = None
    by_defect: list[QualityDefectSummary] = []
    # Frontend-compatible aliases kept during the v1 pilot transition.
    total: int = 0
    good: int | None = None
    scrap: int | None = None
    quality_coverage: float | None = None
    cycle_count: int = 0
    quality_known_cycles: int = 0
    quality_checks_source: dict = Field(default_factory=dict)
    quality_source: str = "unknown"
    defects: list[QualityDefectSummary] = []

    model_config = ConfigDict(populate_by_name=True)


class AuthUser(BaseModel):
    id: UUID | str
    email: str
    display_name: str
    role: Literal["viewer", "analyst", "supervisor", "admin"]
    site_ids: list[int]
    site_roles: dict[int, Literal["viewer", "analyst", "supervisor", "admin"]] = Field(default_factory=dict)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=512)


class LoginResponse(BaseModel):
    user: AuthUser
    expires_at: datetime


class CreateUserRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=512)
    display_name: str = Field(min_length=1, max_length=150)
    role: Literal["viewer", "analyst", "supervisor", "admin"]
    site_ids: list[int] = Field(default_factory=list, max_length=100)


class ActionRequest(BaseModel):
    action_code: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=500)
    run_id: UUID | None = None


class ActionProposal(BaseModel):
    id: UUID
    incident_id: UUID
    run_id: UUID | None = None
    action_code: str
    label: str
    status: Literal["proposed", "accepted", "rejected", "done"]
    created_at: datetime


class ActionDecisionRequest(BaseModel):
    status: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=4000)


class ActionDecisionResponse(BaseModel):
    id: UUID
    proposal_id: UUID
    status: Literal["approved", "rejected"]
    reason: str | None = None
    decided_at: datetime


class ImportJob(BaseModel):
    id: UUID
    site_id: int | None = None
    source_kind: str
    file_name: str
    status: str
    attempt_count: int
    max_attempts: int
    file_hash: str | None = None
    passport_id: UUID | None = None
    last_error_code: str | None = None
    last_error: str | None = None
    discovered_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ImportPage(BaseModel):
    items: list[ImportJob]
    next_cursor: str | None = None


class ImportSessionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=180)


class ImportFileRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    source_kind: Literal["erp", "machines", "quality", "maintenance", "layout", "unknown"] = "unknown"
    mime_type: str | None = Field(default=None, max_length=160)
    size_bytes: int = Field(default=0, ge=0)
    file_hash: str | None = Field(default=None, min_length=8, max_length=64)


class ImportSessionFile(BaseModel):
    id: UUID
    file_name: str
    source_kind: str
    mime_type: str | None = None
    size_bytes: int
    file_hash: str | None = None
    status: str
    profile: dict[str, Any] = {}


class ImportSession(BaseModel):
    id: UUID
    site_id: int
    name: str
    status: str
    summary: dict[str, Any] = {}
    files: list[ImportSessionFile] = []
    created_at: datetime
    updated_at: datetime

class Incident(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; site_id: int; machine_id: int; machine_erp_ref: str | None = None
    production_order_id: str | None = None
    status: Literal["open", "reviewed", "closed"]
    severity: Literal["low", "medium", "high", "critical"]
    symptom: str; defect_type: str | None = None
    started_at: datetime; ended_at: datetime | None = None; created_at: datetime
    data_cutoff: datetime; confidence: Literal["low", "medium", "high"] | None = None
    # Additive read-only projection of the latest persisted human feedback.
    feedback_verdict: str | None = None
    origin: str = "quality"
    process_observations: list[dict[str, Any]] = Field(default_factory=list)

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


class IncidentPage(BaseModel):
    items: list[Incident]
    next_cursor: str | None = None

class FeedbackRequest(BaseModel):
    run_id: UUID | None = None
    verdict: str = Field(min_length=1, max_length=30)
    comment: str | None = Field(default=None, max_length=4000)

class FeedbackResponse(BaseModel):
    id: UUID; incident_id: UUID; verdict: str; comment: str | None = None


class MachineCreateInput(BaseModel):
    """Atelier press creation contract.

    ``erp_ref`` is deliberately optional: ERP identity can be mapped later.
    ``workshop_code`` remains mandatory for a newly created press, including
    when the press has not yet been imported into the ERP.
    """

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    workshop_code: str = Field(min_length=1, max_length=50)
    erp_ref: str | None = Field(default=None, min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    brand: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=100)


class MachinePatchInput(BaseModel):
    """Mutable press identity fields; lifecycle is changed by archive only."""

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    workshop_code: str | None = Field(default=None, min_length=1, max_length=50)
    erp_ref: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    brand: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=100)



class ShiftDefinition(BaseModel):
    model_config = ConfigDict(extra='forbid')
    number: int = Field(ge=1, le=32767)
    start: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    end: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')


class ShiftCalendarInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    timezone: str
    valid_from: date
    valid_to: date | None = None
    expected_version: int = Field(default=0, ge=0)
    shifts: list[ShiftDefinition] = Field(min_length=1, max_length=64)

    @model_validator(mode='after')
    def validate_calendar(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('unknown_timezone') from None
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValueError('invalid_calendar_period')
        if len({shift.number for shift in self.shifts}) != len(self.shifts):
            raise ValueError('duplicate_shift_number')
        return self


class ERPReplacement(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_row: int = Field(ge=1)
    declaration_id: UUID
    expected_revision: int = Field(ge=1)


class ERPConfirmInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    preview_version: int = Field(ge=1)
    create_machine_refs: list[str] = Field(default_factory=list, max_length=1000)
    replacements: list[ERPReplacement] = Field(default_factory=list, max_length=10000)
    new_identity_rows: list[int] = Field(default_factory=list, max_length=10000)


class ERPPreviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sheet_name: str | None = Field(default=None, max_length=100)
    confirmed_order_fields: list[str] = Field(default_factory=list, max_length=6)
    complete_order_refs: list[str] = Field(default_factory=list, max_length=10000)

    @model_validator(mode='after')
    def validate_fields(self):
        from ingest.erp_reader import ORDER_FIELDS
        if set(self.confirmed_order_fields) - ORDER_FIELDS:
            raise ValueError('unknown_order_field')
        return self

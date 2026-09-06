"""Production context uses production time and explicit knowledge revisions."""
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class CycleContext:
    site_id: int
    machine_id: int
    ended_at: datetime

@dataclass(frozen=True)
class DeclarationCandidate:
    id: str
    revision_id: str
    site_id: int
    machine_id: int
    order_ref: str
    start: datetime
    end: datetime
    bounds_source: str

@dataclass(frozen=True)
class MatchDecision:
    status: str
    declaration_id: str | None
    revision_id: str | None
    candidate_ids: list[str]
    confidence: float | None

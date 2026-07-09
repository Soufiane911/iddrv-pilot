"""Wire-compatible domain objects for deterministic investigations."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Evidence:
    id: str
    source_kind: str
    source_ref: str
    metric: str
    window: dict[str, str]
    observation: dict[str, Any]
    baseline: dict[str, Any] | None = None
    delta: float | None = None
    supports: bool = True
    excerpt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Hypothesis:
    cause_code: str
    label: str
    confidence: float
    supporting_evidence_ids: list[str] = field(default_factory=list)
    contradicting_evidence_ids: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    next_check: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Investigation:
    incident: dict[str, Any]
    evidence: list[Evidence]
    hypotheses: list[Hypothesis]
    data_quality: str = "sufficient"

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident": self.incident,
            "evidence": [item.to_dict() for item in self.evidence],
            "hypotheses": [item.to_dict() for item in self.hypotheses],
            "data_quality": self.data_quality,
        }


class InsufficientDataError(ValueError):
    """Raised when an investigation cannot be made without inventing evidence."""


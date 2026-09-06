"""Transport values; quality is never inferred from cycle reception."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class CycleEnvelope:
    event_id: str
    sequence: int
    raw: dict[str, Any]
    cycle_ended_at: datetime | None = None
    cycle_counter: int | None = None
    measurements: dict[str, Any] = field(default_factory=dict)
    rejection_reason: str | None = None


@dataclass(frozen=True)
class CyclePage:
    stream_id: str
    items: list[CycleEnvelope]
    next_cursor: str | None
    has_more: bool
    machine_id: str
    after: str | None = None


@dataclass(frozen=True)
class MachineConnection:
    id: UUID
    site_id: int
    machine_id: int
    base_url: str
    external_machine_id: str
    secret_ref: str | None
    poll_interval_s: int
    enabled: bool
    mapping_profile: str


@dataclass(frozen=True)
class CollectionResult:
    inserted_cycles: int = 0
    duplicates: int = 0
    rejected_events: int = 0
    cursor: str | None = None
    new_scoring_jobs: int = 0
    conflicts: int = 0
    state: str = 'idle'

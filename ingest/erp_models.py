"""Typed, lossless declarations; quantities and order context are independent."""
from dataclasses import asdict, dataclass, field
from datetime import datetime
from hashlib import sha256
import json
from typing import Any


def json_value(value):
    return json.loads(json.dumps(value, default=lambda item: item.isoformat() if isinstance(item, datetime) else str(item), ensure_ascii=False))


@dataclass
class ERPDeclaration:
    machine_ref: str
    order_ref: str
    shift_started_at: datetime
    shift_number: int
    order_type: str = ''
    tool_ref: str | None = None
    product_ref: str | None = None
    produced_parts: int | None = None
    good_parts: int | None = None
    scrap_parts: int | None = None
    cycle_count: int | None = None
    declared_scrap_rate: float | None = None
    declared_trs: float | None = None
    available_hours: float | None = None
    total_stop_hours: float | None = None
    cavities_actual: int | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)
    source_row: int = 0
    sheet_name: str = ''
    production_started_at: datetime | None = None
    production_ended_at: datetime | None = None
    bounds_origin: str = 'awaiting_context'
    calendar_version: int | None = None
    estimated_bounds: set[str] = field(default_factory=set)
    running_hours: float | None = None
    opening_hours: float | None = None
    cycle_time_s: float | None = None
    order_target_quantity: int | None = None
    order_status: str | None = None
    order_status_effective_at: datetime | None = None
    quality_lot_ref: str | None = None
    order_status_reason: str | None = None
    coverage_complete: bool | None = None
    provided_order_fields: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)

    def key(self, site_id: int, machine_id: int) -> str:
        payload = [site_id, machine_id, self.shift_started_at.isoformat(), self.shift_number, self.order_ref, self.order_type]
        return sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()

    def values(self) -> dict:
        value = asdict(self)
        value['provided_order_fields'] = sorted(self.provided_order_fields)
        value['estimated_bounds'] = sorted(self.estimated_bounds)
        return json_value(value)

    def fingerprint(self) -> str:
        value = self.values()
        # A calendar estimate is context, not a new ERP source observation.
        if value['bounds_origin'] == 'calendar':
            for bound in self.estimated_bounds:
                value[bound] = None
            value.update(bounds_origin='awaiting_context', calendar_version=None)
        for key in ('source_row', 'sheet_name', 'estimated_bounds'):
            value.pop(key)
        return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@dataclass
class ERPRowIssue:
    source_row: int
    code: str
    field: str | None
    message: str
    severity: str = "error"


@dataclass
class ERPReadResult:
    declarations: list[ERPDeclaration]
    issues: list[ERPRowIssue]
    sheet_name: str
    header_row: int
    sheets: list[str] = field(default_factory=list)


@dataclass
class ImportCommitResult:
    created: int = 0
    revised: int = 0
    unchanged: int = 0
    awaiting_context: int = 0
    new_machine_ids: list[int] = field(default_factory=list)

"""Repository boundary for diagnostics.

Rows are mappings so this works with psycopg dictionaries and with fixtures;
the SQL/API layer remains outside the diagnostic worker's ownership.
"""

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Protocol


Row = Mapping[str, object]


class DiagnosticRepository(Protocol):
    def cycles(self, machine_id: int | str, start: datetime, end: datetime) -> Iterable[Row]: ...
    def quality_checks(self, machine_id: int | str, start: datetime, end: datetime) -> Iterable[Row]: ...
    def operator_notes(self, machine_id: int | str, start: datetime, end: datetime) -> Iterable[Row]: ...


class InMemoryDiagnosticRepository:
    """Small repository useful for unit tests and local dry runs."""

    def __init__(self, *, cycles=(), quality_checks=(), operator_notes=()):
        self._cycles = list(cycles)
        self._quality = list(quality_checks)
        self._notes = list(operator_notes)

    @staticmethod
    def _in_window(row: Row, start: datetime, end: datetime) -> bool:
        value = row.get("timestamp", row.get("time"))
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return isinstance(value, datetime) and start <= value <= end

    def _select(self, rows, machine_id, start, end):
        return [r for r in rows if str(r.get("machine_id", r.get("machine_erp_ref", ""))) == str(machine_id) and self._in_window(r, start, end)]

    def cycles(self, machine_id, start, end): return self._select(self._cycles, machine_id, start, end)
    def quality_checks(self, machine_id, start, end): return self._select(self._quality, machine_id, start, end)
    def operator_notes(self, machine_id, start, end): return self._select(self._notes, machine_id, start, end)

"""PostgreSQL adapter for the deterministic diagnostic engine."""
from .repository import DiagnosticRepository
from ..db import get_connection

class PostgresDiagnosticRepository:
    def _rows(self, table, machine_id, start, end):
        columns = {"machine_cycles": "time, machine_id, scrap_flag, part_quality_status, defect_type, barrel_temp_zone2_c",
                   "quality_checks": "time, machine_id, defect_type, defect_count, production_order_id",
                   "operator_notes": "time, machine_id, note_id, note_text, production_order_id"}[table]
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT {columns} FROM {table} WHERE machine_id=%s AND time BETWEEN %s AND %s", (machine_id,start,end))
                names=[x.strip() for x in columns.split(',')]
                return [dict(zip(names,row)) for row in cur.fetchall()]
    def cycles(self, machine_id, start, end): return self._rows("machine_cycles",machine_id,start,end)
    def quality_checks(self, machine_id, start, end): return self._rows("quality_checks",machine_id,start,end)
    def operator_notes(self, machine_id, start, end): return self._rows("operator_notes",machine_id,start,end)

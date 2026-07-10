"""PostgreSQL adapter for the deterministic diagnostic engine."""
import os
import psycopg2
from .repository import DiagnosticRepository
from ..db import get_connection

class PostgresDiagnosticRepository:
    def __init__(self, db_url: str | None = None):
        self.db_url = db_url or os.getenv("DATABASE_URL")

    def _connection(self):
        return psycopg2.connect(self.db_url) if self.db_url else get_connection()

    def _rows(self, table, machine_id, start, end):
        # Keep this projection explicit: table names and columns are not user
        # controlled, while the values remain parameterized below.  The
        # deterministic engine can therefore compare process, quality and
        # context signals without ever fetching raw import files.
        columns = {
            "machine_cycles": (
                "time, machine_id, production_order_id, scrap_flag, "
                "part_quality_status, defect_type, quality_flag, "
                "cycle_time_s, dosing_time_s, injection_time_s, cooling_time_s, "
                "cushion_mm, switchover_pressure_bar, switchover_position, "
                "peak_pressure_bar, clamp_force_kn, mold_open_time_s, "
                "barrel_temp_zone1_c, barrel_temp_zone2_c, barrel_temp_zone3_c, "
                "mold_temperature_c, oil_temperature_c, energy_kwh"
            ),
            "quality_checks": (
                "time, machine_id, production_order_id, quality_check_id, "
                "sample_size, defect_count, defect_type, severity, "
                "measured_weight_g, target_weight_g, dimension_deviation_mm, "
                "visual_result, comment"
            ),
            "maintenance_events": (
                "time, machine_id, production_order_id, event_id, event_type, "
                "duration_min, severity, description"
            ),
            "operator_notes": (
                "time, machine_id, note_id, note_text, production_order_id, operator_id"
            ),
        }[table]
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT {columns} FROM {table} WHERE machine_id=%s AND time BETWEEN %s AND %s", (machine_id,start,end))
                names=[x.strip() for x in columns.split(',')]
                return [dict(zip(names,row)) for row in cur.fetchall()]
    def cycles(self, machine_id, start, end): return self._rows("machine_cycles",machine_id,start,end)
    def quality_checks(self, machine_id, start, end): return self._rows("quality_checks",machine_id,start,end)
    def maintenance_events(self, machine_id, start, end): return self._rows("maintenance_events",machine_id,start,end)
    def operator_notes(self, machine_id, start, end): return self._rows("operator_notes",machine_id,start,end)

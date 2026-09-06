"""PostgreSQL adapter for the deterministic diagnostic engine."""
import os
import psycopg2
from .repository import DiagnosticRepository
from ..db import get_connection

class PostgresDiagnosticRepository:
    def __init__(self, db_url: str | None = None, *, site_id=None, known_at=None):
        self.site_id, self.known_at = site_id, known_at
        self.context_snapshot = {"cycles": [], "known_at": known_at.isoformat() if known_at else None}
        self.db_url = db_url or os.getenv("API_DATABASE_URL") or os.getenv("DATABASE_URL")

    def _connection(self):
        return psycopg2.connect(self.db_url) if self.db_url else get_connection()

    def _rows(self, table, machine_id, start, end):
        # Keep this projection explicit: table names and columns are not user
        # controlled, while the values remain parameterized below.  The
        # deterministic engine can therefore compare process, quality and
        # context signals without ever fetching raw import files.
        columns = {
            "machine_cycles": (
                "time, machine_id, production_order_id, scrap_flag, source_event_id, context_cycle_id, "
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
                quality_filter = (
                    " AND COALESCE(data_quality_status,'valid')='valid'"
                    if table in {"machine_cycles", "quality_checks"}
                    else ""
                )
                cur.execute(
                    f"SELECT {columns} FROM {table} "
                    f"WHERE machine_id=%s AND time BETWEEN %s AND %s{quality_filter} ORDER BY time",
                    (machine_id, start, end),
                )
                names=[x.strip() for x in columns.split(',')]
                return [dict(zip(names,row)) for row in cur.fetchall()]
    def cycles(self, machine_id, start, end):
        rows = self._rows("machine_cycles",machine_id,start,end)
        return self._with_context(rows, machine_id, start, end)

    def _with_context(self, rows, machine_id, start, end):
        if self.site_id is None or self.known_at is None or not rows:
            return rows
        from datetime import timedelta
        from ..api.production_context import context_history
        with self._connection() as conn:
            snapshot = context_history(conn,site_id=self.site_id,machine_id=machine_id,start=start,
                end=end+timedelta(microseconds=1),known_at=self.known_at,limit=100000)
        if snapshot['truncated']:
            raise ValueError('investigation_context_window_too_large')
        by_key = {row['cycle_key']:row for row in snapshot['items']}
        declarations = {str(row['id']):row for row in snapshot['declarations']}
        accepted = []
        for row in rows:
            key = str(row['source_event_id']) if row['source_event_id'] else 'legacy:' + str(row['context_cycle_id'])
            context = by_key.get(key)
            if context is None:
                continue  # Received after the investigation knowledge cutoff.
            row = dict(row)
            declaration = declarations.get(str(context['revision_id']))
            if context['source_event_id']:
                row['production_order_id'] = declaration['production_order_id'] if declaration else None
            self.context_snapshot['cycles'].append(context)
            accepted.append(row)
        self.context_snapshot.setdefault('declarations',[]).extend(snapshot['declarations'])
        return accepted

    def comparable_baseline_cycles(self, machine_id, production_order_id, before, minimum):
        """Select the most specific healthy context with enough prior cycles."""
        columns = (
            "c.time, c.machine_id, c.production_order_id, c.scrap_flag, c.source_event_id, c.context_cycle_id, "
            "c.part_quality_status, c.defect_type, c.quality_flag, "
            "c.cycle_time_s, c.dosing_time_s, c.injection_time_s, c.cooling_time_s, "
            "c.cushion_mm, c.switchover_pressure_bar, c.switchover_position, "
            "c.peak_pressure_bar, c.clamp_force_kn, c.mold_open_time_s, "
            "c.barrel_temp_zone1_c, c.barrel_temp_zone2_c, c.barrel_temp_zone3_c, "
            "c.mold_temperature_c, c.oil_temperature_c, c.energy_kwh"
        )
        names = [item.strip().removeprefix("c.") for item in columns.split(",")]
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT po.product_ref,po.tool_ref,po.material_ref,m.site_id
                       FROM machines m
                       LEFT JOIN production_orders po
                         ON po.machine_id=m.id AND po.site_id=m.site_id AND po.id=%s
                       WHERE m.id=%s""",
                    (production_order_id, machine_id),
                )
                context = cur.fetchone()
                if context is None:
                    return []
                product_ref, tool_ref, material_ref, site_id = context
                levels = []
                if product_ref is not None and tool_ref is not None and material_ref is not None:
                    levels.append((
                        "AND po.product_ref IS NOT DISTINCT FROM %s "
                        "AND po.tool_ref IS NOT DISTINCT FROM %s "
                        "AND po.material_ref IS NOT DISTINCT FROM %s",
                        [product_ref, tool_ref, material_ref],
                    ))
                if tool_ref is not None and material_ref is not None:
                    levels.append((
                        "AND po.tool_ref IS NOT DISTINCT FROM %s "
                        "AND po.material_ref IS NOT DISTINCT FROM %s",
                        [tool_ref, material_ref],
                    ))
                if product_ref is not None:
                    levels.append(("AND po.product_ref IS NOT DISTINCT FROM %s", [product_ref]))
                levels.append(("", []))

                for clause, context_args in levels:
                    cur.execute(
                        f"""SELECT {columns}
                            FROM machine_cycles c
                            LEFT JOIN production_orders po
                              ON po.site_id=c.order_site_id AND po.id=c.production_order_id
                            WHERE c.machine_id=%s AND c.time<%s
                              AND (c.order_site_id=%s OR c.order_site_id IS NULL)
                              AND COALESCE(c.data_quality_status,'valid')='valid'
                              {clause}
                            ORDER BY c.time DESC
                            LIMIT 2000""",
                        [machine_id, before, site_id, *context_args],
                    )
                    rows = cur.fetchall()
                    if len(rows) >= minimum:
                        return self._with_context([dict(zip(names, row)) for row in reversed(rows)],machine_id,rows[-1][0],rows[0][0])
        return []

    def quality_checks(self, machine_id, start, end): return self._rows("quality_checks",machine_id,start,end)
    def maintenance_events(self, machine_id, start, end): return self._rows("maintenance_events",machine_id,start,end)
    def operator_notes(self, machine_id, start, end): return self._rows("operator_notes",machine_id,start,end)

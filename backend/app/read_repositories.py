"""Bounded, site-scoped read queries for the v1 supervision API."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any

from .db import get_connection


BUCKETS = {"minute": "1 minute", "hour": "1 hour"}


def _cursor_offset(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(0, int(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()))
    except (ValueError, TypeError):
        return 0


def next_cursor(offset: int, page_size: int, count: int) -> str | None:
    if count < page_size:
        return None
    return base64.urlsafe_b64encode(str(offset + page_size).encode()).decode().rstrip("=")


def _numeric(value):
    return float(value) if value is not None else None


def list_sites(*, site_ids: tuple[int, ...] | None = None, limit: int = 100, cursor: str | None = None):
    offset = _cursor_offset(cursor)
    clauses, args = [], []
    if site_ids is not None:
        if not site_ids:
            return [], None
        clauses.append("s.id = ANY(%s)")
        args.append(list(site_ids))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    sql = f"""SELECT s.id,s.name,s.timezone,COUNT(DISTINCT m.id) AS machine_count,
                     COUNT(DISTINCT i.id) FILTER (WHERE i.status='open') AS open_incident_count,
                     MAX(COALESCE(j.completed_at, p.imported_at)) AS last_import_at
              FROM sites s
              LEFT JOIN machines m ON m.site_id=s.id
              LEFT JOIN incidents i ON i.site_id=s.id
              LEFT JOIN import_passports p ON p.site_id=s.id AND p.status='completed'
              LEFT JOIN import_jobs j ON j.site_id=s.id AND j.status='completed'
              {where}
              GROUP BY s.id,s.name,s.timezone ORDER BY s.id LIMIT %s OFFSET %s"""
    args.extend([limit + 1, offset])
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall()
    items = [
        {
            "id": r[0], "name": r[1], "timezone": r[2],
            "machine_count": r[3], "open_incident_count": r[4], "last_import_at": r[5],
        }
        for r in rows[:limit]
    ]
    return items, next_cursor(offset, limit, len(rows))


def list_lines(site_id: int, *, limit: int = 100, cursor: str | None = None):
    offset = _cursor_offset(cursor)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT l.id,l.site_id,l.code,l.name,COUNT(m.id)
                   FROM production_lines l LEFT JOIN machines m ON m.line_id=l.id
                   WHERE l.site_id=%s GROUP BY l.id,l.site_id,l.code,l.name
                   ORDER BY l.id LIMIT %s OFFSET %s""",
                (site_id, limit + 1, offset),
            )
            rows = cur.fetchall()
    items = [{"id": r[0], "site_id": r[1], "name": r[3], "code": r[2], "machine_count": r[4]} for r in rows[:limit]]
    return items, next_cursor(offset, limit, len(rows))


def _machine_query(site_id: int | None = None, machine_id: int | None = None):
    clauses, args = [], []
    if site_id is not None:
        clauses.append("m.site_id=%s"); args.append(site_id)
    if machine_id is not None:
        clauses.append("m.id=%s"); args.append(machine_id)
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", args


def list_machines(site_id: int, *, limit: int = 100, cursor: str | None = None):
    offset = _cursor_offset(cursor)
    where, args = _machine_query(site_id=site_id)
    sql = f"""SELECT m.id,m.site_id,m.line_id,m.erp_ref,m.name,m.brand,m.model,
                     ml.x,ml.y,ml.z,ml.rotation_deg,ml.display_order,
                     CASE WHEN latest.time IS NULL THEN 'offline'
                          WHEN site_cutoff.time-latest.time > INTERVAL '1 hour' THEN 'stopped'
                          WHEN latest.scrap_flag THEN 'warning' ELSE 'running' END AS status
              FROM machines m LEFT JOIN machine_layouts ml ON ml.machine_id=m.id
              LEFT JOIN LATERAL (SELECT c.time,c.scrap_flag FROM machine_cycles c
                                 WHERE c.machine_id=m.id ORDER BY c.time DESC LIMIT 1) latest ON TRUE
              LEFT JOIN LATERAL (
                  SELECT MAX(c.time) AS time
                  FROM machine_cycles c
                  JOIN machines site_machine ON site_machine.id=c.machine_id
                  WHERE site_machine.site_id=m.site_id
              ) site_cutoff ON TRUE
              {where} ORDER BY m.id LIMIT %s OFFSET %s"""
    args.extend([limit + 1, offset])
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args); rows = cur.fetchall()
    items = []
    for row in rows[:limit]:
        items.append({
            "id": row[0], "site_id": row[1], "line_id": row[2], "erp_ref": row[3], "name": row[4],
            "brand": row[5], "model": row[6], "status": row[12],
            "layout": {"x": _numeric(row[7]) or 0, "y": _numeric(row[8]) or 0, "z": _numeric(row[9]) or 0,
                       "rotation_deg": _numeric(row[10]) or 0, "display_order": row[11]} if row[7] is not None else None,
        })
    return items, next_cursor(offset, limit, len(rows))


def get_machine(machine_id: int):
    where, args = _machine_query(machine_id=machine_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT m.id,m.site_id,m.line_id,m.erp_ref,m.name,m.brand,m.model,
                          ml.x,ml.y,ml.z,ml.rotation_deg,ml.display_order,
                          CASE WHEN latest.time IS NULL OR NOW()-latest.time > INTERVAL '1 hour' THEN 'offline'
                               WHEN NOW()-latest.time > INTERVAL '15 minutes' THEN 'stopped'
                               WHEN latest.scrap_flag THEN 'warning' ELSE 'running' END AS status
                   FROM machines m LEFT JOIN machine_layouts ml ON ml.machine_id=m.id
                   LEFT JOIN LATERAL (SELECT c.time,c.scrap_flag FROM machine_cycles c
                                      WHERE c.machine_id=m.id ORDER BY c.time DESC LIMIT 1) latest ON TRUE""" + where,
                args,
            )
            row = cur.fetchone()
    if row is None:
        return None
    return {
        "id": row[0], "site_id": row[1], "line_id": row[2], "erp_ref": row[3], "name": row[4],
        "brand": row[5], "model": row[6], "status": row[12],
        "layout": {"x": _numeric(row[7]) or 0, "y": _numeric(row[8]) or 0, "z": _numeric(row[9]) or 0,
                    "rotation_deg": _numeric(row[10]) or 0, "display_order": row[11]} if row[7] is not None else None,
    }


def machine_status(machine_id: int, as_of: datetime):
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """WITH latest AS (
                     SELECT c.time,c.production_order_id,c.data_quality_status
                     FROM machine_cycles c WHERE c.machine_id=%s AND c.time<=%s ORDER BY c.time DESC LIMIT 1
                   ), recent AS (
                     SELECT COUNT(*)::int AS n,
                            AVG(c.scrap_flag::int)::float AS scrap_rate
                     FROM machine_cycles c WHERE c.machine_id=%s AND c.time>%s-INTERVAL '24 hours' AND c.time<=%s
                   ) SELECT latest.time,latest.production_order_id,latest.data_quality_status,recent.n,recent.scrap_rate
                   FROM latest CROSS JOIN recent""",
                (machine_id, as_of, machine_id, as_of, as_of),
            )
            row = cur.fetchone()
    if row is None:
        return {"machine_id": machine_id, "status": "offline", "as_of": as_of, "freshness_s": None,
                "last_cycle_at": None, "current_order_id": None, "cycle_count_24h": 0, "scrap_rate_24h": None,
                "data_quality_status": None}
    last_at, order_id, quality_status, count, scrap_rate = row
    freshness = max(0.0, (as_of - last_at).total_seconds()) if last_at else None
    if freshness is None or freshness > 3600:
        status = "offline"
    elif freshness > 900:
        status = "stopped"
    elif scrap_rate is not None and scrap_rate >= 0.10:
        status = "warning"
    else:
        status = "running"
    return {"machine_id": machine_id, "status": status, "as_of": as_of, "freshness_s": freshness,
            "last_cycle_at": last_at, "current_order_id": order_id, "cycle_count_24h": count or 0,
            "scrap_rate_24h": _numeric(scrap_rate), "data_quality_status": quality_status}


def raw_cycles(machine_id: int, as_of: datetime, limit: int = 20):
    """Return the latest raw process cycles at or before ``as_of``.

    The inner descending query keeps the bounded window causal and recent; the
    outer ordering is chronological for the HDT feature builder.
    """
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """WITH bounded_cycles AS (
                     SELECT c.time,
                            c.cycle_counter,
                            c.source_row_hash,
                            m.erp_ref AS machine_erp_ref,
                            c.cycle_time_s,
                            c.dosing_time_s,
                            c.injection_time_s,
                            c.cooling_time_s,
                            c.cushion_mm,
                            c.switchover_position AS switchover_position_mm,
                            c.switchover_pressure_bar,
                            c.peak_pressure_bar,
                            c.clamp_force_kn,
                            c.mold_temperature_c,
                            c.barrel_temp_zone1_c,
                            c.barrel_temp_zone2_c,
                            c.barrel_temp_zone3_c,
                            c.oil_temperature_c,
                            c.energy_kwh
                     FROM machine_cycles c
                     JOIN machines m ON m.id=c.machine_id
                     WHERE c.machine_id=%s AND c.time<=%s
                     ORDER BY c.time DESC, c.cycle_counter DESC NULLS LAST, c.source_row_hash DESC NULLS LAST
                     LIMIT %s
                   )
                   SELECT time,machine_erp_ref,cycle_time_s,dosing_time_s,
                          injection_time_s,cooling_time_s,cushion_mm,
                          switchover_position_mm,switchover_pressure_bar,
                          peak_pressure_bar,clamp_force_kn,mold_temperature_c,
                          barrel_temp_zone1_c,barrel_temp_zone2_c,
                          barrel_temp_zone3_c,oil_temperature_c,energy_kwh
                   FROM bounded_cycles
                   ORDER BY time ASC, cycle_counter ASC NULLS LAST, source_row_hash ASC NULLS LAST""",
                (machine_id, as_of, limit),
            )
            rows = cur.fetchall()
    return [
        {
            "timestamp": row[0],
            "machine_erp_ref": row[1],
            "cycle_time_s": _numeric(row[2]),
            "dosing_time_s": _numeric(row[3]),
            "injection_time_s": _numeric(row[4]),
            "cooling_time_s": _numeric(row[5]),
            "cushion_mm": _numeric(row[6]),
            "switchover_position_mm": _numeric(row[7]),
            "switchover_pressure_bar": _numeric(row[8]),
            "peak_pressure_bar": _numeric(row[9]),
            "clamp_force_kn": _numeric(row[10]),
            "mold_temperature_c": _numeric(row[11]),
            "barrel_temp_zone1_c": _numeric(row[12]),
            "barrel_temp_zone2_c": _numeric(row[13]),
            "barrel_temp_zone3_c": _numeric(row[14]),
            "oil_temperature_c": _numeric(row[15]),
            "energy_kwh": _numeric(row[16]),
        }
        for row in rows
    ]


def timeline(machine_id: int, start: datetime, end: datetime, bucket: str):
    if bucket not in {"minute", "hour", "shift", "order"}:
        raise ValueError("bucket must be one of minute, hour, shift or order")
    if bucket in BUCKETS:
        bucket_expr = "time_bucket(%s::interval,c.time)"
        bucket_args: list[Any] = [BUCKETS[bucket]]
        group = "1"
        order_select = "MIN(c.production_order_id)"
    elif bucket == "shift":
        # A shift is a logical bucket; its earliest cycle is used as the
        # stable timestamp while all metrics remain aggregated.
        bucket_expr = "MIN(c.time)"
        bucket_args = []
        group = "c.shift_id"
        order_select = "MIN(c.production_order_id)"
    else:
        bucket_expr = "MIN(c.time)"
        bucket_args = []
        group = "c.production_order_id"
        order_select = "c.production_order_id"
    sql = f"""SELECT {bucket_expr} AS bucket, COUNT(*)::int,
                     AVG(c.cycle_time_s)::float,
                     AVG(c.scrap_flag::int)::float,
                     AVG(c.barrel_temp_zone2_c)::float,
                     {order_select}
              FROM machine_cycles c
              WHERE c.machine_id=%s AND c.time>=%s AND c.time<=%s
              GROUP BY {group}
              ORDER BY bucket LIMIT 1000"""
    args = bucket_args + [machine_id, start, end]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args); rows = cur.fetchall()
    return [{"bucket": r[0], "cycle_count": r[1], "avg_cycle_time_s": _numeric(r[2]),
             "scrap_rate": _numeric(r[3]), "avg_zone2_temperature_c": _numeric(r[4]),
             "production_order_id": r[5]} for r in rows]


def quality(machine_id: int, start: datetime, end: datetime):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*)::int,COALESCE(SUM(q.defect_count),0)::int,
                          COALESCE(SUM(CASE WHEN lower(COALESCE(q.part_quality_status,''))='scrap' OR q.defect_count>0 THEN 1 ELSE 0 END),0)::int
                   FROM quality_checks q WHERE q.machine_id=%s AND q.time>=%s AND q.time<=%s""",
                (machine_id, start, end),
            )
            total, defects, scrap = cur.fetchone()
            cur.execute(
                """SELECT COUNT(*)::int,COALESCE(SUM(c.scrap_flag::int),0)::int,
                          COUNT(*) FILTER (WHERE c.defect_type IS NOT NULL)::int
                   FROM machine_cycles c WHERE c.machine_id=%s AND c.time>=%s AND c.time<=%s""",
                (machine_id, start, end),
            )
            cycle_total, cycle_scrap, cycle_defects = cur.fetchone()
            cur.execute(
                """SELECT COALESCE(q.defect_type,'unknown'),COUNT(*)::int
                   FROM quality_checks q WHERE q.machine_id=%s AND q.time>=%s AND q.time<=%s
                   GROUP BY COALESCE(q.defect_type,'unknown') ORDER BY COUNT(*) DESC""",
                (machine_id, start, end),
            )
            defect_rows = cur.fetchall()
            cur.execute(
                """SELECT COALESCE(c.defect_type,'unknown'),COUNT(*)::int
                   FROM machine_cycles c WHERE c.machine_id=%s AND c.time>=%s AND c.time<=%s
                   GROUP BY COALESCE(c.defect_type,'unknown') ORDER BY COUNT(*) DESC LIMIT 100""",
                (machine_id, start, end),
            )
            cycle_defect_rows = cur.fetchall()
    total = total or 0
    defects = defects or 0
    scrap = scrap or 0
    cycle_total = cycle_total or 0
    cycle_scrap = cycle_scrap or 0
    cycle_defects = cycle_defects or 0
    if cycle_total:
        # Cycle aggregates are the denominator for a rate; quality samples
        # are sparse and must not make a scrap count exceed 100 percent.
        total = cycle_total
        scrap = cycle_scrap
        defects = max(defects, cycle_defects or cycle_scrap)
    elif total == 0:
        total = cycle_total
        defects = cycle_defects or cycle_scrap
    if not defect_rows and cycle_defects:
        # Keep this aggregate bounded and useful even when no dedicated
        # quality-check export was supplied for a machine.
        defect_rows = cycle_defect_rows
    summaries = [{"defect_type": r[0], "type": r[0], "count": r[1]} for r in defect_rows]
    return {"machine_id": machine_id, "from": start, "to": end, "total_checks": total,
            "total_defects": defects, "scrap_count": scrap, "scrap_rate": scrap / total if total else None,
            "by_defect": summaries, "total": total, "good": max(0, total - scrap), "scrap": scrap,
            "defects": summaries}


def list_imports(*, site_ids: tuple[int, ...] | None = None, site_id: int | None = None, limit: int = 100, cursor: str | None = None):
    offset = _cursor_offset(cursor)
    clauses, args = [], []
    allowed = site_ids
    if site_id is not None:
        clauses.append("j.site_id=%s"); args.append(site_id)
    elif allowed is not None:
        if not allowed:
            return [], None
        clauses.append("j.site_id=ANY(%s)"); args.append(list(allowed))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    sql = f"""SELECT j.id,j.site_id,j.source_kind,j.file_name,j.status,j.attempt_count,j.max_attempts,
                     j.file_hash,j.passport_id,j.last_error_code,j.last_error,j.discovered_at,j.started_at,j.completed_at
              FROM import_jobs j{where} ORDER BY j.discovered_at DESC LIMIT %s OFFSET %s"""
    args.extend([limit + 1, offset])
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args); rows = cur.fetchall()
    items = [{"id": r[0], "site_id": r[1], "source_kind": r[2], "file_name": r[3], "status": r[4],
              "attempt_count": r[5], "max_attempts": r[6], "file_hash": r[7], "passport_id": r[8],
              "last_error_code": r[9], "last_error": r[10], "discovered_at": r[11], "started_at": r[12],
              "completed_at": r[13]} for r in rows[:limit]]
    return items, next_cursor(offset, limit, len(rows))


def get_import(import_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT j.id,j.site_id,j.source_kind,j.file_name,j.status,j.attempt_count,j.max_attempts,
                          j.file_hash,j.passport_id,j.last_error_code,j.last_error,j.discovered_at,j.started_at,j.completed_at
                   FROM import_jobs j WHERE j.id=%s""", (str(import_id),))
            row = cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "site_id": row[1], "source_kind": row[2], "file_name": row[3], "status": row[4],
            "attempt_count": row[5], "max_attempts": row[6], "file_hash": row[7], "passport_id": row[8],
            "last_error_code": row[9], "last_error": row[10], "discovered_at": row[11], "started_at": row[12],
            "completed_at": row[13]}

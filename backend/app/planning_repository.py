"""Persistence boundary for the multi-press workshop planning model."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import json
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from .db import get_connection


class PlanningNotFound(RuntimeError):
    pass


class PlanningConflict(RuntimeError):
    pass


class PlanningValidation(ValueError):
    pass


def normalize_order_number(value: str) -> tuple[str, str]:
    """Return the display value and a case-insensitive comparison value.

    Deliberately only trims and folds case: ``000123`` must never become
    ``123``.
    """
    if not isinstance(value, str):
        raise PlanningValidation("order_number_required")
    display = value.strip()
    if not display:
        raise PlanningValidation("order_number_required")
    if len(display) > 50:
        raise PlanningValidation("order_number_too_long")
    # Keep this identical to PostgreSQL's lower() used by the database check.
    return display, display.lower()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PlanningValidation("timezone_required")
    return value


def _period(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    start, end = _aware(start), _aware(end)
    if start >= end:
        raise PlanningValidation("slot_period_must_be_positive")
    return start, end


def _validate_allocations(allocations: list[dict[str, Any]]) -> None:
    if not allocations:
        raise PlanningValidation("at_least_one_press_required")
    machine_ids = [int(item["machine_id"]) for item in allocations]
    if any(machine_id <= 0 for machine_id in machine_ids):
        raise PlanningValidation("machine_id_invalid")
    if len(machine_ids) != len(set(machine_ids)):
        raise PlanningConflict("duplicate_machine_allocation")
    for item in allocations:
        _period(item["starts_at"], item["ends_at"])


def _audit(cur, *, site_id: int, actor_id: str | None, action: str,
           entity_type: str, entity_id, before=None, after=None) -> None:
    cur.execute(
        """INSERT INTO planning_audit_events
           (site_id, actor_id, action, entity_type, entity_id, before_state, after_state)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (site_id, actor_id, action, entity_type, entity_id,
         Json(before, dumps=lambda value: json.dumps(value, default=str)) if before is not None else None,
         Json(after, dumps=lambda value: json.dumps(value, default=str)) if after is not None else None),
    )


def _active_site(cur, site_id: int) -> None:
    # Every planning lifecycle check takes the site lock first. Archive
    # operations use the same order, so a planning write cannot pass an
    # archive boundary between validation and its child-row writes.
    cur.execute("SELECT status FROM sites WHERE id=%s FOR UPDATE", (site_id,))
    site = cur.fetchone()
    if site is None:
        raise PlanningNotFound("site_not_found")
    if (site["status"] if isinstance(site, dict) else site[0]) == "archived":
        raise PlanningConflict("site_archived")


def _active_machine(cur, site_id: int, machine_id: int) -> None:
    _active_site(cur, site_id)
    cur.execute(
        "SELECT status FROM machines WHERE site_id=%s AND id=%s FOR UPDATE",
        (site_id, machine_id),
    )
    machine = cur.fetchone()
    if not machine:
        raise PlanningNotFound("machine_not_found")
    if (machine["status"] if isinstance(machine, dict) else machine[0]) == "archived":
        raise PlanningConflict("machine_archived")


def _machine_ids_in_site(cur, site_id: int, machine_ids: list[int]) -> None:
    _active_site(cur, site_id)
    # Lock child identities in a deterministic order after the site lock.
    # This avoids both JOIN-lock ambiguity and opposite multi-press lock
    # orders between concurrent planning requests.
    cur.execute(
        """SELECT id,status FROM machines
           WHERE site_id=%s AND id=ANY(%s)
           ORDER BY id FOR UPDATE""",
        (site_id, machine_ids),
    )
    rows = cur.fetchall()
    found = {int(row["id"] if isinstance(row, dict) else row[0]) for row in rows}
    missing = sorted(set(machine_ids) - found)
    if missing:
        raise PlanningNotFound("machine_not_found")
    if any((row["status"] if isinstance(row, dict) else row[1]) == "archived" for row in rows):
        raise PlanningConflict("machine_archived")


def _insert_slot(cur, *, site_id: int, allocation_id, machine_id: int,
                 starts_at: datetime, ends_at: datetime, note: str | None,
                 actor_id: str | None) -> dict:
    cur.execute(
        """INSERT INTO planning_slots
           (site_id, allocation_id, machine_id, starts_at, ends_at, note, created_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s)
           RETURNING id, site_id, allocation_id, machine_id, starts_at, ends_at,
                     note, status, row_version, created_at, updated_at""",
        (site_id, allocation_id, machine_id, starts_at, ends_at, note, actor_id),
    )
    return dict(cur.fetchone())


def _integrity_conflict(exc: psycopg2.IntegrityError) -> PlanningConflict:
    name = getattr(getattr(exc, "diag", None), "constraint_name", None)
    if name == "work_orders_site_id_order_number_normalized_key":
        return PlanningConflict("work_order_already_exists")
    if name == "work_order_allocations_site_id_work_order_id_machine_id_key":
        return PlanningConflict("allocation_already_exists")
    if name == "planning_slots_machine_time_no_overlap":
        return PlanningConflict("press_slot_conflict")
    return PlanningConflict("planning_constraint_conflict")


def create_work_order(*, site_id: int, order_number: str,
                      allocations: list[dict[str, Any]], note: str | None = None,
                      actor_id: str | None = None) -> dict:
    display, normalized = normalize_order_number(order_number)
    _validate_allocations(allocations)
    try:
        with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            _machine_ids_in_site(cur, site_id, [int(item["machine_id"]) for item in allocations])
            cur.execute(
                """INSERT INTO work_orders
                   (site_id, order_number, order_number_normalized, note, created_by)
                   VALUES (%s,%s,%s,%s,%s)
                   RETURNING id, site_id, order_number, order_number_normalized, status,
                             note, created_at, updated_at""",
                (site_id, display, normalized, note, actor_id),
            )
            order = dict(cur.fetchone())
            result_allocations = []
            for item in allocations:
                cur.execute(
                    """INSERT INTO work_order_allocations
                       (site_id, work_order_id, machine_id, created_by)
                       VALUES (%s,%s,%s,%s)
                       RETURNING id, site_id, work_order_id, machine_id, created_at""",
                    (site_id, order["id"], int(item["machine_id"]), actor_id),
                )
                allocation = dict(cur.fetchone())
                slot = _insert_slot(
                    cur, site_id=site_id, allocation_id=allocation["id"],
                    machine_id=int(item["machine_id"]), starts_at=item["starts_at"],
                    ends_at=item["ends_at"], note=item.get("note"), actor_id=actor_id,
                )
                allocation["slot"] = slot
                result_allocations.append(allocation)
            order["allocations"] = result_allocations
            # OF creation is also a reconciliation event for gateway receipts
            # that arrived before the planning UI was configured.
            from .source_repository import replay_pending_receipts_in_transaction
            replay_pending_receipts_in_transaction(cur, site_id=site_id, order_number=display)
            _audit(cur, site_id=site_id, actor_id=actor_id, action="created",
                   entity_type="work_order", entity_id=order["id"], after=order)
            return order
    except psycopg2.IntegrityError as exc:
        raise _integrity_conflict(exc) from exc


def get_work_order(work_order_id, *, site_id: int | None = None) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        if site_id is None:
            cur.execute("SELECT * FROM work_orders WHERE id=%s", (work_order_id,))
        else:
            cur.execute("SELECT * FROM work_orders WHERE id=%s AND site_id=%s", (work_order_id, site_id))
        row = cur.fetchone()
        return dict(row) if row else None


def get_allocation(allocation_id) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT a.*, w.order_number, w.order_number_normalized, w.status AS work_order_status
               FROM work_order_allocations a JOIN work_orders w
                 ON w.id=a.work_order_id AND w.site_id=a.site_id
               WHERE a.id=%s""",
            (allocation_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def create_allocation(*, work_order_id, machine_id: int, slots: list[dict[str, Any]] | None = None,
                      actor_id: str | None = None) -> dict:
    slots = slots or []
    if machine_id <= 0:
        raise PlanningValidation("machine_id_invalid")
    for item in slots:
        _period(item["starts_at"], item["ends_at"])
    try:
        with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM work_orders WHERE id=%s FOR UPDATE", (work_order_id,))
            order = cur.fetchone()
            if not order:
                raise PlanningNotFound("work_order_not_found")
            site_id = int(order["site_id"])
            _machine_ids_in_site(cur, site_id, [machine_id])
            cur.execute(
                """INSERT INTO work_order_allocations(site_id, work_order_id, machine_id, created_by)
                   VALUES (%s,%s,%s,%s)
                   RETURNING id, site_id, work_order_id, machine_id, created_at""",
                (site_id, work_order_id, machine_id, actor_id),
            )
            allocation = dict(cur.fetchone())
            allocation["slots"] = [
                _insert_slot(cur, site_id=site_id, allocation_id=allocation["id"], machine_id=machine_id,
                             starts_at=item["starts_at"], ends_at=item["ends_at"], note=item.get("note"),
                             actor_id=actor_id)
                for item in slots
            ]
            from .source_repository import replay_pending_receipts_in_transaction
            replay_pending_receipts_in_transaction(cur, site_id=site_id, machine_id=machine_id)
            _audit(cur, site_id=site_id, actor_id=actor_id, action="allocation_created",
                   entity_type="allocation", entity_id=allocation["id"], after=allocation)
            return allocation
    except psycopg2.IntegrityError as exc:
        raise _integrity_conflict(exc) from exc


def create_slot(*, allocation_id, site_id: int, machine_id: int, starts_at: datetime,
                ends_at: datetime, note: str | None = None,
                actor_id: str | None = None) -> dict:
    _period(starts_at, ends_at)
    try:
        with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT site_id, machine_id FROM work_order_allocations
                   WHERE id=%s FOR UPDATE""",
                (allocation_id,),
            )
            allocation = cur.fetchone()
            if not allocation:
                raise PlanningNotFound("allocation_not_found")
            _active_machine(cur, site_id, machine_id)
            if int(allocation["site_id"]) != site_id or int(allocation["machine_id"]) != machine_id:
                raise PlanningConflict("allocation_scope_mismatch")
            slot = _insert_slot(cur, site_id=site_id, allocation_id=allocation_id,
                                machine_id=machine_id, starts_at=starts_at, ends_at=ends_at,
                                note=note, actor_id=actor_id)
            _audit(cur, site_id=site_id, actor_id=actor_id, action="created",
                   entity_type="planning_slot", entity_id=slot["id"], after=slot)
            return slot
    except psycopg2.IntegrityError as exc:
        raise _integrity_conflict(exc) from exc


def get_slot(slot_id) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT ps.*, a.work_order_id, w.order_number, w.order_number_normalized,
                      w.status AS work_order_status, m.name AS machine_name, m.erp_ref
               FROM planning_slots ps
               JOIN work_order_allocations a ON a.id=ps.allocation_id AND a.site_id=ps.site_id
               JOIN work_orders w ON w.id=a.work_order_id AND w.site_id=a.site_id
               JOIN machines m ON m.id=ps.machine_id AND m.site_id=ps.site_id
               WHERE ps.id=%s""",
            (slot_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def update_slot(*, slot_id, row_version: int, starts_at: datetime | None = None,
                ends_at: datetime | None = None, note: str | None = None,
                note_provided: bool = False, actor_id: str | None = None) -> dict:
    if row_version < 1:
        raise PlanningValidation("row_version_invalid")
    if starts_at is not None:
        _aware(starts_at)
    if ends_at is not None:
        _aware(ends_at)
    try:
        with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM planning_slots WHERE id=%s FOR UPDATE", (slot_id,))
            before = cur.fetchone()
            if not before:
                raise PlanningNotFound("slot_not_found")
            before = dict(before)
            _active_machine(cur, int(before["site_id"]), int(before["machine_id"]))
            if before["status"] == "cancelled":
                raise PlanningConflict("slot_cancelled")
            if int(before["row_version"]) != row_version:
                raise PlanningConflict("stale_row_version")
            start = starts_at if starts_at is not None else before["starts_at"]
            end = ends_at if ends_at is not None else before["ends_at"]
            _period(start, end)
            new_note = note if note_provided else before["note"]
            cur.execute(
                """UPDATE planning_slots
                   SET starts_at=%s, ends_at=%s, note=%s, row_version=row_version+1, updated_at=now()
                   WHERE id=%s AND row_version=%s
                   RETURNING *""",
                (start, end, new_note, slot_id, row_version),
            )
            after = dict(cur.fetchone())
            _audit(cur, site_id=int(before["site_id"]), actor_id=actor_id, action="updated",
                   entity_type="planning_slot", entity_id=slot_id, before=before, after=after)
            return after
    except psycopg2.IntegrityError as exc:
        raise _integrity_conflict(exc) from exc


def cancel_slot(*, slot_id, row_version: int, actor_id: str | None = None) -> dict:
    if row_version < 1:
        raise PlanningValidation("row_version_invalid")
    try:
        with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM planning_slots WHERE id=%s FOR UPDATE", (slot_id,))
            before = cur.fetchone()
            if not before:
                raise PlanningNotFound("slot_not_found")
            before = dict(before)
            _active_machine(cur, int(before["site_id"]), int(before["machine_id"]))
            if int(before["row_version"]) != row_version:
                raise PlanningConflict("stale_row_version")
            if before["status"] == "cancelled":
                return before
            cur.execute(
                """UPDATE planning_slots SET status='cancelled', row_version=row_version+1, updated_at=now()
                   WHERE id=%s AND row_version=%s RETURNING *""",
                (slot_id, row_version),
            )
            after = dict(cur.fetchone())
            _audit(cur, site_id=int(before["site_id"]), actor_id=actor_id, action="cancelled",
                   entity_type="planning_slot", entity_id=slot_id, before=before, after=after)
            return after
    except psycopg2.IntegrityError as exc:
        raise _integrity_conflict(exc) from exc


def _week_bounds(site_timezone: str, week_start: date) -> tuple[datetime, datetime]:
    try:
        zone = ZoneInfo(site_timezone)
    except ZoneInfoNotFoundError as exc:
        raise PlanningValidation("site_timezone_invalid") from exc
    if week_start.weekday() != 0:
        raise PlanningValidation("week_start_must_be_monday")
    start = datetime.combine(week_start, time.min, tzinfo=zone)
    return start.astimezone(timezone.utc), (start + timedelta(days=7)).astimezone(timezone.utc)


def list_planning_week(*, site_id: int, week_start: date) -> dict:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, timezone, status FROM sites WHERE id=%s", (site_id,))
        site = cur.fetchone()
        if not site:
            raise PlanningNotFound("site_not_found")
        if site["status"] == "archived":
            raise PlanningConflict("site_archived")
        utc_start, utc_end = _week_bounds(site["timezone"], week_start)
        cur.execute(
            """SELECT ps.id, ps.site_id, ps.allocation_id, ps.machine_id, ps.starts_at, ps.ends_at,
                      ps.note, ps.status, ps.row_version, ps.created_at, ps.updated_at,
                      w.id AS work_order_id, w.order_number, w.order_number_normalized,
                      w.status AS work_order_status, m.name AS machine_name, m.workshop_code, m.erp_ref,
                      COALESCE(c.cycles_received, 0)::int AS cycles_received,
                      c.first_cycle_at, c.last_cycle_at, c.last_cycle_counter,
                      c.observed_order_number,
                      gateway.last_seen_at AS source_last_success_at,
                      CASE WHEN ps.status = 'cancelled' THEN 'cancelled'
                           WHEN w.status = 'completed' THEN 'completed'
                           WHEN c.cycles_received > 0 THEN 'in_progress'
                           ELSE 'planned' END AS planning_status,
                      CASE WHEN gateway.receipts_received > 0 THEN 'receiving'
                           WHEN gateway.mapping_count = 0 THEN 'not_configured'
                           WHEN gateway.last_seen_at IS NOT NULL
                                AND now() - gateway.last_seen_at > INTERVAL '15 minutes' THEN 'interrupted'
                           ELSE 'no_cycle' END AS collection_status,
                      CASE WHEN erp.declaration_count = 0 THEN 'pending'
                           WHEN erp.has_warnings THEN 'incomplete'
                           ELSE 'matched' END AS erp_status,
                      erp.recorded_at AS erp_imported_at,
                      erp.revision_number AS erp_version,
                      erp.declaration_id AS erp_declaration_id,
                      erp.revision_id AS erp_revision_id,
                      erp.produced_parts AS produced_parts_erp,
                      erp.good_parts AS good_parts_erp,
                      erp.scrap_parts AS scrap_parts_erp,
                      erp.cycle_count AS cycles_erp,
                      erp.order_status AS erp_order_status,
                      totals.produced_parts AS order_total_produced_parts,
                      totals.good_parts AS order_total_good_parts,
                      totals.scrap_parts AS order_total_scrap_parts,
                      totals.cycle_count AS order_total_cycles,
                      totals.produced_parts AS erp_total_produced_parts,
                      totals.good_parts AS erp_total_good_parts,
                      totals.scrap_parts AS erp_total_scrap_parts,
                      totals.cycle_count AS erp_total_cycles
               FROM planning_slots ps
               JOIN work_order_allocations a ON a.id=ps.allocation_id AND a.site_id=ps.site_id
               JOIN work_orders w ON w.id=a.work_order_id AND w.site_id=a.site_id
               JOIN machines m ON m.id=ps.machine_id AND m.site_id=ps.site_id
               LEFT JOIN LATERAL (
                   SELECT count(*) AS cycles_received, min(c.time) AS first_cycle_at,
                          max(c.time) AS last_cycle_at,
                          (array_agg(c.cycle_counter ORDER BY c.time DESC))[1] AS last_cycle_counter,
                          (array_agg(COALESCE(w.order_number, c.production_order_id) ORDER BY c.time DESC))[1] AS observed_order_number
                   FROM machine_cycles c
                   LEFT JOIN work_orders w ON w.id=c.work_order_id AND w.site_id=ps.site_id
                   WHERE c.machine_id=ps.machine_id
                     AND c.work_order_allocation_id=ps.allocation_id
                     AND c.time >= ps.starts_at AND c.time < ps.ends_at
               ) c ON true
               LEFT JOIN LATERAL (
                   SELECT count(DISTINCT r.id) FILTER (WHERE r.work_order_allocation_id=ps.allocation_id) AS receipts_received,
                          count(DISTINCT mapping.id) AS mapping_count,
                          max(src.last_seen_at) AS last_seen_at
                   FROM site_sources src
                   LEFT JOIN source_machine_mappings mapping
                     ON mapping.source_id=src.id AND mapping.site_id=ps.site_id
                    AND mapping.machine_id=ps.machine_id
                    AND mapping.valid_from < ps.ends_at
                    AND (mapping.valid_to IS NULL OR mapping.valid_to > ps.starts_at)
                   LEFT JOIN cycle_event_receipts r
                     ON r.source_id=src.id AND r.site_id=ps.site_id
                    AND r.external_machine_id=mapping.external_machine_id
                    -- Mapping validity is evaluated at the receipt's source
                    -- time, not merely at the slot boundaries.
                    AND mapping.valid_from <= r.occurred_at
                    AND (mapping.valid_to IS NULL OR mapping.valid_to > r.occurred_at)
                    AND r.occurred_at >= ps.starts_at AND r.occurred_at < ps.ends_at
                   WHERE src.site_id=ps.site_id AND src.status='active'
               ) gateway ON true
               LEFT JOIN LATERAL (
                   SELECT count(*)::int AS declaration_count,
                          (array_agg(d.id ORDER BY r.recorded_at DESC, d.id DESC))[1] AS declaration_id,
                          (array_agg(r.id ORDER BY r.recorded_at DESC, r.id DESC))[1] AS revision_id,
                          max(r.revision_number) AS revision_number,
                          max(r.recorded_at) AS recorded_at,
                          sum(r.produced_parts) AS produced_parts,
                          sum(r.good_parts) AS good_parts,
                          sum(r.scrap_parts) AS scrap_parts,
                          sum(r.cycle_count) AS cycle_count,
                          bool_or(jsonb_array_length(COALESCE(r.warnings, '[]'::jsonb)) > 0) AS has_warnings,
                          (
                              SELECT por.values->>'order_status'
                                FROM production_order_revisions por
                               WHERE por.site_id=ps.site_id
                                 AND lower(btrim(por.production_order_id))=w.order_number_normalized
                               ORDER BY por.recorded_at DESC, por.id DESC LIMIT 1
                          ) AS order_status
                     FROM erp_declarations d
                     JOIN erp_declaration_revisions r
                       ON r.id=d.current_revision_id AND r.declaration_id=d.id
                    WHERE d.site_id=ps.site_id AND d.machine_id=ps.machine_id
                      AND lower(btrim(d.production_order_id))=w.order_number_normalized
                      AND d.superseded_by IS NULL
               ) erp ON true
               LEFT JOIN LATERAL (
                   SELECT sum(r.produced_parts) AS produced_parts,
                          sum(r.good_parts) AS good_parts,
                          sum(r.scrap_parts) AS scrap_parts,
                          sum(r.cycle_count) AS cycle_count
                     FROM erp_declarations d
                     JOIN erp_declaration_revisions r
                       ON r.id=d.current_revision_id AND r.declaration_id=d.id
                    WHERE d.site_id=ps.site_id
                      AND lower(btrim(d.production_order_id))=w.order_number_normalized
                      AND d.superseded_by IS NULL
               ) totals ON true
               WHERE ps.site_id=%s AND ps.starts_at < %s AND ps.ends_at > %s
               ORDER BY ps.starts_at, m.name NULLS LAST, w.order_number, ps.id""",
            (site_id, utc_end, utc_start),
        )
        items = [dict(row) for row in cur.fetchall()]
    for item in items:
        # Collection is derived from the site source/mapping/receipt journal;
        # legacy machine_connections are deliberately not authoritative here.
        item["source_state"] = item["collection_status"]
        item["source_last_success_at"] = item.get("source_last_success_at")
    return {
        "site_id": site_id,
        "timezone": site["timezone"],
        "week_start": week_start,
        "week_end": week_start + timedelta(days=7),
        "items": items,
    }

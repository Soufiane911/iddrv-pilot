"""Persistence boundary for site gateway sources and cycle push receipts.

Gateway pushes deliberately do not use the user session.  The source id plus
its one-time-issued credential identify the tenant; no site id from an event is
trusted.  Receipts are committed even when the cycle read model cannot be
populated yet. Materialisation requires a historical source mapping, a known
planning OF and its OF-presse allocation; all other receipts remain pending.
Gateway pushes use a nullable receipt anchor and planning identity columns on
``machine_cycles``; the legacy polling journal remains intact. Quality
columns remain NULL unless a future source contract explicitly supplies those
values.
"""

from __future__ import annotations

import hashlib
import json
import math
import secrets
from datetime import datetime, timezone
from numbers import Real
from typing import Any
from uuid import UUID

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from .db import get_connection
from .security import hash_password, verify_password


class SourceNotFound(RuntimeError):
    pass


class SourceConflict(RuntimeError):
    pass


class InvalidSourceCredential(RuntimeError):
    pass


class SourceForbidden(RuntimeError):
    pass


class EventPayloadConflict(RuntimeError):
    pass


def canonical_payload_hash(payload: dict[str, Any]) -> str:
    """Hash the complete canonical JSON payload, not a selected business field."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_order_number(value: Any) -> str | None:
    """Return only a comparison key; the raw OF remains in the receipt payload."""
    if value is None:
        return None
    result = str(value).strip().casefold()
    return result or None


def _raw_order_number(payload: dict[str, Any]) -> Any:
    # ``work_order`` is the public canonical name.  The aliases make the
    # gateway tolerant of existing press adapters without changing the value.
    for key in ("work_order", "of_number", "production_order_id", "order_number", "of"):
        if key in payload:
            return payload[key]
    return None


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _public_source(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in ("id", "site_id", "kind", "name", "status", "last_seen_at", "created_at") if key in row}


def list_sources(*, site_id: int) -> list[dict[str, Any]]:
    """List source metadata only; credentials are never returned or inferred."""
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT id,site_id,kind,name,status,last_seen_at,created_at,updated_at
                 FROM site_sources WHERE site_id=%s ORDER BY created_at DESC,id""",
            (site_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def create_source(*, site_id: int, name: str) -> dict[str, Any]:
    clean_name = " ".join(name.split())
    if not clean_name:
        raise ValueError("source_name_required")
    secret = secrets.token_urlsafe(32)
    with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id,status FROM sites WHERE id=%s FOR SHARE", (site_id,))
        site = cur.fetchone()
        if site is None:
            raise SourceNotFound("site_not_found")
        if site["status"] == "archived":
            raise SourceConflict("site_archived")
        try:
            cur.execute(
                """INSERT INTO site_sources(site_id,kind,name)
                   VALUES (%s,'gateway_push',%s)
                   RETURNING id,site_id,kind,name,status,last_seen_at,created_at""",
                (site_id, clean_name),
            )
        except psycopg2.errors.UniqueViolation as exc:
            raise SourceConflict("active_source_already_exists") from exc
        source = dict(cur.fetchone())
        cur.execute(
            """INSERT INTO site_source_credentials(source_id,site_id,secret_hash)
               VALUES (%s,%s,%s)""",
            (source["id"], site_id, hash_password(secret)),
        )
    # The plaintext is intentionally only present in this return value.
    return {**_public_source(source), "secret": secret}


def _source_site(source_id: UUID | str, cur) -> int:
    cur.execute(
        """SELECT s.site_id,sites.status AS site_status
           FROM site_sources s JOIN sites ON sites.id=s.site_id WHERE s.id=%s""",
        (str(source_id),),
    )
    row = cur.fetchone()
    if row is None:
        raise SourceNotFound("source_not_found")
    if (row["site_status"] if isinstance(row, dict) else row[1]) == "archived":
        raise SourceForbidden("site_archived")
    return int(row["site_id"] if isinstance(row, dict) else row[0])


def source_site(source_id: UUID | str) -> int:
    with get_connection() as conn, conn.cursor() as cur:
        return _source_site(source_id, cur)


def rotate_source_credential(*, source_id: UUID | str) -> dict[str, Any]:
    secret = secrets.token_urlsafe(32)
    with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT s.site_id,sites.status AS site_status
               FROM site_sources s JOIN sites ON sites.id=s.site_id
               WHERE s.id=%s FOR UPDATE""",
            (str(source_id),),
        )
        source = cur.fetchone()
        if source is None:
            raise SourceNotFound("source_not_found")
        if source["site_status"] == "archived":
            raise SourceForbidden("site_archived")
        cur.execute(
            "UPDATE site_source_credentials SET revoked_at=now() WHERE source_id=%s AND revoked_at IS NULL",
            (str(source_id),),
        )
        cur.execute(
            """INSERT INTO site_source_credentials(source_id,site_id,secret_hash)
               VALUES (%s,%s,%s) RETURNING id,created_at""",
            (str(source_id), source["site_id"], hash_password(secret)),
        )
        credential = dict(cur.fetchone())
    return {"id": credential["id"], "source_id": source_id, "created_at": credential["created_at"], "secret": secret}


def authenticate_source(*, source_id: UUID | str, secret: str) -> dict[str, Any]:
    """Authenticate without ever returning the stored hash.

    Unknown ids/secrets are 401-equivalent.  A known but disabled/revoked source
    is distinct so the API can return 403 and operators can see the difference.
    """
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT s.id,s.site_id,s.kind,s.name,s.status,c.secret_hash,sites.status AS site_status
               FROM site_sources s
               JOIN sites ON sites.id=s.site_id
               LEFT JOIN site_source_credentials c
                 ON c.source_id=s.id AND c.revoked_at IS NULL
               WHERE s.id=%s""",
            (str(source_id),),
        )
        row = cur.fetchone()
    if row is None or not row["secret_hash"] or not verify_password(secret, row["secret_hash"]):
        raise InvalidSourceCredential("invalid_source_credential")
    if row["site_status"] != "active":
        raise SourceForbidden("site_archived")
    if row["status"] != "active":
        raise SourceForbidden("source_not_active")
    return {key: row[key] for key in ("id", "site_id", "kind", "name", "status")}


def _mapping_for_event(cur, source_id: str, external_machine_id: str, occurred_at: datetime):
    cur.execute(
        """SELECT mapping.id,mapping.machine_id,mapping.site_id,mapping.valid_from,mapping.valid_to,
                      machines.status AS machine_status, sites.status AS site_status
           FROM source_machine_mappings mapping
           JOIN machines ON machines.id=mapping.machine_id AND machines.site_id=mapping.site_id
           JOIN sites ON sites.id=mapping.site_id
           WHERE mapping.source_id=%s AND mapping.external_machine_id=%s
             AND mapping.valid_from <= %s AND (mapping.valid_to IS NULL OR mapping.valid_to > %s)
           ORDER BY mapping.valid_from DESC LIMIT 1""",
        (source_id, external_machine_id, occurred_at, occurred_at),
    )
    return cur.fetchone()


def _number(payload: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    parameters = payload.get("process_parameters") or payload.get("parameters") or {}
    if isinstance(parameters, dict):
        for name in names:
            if name in parameters:
                return parameters[name]
    return None


_PROCESS_FIELDS = {
    "cycle_counter": ("cycle_counter", "counter", "cycle_count"),
    "cycle_time_s": ("cycle_time_s",),
    "dosing_time_s": ("dosing_time_s",),
    "injection_time_s": ("injection_time_s",),
    "cooling_time_s": ("cooling_time_s",),
    "cushion_mm": ("cushion_mm",),
    "switchover_pressure_bar": ("switchover_pressure_bar",),
    "switchover_position": ("switchover_position", "switchover_position_mm"),
    "peak_pressure_bar": ("peak_pressure_bar",),
    "clamp_force_kn": ("clamp_force_kn",),
    "energy_kwh": ("energy_kwh",),
}


_PROCESS_LIMITS = {
    "cycle_counter": (0, 9223372036854775807),
    "cycle_time_s": (0, 9999.999), "dosing_time_s": (0, 9999.999),
    "injection_time_s": (0, 9999.999), "cooling_time_s": (0, 9999.999),
    "cushion_mm": (0, 999.999), "switchover_pressure_bar": (0, 999999.99),
    "switchover_position": (0, 999.999), "peak_pressure_bar": (0, 999999.99),
    "clamp_force_kn": (0, 999999.99), "energy_kwh": (0, 999999.9999),
}


def _invalid_process_field(payload: dict[str, Any]) -> str | None:
    """Validate values before psycopg sees them.

    A bad parameter is a source-data problem, not a reason to roll back the
    durable receipt. ``None`` means the field was absent or valid.
    """
    for field, names in _PROCESS_FIELDS.items():
        value = _number(payload, *names)
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError):
            return field
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(numeric):
            return field
        lower, upper = _PROCESS_LIMITS[field]
        if numeric < lower or numeric > upper:
            return field
    return None


def _set_receipt_pending(cur, receipt_id, *, reason: str, machine_id=None, work_order_id=None) -> None:
    cur.execute(
        """UPDATE cycle_event_receipts
           SET state='pending',pending_reason=%s,machine_id=%s,work_order_id=%s,
               work_order_allocation_id=NULL,production_order_id=NULL,materialized_at=NULL
           WHERE id=%s""",
        (reason, machine_id, work_order_id, receipt_id),
    )


def _set_receipt_rejected(cur, receipt_id, *, reason: str, machine_id=None) -> None:
    """Make a receipt terminal when its historical target cannot return."""
    cur.execute(
        """UPDATE cycle_event_receipts
           SET state='rejected',pending_reason=%s,machine_id=%s,work_order_id=NULL,
               work_order_allocation_id=NULL,production_order_id=NULL,materialized_at=NULL
           WHERE id=%s""",
        (reason, machine_id, receipt_id),
    )


def _materialize_receipt(cur, receipt: dict[str, Any], *, terminal_archived: bool = False) -> bool:
    """Materialise a receipt against the planning OF and OF-presse allocation.

    A live gateway push still reports an archived target as forbidden. Replay
    is different: an old receipt must not roll back the OF/import transaction;
    it is terminally rejected and the following receipts are still replayed.
    """
    occurred_at = _as_datetime(receipt["occurred_at"])
    payload = dict(receipt["payload"])
    mapping = _mapping_for_event(cur, str(receipt["source_id"]), receipt["external_machine_id"], occurred_at)
    if mapping is None:
        _set_receipt_pending(cur, receipt["id"], reason="machine_not_mapped")
        return False
    if mapping["site_status"] != "active":
        if terminal_archived:
            _set_receipt_rejected(cur, receipt["id"], reason="site_archived", machine_id=mapping["machine_id"])
            return False
        raise SourceForbidden("site_archived")
    if mapping["machine_status"] == "archived":
        if terminal_archived:
            _set_receipt_rejected(cur, receipt["id"], reason="machine_archived", machine_id=mapping["machine_id"])
            return False
        raise SourceForbidden("machine_archived")

    invalid_field = _invalid_process_field(payload)
    if invalid_field:
        cur.execute(
            """UPDATE cycle_event_receipts
               SET state='rejected',pending_reason=%s,machine_id=%s,materialized_at=NULL
               WHERE id=%s""",
            (f"invalid_process_parameter:{invalid_field}", mapping["machine_id"], receipt["id"]),
        )
        return False

    raw_order = _raw_order_number(payload)
    normalized_order = normalize_order_number(raw_order)
    if normalized_order is None:
        _set_receipt_pending(cur, receipt["id"], reason="work_order_missing", machine_id=mapping["machine_id"])
        return False

    cur.execute(
        """SELECT id,order_number FROM work_orders
           WHERE site_id=%s AND order_number_normalized=%s AND status <> 'cancelled'
           LIMIT 1""",
        (mapping["site_id"], normalized_order),
    )
    order = cur.fetchone()
    if order is None:
        _set_receipt_pending(cur, receipt["id"], reason="work_order_unknown", machine_id=mapping["machine_id"])
        return False

    cur.execute(
        """SELECT id FROM work_order_allocations
           WHERE site_id=%s AND work_order_id=%s AND machine_id=%s
           LIMIT 1""",
        (mapping["site_id"], order["id"], mapping["machine_id"]),
    )
    allocation = cur.fetchone()
    if allocation is None:
        _set_receipt_pending(
            cur, receipt["id"], reason="allocation_missing", machine_id=mapping["machine_id"], work_order_id=order["id"]
        )
        return False

    # Gateway cycles have no quality declaration. Keep both quality columns
    # NULL rather than turning a cycle count into an invented good part.
    cur.execute(
        """INSERT INTO machine_cycles
           (time,machine_id,production_order_id,order_site_id,work_order_id,
            work_order_allocation_id,cycle_counter,cycle_time_s,dosing_time_s,
            injection_time_s,cooling_time_s,cushion_mm,switchover_pressure_bar,
            switchover_position,peak_pressure_bar,clamp_force_kn,energy_kwh,
            good_parts,scrap_flag,raw_data,source_row_hash,cycle_event_receipt_id)
           VALUES (%s,%s,NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,NULL,%s,%s,%s)
           ON CONFLICT DO NOTHING""",
        (
            occurred_at, mapping["machine_id"], mapping["site_id"], order["id"], allocation["id"],
            _number(payload, "cycle_counter", "counter", "cycle_count"),
            _number(payload, "cycle_time_s"), _number(payload, "dosing_time_s"),
            _number(payload, "injection_time_s"), _number(payload, "cooling_time_s"),
            _number(payload, "cushion_mm"), _number(payload, "switchover_pressure_bar"),
            _number(payload, "switchover_position", "switchover_position_mm"),
            _number(payload, "peak_pressure_bar"), _number(payload, "clamp_force_kn"),
            _number(payload, "energy_kwh"), Json(payload), None, receipt["id"],
        ),
    )
    cur.execute(
        """UPDATE cycle_event_receipts
           SET state='materialized',pending_reason=NULL,machine_id=%s,
               work_order_id=%s,work_order_allocation_id=%s,production_order_id=NULL,
               materialized_at=COALESCE(materialized_at,now())
           WHERE id=%s""",
        (mapping["machine_id"], order["id"], allocation["id"], receipt["id"]),
    )
    return True


def map_source_machine(*, source_id: UUID | str, external_machine_id: str, machine_id: int, effective_at: datetime | None = None) -> dict[str, Any]:
    clean_external = external_machine_id.strip()
    if not clean_external:
        raise ValueError("external_machine_id_required")
    supplied_effective_at = effective_at is not None
    start = _as_datetime(effective_at or datetime.now(timezone.utc))
    with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT site_id,status FROM site_sources WHERE id=%s FOR UPDATE", (str(source_id),))
        source = cur.fetchone()
        if source is None:
            raise SourceNotFound("source_not_found")
        if source["status"] != "active":
            raise SourceConflict("source_not_active")
        site_id = int(source["site_id"])
        cur.execute(
            "SELECT m.id,m.status,s.status AS site_status FROM machines m JOIN sites s ON s.id=m.site_id WHERE m.id=%s AND m.site_id=%s",
            (machine_id, site_id),
        )
        machine = cur.fetchone()
        if machine is None:
            raise SourceConflict("machine_not_in_source_site")
        if machine["site_status"] == "archived" or machine["status"] == "archived":
            raise SourceConflict("machine_archived")

        # For the first mapping, pending events are evidence that the operator
        # is validating an identity that already existed. Let that mapping
        # cover those receipts; otherwise a default ``now`` interval would
        # strand every event received before the operator configured the map.
        if not supplied_effective_at:
            cur.execute(
                "SELECT COUNT(*) AS count FROM source_machine_mappings WHERE source_id=%s AND external_machine_id=%s",
                (str(source_id), clean_external),
            )
            if int(cur.fetchone()["count"]) == 0:
                cur.execute(
                    """SELECT min(occurred_at) AS first_pending
                       FROM cycle_event_receipts
                       WHERE source_id=%s AND external_machine_id=%s AND state='pending'""",
                    (str(source_id), clean_external),
                )
                first_pending = cur.fetchone()["first_pending"]
                if first_pending is not None and first_pending < start:
                    start = first_pending

        # Close the interval containing the effective instant. This preserves
        # historical mappings while making the current identity unambiguous.
        cur.execute(
            """SELECT id,valid_from,valid_to FROM source_machine_mappings
               WHERE source_id=%s AND external_machine_id=%s
                 AND valid_from < %s AND (valid_to IS NULL OR valid_to > %s)
               FOR UPDATE""",
            (str(source_id), clean_external, start, start),
        )
        previous = cur.fetchone()
        old_end = previous["valid_to"] if previous else None
        if previous:
            cur.execute("UPDATE source_machine_mappings SET valid_to=%s WHERE id=%s", (start, previous["id"]))
        try:
            cur.execute(
                """INSERT INTO source_machine_mappings
                   (source_id,site_id,external_machine_id,machine_id,valid_from,valid_to)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   RETURNING id,source_id,site_id,external_machine_id,machine_id,valid_from,valid_to""",
                (str(source_id), site_id, clean_external, machine_id, start, old_end),
            )
        except psycopg2.errors.UniqueViolation as exc:
            raise SourceConflict("source_mapping_conflict") from exc
        mapping = dict(cur.fetchone())

        cur.execute(
            """SELECT * FROM cycle_event_receipts
               WHERE source_id=%s AND external_machine_id=%s AND state='pending'
                 AND occurred_at >= %s AND (%s IS NULL OR occurred_at < %s)
               ORDER BY occurred_at,id FOR UPDATE""",
            (str(source_id), clean_external, start, old_end, old_end),
        )
        replayed = 0
        for receipt in cur.fetchall():
            # A historical mapping may point at a press archived after the
            # event arrived. Reject only that receipt; never abort the ERP or
            # planning transaction, and continue with the remaining queue.
            if _materialize_receipt(cur, dict(receipt), terminal_archived=True):
                replayed += 1
    return {**mapping, "replayed_count": replayed}


def ingest_cycle_event(*, source: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    # Repository callers (not only FastAPI) may pass datetime/UUID instances.
    # Store one deterministic JSON representation in the receipt.
    payload = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
    source_id = str(source["id"])
    occurred_at = _as_datetime(payload["occurred_at"])
    event_id = str(payload["event_id"]).strip()
    external_machine_id = str(payload["external_machine_id"]).strip()
    if not event_id:
        raise ValueError("event_id_required")
    if not external_machine_id:
        raise ValueError("external_machine_id_required")
    payload = {**payload, "event_id": event_id, "external_machine_id": external_machine_id}
    payload_hash = canonical_payload_hash(payload)
    with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Re-check under a row lock after credential authentication. This
        # closes the archive-vs-ingestion race and prevents a stale source
        # object from writing a receipt for an archived site.
        cur.execute(
            """SELECT src.status AS source_status, sites.status AS site_status
                  FROM site_sources src JOIN sites ON sites.id=src.site_id
                 WHERE src.id=%s FOR SHARE""",
            (source_id,),
        )
        source_state = cur.fetchone()
        if source_state is None:
            raise InvalidSourceCredential("invalid_source_credential")
        if source_state["site_status"] != "active":
            raise SourceForbidden("site_archived")
        if source_state["source_status"] != "active":
            raise SourceForbidden("source_not_active")
        cur.execute(
            """INSERT INTO cycle_event_receipts
               (source_id,site_id,event_id,external_machine_id,occurred_at,payload_hash,payload)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (source_id,event_id) DO NOTHING
               RETURNING *""",
            (source_id, source["site_id"], event_id, external_machine_id, occurred_at, payload_hash, Json(payload)),
        )
        inserted = cur.fetchone()
        if inserted is None:
            cur.execute(
                "SELECT * FROM cycle_event_receipts WHERE source_id=%s AND event_id=%s FOR UPDATE",
                (source_id, event_id),
            )
            existing = dict(cur.fetchone())
            if existing["payload_hash"] != payload_hash:
                raise EventPayloadConflict("event_id_payload_mismatch")
            cur.execute("UPDATE site_sources SET last_seen_at=now(),updated_at=now() WHERE id=%s", (source_id,))
            return {"status_code": 200, "state": existing["state"], "duplicate": True, "receipt": existing}

        receipt = dict(inserted)
        materialized = _materialize_receipt(cur, receipt)
        cur.execute("UPDATE site_sources SET last_seen_at=now(),updated_at=now() WHERE id=%s", (source_id,))
        cur.execute("SELECT * FROM cycle_event_receipts WHERE id=%s", (receipt["id"],))
        saved = dict(cur.fetchone())
    return {
        "status_code": 201 if materialized else 202,
        "state": saved["state"],
        "duplicate": False,
        "receipt": saved,
    }


def replay_pending_receipts_in_transaction(cur, *, site_id: int, order_number: str | None = None,
                                            machine_id: int | None = None) -> int:
    """Replay durable receipts after an OF/allocation/ERP write.

    This cursor-level hook lets ERP workers call the same reconciliation path
    before committing their transaction. It is intentionally idempotent: a
    materialised cycle is protected by the receipt anchor and pending rows are
    re-evaluated using the exact source mapping and allocation rules.
    """
    clauses = ["r.site_id=%s", "r.state='pending'"]
    args: list[Any] = [site_id]
    if machine_id is not None:
        clauses.append("r.machine_id=%s")
        args.append(machine_id)
    if order_number is not None:
        clauses.append("lower(btrim(COALESCE(r.payload->>'work_order', r.payload->>'of_number', r.payload->>'production_order_id', r.payload->>'order_number', r.payload->>'of'))) = lower(btrim(%s))")
        args.append(order_number)
    cur.execute(
        f"SELECT r.* FROM cycle_event_receipts r WHERE {' AND '.join(clauses)} ORDER BY r.occurred_at,r.id FOR UPDATE",
        args,
    )
    replayed = 0
    for row in cur.fetchall():
        # A historical mapping may point at a press archived after the event
        # arrived. Reject only that receipt and continue the queue so an ERP
        # or planning transaction is never rolled back by it.
        if _materialize_receipt(cur, dict(row), terminal_archived=True):
            replayed += 1
    return replayed


def replay_pending_receipts(*, site_id: int, order_number: str | None = None,
                            machine_id: int | None = None) -> int:
    """Public post-ERP hook for workers that own a separate transaction."""
    with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        return replay_pending_receipts_in_transaction(
            cur, site_id=site_id, order_number=order_number, machine_id=machine_id
        )


def detected_machines(*, source_id: UUID | str) -> list[dict[str, Any]]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        _source_site(source_id, cur)
        cur.execute(
            """SELECT r.external_machine_id, min(r.received_at) AS first_seen_at,
                      max(r.received_at) AS last_seen_at,
                      (array_agg(COALESCE(r.payload->'work_order',r.payload->'of_number',r.payload->'production_order_id',r.payload->'of') ORDER BY r.received_at DESC))[1] AS last_work_order,
                      (array_agg(COALESCE(r.payload->'cycle_counter',r.payload->'counter',r.payload->'cycle_count') ORDER BY r.received_at DESC))[1] AS last_cycle_counter,
                      current_mapping.machine_id,
                      count(*) FILTER (WHERE r.state='pending') AS pending_count
               FROM cycle_event_receipts r
               LEFT JOIN LATERAL (
                   SELECT mapping.machine_id
                   FROM source_machine_mappings mapping
                   WHERE mapping.source_id=r.source_id
                     AND mapping.external_machine_id=r.external_machine_id
                     AND mapping.valid_to IS NULL
                   ORDER BY mapping.valid_from DESC LIMIT 1
               ) current_mapping ON TRUE
               WHERE r.source_id=%s
               GROUP BY r.external_machine_id,current_mapping.machine_id
               ORDER BY r.external_machine_id""",
            (str(source_id),),
        )
        return [dict(row) for row in cur.fetchall()]

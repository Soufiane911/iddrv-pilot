"""Persistence for site and press identity lifecycle.

Site and press rows are historical identities.  They are archived in place;
no lifecycle API in this module deletes them or their dependent history.
"""

from __future__ import annotations

import psycopg2
from psycopg2.extras import RealDictCursor

from .db import get_connection


class SiteConflict(RuntimeError):
    pass


class SiteNotFound(RuntimeError):
    pass


class MachineConflict(RuntimeError):
    pass


class MachineNotFound(RuntimeError):
    pass


def create_site(*, name: str, timezone: str, creator_id: str, creator_role: str) -> dict:
    clean_name = " ".join(name.split())
    clean_timezone = timezone.strip()
    if not clean_name:
        raise ValueError("site_name_required")
    with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        try:
            cur.execute(
                """INSERT INTO sites(name, timezone) VALUES (%s, %s)
                   RETURNING id, name, timezone, status""",
                (clean_name, clean_timezone),
            )
        except psycopg2.errors.UniqueViolation as exc:
            raise SiteConflict("site_name_already_exists") from exc
        site = dict(cur.fetchone())
        # The creator must immediately see the new tenant after the next
        # session refresh. Site-scoped roles remain the source of truth.
        role = creator_role if creator_role in {"viewer", "analyst", "supervisor", "admin"} else "supervisor"
        cur.execute(
            """INSERT INTO user_site_roles(user_id, site_id, role)
               VALUES (%s, %s, %s)
               ON CONFLICT (user_id, site_id) DO UPDATE SET role=EXCLUDED.role""",
            (creator_id, site["id"], role),
        )
        return site


def archive_site(site_id: int) -> None:
    """Archive a site and its presses without touching historical rows."""
    with get_connection() as conn, conn, conn.cursor() as cur:
        cur.execute("SELECT id, status FROM sites WHERE id=%s FOR UPDATE", (site_id,))
        row = cur.fetchone()
        if row is None:
            raise SiteNotFound("site_not_found")
        if row[1] == "archived":
            raise SiteConflict("site_already_archived")

        cur.execute(
            """UPDATE sites
                  SET status='archived', archived_at=COALESCE(archived_at, NOW()), updated_at=NOW()
                WHERE id=%s""",
            (site_id,),
        )
        # A site archive also stops new operational use of its presses.  The
        # rows themselves and every event/reference pointing to them remain.
        cur.execute(
            """UPDATE machines
                  SET status='archived', archived_at=COALESCE(archived_at, NOW()), updated_at=NOW()
                WHERE site_id=%s AND status <> 'archived'""",
            (site_id,),
        )
        # Archiving is an operational stop as well as a lifecycle change. Keep
        # source credentials and connection history, but make both ingestion
        # and the legacy polling worker refuse new work immediately.
        cur.execute(
            """UPDATE site_sources
                  SET status='disabled', updated_at=NOW()
                WHERE site_id=%s AND status <> 'disabled'""",
            (site_id,),
        )
        _close_active_mappings(cur, site_id=site_id)
        cur.execute(
            """UPDATE machine_connections
                  SET enabled=FALSE, state='disabled', next_poll_at=NOW(), updated_at=NOW()
                WHERE site_id=%s""",
            (site_id,),
        )


def delete_site(site_id: int) -> None:
    """Backward-compatible name for callers of the old DELETE endpoint.

    It is intentionally an archive now; no physical deletion is performed.
    """
    archive_site(site_id)


def _machine_conflict(exc: psycopg2.errors.UniqueViolation) -> MachineConflict:
    constraint = getattr(exc.diag, "constraint_name", "") or ""
    if "workshop" in constraint:
        return MachineConflict("workshop_code_already_exists")
    if "erp" in constraint:
        return MachineConflict("machine_erp_ref_already_exists")
    return MachineConflict("machine_identity_already_exists")


def create_machine(
    *,
    site_id: int,
    workshop_code: str,
    name: str,
    erp_ref: str | None = None,
    brand: str | None = None,
    model: str | None = None,
) -> dict:
    """Create a press from the Atelier, with ERP identity optional."""
    clean_code = " ".join(workshop_code.split())
    clean_name = " ".join(name.split())
    clean_erp_ref = erp_ref.strip() if erp_ref is not None else None
    clean_erp_ref = clean_erp_ref or None
    if not clean_code:
        raise ValueError("workshop_code_required")
    if not clean_name:
        raise ValueError("machine_name_required")

    with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, status FROM sites WHERE id=%s FOR UPDATE", (site_id,))
        site = cur.fetchone()
        if site is None:
            raise SiteNotFound("site_not_found")
        if site["status"] == "archived":
            raise SiteConflict("site_archived")

        # Explicit checks give stable conflict messages; the unique indexes
        # still protect the invariant under concurrent requests.
        cur.execute(
            "SELECT 1 FROM machines WHERE site_id=%s AND workshop_code=%s LIMIT 1",
            (site_id, clean_code),
        )
        if cur.fetchone() is not None:
            raise MachineConflict("workshop_code_already_exists")
        if clean_erp_ref is not None:
            cur.execute(
                "SELECT 1 FROM machines WHERE site_id=%s AND erp_ref=%s LIMIT 1",
                (site_id, clean_erp_ref),
            )
            if cur.fetchone() is not None:
                raise MachineConflict("machine_erp_ref_already_exists")

        try:
            cur.execute(
                """INSERT INTO machines(site_id, workshop_code, erp_ref, name, brand, model)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id, site_id, workshop_code, erp_ref, name, brand, model, status""",
                (site_id, clean_code, clean_erp_ref, clean_name, brand, model),
            )
        except psycopg2.errors.UniqueViolation as exc:
            raise _machine_conflict(exc) from exc
        return dict(cur.fetchone())


def update_machine(*, machine_id: int, **changes) -> dict:
    """Update editable press identity while holding the site lifecycle lock."""
    allowed = {"workshop_code", "erp_ref", "name", "brand", "model"}
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError("machine_field_not_allowed")
    if not changes:
        raise ValueError("machine_patch_empty")

    clean = dict(changes)
    if "workshop_code" in clean:
        clean["workshop_code"] = " ".join(str(clean["workshop_code"] or "").split())
        if not clean["workshop_code"]:
            raise ValueError("workshop_code_required")
    if "name" in clean:
        clean["name"] = " ".join(str(clean["name"] or "").split())
        if not clean["name"]:
            raise ValueError("machine_name_required")
    for field in ("erp_ref", "brand", "model"):
        if field in clean and clean[field] is not None:
            clean[field] = " ".join(str(clean[field]).split()) or None

    with get_connection() as conn, conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Identity rows are immutable, so the unkeyed lookup only discovers
        # the tenant. Lifecycle locks are then always acquired site first,
        # machine second; never rely on a JOIN lock order chosen by PostgreSQL.
        cur.execute("SELECT site_id FROM machines WHERE id=%s", (machine_id,))
        identity = cur.fetchone()
        if identity is None:
            raise MachineNotFound("machine_not_found")
        site_id = int(identity["site_id"] if isinstance(identity, dict) else identity[0])
        cur.execute("SELECT id,status FROM sites WHERE id=%s FOR UPDATE", (site_id,))
        site = cur.fetchone()
        if site is None:
            raise MachineNotFound("machine_not_found")
        if (site["status"] if isinstance(site, dict) else site[1]) == "archived":
            raise SiteConflict("site_archived")
        cur.execute(
            """SELECT id,site_id,workshop_code,erp_ref,name,brand,model,status
                 FROM machines WHERE id=%s AND site_id=%s FOR UPDATE""",
            (machine_id, site_id),
        )
        machine = cur.fetchone()
        if machine is None:
            raise MachineNotFound("machine_not_found")
        if (machine["status"] if isinstance(machine, dict) else machine[7]) == "archived":
            raise MachineConflict("machine_archived")
        assignments = ", ".join(f"{field}=%s" for field in clean)
        try:
            cur.execute(
                f"""UPDATE machines SET {assignments}, updated_at=NOW()
                     WHERE id=%s
                 RETURNING id,site_id,workshop_code,erp_ref,name,brand,model,status""",
                [*clean.values(), machine_id],
            )
        except psycopg2.errors.UniqueViolation as exc:
            raise _machine_conflict(exc) from exc
        return dict(cur.fetchone())


def machine_site_id(machine_id: int) -> int:
    """Return a press tenant without exposing whether it is archived."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT site_id FROM machines WHERE id=%s", (machine_id,))
        row = cur.fetchone()
    if row is None:
        raise MachineNotFound("machine_not_found")
    return int(row[0])


def _close_active_mappings(cur, *, site_id: int, machine_id: int | None = None) -> None:
    """End mapping intervals without making an invalid future interval."""
    clauses = ["site_id=%s", "valid_to IS NULL"]
    args: list[object] = [site_id]
    if machine_id is not None:
        clauses.append("machine_id=%s")
        args.append(machine_id)
    cur.execute(
        f"""UPDATE source_machine_mappings
                SET valid_to=CASE WHEN valid_from < NOW() THEN NOW()
                                  ELSE valid_from + INTERVAL '1 microsecond' END
              WHERE {' AND '.join(clauses)}""",
        args,
    )


def archive_machine(machine_id: int) -> None:
    """Archive a press and stop all current collection/mapping paths."""
    with get_connection() as conn, conn, conn.cursor() as cur:
        # Do not lock a joined relation: the planner is free to acquire the
        # two row locks in either order. Machine identity is append-only, so a
        # preliminary lookup safely gives us the tenant lock key.
        cur.execute("SELECT site_id FROM machines WHERE id=%s", (machine_id,))
        identity = cur.fetchone()
        if identity is None:
            raise MachineNotFound("machine_not_found")
        site_id = int(identity[0])
        cur.execute("SELECT id,status FROM sites WHERE id=%s FOR UPDATE", (site_id,))
        site = cur.fetchone()
        if site is None:
            raise MachineNotFound("machine_not_found")
        if site[1] == "archived":
            raise MachineConflict("site_archived")
        cur.execute(
            "SELECT id,site_id,status FROM machines WHERE id=%s AND site_id=%s FOR UPDATE",
            (machine_id, site_id),
        )
        row = cur.fetchone()
        if row is None:
            raise MachineNotFound("machine_not_found")
        if row[2] == "archived":
            raise MachineConflict("machine_already_archived")
        cur.execute(
            """UPDATE machines
                  SET status='archived', archived_at=COALESCE(archived_at, NOW()), updated_at=NOW()
                WHERE id=%s""",
            (machine_id,),
        )
        _close_active_mappings(cur, site_id=int(row[1]), machine_id=machine_id)
        cur.execute(
            """UPDATE machine_connections
                  SET enabled=FALSE, state='disabled', next_poll_at=NOW(), updated_at=NOW()
                WHERE site_id=%s AND machine_id=%s""",
            (int(row[1]), machine_id),
        )

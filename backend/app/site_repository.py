"""Tenant lifecycle persistence for production sites.

Sites share one PostgreSQL database.  Removing a site therefore removes all
rows owned by its ``site_id`` in one transaction while leaving other tenants
untouched.
"""

from __future__ import annotations

import psycopg2
from psycopg2.extras import RealDictCursor

from .db import get_connection


class SiteConflict(RuntimeError):
    pass


class SiteNotFound(RuntimeError):
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
                   RETURNING id, name, timezone""",
                (clean_name, clean_timezone),
            )
        except psycopg2.errors.UniqueViolation as exc:
            raise SiteConflict("site_name_already_exists") from exc
        site = dict(cur.fetchone())
        # The creator must immediately see the new tenant after the next
        # session refresh.  Site-scoped roles remain the source of truth.
        role = creator_role if creator_role in {"viewer", "analyst", "supervisor", "admin"} else "supervisor"
        cur.execute(
            """INSERT INTO user_site_roles(user_id, site_id, role)
               VALUES (%s, %s, %s)
               ON CONFLICT (user_id, site_id) DO UPDATE SET role=EXCLUDED.role""",
            (creator_id, site["id"], role),
        )
        return site


def _delete_cycle_context_links(cur, site_id: int) -> None:
    # ``supersedes_id`` is a deliberately append-only self-reference. Delete
    # leaves first so the normal FK remains active throughout the transaction.
    for _ in range(10000):
        cur.execute(
            """DELETE FROM cycle_context_links AS link
               WHERE link.site_id=%s
                 AND NOT EXISTS (
                   SELECT 1 FROM cycle_context_links AS child
                   WHERE child.site_id=%s AND child.supersedes_id=link.id
                 )""",
            (site_id, site_id),
        )
        if cur.rowcount == 0:
            break


def _delete_hdt_predictions(cur, site_id: int) -> None:
    # Jobs may point to a superseded prediction. Clear that nullable pointer
    # before removing the immutable prediction history.
    cur.execute("UPDATE hdt_scoring_jobs SET supersedes_id=NULL WHERE site_id=%s", (site_id,))
    for _ in range(10000):
        cur.execute(
            """DELETE FROM hdt_predictions AS prediction
               WHERE prediction.site_id=%s
                 AND NOT EXISTS (
                   SELECT 1 FROM hdt_predictions AS child
                   WHERE child.site_id=%s AND child.supersedes_id=prediction.id
                 )""",
            (site_id, site_id),
        )
        if cur.rowcount == 0:
            break


def delete_site(site_id: int) -> None:
    with get_connection() as conn, conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM sites WHERE id=%s FOR UPDATE", (site_id,))
        if cur.fetchone() is None:
            raise SiteNotFound("site_not_found")
        cur.execute("SELECT COUNT(*) FROM sites")
        if int(cur.fetchone()[0]) <= 1:
            raise SiteConflict("last_site_cannot_be_deleted")

        # Tenant deletion is the one supported exception to append-only
        # history. The trigger function recognises this transaction-local flag.
        cur.execute("SET LOCAL iddrv.allow_tenant_delete = 'on'")
        cur.execute("SELECT id FROM machines WHERE site_id=%s", (site_id,))
        machine_ids = [row[0] for row in cur.fetchall()]
        machine_ids_sql = tuple(machine_ids) if machine_ids else (-1,)

        cur.execute("DELETE FROM continuity_recovery_reviews WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM process_drift_episode_predictions WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM process_drift_episodes WHERE site_id=%s", (site_id,))
        _delete_cycle_context_links(cur, site_id)

        cur.execute("DELETE FROM machine_cycles WHERE order_site_id=%s OR machine_id = ANY(%s)", (site_id, list(machine_ids_sql)))
        _delete_hdt_predictions(cur, site_id)
        cur.execute("DELETE FROM hdt_scoring_jobs WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM machine_source_events WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM machine_stream_offsets WHERE connection_id IN (SELECT id FROM machine_connections WHERE site_id=%s)", (site_id,))
        cur.execute("DELETE FROM machine_connections WHERE site_id=%s", (site_id,))

        cur.execute("DELETE FROM production_order_observation_sources WHERE observation_id IN (SELECT id FROM production_order_revisions WHERE site_id=%s) OR declaration_revision_id IN (SELECT id FROM erp_declaration_revisions WHERE site_id=%s)", (site_id, site_id))
        cur.execute("UPDATE erp_declarations SET current_revision_id=NULL, superseded_by=NULL WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM production_order_revisions WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM erp_declaration_revisions WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM erp_declarations WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM erp_import_requests WHERE site_id=%s", (site_id,))

        cur.execute("DELETE FROM quality_checks WHERE site_id=%s OR machine_id = ANY(%s)", (site_id, list(machine_ids_sql)))
        cur.execute("DELETE FROM maintenance_events WHERE site_id=%s OR machine_id = ANY(%s)", (site_id, list(machine_ids_sql)))
        cur.execute("DELETE FROM operator_notes WHERE site_id=%s OR machine_id = ANY(%s)", (site_id, list(machine_ids_sql)))
        cur.execute("DELETE FROM incidents WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM shifts WHERE machine_id = ANY(%s) OR order_site_id=%s", (list(machine_ids_sql), site_id))
        cur.execute("DELETE FROM production_orders WHERE site_id=%s", (site_id,))

        cur.execute("DELETE FROM data_quality_issues WHERE machine_id = ANY(%s) OR passport_id IN (SELECT id FROM import_passports WHERE site_id=%s)", (list(machine_ids_sql), site_id))
        cur.execute("DELETE FROM evidence_vault WHERE passport_id IN (SELECT id FROM import_passports WHERE site_id=%s)", (site_id,))
        cur.execute("DELETE FROM import_jobs WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM import_sessions WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM import_passports WHERE site_id=%s", (site_id,))

        cur.execute("DELETE FROM machine_aliases WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM machine_layouts WHERE machine_id = ANY(%s)", (list(machine_ids_sql),))
        cur.execute("DELETE FROM machines WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM production_lines WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM site_shift_calendars WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM user_site_roles WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM sites WHERE id=%s", (site_id,))

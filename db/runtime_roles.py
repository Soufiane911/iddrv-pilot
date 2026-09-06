#!/usr/bin/env python3
"""Create the least-privilege PostgreSQL roles used by API and worker processes.

Schema changes remain owned by ``OWNER_DATABASE_URL``.  The two runtime roles
are deliberately described by an explicit table matrix: a new table receives
no runtime privilege until it is added here and this script is rerun.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Mapping
from urllib.parse import unquote, urlparse

import psycopg2
from psycopg2 import sql


class RuntimeRoleError(RuntimeError):
    pass


# Operations are intentionally table-scoped instead of using ON ALL TABLES.
# This keeps schema_migrations/schema_version and future tables owner-only.
API_TABLE_GRANTS: Mapping[str, frozenset[str]] = {
    "cycle_context_links": frozenset({"SELECT", "INSERT"}),
    "hdt_predictions": frozenset({"SELECT"}),
    "process_drift_episodes": frozenset({"SELECT"}),
    "process_drift_episode_predictions": frozenset({"SELECT"}),
    "production_order_observation_sources": frozenset({"SELECT"}),
    "machine_connections": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "machine_stream_offsets": frozenset({"SELECT"}),
    "continuity_recovery_reviews": frozenset({"SELECT", "INSERT"}),
    "machine_source_events": frozenset({"SELECT"}),
    "hdt_scoring_jobs": frozenset({"SELECT"}),
    "sites": frozenset({"SELECT"}),
    "production_lines": frozenset({"SELECT"}),
    "machines": frozenset({"SELECT", "INSERT"}),
    "machine_layouts": frozenset({"SELECT"}),
    "machine_cycles": frozenset({"SELECT"}),
    "production_orders": frozenset({"SELECT"}),
    "quality_checks": frozenset({"SELECT"}),
    "maintenance_events": frozenset({"SELECT"}),
    "operator_notes": frozenset({"SELECT"}),
    "import_passports": frozenset({"SELECT"}),
    "import_jobs": frozenset({"SELECT"}),
    "incidents": frozenset({"SELECT"}),
    "feedback": frozenset({"SELECT", "INSERT"}),
    "diagnostic_runs": frozenset({"SELECT", "INSERT"}),
    "diagnostic_evidence": frozenset({"SELECT", "INSERT"}),
    "diagnostic_hypotheses": frozenset({"INSERT"}),
    "action_proposals": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "action_proposal_decisions": frozenset({"SELECT", "INSERT"}),
    "users": frozenset({"SELECT", "INSERT"}),
    "user_site_roles": frozenset({"SELECT", "INSERT"}),
    "sessions": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "erp_import_requests": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "site_shift_calendars": frozenset({"SELECT", "INSERT"}),
    "erp_declarations": frozenset({"SELECT"}),
    "erp_declaration_revisions": frozenset({"SELECT"}),
    "production_order_revisions": frozenset({"SELECT"}),
    "import_sessions": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "import_session_files": frozenset({"SELECT", "INSERT", "UPDATE"}),
}

WORKER_TABLE_GRANTS: Mapping[str, frozenset[str]] = {
    "cycle_context_links": frozenset({"SELECT", "INSERT"}),
    "hdt_predictions": frozenset({"SELECT", "INSERT"}),
    "process_drift_episodes": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "process_drift_episode_predictions": frozenset({"SELECT", "INSERT"}),
    "production_order_observation_sources": frozenset({"SELECT", "INSERT"}),
    "machine_connections": frozenset({"SELECT", "UPDATE"}),
    "machine_stream_offsets": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "machine_source_events": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "hdt_scoring_jobs": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "sites": frozenset({"SELECT"}),
    "machines": frozenset({"SELECT", "INSERT"}),
    "erp_import_requests": frozenset({"SELECT", "UPDATE"}),
    "site_shift_calendars": frozenset({"SELECT"}),
    "erp_declarations": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "erp_declaration_revisions": frozenset({"SELECT", "INSERT"}),
    "production_order_revisions": frozenset({"SELECT", "INSERT"}),
    "machine_aliases": frozenset({"SELECT"}),
    "production_orders": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "shifts": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "import_passports": frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"}),
    "staging_import_rows": frozenset({"SELECT", "INSERT"}),
    "import_rejections": frozenset({"INSERT"}),
    "evidence_vault": frozenset({"DELETE"}),
    "data_quality_issues": frozenset({"INSERT", "DELETE"}),
    "machine_cycles": frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"}),
    "quality_checks": frozenset({"INSERT"}),
    "maintenance_events": frozenset({"INSERT"}),
    "operator_notes": frozenset({"INSERT"}),
    "import_jobs": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "import_job_events": frozenset({"INSERT"}),
    "incidents": frozenset({"SELECT", "INSERT", "UPDATE"}),
}

RUNTIME_TABLE_GRANTS: Mapping[str, Mapping[str, frozenset[str]]] = {
    "api": API_TABLE_GRANTS,
    "worker": WORKER_TABLE_GRANTS,
}

# Only these runtime code paths allocate database sequences. UUID defaults use
# uuid_generate_v4(), whose EXECUTE privilege is granted separately below.
WORKER_SEQUENCE_GRANTS: Mapping[str, frozenset[str]] = {
    "machines_id_seq": frozenset({"USAGE", "SELECT"}),
    "staging_import_rows_id_seq": frozenset({"USAGE", "SELECT", "UPDATE"}),
    "shifts_id_seq": frozenset({"USAGE", "SELECT", "UPDATE"}),
    "import_job_events_id_seq": frozenset({"USAGE", "SELECT", "UPDATE"}),
}


_ALLOWED_TABLE_PRIVILEGES = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"})


def _url_parts(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    username = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    if not username or not password:
        raise RuntimeRoleError("runtime database URL must contain username and password")
    return username, password


def _database_target(url: str) -> tuple[str, str, int, str]:
    parsed = urlparse(url)
    if not parsed.path or not parsed.path.lstrip("/"):
        raise RuntimeRoleError("runtime database URL must contain a database name")
    try:
        port = parsed.port or 5432
    except ValueError as exc:
        raise RuntimeRoleError("runtime database URL has an invalid port") from exc
    return (
        parsed.scheme.lower(),
        (parsed.hostname or "").lower(),
        port,
        parsed.path.lstrip("/"),
    )


def _configure_role(cursor, role_name: str, password: str, *, preserve_credentials: bool = False) -> sql.Identifier:
    role = sql.Identifier(role_name)
    password_literal = sql.Literal(password)
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role_name,))
    if cursor.fetchone() is None:
        cursor.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(role, password_literal)
        )
    elif not preserve_credentials:
        cursor.execute(
            sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(role, password_literal)
        )
    # Explicitly reset capabilities even when a role pre-dates this script.
    cursor.execute(
        sql.SQL(
            "ALTER ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOINHERIT NOREPLICATION NOBYPASSRLS"
        ).format(role)
    )
    return role


def _grant_matrix(cursor, role: sql.Identifier, grants: Mapping[str, frozenset[str]]) -> None:
    for table_name, privileges in grants.items():
        invalid = set(privileges) - _ALLOWED_TABLE_PRIVILEGES
        if invalid:
            raise RuntimeRoleError(f"invalid table privilege for {table_name}: {sorted(invalid)}")
        rendered = sql.SQL(", ").join(sql.SQL(value) for value in sorted(privileges))
        cursor.execute(
            sql.SQL("GRANT {} ON TABLE {} TO {}").format(
                rendered, sql.Identifier(table_name), role,
            )
        )


def _grant_sequences(cursor, role: sql.Identifier, grants: Mapping[str, frozenset[str]]) -> None:
    for sequence_name, privileges in grants.items():
        rendered = sql.SQL(", ").join(sql.SQL(value) for value in sorted(privileges))
        cursor.execute(
            sql.SQL("GRANT {} ON SEQUENCE {} TO {}").format(
                rendered, sql.Identifier(sequence_name), role,
            )
        )


def ensure_runtime_roles(owner_url: str, api_url: str, worker_url: str, *, grants_only: bool = False) -> tuple[str, str]:
    """Create/configure the API and worker roles and apply the explicit matrix."""
    owner_name, _ = _url_parts(owner_url)
    api_name, api_password = _url_parts(api_url)
    worker_name, worker_password = _url_parts(worker_url)
    if len({owner_name, api_name, worker_name}) != 3:
        raise RuntimeRoleError("owner, API and worker roles must all be distinct")
    if _database_target(api_url) != _database_target(worker_url):
        raise RuntimeRoleError("API_DATABASE_URL and WORKER_DATABASE_URL must target the same database")

    with psycopg2.connect(owner_url) as conn:
        with conn.cursor() as cur:
            api_role = _configure_role(cur, api_name, api_password, preserve_credentials=grants_only)
            worker_role = _configure_role(cur, worker_name, worker_password, preserve_credentials=grants_only)

            # Remove privileges left by older shared-role versions and prevent
            # PUBLIC from reintroducing access to existing or future objects.
            cur.execute("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM PUBLIC")
            cur.execute("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC")
            cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {} ").format(api_role))
            cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {} ").format(worker_role))
            cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {} ").format(api_role))
            cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {} ").format(worker_role))

            cur.execute("REVOKE ALL PRIVILEGES ON SCHEMA public FROM PUBLIC")
            cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON SCHEMA public FROM {} ").format(api_role))
            cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON SCHEMA public FROM {} ").format(worker_role))
            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}, {} ").format(api_role, worker_role))
            cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")

            cur.execute("SELECT current_database()")
            database_name = cur.fetchone()[0]
            cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database_name)))
            cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON DATABASE {} FROM {}, {}").format(
                sql.Identifier(database_name), api_role, worker_role,
            ))
            cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}").format(
                sql.Identifier(database_name), api_role, worker_role,
            ))

            # Defaults are intentionally empty. Runtime access to a future
            # table must be reviewed and added to the matrix, never inherited.
            for object_kind in ("TABLES", "SEQUENCES"):
                cur.execute(sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                    "REVOKE ALL PRIVILEGES ON {} FROM PUBLIC"
                ).format(sql.Identifier(owner_name), sql.SQL(object_kind)))
            # Role-specific defaults are also cleared for idempotence.
            for role in (api_role, worker_role):
                for object_kind in ("TABLES", "SEQUENCES"):
                    cur.execute(sql.SQL(
                        "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                        "REVOKE ALL PRIVILEGES ON {} FROM {}"
                    ).format(sql.Identifier(owner_name), sql.SQL(object_kind), role))

            _grant_matrix(cur, api_role, API_TABLE_GRANTS)
            _grant_matrix(cur, worker_role, WORKER_TABLE_GRANTS)
            _grant_sequences(cur, api_role, {"machines_id_seq": frozenset({"USAGE", "SELECT"})})
            _grant_sequences(cur, worker_role, WORKER_SEQUENCE_GRANTS)
            cur.execute("REVOKE ALL PRIVILEGES ON FUNCTION public.uuid_generate_v4() FROM PUBLIC")
            cur.execute(sql.SQL("GRANT EXECUTE ON FUNCTION public.uuid_generate_v4() TO {}, {} ").format(
                api_role, worker_role,
            ))

    return api_name, worker_name


def ensure_runtime_grants(owner_url: str, api_url: str, worker_url: str) -> tuple[str, str]:
    """Apply the reviewed grant matrix while preserving existing credentials.

    This path refuses to provision missing roles and never emits or compares a
    password value. Fresh installations continue to use ``ensure_runtime_roles``.
    """
    owner_name, _ = _url_parts(owner_url)
    api_name, _ = _url_parts(api_url)
    worker_name, _ = _url_parts(worker_url)
    if len({owner_name, api_name, worker_name}) != 3:
        raise RuntimeRoleError("owner, API and worker roles must all be distinct")
    with psycopg2.connect(owner_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT rolname FROM pg_roles WHERE rolname IN (%s,%s)", (api_name, worker_name))
        existing = {row[0] for row in cur.fetchall()}
    if {api_name, worker_name} - existing:
        raise RuntimeRoleError("grants-only requires both runtime roles to already exist")
    return ensure_runtime_roles(owner_url, api_url, worker_url, grants_only=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-url", default=os.getenv("OWNER_DATABASE_URL") or os.getenv("DATABASE_URL"))
    parser.add_argument("--api-url", default=os.getenv("API_DATABASE_URL"))
    parser.add_argument("--worker-url", default=os.getenv("WORKER_DATABASE_URL"))
    parser.add_argument("--grants-only", action="store_true", help="mettre à jour les droits sans toucher aux credentials")
    args = parser.parse_args()
    if not args.owner_url or not args.api_url or not args.worker_url:
        raise SystemExit(
            "OWNER_DATABASE_URL, API_DATABASE_URL et WORKER_DATABASE_URL doivent être définis"
        )
    try:
        api_role, worker_role = ensure_runtime_grants(args.owner_url, args.api_url, args.worker_url) if args.grants_only else ensure_runtime_roles(args.owner_url, args.api_url, args.worker_url)
    except (psycopg2.Error, RuntimeRoleError) as exc:
        raise SystemExit(f"Impossible de configurer les rôles runtime: {exc}") from None
    print(f"Rôles runtime configurés: API={api_role}, worker={worker_role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

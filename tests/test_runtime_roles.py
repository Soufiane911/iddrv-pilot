from pathlib import Path

import pytest

from db.runtime_roles import (
    API_TABLE_GRANTS,
    RUNTIME_TABLE_GRANTS,
    RuntimeRoleError,
    WORKER_TABLE_GRANTS,
    ensure_runtime_roles,
)


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_urls_must_use_distinct_roles_on_one_database():
    with pytest.raises(RuntimeRoleError, match="same database"):
        ensure_runtime_roles(
            "postgresql://owner:pw@db/iddrv",
            "postgresql://api:pw@db/iddrv",
            "postgresql://worker:pw@other-db/iddrv",
        )


def test_runtime_matrix_is_explicit_and_excludes_schema_metadata():
    forbidden = {"schema_migrations", "schema_version"}
    assert forbidden.isdisjoint(API_TABLE_GRANTS)
    assert forbidden.isdisjoint(WORKER_TABLE_GRANTS)
    assert set(RUNTIME_TABLE_GRANTS) == {"api", "worker"}
    assert all(privileges <= {"SELECT", "INSERT", "UPDATE", "DELETE"}
               for grants in RUNTIME_TABLE_GRANTS.values()
               for privileges in grants.values())


def test_worker_cannot_read_auth_tables_or_api_role_cannot_ingest():
    auth_tables = {"users", "user_site_roles", "sessions"}
    ingest_tables = {"import_jobs", "import_job_events", "staging_import_rows", "machine_cycles"}
    assert auth_tables.isdisjoint(WORKER_TABLE_GRANTS)
    assert ingest_tables.isdisjoint({name for name, grants in API_TABLE_GRANTS.items()
                                     if grants & {"INSERT", "UPDATE", "DELETE"}})
    assert "incidents" in WORKER_TABLE_GRANTS
    assert WORKER_TABLE_GRANTS["incidents"] == {"SELECT", "INSERT", "UPDATE"}


def test_runtime_role_setup_does_not_grant_all_tables_or_ddl():
    source = (ROOT / "db/runtime_roles.py").read_text(encoding="utf-8")
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES" not in source
    assert "ALTER DEFAULT PRIVILEGES" in source
    assert "REVOKE ALL PRIVILEGES ON DATABASE" in source
    assert "NOCREATEDB NOCREATEROLE" in source
    assert "NOINHERIT NOREPLICATION NOBYPASSRLS" in source
    assert "CREATE ON SCHEMA public TO" not in source


def test_pilot_wires_distinct_runtime_urls():
    compose = (ROOT / "deploy/compose.pilot.yml").read_text(encoding="utf-8")
    assert "API_DATABASE_URL: ${API_DATABASE_URL:?API_DATABASE_URL is required}" in compose
    assert "WORKER_DATABASE_URL: ${WORKER_DATABASE_URL:?WORKER_DATABASE_URL is required}" in compose
    assert "APP_DATABASE_URL" not in compose
    assert "DATABASE_URL: ${API_DATABASE_URL:?API_DATABASE_URL is required}" in compose
    assert "DATABASE_URL: ${WORKER_DATABASE_URL:?WORKER_DATABASE_URL is required}" in compose


def test_telemetry_grants_keep_api_out_of_ingestion_and_secrets_out_of_database():
    for table in ('machine_source_events', 'machine_stream_offsets', 'hdt_scoring_jobs'):
        assert API_TABLE_GRANTS[table] == {'SELECT'}
        assert {'SELECT', 'INSERT', 'UPDATE'} <= WORKER_TABLE_GRANTS[table]
    assert API_TABLE_GRANTS['machine_connections'] == {'SELECT', 'INSERT', 'UPDATE'}
    assert WORKER_TABLE_GRANTS['machine_connections'] == {'SELECT', 'UPDATE'}
    assert all('secret' not in table for table in API_TABLE_GRANTS)


def test_hdt_history_is_read_only_to_api_and_append_only_to_worker():
    assert API_TABLE_GRANTS['hdt_predictions'] == {'SELECT'}
    assert WORKER_TABLE_GRANTS['hdt_predictions'] == {'SELECT','INSERT'}
    assert API_TABLE_GRANTS['cycle_context_links'] == {'SELECT','INSERT'}
    assert WORKER_TABLE_GRANTS['process_drift_episode_predictions'] == {'SELECT','INSERT'}

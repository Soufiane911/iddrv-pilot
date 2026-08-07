#!/usr/bin/env sh
set -eu

: "${DATABASE_URL:?DATABASE_URL must be set}"
: "${BACKUP_FILE:?BACKUP_FILE must point to a pg_dump custom-format file}"
: "${DB_CONTAINER:?DB_CONTAINER must name the Compose PostgreSQL service}"
: "${RESTORE_TARGET_DATABASE:?RESTORE_TARGET_DATABASE must confirm the exact target database}"

if [ "$DB_CONTAINER" != "timescaledb" ]; then
  echo "Refusing restore: DB_CONTAINER must be the verified 'timescaledb' Compose service." >&2
  exit 1
fi
if [ "${RESTORE_TARGET_ISOLATED:-false}" != "true" ]; then
  echo "Refusing restore: set RESTORE_TARGET_ISOLATED=true only for a fresh isolated target." >&2
  exit 1
fi
case "$RESTORE_TARGET_DATABASE" in
  iddrv_restore_*) ;;
  *)
    echo "Refusing restore: isolated database names must start with 'iddrv_restore_'." >&2
    exit 1
    ;;
esac

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PGPASSFILE_LOCAL="$(mktemp)"
PGPASSFILE_CONTAINER="/tmp/iddrv-restore-pgpass-$$"
DUMP_CONTAINER="/tmp/iddrv-restore-$$.dump"
MC_CONTAINER="/tmp/iddrv-machine-cycles-$$.csv"
PASSFILE_IN_CONTAINER=false
DUMP_IN_CONTAINER=false
MC_IN_CONTAINER=false

finish_restore() {
  rm -f "$PGPASSFILE_LOCAL"
  if [ "$PASSFILE_IN_CONTAINER" = "true" ]; then
    docker compose exec -T "$DB_CONTAINER" rm -f "$PGPASSFILE_CONTAINER" >/dev/null 2>&1 || true
  fi
  if [ "$DUMP_IN_CONTAINER" = "true" ]; then
    docker compose exec -T "$DB_CONTAINER" rm -f "$DUMP_CONTAINER" >/dev/null 2>&1 || true
  fi
  if [ "$MC_IN_CONTAINER" = "true" ]; then
    docker compose exec -T "$DB_CONTAINER" rm -f "$MC_CONTAINER" >/dev/null 2>&1 || true
  fi
}
trap finish_restore EXIT INT TERM

SAFE_DATABASE_URL="$(python3 "$SCRIPT_DIR/pg_url_guard.py" --passfile "$PGPASSFILE_LOCAL" --require-local)"
MC_FILE="${BACKUP_FILE}.machine_cycles.csv"
MC_COLUMNS='time,machine_id,production_order_id,order_site_id,shift_id,passport_id,source_line_no,source_row_hash,cycle_counter,cycle_time_s,dosing_time_s,injection_time_s,cushion_mm,switchover_pressure_bar,switchover_position,peak_pressure_bar,clamp_force_kn,mold_open_time_s,good_parts,scrap_flag,barrel_temp_zone1_c,barrel_temp_zone2_c,barrel_temp_zone3_c,oil_temperature_c,link_confidence,quality_flag,raw_data,data_quality_status,part_quality_status,defect_type,cooling_time_s,mold_temperature_c,energy_kwh'

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Missing backup file: $BACKUP_FILE" >&2
  exit 1
fi
if [ ! -f "$MC_FILE" ]; then
  echo "Missing TimescaleDB sidecar: $MC_FILE" >&2
  exit 1
fi
MC_HEADER="$(head -n 1 "$MC_FILE" | tr -d '\r')"
if [ "$MC_HEADER" != "$MC_COLUMNS" ]; then
  echo "Invalid TimescaleDB sidecar header" >&2
  exit 1
fi

USE_HOST_TOOLS=false
if command -v pg_restore >/dev/null 2>&1 && command -v psql >/dev/null 2>&1; then
  USE_HOST_TOOLS=true
else
  docker compose cp "$PGPASSFILE_LOCAL" "$DB_CONTAINER:$PGPASSFILE_CONTAINER" >/dev/null
  docker compose exec -T "$DB_CONTAINER" chmod 600 "$PGPASSFILE_CONTAINER"
  PASSFILE_IN_CONTAINER=true
fi

run_psql() {
  if [ "$USE_HOST_TOOLS" = "true" ]; then
    PGPASSFILE="$PGPASSFILE_LOCAL" psql "$SAFE_DATABASE_URL" "$@"
  else
    docker compose exec -T -e PGPASSFILE="$PGPASSFILE_CONTAINER" "$DB_CONTAINER" \
      psql "$SAFE_DATABASE_URL" "$@"
  fi
}

# Complete every non-mutating check before touching target data.
if [ "$USE_HOST_TOOLS" = "true" ]; then
  pg_restore --list "$BACKUP_FILE" >/dev/null
else
  docker compose cp "$BACKUP_FILE" "$DB_CONTAINER:$DUMP_CONTAINER" >/dev/null
  DUMP_IN_CONTAINER=true
  docker compose exec -T "$DB_CONTAINER" pg_restore --list "$DUMP_CONTAINER" >/dev/null
fi

ACTUAL_DATABASE="$(run_psql -Atqc 'SELECT current_database()' | tr -d '\r')"
if [ "$ACTUAL_DATABASE" != "$RESTORE_TARGET_DATABASE" ]; then
  echo "Refusing restore: RESTORE_TARGET_DATABASE does not match the effective connection target." >&2
  exit 1
fi

TARGET_SYSTEM_ID="$(run_psql -Atqc 'SELECT system_identifier FROM pg_control_system()' | tr -d '\r')"
CONTAINER_SYSTEM_ID="$(docker compose exec -T "$DB_CONTAINER" psql -U "${POSTGRES_USER:-iddrv_user}" -d postgres -Atqc 'SELECT system_identifier FROM pg_control_system()' | tr -d '\r')"
if [ -z "$TARGET_SYSTEM_ID" ] || [ "$TARGET_SYSTEM_ID" != "$CONTAINER_SYSTEM_ID" ]; then
  echo "Refusing restore: DATABASE_URL and DB_CONTAINER do not identify the same PostgreSQL server." >&2
  exit 1
fi

OTHER_SESSIONS="$(run_psql -Atqc "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND backend_type='client backend' AND pid<>pg_backend_pid()" | tr -d '\r')"
if [ "$OTHER_SESSIONS" -ne 0 ]; then
  echo "Refusing restore: the isolated target still has active sessions." >&2
  exit 1
fi

if [ "${ALLOW_NONEMPTY_RESTORE:-false}" != "true" ]; then
  run_psql -v ON_ERROR_STOP=1 <<'SQL'
DO $guard$
DECLARE
  item RECORD;
  occupied BOOLEAN;
BEGIN
  FOR item IN
    SELECT schemaname, tablename
    FROM pg_tables
    WHERE schemaname = 'public'
      AND tablename NOT IN (
        'spatial_ref_sys', '_iddrv_e2e_guard', 'schema_migrations', 'schema_version',
        'sites', 'machines', 'machine_aliases', 'production_lines', 'machine_layouts'
      )
  LOOP
    EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I.%I LIMIT 1)', item.schemaname, item.tablename)
      INTO occupied;
    IF occupied THEN
      RAISE EXCEPTION 'restore target contains application data in %.%', item.schemaname, item.tablename;
    END IF;
  END LOOP;
END
$guard$;
SQL
fi

run_psql -v ON_ERROR_STOP=1 <<'SQL'
DO $truncate$
DECLARE
  targets TEXT;
BEGIN
  SELECT string_agg(format('%I.%I', schemaname, tablename), ', ' ORDER BY tablename)
    INTO targets
  FROM pg_tables
  WHERE schemaname = 'public'
    AND tablename NOT IN ('spatial_ref_sys', '_iddrv_e2e_guard');
  IF targets IS NOT NULL THEN
    EXECUTE 'TRUNCATE TABLE ' || targets || ' CASCADE';
  END IF;
END
$truncate$;
SQL

if [ "$USE_HOST_TOOLS" = "true" ]; then
  PGPASSFILE="$PGPASSFILE_LOCAL" pg_restore \
    --dbname="$SAFE_DATABASE_URL" --data-only --no-owner --exit-on-error --single-transaction "$BACKUP_FILE"
  PGPASSFILE="$PGPASSFILE_LOCAL" psql "$SAFE_DATABASE_URL" -v ON_ERROR_STOP=1 \
    -c "\\copy public.machine_cycles ($MC_COLUMNS) FROM STDIN WITH CSV HEADER" <"$MC_FILE"
else
  docker compose cp "$MC_FILE" "$DB_CONTAINER:$MC_CONTAINER" >/dev/null
  MC_IN_CONTAINER=true
  docker compose exec -T -e PGPASSFILE="$PGPASSFILE_CONTAINER" "$DB_CONTAINER" \
    pg_restore --dbname="$SAFE_DATABASE_URL" --data-only --no-owner --exit-on-error --single-transaction "$DUMP_CONTAINER"
  docker compose exec -T -e PGPASSFILE="$PGPASSFILE_CONTAINER" "$DB_CONTAINER" \
    psql "$SAFE_DATABASE_URL" -v ON_ERROR_STOP=1 \
    -c "\\copy public.machine_cycles ($MC_COLUMNS) FROM '$MC_CONTAINER' WITH CSV HEADER"
fi

printf 'Restore completed in isolated database %s. Validate it before switching application connections.\n' "$ACTUAL_DATABASE"

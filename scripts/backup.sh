#!/usr/bin/env sh
set -eu

: "${DATABASE_URL:?DATABASE_URL must be set}"
: "${DB_CONTAINER:?DB_CONTAINER must name the Compose PostgreSQL service}"
if [ "$DB_CONTAINER" != "timescaledb" ]; then
  echo "Refusing backup: DB_CONTAINER must be the verified 'timescaledb' Compose service." >&2
  exit 1
fi
if [ "${QUIESCE_SERVICES:-true}" != "true" ]; then
  echo "Refusing a live backup without verified writer quiescing." >&2
  exit 1
fi

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PGPASSFILE_LOCAL="$(mktemp)"
PGPASSFILE_CONTAINER="/tmp/iddrv-backup-pgpass-$$"
PASSFILE_IN_CONTAINER=false
WRITERS_PAUSED=false
RUNNING_WRITERS=""

finish_backup() {
  if [ "$WRITERS_PAUSED" = "true" ] && [ -n "$RUNNING_WRITERS" ]; then
    # Resume exactly the services that were running before the backup.
    docker compose unpause $RUNNING_WRITERS >/dev/null 2>&1 || true
  fi
  rm -f "$PGPASSFILE_LOCAL"
  if [ "$PASSFILE_IN_CONTAINER" = "true" ]; then
    docker compose exec -T "$DB_CONTAINER" rm -f "$PGPASSFILE_CONTAINER" >/dev/null 2>&1 || true
  fi
}
trap finish_backup EXIT INT TERM

SAFE_DATABASE_URL="$(python3 "$SCRIPT_DIR/pg_url_guard.py" --passfile "$PGPASSFILE_LOCAL" --require-local)"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUP_DIR/iddrv-$STAMP.dump"
MC_OUT="$OUT.machine_cycles.csv"
MC_COLUMNS='time,machine_id,production_order_id,order_site_id,shift_id,passport_id,source_line_no,source_row_hash,cycle_counter,cycle_time_s,dosing_time_s,injection_time_s,cushion_mm,switchover_pressure_bar,switchover_position,peak_pressure_bar,clamp_force_kn,mold_open_time_s,good_parts,scrap_flag,barrel_temp_zone1_c,barrel_temp_zone2_c,barrel_temp_zone3_c,oil_temperature_c,link_confidence,quality_flag,raw_data,data_quality_status,part_quality_status,defect_type,cooling_time_s,mold_temperature_c,energy_kwh'

USE_HOST_TOOLS=false
if command -v pg_dump >/dev/null 2>&1 && command -v psql >/dev/null 2>&1; then
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

TARGET_SYSTEM_ID="$(run_psql -Atqc 'SELECT system_identifier FROM pg_control_system()' | tr -d '\r')"
CONTAINER_SYSTEM_ID="$(docker compose exec -T "$DB_CONTAINER" psql -U "${POSTGRES_USER:-iddrv_user}" -d postgres -Atqc 'SELECT system_identifier FROM pg_control_system()' | tr -d '\r')"
if [ -z "$TARGET_SYSTEM_ID" ] || [ "$TARGET_SYSTEM_ID" != "$CONTAINER_SYSTEM_ID" ]; then
  echo "Refusing backup: DATABASE_URL and DB_CONTAINER do not identify the same PostgreSQL server." >&2
  exit 1
fi

RUNNING_WRITERS="$(docker compose ps --status running --services api worker | tr '\n' ' ')"
if [ -n "$RUNNING_WRITERS" ]; then
  docker compose pause $RUNNING_WRITERS >/dev/null
  WRITERS_PAUSED=true
fi

if [ "$USE_HOST_TOOLS" = "true" ]; then
  PGPASSFILE="$PGPASSFILE_LOCAL" pg_dump "$SAFE_DATABASE_URL" \
    --schema=public --format=custom --data-only --no-owner --file="$OUT"
  PGPASSFILE="$PGPASSFILE_LOCAL" psql "$SAFE_DATABASE_URL" \
    -c "\\copy (SELECT $MC_COLUMNS FROM public.machine_cycles ORDER BY time, machine_id) TO STDOUT WITH CSV HEADER" >"$MC_OUT"
else
  docker compose exec -T -e PGPASSFILE="$PGPASSFILE_CONTAINER" "$DB_CONTAINER" \
    pg_dump "$SAFE_DATABASE_URL" --schema=public --format=custom --data-only --no-owner >"$OUT"
  docker compose exec -T -e PGPASSFILE="$PGPASSFILE_CONTAINER" "$DB_CONTAINER" \
    psql "$SAFE_DATABASE_URL" \
    -c "\\copy (SELECT $MC_COLUMNS FROM public.machine_cycles ORDER BY time, machine_id) TO STDOUT WITH CSV HEADER" >"$MC_OUT"
fi
printf '%s\n' "$OUT"

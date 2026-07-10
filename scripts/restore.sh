#!/usr/bin/env sh
set -eu

: "${DATABASE_URL:?DATABASE_URL must be set}"
: "${BACKUP_FILE:?BACKUP_FILE must point to a pg_dump custom-format file}"
MC_FILE="${BACKUP_FILE}.machine_cycles.csv"
MC_COLUMNS='time,machine_id,production_order_id,shift_id,passport_id,source_line_no,source_row_hash,cycle_counter,cycle_time_s,dosing_time_s,injection_time_s,cushion_mm,switchover_pressure_bar,switchover_position,peak_pressure_bar,clamp_force_kn,mold_open_time_s,good_parts,scrap_flag,barrel_temp_zone1_c,barrel_temp_zone2_c,barrel_temp_zone3_c,oil_temperature_c,link_confidence,quality_flag,raw_data,data_quality_status,part_quality_status,defect_type,cooling_time_s,mold_temperature_c,energy_kwh'
if [ ! -f "$MC_FILE" ]; then
  echo "Missing TimescaleDB sidecar: $MC_FILE" >&2
  exit 1
fi
if command -v pg_restore >/dev/null 2>&1; then
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c 'TRUNCATE schema_version; TRUNCATE sites CASCADE'
  pg_restore --dbname="$DATABASE_URL" --data-only --no-owner --exit-on-error "$BACKUP_FILE"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "\\copy public.machine_cycles ($MC_COLUMNS) FROM '$MC_FILE' WITH CSV HEADER"
elif [ -n "${DB_CONTAINER:-}" ]; then
  docker compose exec -T "$DB_CONTAINER" psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c 'TRUNCATE schema_version; TRUNCATE sites CASCADE'
  docker compose cp "$BACKUP_FILE" "$DB_CONTAINER:/tmp/iddrv-restore.dump" >/dev/null
  docker compose cp "$MC_FILE" "$DB_CONTAINER:/tmp/iddrv-machine_cycles.csv" >/dev/null
  docker compose exec -T -e DATABASE_URL="$DATABASE_URL" "$DB_CONTAINER" \
    pg_restore --dbname="$DATABASE_URL" --data-only --no-owner --exit-on-error /tmp/iddrv-restore.dump
  docker compose exec -T "$DB_CONTAINER" psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "\\copy public.machine_cycles ($MC_COLUMNS) FROM '/tmp/iddrv-machine_cycles.csv' WITH CSV HEADER"
else
  echo "pg_restore is required (or set DB_CONTAINER=timescaledb)" >&2
  exit 1
fi

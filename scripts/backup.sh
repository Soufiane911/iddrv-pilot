#!/usr/bin/env sh
set -eu

: "${DATABASE_URL:?DATABASE_URL must be set}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUP_DIR/iddrv-$STAMP.dump"
MC_OUT="$OUT.machine_cycles.csv"
MC_COLUMNS='time,machine_id,production_order_id,shift_id,passport_id,source_line_no,source_row_hash,cycle_counter,cycle_time_s,dosing_time_s,injection_time_s,cushion_mm,switchover_pressure_bar,switchover_position,peak_pressure_bar,clamp_force_kn,mold_open_time_s,good_parts,scrap_flag,barrel_temp_zone1_c,barrel_temp_zone2_c,barrel_temp_zone3_c,oil_temperature_c,link_confidence,quality_flag,raw_data,data_quality_status,part_quality_status,defect_type,cooling_time_s,mold_temperature_c,energy_kwh'
if command -v pg_dump >/dev/null 2>&1; then
  pg_dump "$DATABASE_URL" --schema=public --format=custom --data-only --no-owner --file="$OUT"
  psql "$DATABASE_URL" -c "\\copy (SELECT $MC_COLUMNS FROM public.machine_cycles ORDER BY time, machine_id) TO '$MC_OUT' WITH CSV HEADER"
elif [ -n "${DB_CONTAINER:-}" ]; then
  # Useful on the minimal pilot host where PostgreSQL client tools are only
  # present in the database container.
  docker compose exec -T -e DATABASE_URL="$DATABASE_URL" "$DB_CONTAINER" \
    pg_dump "$DATABASE_URL" --schema=public --format=custom --data-only --no-owner >"$OUT"
  docker compose exec -T -e DATABASE_URL="$DATABASE_URL" "$DB_CONTAINER" \
    psql "$DATABASE_URL" -c "\\copy (SELECT $MC_COLUMNS FROM public.machine_cycles ORDER BY time, machine_id) TO STDOUT WITH CSV HEADER" >"$MC_OUT"
else
  echo "pg_dump is required (or set DB_CONTAINER=timescaledb)" >&2
  exit 1
fi
printf '%s\n' "$OUT"

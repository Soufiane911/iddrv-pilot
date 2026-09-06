-- Migration 002: quality, maintenance and operator context for scenario imports
CREATE TABLE IF NOT EXISTS quality_checks (
  quality_check_id VARCHAR(80) PRIMARY KEY,
  time TIMESTAMPTZ NOT NULL,
  production_order_id VARCHAR(50) REFERENCES production_orders(id) ON DELETE SET NULL,
  machine_id INT REFERENCES machines(id), product_ref VARCHAR(100),
  sample_size INT, defect_count INT, defect_type TEXT,
  severity VARCHAR(30), measured_weight_g NUMERIC, target_weight_g NUMERIC,
  dimension_deviation_mm NUMERIC, visual_result VARCHAR(50), comment TEXT,
  passport_id UUID REFERENCES import_passports(id), source_row_hash VARCHAR(64),
  data_quality_status VARCHAR(20) NOT NULL DEFAULT 'valid',
  part_quality_status VARCHAR(30), created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS maintenance_events (
  event_id VARCHAR(80) PRIMARY KEY, time TIMESTAMPTZ NOT NULL,
  machine_id INT REFERENCES machines(id), production_order_id VARCHAR(50) REFERENCES production_orders(id) ON DELETE SET NULL,
  event_type VARCHAR(100), duration_min NUMERIC, severity VARCHAR(30), description TEXT,
  passport_id UUID REFERENCES import_passports(id), source_row_hash VARCHAR(64), data_quality_status VARCHAR(20) NOT NULL DEFAULT 'valid'
);
CREATE TABLE IF NOT EXISTS operator_notes (
  note_id VARCHAR(80) PRIMARY KEY, time TIMESTAMPTZ NOT NULL,
  machine_id INT REFERENCES machines(id), production_order_id VARCHAR(50) REFERENCES production_orders(id) ON DELETE SET NULL,
  operator_id VARCHAR(80), note_text TEXT NOT NULL,
  passport_id UUID REFERENCES import_passports(id), source_row_hash VARCHAR(64), data_quality_status VARCHAR(20) NOT NULL DEFAULT 'valid'
);
ALTER TABLE machine_cycles ADD COLUMN IF NOT EXISTS data_quality_status VARCHAR(20) DEFAULT 'valid';
ALTER TABLE machine_cycles ADD COLUMN IF NOT EXISTS part_quality_status VARCHAR(30);
ALTER TABLE machine_cycles ADD COLUMN IF NOT EXISTS defect_type VARCHAR(100);
ALTER TABLE machine_cycles ADD COLUMN IF NOT EXISTS cooling_time_s NUMERIC(7,3);
ALTER TABLE machine_cycles ADD COLUMN IF NOT EXISTS mold_temperature_c NUMERIC(6,2);
ALTER TABLE machine_cycles ADD COLUMN IF NOT EXISTS energy_kwh NUMERIC(10,4);
CREATE INDEX IF NOT EXISTS idx_quality_checks_machine_time ON quality_checks(machine_id,time DESC);
CREATE INDEX IF NOT EXISTS idx_maintenance_events_machine_time ON maintenance_events(machine_id,time DESC);
CREATE INDEX IF NOT EXISTS idx_operator_notes_machine_time ON operator_notes(machine_id,time DESC);
DO $$ BEGIN
  ALTER TABLE staging_import_rows DROP CONSTRAINT IF EXISTS staging_import_rows_source_kind_check;
  ALTER TABLE staging_import_rows ADD CONSTRAINT staging_import_rows_source_kind_check CHECK (source_kind IN ('machine_cycle','erp_order','erp_shift','quality_check','maintenance_event','operator_note','unknown'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

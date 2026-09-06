-- =============================================================
-- IDDRV — Script d'initialisation PostgreSQL + TimescaleDB
-- =============================================================

-- Activation de TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- Pour la recherche floue sur les noms

-- =============================================================
-- TABLES RELATIONNELLES (Contexte ERP / Usine)
-- =============================================================

-- Sites industriels (usines)
CREATE TABLE IF NOT EXISTS sites (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO sites (id, name, timezone)
VALUES (1, 'Usine Principale', 'Europe/Paris')
ON CONFLICT (id) DO NOTHING;

-- Machines (presses à injecter)
CREATE TABLE IF NOT EXISTS machines (
    id SERIAL PRIMARY KEY,
    site_id INT NOT NULL REFERENCES sites(id) DEFAULT 1,
    erp_ref VARCHAR(50) NOT NULL,
    name VARCHAR(100),
    brand VARCHAR(50),
    model VARCHAR(100),
    max_clamp_force_kn NUMERIC(8,2),
    max_shot_volume_cm3 NUMERIC(8,2),
    controller_type VARCHAR(50),
    opcua_endpoint VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(site_id, erp_ref)
);

-- Alias de machines (liens entre ERP, fichiers, OPC UA)
CREATE TABLE IF NOT EXISTS machine_aliases (
    id SERIAL PRIMARY KEY,
    machine_id INT NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    site_id INT NOT NULL REFERENCES sites(id),
    alias_context VARCHAR(50) NOT NULL,   -- 'erp', 'file', 'opcua', 'network'
    alias_value VARCHAR(100) NOT NULL,
    CONSTRAINT machine_aliases_site_context_value_key
        UNIQUE(site_id, alias_context, alias_value)
);

-- Ordres de Fabrication (OF)
CREATE TABLE IF NOT EXISTS production_orders (
    id VARCHAR(50) PRIMARY KEY,
    machine_id INT REFERENCES machines(id),
    product_ref VARCHAR(100),
    product_name VARCHAR(255),
    tool_ref VARCHAR(100),
    material_ref VARCHAR(100),
    target_quantity INT,
    operator_id VARCHAR(50),
    order_type VARCHAR(50),               -- 'normal', 'sous-charge', 'prototypage'
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    erp_cycle_time_s NUMERIC(6,3),
    erp_trs NUMERIC(5,4),
    erp_trs_calc NUMERIC(5,4),
    erp_scrap_count INT DEFAULT 0,
    erp_good_parts INT DEFAULT 0,
    erp_available_time_h NUMERIC(8,4),
    erp_running_time_h NUMERIC(8,4),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Équipes de production
CREATE TABLE IF NOT EXISTS shifts (
    id SERIAL PRIMARY KEY,
    machine_id INT NOT NULL REFERENCES machines(id),
    production_order_id VARCHAR(50) REFERENCES production_orders(id),
    shift_number SMALLINT NOT NULL CHECK (shift_number IN (1, 2, 3)),
    shift_date DATE NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    operator_id VARCHAR(50),
    planned_duration_h NUMERIC(5,3),
    UNIQUE(machine_id, shift_date, shift_number)
);

-- Passeports d'import (traçabilité des fichiers importés)
CREATE TABLE IF NOT EXISTS import_passports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id INT NOT NULL REFERENCES sites(id) DEFAULT 1,
    file_name VARCHAR(255),
    file_hash VARCHAR(64),
    file_path_raw TEXT,
    parser_type VARCHAR(80),
    brand_detected VARCHAR(50),
    encoding_detected VARCHAR(20),
    delimiter_detected VARCHAR(5),
    is_transposed BOOLEAN DEFAULT FALSE,
    row_count_total INT DEFAULT 0,
    row_count_accepted INT DEFAULT 0,
    row_count_rejected INT DEFAULT 0,
    column_mapping_confidence NUMERIC(4,3),
    imported_at TIMESTAMPTZ DEFAULT NOW(),
    error_log TEXT,
    metadata JSONB,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed'))
);

-- Staging brut : 1 ligne source = 1 trace rejouable
CREATE TABLE IF NOT EXISTS staging_import_rows (
    id BIGSERIAL PRIMARY KEY,
    passport_id UUID NOT NULL REFERENCES import_passports(id) ON DELETE CASCADE,
    source_line_no INT NOT NULL,
    source_kind VARCHAR(30) NOT NULL CHECK (source_kind IN ('machine_cycle', 'erp_order', 'erp_shift', 'unknown')),
    raw_data JSONB NOT NULL,
    normalized_data JSONB,
    source_row_hash VARCHAR(64) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'warning', 'rejected')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(passport_id, source_line_no),
    UNIQUE(passport_id, source_row_hash)
);

-- Rejets et alertes d'import exploitables par ligne source
CREATE TABLE IF NOT EXISTS import_rejections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    passport_id UUID REFERENCES import_passports(id) ON DELETE CASCADE,
    staging_row_id BIGINT REFERENCES staging_import_rows(id) ON DELETE CASCADE,
    severity VARCHAR(10) DEFAULT 'warning' CHECK (severity IN ('info', 'warning', 'error')),
    error_code VARCHAR(80) NOT NULL,
    field_name VARCHAR(100),
    raw_value TEXT,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Evidence Vault (preuves pour l'agent IA)
CREATE TABLE IF NOT EXISTS evidence_vault (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('file', 'opcua')),
    passport_id UUID REFERENCES import_passports(id),
    file_hash VARCHAR(64),
    sheet_name VARCHAR(100),
    line_start INT,
    line_end INT,
    column_name VARCHAR(100),
    opcua_node_id VARCHAR(255),
    timestamp_start TIMESTAMPTZ,
    timestamp_end TIMESTAMPTZ,
    context_json JSONB
);

-- Problèmes de qualité des données
CREATE TABLE IF NOT EXISTS data_quality_issues (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    passport_id UUID REFERENCES import_passports(id),
    issue_type VARCHAR(50),           -- 'missing_of', 'ambiguous_shift', 'outlier_value', etc.
    severity VARCHAR(10) DEFAULT 'warning' CHECK (severity IN ('info', 'warning', 'error')),
    machine_id INT REFERENCES machines(id),
    field_name VARCHAR(100),
    raw_value TEXT,
    description TEXT,
    detected_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================
-- HYPERTABLE TIMESCALEDB (Cycles machine — séries temporelles)
-- =============================================================

CREATE TABLE IF NOT EXISTS machine_cycles (
    time TIMESTAMPTZ NOT NULL,
    machine_id INT NOT NULL REFERENCES machines(id),
    production_order_id VARCHAR(50) REFERENCES production_orders(id) ON DELETE SET NULL,
    shift_id INT REFERENCES shifts(id) ON DELETE SET NULL,
    passport_id UUID REFERENCES import_passports(id),
    source_line_no INT,
    source_row_hash VARCHAR(64),
    cycle_counter BIGINT,
    -- Paramètres process canoniques
    cycle_time_s NUMERIC(7,3),
    dosing_time_s NUMERIC(7,3),
    injection_time_s NUMERIC(7,3),
    cooling_time_s NUMERIC(7,3),
    cushion_mm NUMERIC(6,3),
    switchover_pressure_bar NUMERIC(8,2),
    switchover_position NUMERIC(6,3),
    peak_pressure_bar NUMERIC(8,2),
    clamp_force_kn NUMERIC(8,2),
    mold_open_time_s NUMERIC(7,3),
    -- Qualité
    good_parts SMALLINT DEFAULT 1,
    scrap_flag BOOLEAN DEFAULT FALSE,
    -- Températures
    barrel_temp_zone1_c NUMERIC(6,2),
    barrel_temp_zone2_c NUMERIC(6,2),
    barrel_temp_zone3_c NUMERIC(6,2),
    mold_temperature_c NUMERIC(6,2),
    oil_temperature_c NUMERIC(6,2),
    energy_kwh NUMERIC(10,4),
    -- Métadonnées de réconciliation
    link_confidence NUMERIC(4,3) DEFAULT 1.0,
    quality_flag VARCHAR(20) DEFAULT 'valid' CHECK (quality_flag IN ('valid', 'suspect', 'outlier', 'sensor_error')),
    data_quality_status VARCHAR(20) DEFAULT 'valid',
    part_quality_status VARCHAR(30),
    defect_type VARCHAR(100),
    -- Données brutes supplémentaires (colonnes non canoniques)
    raw_data JSONB
);

-- Conversion en Hypertable (partitions de 7 jours)
SELECT create_hypertable(
    'machine_cycles',
    'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Index pour les requêtes fréquentes
CREATE INDEX IF NOT EXISTS idx_cycles_machine_time
    ON machine_cycles (machine_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_cycles_order
    ON machine_cycles (production_order_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_cycles_quality
    ON machine_cycles (quality_flag, time DESC)
    WHERE quality_flag != 'valid';

-- Idempotence par ligne source normalisee.
-- TimescaleDB impose d'inclure la colonne de partition temporelle dans les index uniques.
CREATE UNIQUE INDEX IF NOT EXISTS uq_machine_cycles_source_row
    ON machine_cycles (time, machine_id, source_row_hash)
    WHERE source_row_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_staging_import_rows_passport
    ON staging_import_rows (passport_id, status);

CREATE INDEX IF NOT EXISTS idx_import_rejections_passport
    ON import_rejections (passport_id, severity);

-- Politique de compression (données > 30 jours)
ALTER TABLE machine_cycles SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'time',
    timescaledb.compress_segmentby = 'machine_id'
);

SELECT add_compression_policy(
    'machine_cycles',
    INTERVAL '30 days',
    if_not_exists => TRUE
);

-- =============================================================
-- VUE CONTINUE (Synthèse horaire automatique)
-- =============================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS machine_cycles_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    machine_id,
    production_order_id,
    COUNT(*)                                                        AS cycle_count,
    ROUND(AVG(cycle_time_s)::NUMERIC, 3)                          AS avg_cycle_time_s,
    ROUND(STDDEV(cycle_time_s)::NUMERIC, 3)                       AS stddev_cycle_time_s,
    ROUND(AVG(cushion_mm)::NUMERIC, 3)                            AS avg_cushion_mm,
    ROUND(STDDEV(cushion_mm)::NUMERIC, 3)                         AS stddev_cushion_mm,
    ROUND(AVG(dosing_time_s)::NUMERIC, 3)                         AS avg_dosing_time_s,
    ROUND(AVG(switchover_pressure_bar)::NUMERIC, 2)               AS avg_switchover_pressure_bar,
    SUM(CASE WHEN scrap_flag THEN 1 ELSE 0 END)                   AS total_scraps,
    COUNT(*) - SUM(CASE WHEN scrap_flag THEN 1 ELSE 0 END)        AS total_good,
    ROUND(AVG(link_confidence)::NUMERIC, 3)                        AS avg_link_confidence
FROM machine_cycles
GROUP BY bucket, machine_id, production_order_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'machine_cycles_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- =============================================================
-- INDEX SUPPLÉMENTAIRES
-- =============================================================

CREATE INDEX IF NOT EXISTS idx_orders_machine_dates
    ON production_orders (machine_id, started_at, ended_at);

CREATE INDEX IF NOT EXISTS idx_shifts_machine_dates
    ON shifts (machine_id, started_at, ended_at);

CREATE INDEX IF NOT EXISTS idx_passports_hash
    ON import_passports (file_hash);

-- =============================================================
-- COMMENTAIRES
-- =============================================================
COMMENT ON TABLE machines IS 'Catalogue des presses à injecter et de leurs caractéristiques';
COMMENT ON TABLE production_orders IS 'Ordres de fabrication issus de l ERP (grain : OF complet)';
COMMENT ON TABLE shifts IS 'Équipes de production (grain : 8h par équipe par machine)';
COMMENT ON TABLE machine_cycles IS 'Cycles machine au cycle près (1 ligne = 1 injection)';
COMMENT ON TABLE import_passports IS 'Traçabilité des imports de fichiers (hash, parser, qualité)';
COMMENT ON TABLE evidence_vault IS 'Preuves sources pour justifier les diagnostics de l agent IA';

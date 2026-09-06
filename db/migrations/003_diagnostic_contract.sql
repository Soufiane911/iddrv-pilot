-- G2 deterministic investigation persistence (no LLM coupling)
CREATE TABLE IF NOT EXISTS incidents (
 id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), site_id INT NOT NULL REFERENCES sites(id),
 machine_id INT NOT NULL REFERENCES machines(id), production_order_id VARCHAR(50) REFERENCES production_orders(id) ON DELETE SET NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open','reviewed','closed')),
 severity VARCHAR(20) NOT NULL DEFAULT 'medium' CHECK (severity IN ('low','medium','high','critical')),
 symptom VARCHAR(100) NOT NULL, defect_type VARCHAR(100), started_at TIMESTAMPTZ NOT NULL, ended_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), data_cutoff TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 confidence VARCHAR(20) CHECK (confidence IN ('low','medium','high'))
);
CREATE TABLE IF NOT EXISTS diagnostic_runs (
 id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
 engine VARCHAR(40) NOT NULL DEFAULT 'deterministic_local', status VARCHAR(20) NOT NULL DEFAULT 'completed' CHECK (status IN ('running','completed','failed')),
 started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), completed_at TIMESTAMPTZ, data_cutoff TIMESTAMPTZ NOT NULL,
 result JSONB, error_message TEXT
);
CREATE TABLE IF NOT EXISTS diagnostic_evidence (
 id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), run_id UUID NOT NULL REFERENCES diagnostic_runs(id) ON DELETE CASCADE,
 source_kind VARCHAR(30) NOT NULL CHECK (source_kind IN ('cycle_aggregate','quality_check','maintenance_event','operator_note','production_order')),
 source_ref VARCHAR(200) NOT NULL, metric VARCHAR(100) NOT NULL, window_start TIMESTAMPTZ, window_end TIMESTAMPTZ,
 observation JSONB NOT NULL, baseline JSONB, delta NUMERIC, supports BOOLEAN NOT NULL, excerpt TEXT,
 UNIQUE(run_id, source_kind, source_ref, metric)
);
CREATE TABLE IF NOT EXISTS diagnostic_hypotheses (
 id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), run_id UUID NOT NULL REFERENCES diagnostic_runs(id) ON DELETE CASCADE,
 cause_code VARCHAR(120) NOT NULL, label TEXT NOT NULL, confidence NUMERIC(5,4) CHECK (confidence BETWEEN 0 AND 1),
 supporting_evidence_ids UUID[] NOT NULL DEFAULT '{}', contradicting_evidence_ids UUID[] NOT NULL DEFAULT '{}',
 missing_data JSONB NOT NULL DEFAULT '[]', next_check VARCHAR(200), UNIQUE(run_id, cause_code)
);
CREATE TABLE IF NOT EXISTS feedback (
 id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
 run_id UUID REFERENCES diagnostic_runs(id) ON DELETE SET NULL, verdict VARCHAR(30) NOT NULL,
 comment TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS action_proposals (
 id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
 run_id UUID REFERENCES diagnostic_runs(id) ON DELETE SET NULL, action_code VARCHAR(120) NOT NULL,
 label TEXT NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','accepted','rejected','done')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(incident_id, action_code)
);
CREATE INDEX IF NOT EXISTS idx_incidents_machine_time ON incidents(machine_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_site_status ON incidents(site_id, status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_diagnostic_runs_incident ON diagnostic_runs(incident_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_run ON diagnostic_evidence(run_id);
CREATE OR REPLACE VIEW incident_machine_context AS
SELECT i.id AS incident_id, i.machine_id, i.production_order_id, i.started_at, i.ended_at,
       COUNT(mc.time) AS cycle_count, AVG(mc.barrel_temp_zone2_c) AS avg_zone2_temp_c,
       AVG(mc.scrap_flag::int) AS scrap_rate, COUNT(q.quality_check_id) AS quality_check_count
FROM incidents i
LEFT JOIN machine_cycles mc ON mc.machine_id=i.machine_id AND mc.time BETWEEN i.started_at AND COALESCE(i.ended_at,i.data_cutoff)
LEFT JOIN quality_checks q ON q.machine_id=i.machine_id AND q.time BETWEEN i.started_at AND COALESCE(i.ended_at,i.data_cutoff)
GROUP BY i.id, i.machine_id, i.production_order_id, i.started_at, i.ended_at;

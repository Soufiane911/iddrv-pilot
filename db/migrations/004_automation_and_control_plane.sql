-- Migration 004: import worker state and pilot control-plane contracts.
--
-- The worker owns only import_jobs/import_job_events.  The remaining tables
-- are deliberately small, append-safe control-plane tables consumed by the
-- API and the 2D/3D clients.  No user credential is seeded here.

-- ---------------------------------------------------------------------------
-- Multi-site production topology
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS production_lines (
    id SERIAL PRIMARY KEY,
    site_id INT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    code VARCHAR(80) NOT NULL,
    name VARCHAR(150) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (site_id, code)
);

ALTER TABLE machines
    ADD COLUMN IF NOT EXISTS line_id INT REFERENCES production_lines(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS machine_layouts (
    id SERIAL PRIMARY KEY,
    machine_id INT NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    line_id INT REFERENCES production_lines(id) ON DELETE SET NULL,
    x NUMERIC(10,3) NOT NULL DEFAULT 0,
    y NUMERIC(10,3) NOT NULL DEFAULT 0,
    z NUMERIC(10,3) NOT NULL DEFAULT 0,
    rotation_deg NUMERIC(7,3) NOT NULL DEFAULT 0,
    display_order INT NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (machine_id)
);

CREATE INDEX IF NOT EXISTS idx_production_lines_site
    ON production_lines(site_id, name);
CREATE INDEX IF NOT EXISTS idx_machines_line
    ON machines(line_id, id);
CREATE INDEX IF NOT EXISTS idx_machine_layouts_line_order
    ON machine_layouts(line_id, display_order, machine_id);

-- ---------------------------------------------------------------------------
-- Local authentication/control plane (credentials are managed by the API)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(320) NOT NULL,
    password_hash TEXT NOT NULL,
    display_name VARCHAR(150) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower ON users(lower(email));

CREATE TABLE IF NOT EXISTS user_site_roles (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    site_id INT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('viewer','analyst','supervisor','admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, site_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(128) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_user_site_roles_site_role
    ON user_site_roles(site_id, role, user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_active
    ON sessions(user_id, expires_at)
    WHERE revoked_at IS NULL;

-- Human decision history is append-only; one proposal has at most one final
-- decision in the pilot.  The proposal itself remains in migration 003.
CREATE TABLE IF NOT EXISTS action_proposal_decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id UUID NOT NULL REFERENCES action_proposals(id) ON DELETE CASCADE,
    decided_by UUID NOT NULL REFERENCES users(id),
    status VARCHAR(20) NOT NULL CHECK (status IN ('approved','rejected')),
    reason TEXT,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (proposal_id)
);

CREATE INDEX IF NOT EXISTS idx_action_decisions_decided_by
    ON action_proposal_decisions(decided_by, decided_at DESC);

-- Idempotent pilot topology seed.  No credentials or tokens are inserted.
INSERT INTO production_lines(site_id, code, name)
VALUES (1, 'LINE-01', 'Ligne pilote')
ON CONFLICT (site_id, code) DO NOTHING;

INSERT INTO machine_layouts(machine_id, line_id, x, y, z, rotation_deg, display_order)
SELECT m.id, l.id,
       CASE m.erp_ref WHEN '1003' THEN 0 WHEN '606' THEN 1 WHEN '152' THEN 2 ELSE 3 END,
       0, 0, 0,
       CASE m.erp_ref WHEN '1003' THEN 1 WHEN '606' THEN 2 WHEN '152' THEN 3 ELSE 4 END
FROM machines m
JOIN production_lines l ON l.site_id = m.site_id AND l.code = 'LINE-01'
WHERE m.site_id = 1
ON CONFLICT (machine_id) DO NOTHING;

UPDATE machines m
SET line_id = ml.line_id
FROM machine_layouts ml
WHERE ml.machine_id = m.id
  AND m.line_id IS NULL;

-- ---------------------------------------------------------------------------
-- Watched-folder worker state
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS import_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id INT REFERENCES sites(id) ON DELETE SET NULL,
    source_kind VARCHAR(40) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    source_path TEXT NOT NULL,
    processing_path TEXT,
    archive_path TEXT,
    quarantine_path TEXT,
    file_hash VARCHAR(64),
    status VARCHAR(20) NOT NULL DEFAULT 'discovered'
        CHECK (status IN ('discovered','processing','retry_wait','completed','quarantined','failed')),
    attempt_count INT NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts INT NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    passport_id UUID REFERENCES import_passports(id) ON DELETE SET NULL,
    last_error_code VARCHAR(80),
    last_error TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(source_path, file_hash)
);

CREATE TABLE IF NOT EXISTS import_job_events (
    id BIGSERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES import_jobs(id) ON DELETE CASCADE,
    attempt INT NOT NULL DEFAULT 0,
    event_type VARCHAR(40) NOT NULL,
    status VARCHAR(20),
    source_path TEXT,
    destination_path TEXT,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- A copied file with the same bytes is one logical job even when it is
-- deposited under another path.  NULL hashes are allowed until stability is
-- confirmed; the worker always fills the hash before claiming the job.
CREATE UNIQUE INDEX IF NOT EXISTS uq_import_jobs_site_file_hash
    ON import_jobs(site_id, file_hash)
    WHERE file_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_import_jobs_status_schedule
    ON import_jobs(status, next_attempt_at, discovered_at);
CREATE INDEX IF NOT EXISTS idx_import_jobs_site_created
    ON import_jobs(site_id, discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_import_job_events_job_time
    ON import_job_events(job_id, created_at DESC);

COMMENT ON TABLE import_jobs IS 'Durable watched-folder state machine; one logical file hash is one job';
COMMENT ON TABLE import_job_events IS 'Append-only worker transitions and retry diagnostics';

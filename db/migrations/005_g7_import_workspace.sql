-- Migration 005: interactive import workspace and semantic validation.
CREATE TABLE IF NOT EXISTS import_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id INT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    name VARCHAR(180) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'collecting'
        CHECK (status IN ('collecting','profiling','needs_review','validated','integrated','failed')),
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS import_session_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES import_sessions(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    source_kind VARCHAR(40) NOT NULL DEFAULT 'unknown',
    mime_type VARCHAR(160),
    size_bytes BIGINT NOT NULL DEFAULT 0,
    file_hash VARCHAR(64),
    status VARCHAR(30) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued','profiling','needs_review','validated','integrated','failed')),
    profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (session_id, file_name, file_hash)
);

CREATE TABLE IF NOT EXISTS semantic_mapping_decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES import_sessions(id) ON DELETE CASCADE,
    file_id UUID REFERENCES import_session_files(id) ON DELETE CASCADE,
    source_column VARCHAR(180) NOT NULL,
    canonical_field VARCHAR(180),
    confidence NUMERIC(5,4) NOT NULL DEFAULT 0,
    decision VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (decision IN ('pending','accepted','rejected')),
    decided_by UUID REFERENCES users(id) ON DELETE SET NULL,
    decided_at TIMESTAMPTZ,
    UNIQUE (session_id, file_id, source_column)
);

CREATE INDEX IF NOT EXISTS idx_import_sessions_site_updated
    ON import_sessions(site_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_import_session_files_session
    ON import_session_files(session_id, created_at);

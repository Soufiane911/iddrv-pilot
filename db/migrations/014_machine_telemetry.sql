-- Stable identities live outside the Timescale hypertable. No data is deleted.
CREATE UNIQUE INDEX IF NOT EXISTS machines_site_id_id_telemetry_key ON machines(site_id, id);
CREATE TABLE machine_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id INT NOT NULL REFERENCES sites(id),
    machine_id INT NOT NULL UNIQUE,
    base_url TEXT NOT NULL,
    external_machine_id TEXT NOT NULL,
    secret_ref TEXT,
    poll_interval_s INT NOT NULL DEFAULT 1 CHECK (poll_interval_s BETWEEN 1 AND 60),
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    mapping_profile TEXT NOT NULL DEFAULT 'iddrv-cycle-v1' CHECK (mapping_profile = 'iddrv-cycle-v1'),
    state TEXT NOT NULL DEFAULT 'disabled' CHECK (state IN ('disabled','configured','collecting','retrying','access_error','configuration_error','gap_detected','contract_error')),
    public_error TEXT,
    last_test_at TIMESTAMPTZ,
    last_test_result JSONB,
    last_response_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_cycle_at TIMESTAMPTZ,
    next_poll_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    failure_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(site_id, base_url, external_machine_id),
    UNIQUE(id, site_id, machine_id),
    FOREIGN KEY(site_id, machine_id) REFERENCES machines(site_id, id)
);
CREATE UNIQUE INDEX machine_connections_one_active ON machine_connections(machine_id) WHERE enabled;
CREATE TABLE machine_stream_offsets (
    connection_id UUID PRIMARY KEY REFERENCES machine_connections(id),
    stream_id TEXT NOT NULL,
    cursor TEXT,
    last_sequence BIGINT,
    committed_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE machine_source_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL,
    site_id INT NOT NULL,
    machine_id INT NOT NULL,
    stream_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    sequence BIGINT NOT NULL CHECK (sequence >= 0),
    cycle_ended_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL,
    payload_hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('accepted','rejected')),
    rejection_reason TEXT,
    conflict_count INT NOT NULL DEFAULT 0,
    last_conflict_at TIMESTAMPTZ,
    UNIQUE(connection_id, stream_id, event_id),
    UNIQUE(connection_id, stream_id, sequence),
    UNIQUE(id, site_id, machine_id),
    FOREIGN KEY(connection_id, site_id, machine_id) REFERENCES machine_connections(id, site_id, machine_id)
);
-- Timescale columnstore permits adding a nullable column without an inline FK.
-- The transactional writer resolves this UUID from the ordinary identity journal.
ALTER TABLE machine_cycles ADD COLUMN source_event_id UUID;
CREATE INDEX machine_cycles_source_event_idx ON machine_cycles(source_event_id) WHERE source_event_id IS NOT NULL;
CREATE TABLE hdt_scoring_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID NOT NULL,
    machine_id INT NOT NULL,
    site_id INT NOT NULL,
    model_version TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'live' CHECK (mode IN ('live','backfill')),
    calculation_revision INT NOT NULL DEFAULT 1 CHECK (calculation_revision > 0),
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','running','completed','failed')),
    attempts INT NOT NULL DEFAULT 0,
    lease_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    public_error TEXT,
    UNIQUE(event_id, model_version, mode, calculation_revision),
    FOREIGN KEY(event_id, site_id, machine_id) REFERENCES machine_source_events(id, site_id, machine_id)
);
CREATE INDEX hdt_scoring_jobs_pending_idx ON hdt_scoring_jobs(state, created_at);

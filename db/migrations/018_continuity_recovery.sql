-- A retention gap is resolved by an explicit human decision. History and
-- offsets remain append-only evidence; no automatic jump to the latest item.
CREATE TABLE IF NOT EXISTS continuity_recovery_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES machine_connections(id),
    site_id INT NOT NULL,
    machine_id INT NOT NULL,
    actor_user_id UUID NOT NULL REFERENCES users(id),
    previous_stream_id TEXT NOT NULL,
    new_stream_id TEXT NOT NULL,
    last_validated_cursor TEXT,
    last_validated_sequence BIGINT,
    available_from_sequence BIGINT,
    decision TEXT NOT NULL CHECK (decision IN ('resume_available', 'initialize_new_stream')),
    confirmation TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (site_id, machine_id) REFERENCES machines(site_id, id)
);
CREATE INDEX IF NOT EXISTS continuity_recovery_connection_idx
    ON continuity_recovery_reviews(connection_id, created_at DESC);

-- Keep the latest human verdict lookup bounded for incident catalogue/detail reads.
CREATE INDEX IF NOT EXISTS idx_feedback_incident_created
    ON feedback (incident_id, created_at DESC, id DESC);

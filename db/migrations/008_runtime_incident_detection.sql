-- Migration 008: idempotent runtime incident detection.

ALTER TABLE incidents ADD COLUMN IF NOT EXISTS detection_key VARCHAR(64);

CREATE UNIQUE INDEX IF NOT EXISTS uq_incidents_detection_key
    ON incidents(detection_key)
    WHERE detection_key IS NOT NULL;

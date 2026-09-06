-- Migration 007: make ingestion identity and idempotence site-scoped.

UPDATE import_passports SET site_id = 1 WHERE site_id IS NULL;
UPDATE import_jobs SET site_id = 1 WHERE site_id IS NULL;

ALTER TABLE import_passports ALTER COLUMN site_id SET NOT NULL;
ALTER TABLE import_jobs ALTER COLUMN site_id SET NOT NULL;

ALTER TABLE import_passports
    DROP CONSTRAINT IF EXISTS import_passports_file_hash_key;
DROP INDEX IF EXISTS uq_import_jobs_file_hash;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM import_passports
        WHERE file_hash IS NOT NULL
        GROUP BY site_id, file_hash
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'duplicate import_passports hashes exist inside one site';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM import_jobs
        WHERE file_hash IS NOT NULL
        GROUP BY site_id, file_hash
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'duplicate import_jobs hashes exist inside one site';
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_import_passports_site_file_hash
    ON import_passports(site_id, file_hash)
    WHERE file_hash IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_import_jobs_site_file_hash
    ON import_jobs(site_id, file_hash)
    WHERE file_hash IS NOT NULL;

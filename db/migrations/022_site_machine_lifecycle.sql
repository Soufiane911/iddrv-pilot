-- Site and press lifecycle.
-- Archive operations are deliberately non-destructive: operational rows and
-- their historical references remain available after a tenant/equipment is
-- archived.

ALTER TABLE sites
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

DO $$
BEGIN
    ALTER TABLE sites ADD CONSTRAINT sites_lifecycle_status_check
        CHECK (status IN ('active', 'archived'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- No tenant may be silently assigned to site 1.  Existing rows already
-- carry their migrated site, while all future writes must provide it.
ALTER TABLE machines ALTER COLUMN site_id DROP DEFAULT;
ALTER TABLE import_passports ALTER COLUMN site_id DROP DEFAULT;
ALTER TABLE production_orders ALTER COLUMN site_id DROP DEFAULT;

ALTER TABLE machines
    ADD COLUMN IF NOT EXISTS workshop_code VARCHAR(50),
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

-- The prototype made both ERP identity and display name mandatory.  Existing
-- rows are repaired before tightening the new Atelier contract.
UPDATE machines
SET name = COALESCE(NULLIF(BTRIM(name), ''), 'Presse ' || id::text)
WHERE name IS NULL OR BTRIM(name) = '';

UPDATE machines
SET erp_ref = NULL
WHERE erp_ref IS NOT NULL AND BTRIM(erp_ref) = '';

UPDATE machines
SET workshop_code = COALESCE(NULLIF(BTRIM(workshop_code), ''), NULLIF(BTRIM(erp_ref), ''), 'MACHINE-' || id::text)
WHERE workshop_code IS NULL OR BTRIM(workshop_code) = '';

-- Keep old ERP-import writers working while making the persisted column NOT
-- NULL: legacy inserts that provide an ERP reference get that reference as
-- their initial workshop code.  New API writes always provide it explicitly.
CREATE OR REPLACE FUNCTION fill_machine_workshop_code() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.erp_ref IS NOT NULL AND BTRIM(NEW.erp_ref) = '' THEN
        NEW.erp_ref := NULL;
    END IF;
    IF NEW.workshop_code IS NULL OR BTRIM(NEW.workshop_code) = '' THEN
        IF NEW.erp_ref IS NOT NULL THEN
            NEW.workshop_code := BTRIM(NEW.erp_ref);
        END IF;
    END IF;
    IF NEW.name IS NULL OR BTRIM(NEW.name) = '' THEN
        NEW.name := 'Presse ' || COALESCE(NEW.workshop_code, NEW.erp_ref);
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS machine_workshop_code_compatibility ON machines;
CREATE TRIGGER machine_workshop_code_compatibility
    BEFORE INSERT OR UPDATE OF workshop_code, erp_ref, name ON machines
    FOR EACH ROW EXECUTE FUNCTION fill_machine_workshop_code();

ALTER TABLE machines ALTER COLUMN erp_ref DROP NOT NULL;
ALTER TABLE machines ALTER COLUMN name SET NOT NULL;
ALTER TABLE machines ALTER COLUMN workshop_code SET NOT NULL;

DO $$
BEGIN
    ALTER TABLE machines ADD CONSTRAINT machines_lifecycle_status_check
        CHECK (status IN ('active', 'inactive', 'archived'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 019 intentionally made historical tables append-only.  Site/press identity
-- follows the same rule: an archived identity cannot be physically removed.
-- PostgreSQL UNIQUE already treats NULL as distinct, so this constraint gives
-- the required "unique when present" behavior and remains inferable by the
-- legacy ERP importer's ON CONFLICT(site_id, erp_ref) clause.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'machines'::regclass
          AND conname = 'machines_site_id_erp_ref_key'
    ) THEN
        ALTER TABLE machines ADD CONSTRAINT machines_site_id_erp_ref_key
            UNIQUE (site_id, erp_ref);
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS machines_site_workshop_code_key
    ON machines (site_id, workshop_code);

CREATE INDEX IF NOT EXISTS sites_status_idx ON sites (status, id);
CREATE INDEX IF NOT EXISTS machines_site_status_idx ON machines (site_id, status, id);

UPDATE sites SET name = 'Site ' || id::text WHERE btrim(name) = '';

DO $$
BEGIN
    ALTER TABLE sites ADD CONSTRAINT sites_name_nonempty
        CHECK (btrim(name) <> '');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$
BEGIN
    ALTER TABLE machines ADD CONSTRAINT machines_name_nonempty
        CHECK (btrim(name) <> '');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$
BEGIN
    ALTER TABLE machines ADD CONSTRAINT machines_workshop_code_nonempty
        CHECK (btrim(workshop_code) <> '');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Identity rows are append-only. TRUNCATE remains available to the
-- explicitly isolated test/database reset tooling, while ordinary DELETEs
-- cannot bypass the archive API.
CREATE OR REPLACE FUNCTION reject_identity_delete() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'immutable_identity';
END $$;

DROP TRIGGER IF EXISTS immutable_site_identity ON sites;
CREATE TRIGGER immutable_site_identity
    BEFORE DELETE ON sites FOR EACH ROW EXECUTE FUNCTION reject_identity_delete();
DROP TRIGGER IF EXISTS immutable_machine_identity ON machines;
CREATE TRIGGER immutable_machine_identity
    BEFORE DELETE ON machines FOR EACH ROW EXECUTE FUNCTION reject_identity_delete();

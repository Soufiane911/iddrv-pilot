-- Site gateway sources, historical machine mappings and durable cycle receipts.
--
-- A receipt is the source of truth for an HTTP push.  It is written before
-- attempting to materialise a machine cycle, so an unmapped press or unknown
-- OF can be repaired without losing the original event.

CREATE TABLE IF NOT EXISTS site_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id INT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    kind TEXT NOT NULL DEFAULT 'gateway_push' CHECK (kind = 'gateway_push'),
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'disabled', 'revoked')),
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id, site_id)
);
CREATE INDEX IF NOT EXISTS site_sources_site_idx ON site_sources(site_id, created_at DESC);
-- A site has one active gateway identity. Disabled historical sources remain
-- visible and may be audited, but retries cannot create a second live source.
CREATE UNIQUE INDEX IF NOT EXISTS site_sources_one_active_idx
    ON site_sources(site_id) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS site_source_credentials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL,
    site_id INT NOT NULL,
    secret_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ,
    FOREIGN KEY (source_id, site_id) REFERENCES site_sources(id, site_id) ON DELETE CASCADE,
    UNIQUE (id, source_id),
    CHECK (revoked_at IS NULL OR revoked_at >= created_at)
);
CREATE UNIQUE INDEX IF NOT EXISTS site_source_one_current_credential
    ON site_source_credentials(source_id) WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS source_machine_mappings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL,
    site_id INT NOT NULL,
    external_machine_id TEXT NOT NULL,
    machine_id INT NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (source_id, site_id) REFERENCES site_sources(id, site_id) ON DELETE CASCADE,
    FOREIGN KEY (site_id, machine_id) REFERENCES machines(site_id, id),
    UNIQUE (id, source_id, site_id),
    CHECK (length(btrim(external_machine_id)) > 0),
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE UNIQUE INDEX IF NOT EXISTS source_mapping_current_identity
    ON source_machine_mappings(source_id, external_machine_id)
    WHERE valid_to IS NULL;
CREATE INDEX IF NOT EXISTS source_mapping_lookup_idx
    ON source_machine_mappings(source_id, external_machine_id, valid_from DESC);
CREATE INDEX IF NOT EXISTS source_mapping_machine_idx
    ON source_machine_mappings(site_id, machine_id, valid_from DESC);

CREATE TABLE IF NOT EXISTS cycle_event_receipts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL,
    site_id INT NOT NULL,
    event_id TEXT NOT NULL,
    external_machine_id TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    payload_hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    machine_id INT,
    production_order_id VARCHAR(50),
    work_order_id UUID,
    work_order_allocation_id UUID,
    state TEXT NOT NULL DEFAULT 'pending'
        CHECK (state IN ('pending', 'rejected', 'materialized')),
    pending_reason TEXT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    materialized_at TIMESTAMPTZ,
    FOREIGN KEY (source_id, site_id) REFERENCES site_sources(id, site_id) ON DELETE CASCADE,
    FOREIGN KEY (site_id, machine_id) REFERENCES machines(site_id, id),
    FOREIGN KEY (site_id, production_order_id)
        REFERENCES production_orders(site_id, id),
    FOREIGN KEY (site_id, work_order_id)
        REFERENCES work_orders(site_id, id),
    FOREIGN KEY (site_id, work_order_allocation_id)
        REFERENCES work_order_allocations(site_id, id),
    UNIQUE (source_id, event_id),
    UNIQUE (id, site_id),
    CHECK ((state = 'materialized') = (materialized_at IS NOT NULL)),
    CHECK (state <> 'materialized' OR (machine_id IS NOT NULL AND work_order_id IS NOT NULL)),
    CHECK (btrim(event_id) <> ''),
    CHECK (btrim(external_machine_id) <> '')
);
-- Upgrade a receipt table created by an early prototype. CREATE TABLE IF NOT
-- EXISTS does not add columns to an existing table, so add every receipt
-- identity/processing column explicitly before any query below references it.
DO $$
BEGIN
    ALTER TABLE cycle_event_receipts ADD COLUMN IF NOT EXISTS id UUID DEFAULT uuid_generate_v4();
    ALTER TABLE cycle_event_receipts ADD COLUMN IF NOT EXISTS source_id UUID;
    ALTER TABLE cycle_event_receipts ADD COLUMN IF NOT EXISTS site_id INT;
    ALTER TABLE cycle_event_receipts ADD COLUMN IF NOT EXISTS event_id TEXT;
    ALTER TABLE cycle_event_receipts ADD COLUMN IF NOT EXISTS external_machine_id TEXT;
    ALTER TABLE cycle_event_receipts ADD COLUMN IF NOT EXISTS occurred_at TIMESTAMPTZ;
    ALTER TABLE cycle_event_receipts ADD COLUMN IF NOT EXISTS payload_hash TEXT;
    ALTER TABLE cycle_event_receipts ADD COLUMN IF NOT EXISTS payload JSONB DEFAULT '{}'::jsonb;
    ALTER TABLE cycle_event_receipts ADD COLUMN IF NOT EXISTS machine_id INT;
    ALTER TABLE cycle_event_receipts ADD COLUMN IF NOT EXISTS production_order_id VARCHAR(50);
    ALTER TABLE cycle_event_receipts ADD COLUMN IF NOT EXISTS work_order_id UUID;
    ALTER TABLE cycle_event_receipts ADD COLUMN IF NOT EXISTS work_order_allocation_id UUID;
    ALTER TABLE cycle_event_receipts ADD COLUMN IF NOT EXISTS state TEXT DEFAULT 'pending';
    ALTER TABLE cycle_event_receipts ADD COLUMN IF NOT EXISTS pending_reason TEXT;
    ALTER TABLE cycle_event_receipts ADD COLUMN IF NOT EXISTS received_at TIMESTAMPTZ DEFAULT now();
    ALTER TABLE cycle_event_receipts ADD COLUMN IF NOT EXISTS materialized_at TIMESTAMPTZ;
EXCEPTION WHEN undefined_table THEN
    RAISE EXCEPTION 'migration_021_receipts_table_unavailable'
        USING HINT = 'Apply the CREATE TABLE portion of migration 021 first';
END $$;

-- Required identity cannot be reconstructed safely for old rows. Fail with a
-- useful migration error instead of an undefined-column or NOT NULL error.
DO $$
DECLARE missing_count BIGINT;
BEGIN
    SELECT count(*) INTO missing_count FROM cycle_event_receipts
     WHERE id IS NULL OR source_id IS NULL OR site_id IS NULL OR event_id IS NULL
        OR external_machine_id IS NULL OR occurred_at IS NULL OR payload_hash IS NULL
        OR payload IS NULL OR state IS NULL OR received_at IS NULL;
    IF missing_count > 0 THEN
        RAISE EXCEPTION 'migration_021_receipts_missing_required_values: % rows', missing_count
            USING HINT = 'Backfill source_id/site_id/event_id/occurred_at/payload_hash before rerunning migration 021';
    END IF;
    UPDATE cycle_event_receipts
       SET materialized_at=COALESCE(materialized_at, received_at, now())
     WHERE state='materialized' AND materialized_at IS NULL;
END $$;
ALTER TABLE cycle_event_receipts
    ALTER COLUMN id SET NOT NULL,
    ALTER COLUMN source_id SET NOT NULL,
    ALTER COLUMN site_id SET NOT NULL,
    ALTER COLUMN event_id SET NOT NULL,
    ALTER COLUMN external_machine_id SET NOT NULL,
    ALTER COLUMN occurred_at SET NOT NULL,
    ALTER COLUMN payload_hash SET NOT NULL,
    ALTER COLUMN payload SET NOT NULL,
    ALTER COLUMN state SET NOT NULL,
    ALTER COLUMN received_at SET NOT NULL;

CREATE INDEX IF NOT EXISTS cycle_event_receipts_pending_idx
    ON cycle_event_receipts(site_id, received_at)
    WHERE state = 'pending';
CREATE INDEX IF NOT EXISTS cycle_event_receipts_mapping_idx
    ON cycle_event_receipts(source_id, external_machine_id, occurred_at);

-- Repair malformed identities from an early prototype before tightening
-- constraints. The receipt payload itself remains untouched.
UPDATE site_sources
   SET name = 'Passerelle ' || id::text
 WHERE btrim(name) = '';
UPDATE cycle_event_receipts
   SET event_id = 'legacy-' || id::text
 WHERE btrim(event_id) = '';
UPDATE cycle_event_receipts
   SET external_machine_id = 'machine-' || id::text
 WHERE btrim(external_machine_id) = '';

-- Upgrade the first draft of this migration, whose receipt state had no
-- explicit rejected value.  Constraint names generated by PostgreSQL vary
-- across the initial schema, so inspect their definitions rather than relying
-- on one generated name.
DO $$
DECLARE constraint_row RECORD;
BEGIN
    FOR constraint_row IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'cycle_event_receipts'::regclass
          AND contype = 'c'
          AND (pg_get_constraintdef(oid) ILIKE '%pending%materialized%'
               OR pg_get_constraintdef(oid) ILIKE '%state%pending%')
    LOOP
        EXECUTE format('ALTER TABLE cycle_event_receipts DROP CONSTRAINT %I', constraint_row.conname);
    END LOOP;
END $$;
ALTER TABLE cycle_event_receipts
    DROP CONSTRAINT IF EXISTS cycle_event_receipts_state_check_v2,
    DROP CONSTRAINT IF EXISTS cycle_event_receipts_materialized_state_check_v2;
ALTER TABLE cycle_event_receipts
    ADD CONSTRAINT cycle_event_receipts_state_check_v2
        CHECK (state IN ('pending', 'rejected', 'materialized')),
    ADD CONSTRAINT cycle_event_receipts_materialized_state_check_v2
        CHECK ((state = 'materialized') = (materialized_at IS NOT NULL));

-- Compatibility constraints for databases that already had the prototype
-- tables.  The checks make malformed source identities impossible to store.
DO $$
BEGIN
    ALTER TABLE site_sources ADD CONSTRAINT site_sources_name_nonempty
        CHECK (btrim(name) <> '');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$
BEGIN
    ALTER TABLE cycle_event_receipts ADD CONSTRAINT cycle_event_receipts_event_id_nonempty
        CHECK (btrim(event_id) <> '');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$
BEGIN
    ALTER TABLE cycle_event_receipts ADD CONSTRAINT cycle_event_receipts_external_machine_nonempty
        CHECK (btrim(external_machine_id) <> '');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- The legacy machine_cycles table is retained as the materialised read model.
-- Its existing source_event_id cannot reference a gateway receipt because it is
-- coupled to the polling connection table, therefore this independent nullable
-- anchor is used for gateway pushes. Timescale unique indexes must include the
-- partitioning column, so both the uniqueness key and the FK include time.
ALTER TABLE machine_cycles
    ADD COLUMN IF NOT EXISTS cycle_event_receipt_id UUID,
    ADD COLUMN IF NOT EXISTS work_order_id UUID,
    ADD COLUMN IF NOT EXISTS work_order_allocation_id UUID;
DO $$ BEGIN
    ALTER TABLE cycle_event_receipts
        ADD CONSTRAINT cycle_event_receipts_id_time_key UNIQUE (id, occurred_at);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS machine_cycles_gateway_receipt_key
    ON machine_cycles(cycle_event_receipt_id, time)
    WHERE cycle_event_receipt_id IS NOT NULL;
DO $$ BEGIN
    ALTER TABLE machine_cycles
        ADD CONSTRAINT machine_cycles_gateway_receipt_fkey
        FOREIGN KEY (cycle_event_receipt_id, time)
        REFERENCES cycle_event_receipts(id, occurred_at) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE machine_cycles
        ADD CONSTRAINT machine_cycles_work_order_fkey
        FOREIGN KEY (order_site_id, work_order_id)
        REFERENCES work_orders(site_id, id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE machine_cycles
        ADD CONSTRAINT machine_cycles_work_order_allocation_fkey
        FOREIGN KEY (order_site_id, work_order_allocation_id)
        REFERENCES work_order_allocations(site_id, id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- A receipt table may have been created by the first gateway prototype, so
-- CREATE TABLE IF NOT EXISTS above does not have an opportunity to install
-- its constraints. Add the cross-table invariants explicitly for that case;
-- duplicate-object handling keeps a fresh or already-upgraded database
-- idempotent as well.
DO $$ BEGIN
    ALTER TABLE cycle_event_receipts
        ADD CONSTRAINT cycle_event_receipts_source_site_fkey
        FOREIGN KEY (source_id, site_id) REFERENCES site_sources(id, site_id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE cycle_event_receipts
        ADD CONSTRAINT cycle_event_receipts_work_order_fkey
        FOREIGN KEY (site_id, work_order_id) REFERENCES work_orders(site_id, id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE cycle_event_receipts
        ADD CONSTRAINT cycle_event_receipts_allocation_fkey
        FOREIGN KEY (site_id, work_order_allocation_id) REFERENCES work_order_allocations(site_id, id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE cycle_event_receipts
        ADD CONSTRAINT cycle_event_receipts_source_event_key UNIQUE (source_id, event_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

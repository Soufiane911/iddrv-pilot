-- Migration 006: site-scoped ingestion isolation.
-- Production orders, machine aliases and import passports are now
-- site-scoped so two factories can share the same external order id,
-- machine reference or alias without cross-contamination.
--
-- Re-playable: every statement is guarded with IF NOT EXISTS / DO $$.

-- ---------------------------------------------------------------------------
-- 1. production_orders: add site_id, change PK to composite (site_id, id)
-- ---------------------------------------------------------------------------

-- 1a. Add site_id column (default to site 1 for existing rows).
ALTER TABLE production_orders ADD COLUMN IF NOT EXISTS site_id INT DEFAULT 1;
UPDATE production_orders SET site_id = 1 WHERE site_id IS NULL;
ALTER TABLE production_orders ALTER COLUMN site_id SET NOT NULL;
ALTER TABLE production_orders ALTER COLUMN site_id SET DEFAULT 1;

DO $$ BEGIN
    ALTER TABLE production_orders ADD CONSTRAINT fk_production_orders_site
        FOREIGN KEY (site_id) REFERENCES sites(id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 1b. Add site_id column to every child table that references production_orders.
ALTER TABLE machine_cycles ADD COLUMN IF NOT EXISTS order_site_id INT;
ALTER TABLE shifts ADD COLUMN IF NOT EXISTS order_site_id INT;
ALTER TABLE quality_checks ADD COLUMN IF NOT EXISTS order_site_id INT;
ALTER TABLE maintenance_events ADD COLUMN IF NOT EXISTS order_site_id INT;
ALTER TABLE operator_notes ADD COLUMN IF NOT EXISTS order_site_id INT;
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS order_site_id INT;

-- 1c. Populate order_site_id on child tables from the machines relation.
UPDATE machine_cycles
SET order_site_id = m.site_id
FROM machines m
WHERE machine_cycles.machine_id = m.id
  AND machine_cycles.order_site_id IS NULL;

UPDATE shifts
SET order_site_id = m.site_id
FROM machines m
WHERE shifts.machine_id = m.id
  AND shifts.order_site_id IS NULL;

UPDATE quality_checks
SET order_site_id = m.site_id
FROM machines m
WHERE quality_checks.machine_id = m.id
  AND quality_checks.order_site_id IS NULL;

UPDATE maintenance_events
SET order_site_id = m.site_id
FROM machines m
WHERE maintenance_events.machine_id = m.id
  AND maintenance_events.order_site_id IS NULL;

UPDATE operator_notes
SET order_site_id = m.site_id
FROM machines m
WHERE operator_notes.machine_id = m.id
  AND operator_notes.order_site_id IS NULL;

UPDATE incidents
SET order_site_id = i2.site_id
FROM incidents i2
WHERE incidents.id = i2.id
  AND incidents.order_site_id IS NULL;

-- 1d. Drop existing foreign-key constraints referencing production_orders(id).
--     We target both old names (single-column PK) and new names (composite PK)
--     so the migration is re-playable.
ALTER TABLE machine_cycles DROP CONSTRAINT IF EXISTS machine_cycles_production_order_id_fkey;
ALTER TABLE machine_cycles DROP CONSTRAINT IF EXISTS machine_cycles_production_order_fkey;
ALTER TABLE shifts DROP CONSTRAINT IF EXISTS shifts_production_order_id_fkey;
ALTER TABLE shifts DROP CONSTRAINT IF EXISTS shifts_production_order_fkey;
ALTER TABLE quality_checks DROP CONSTRAINT IF EXISTS quality_checks_production_order_id_fkey;
ALTER TABLE quality_checks DROP CONSTRAINT IF EXISTS quality_checks_production_order_fkey;
ALTER TABLE maintenance_events DROP CONSTRAINT IF EXISTS maintenance_events_production_order_id_fkey;
ALTER TABLE maintenance_events DROP CONSTRAINT IF EXISTS maintenance_events_production_order_fkey;
ALTER TABLE operator_notes DROP CONSTRAINT IF EXISTS operator_notes_production_order_id_fkey;
ALTER TABLE operator_notes DROP CONSTRAINT IF EXISTS operator_notes_production_order_fkey;
ALTER TABLE incidents DROP CONSTRAINT IF EXISTS incidents_production_order_id_fkey;
ALTER TABLE incidents DROP CONSTRAINT IF EXISTS incidents_production_order_fkey;

-- 1e. Drop the old single-column primary key on production_orders.
ALTER TABLE production_orders DROP CONSTRAINT IF EXISTS production_orders_pkey;

-- 1f. Create the new composite primary key.
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'production_orders'::regclass AND contype = 'p'
    ) THEN
        ALTER TABLE production_orders ADD PRIMARY KEY (site_id, id);
    END IF;
END $$;

-- 1g. Re-create foreign-key constraints using the composite key.
DO $$ BEGIN
    ALTER TABLE machine_cycles
        ADD CONSTRAINT machine_cycles_production_order_fkey
        FOREIGN KEY (order_site_id, production_order_id)
        REFERENCES production_orders(site_id, id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE shifts
        ADD CONSTRAINT shifts_production_order_fkey
        FOREIGN KEY (order_site_id, production_order_id)
        REFERENCES production_orders(site_id, id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE quality_checks
        ADD CONSTRAINT quality_checks_production_order_fkey
        FOREIGN KEY (order_site_id, production_order_id)
        REFERENCES production_orders(site_id, id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE maintenance_events
        ADD CONSTRAINT maintenance_events_production_order_fkey
        FOREIGN KEY (order_site_id, production_order_id)
        REFERENCES production_orders(site_id, id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE operator_notes
        ADD CONSTRAINT operator_notes_production_order_fkey
        FOREIGN KEY (order_site_id, production_order_id)
        REFERENCES production_orders(site_id, id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE incidents
        ADD CONSTRAINT incidents_production_order_fkey
        FOREIGN KEY (order_site_id, production_order_id)
        REFERENCES production_orders(site_id, id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ---------------------------------------------------------------------------
-- 2. machine_aliases: scope unique constraint to machine (inherently site-scoped)
-- ---------------------------------------------------------------------------

-- Drop the old global constraint.
ALTER TABLE machine_aliases DROP CONSTRAINT IF EXISTS machine_aliases_alias_context_alias_value_key;

-- Create a new constraint scoped per machine (each machine belongs to exactly one site).
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'machine_aliases'::regclass
          AND conname = 'machine_aliases_machine_context_value_key'
    ) THEN
        ALTER TABLE machine_aliases
            ADD CONSTRAINT machine_aliases_machine_context_value_key
            UNIQUE (machine_id, alias_context, alias_value);
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 3. import_passports: add site_id for import isolation
-- ---------------------------------------------------------------------------

ALTER TABLE import_passports ADD COLUMN IF NOT EXISTS site_id INT;
UPDATE import_passports SET site_id = 1 WHERE site_id IS NULL;

DO $$ BEGIN
    ALTER TABLE import_passports ADD CONSTRAINT fk_import_passports_site
        FOREIGN KEY (site_id) REFERENCES sites(id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ---------------------------------------------------------------------------
-- 4. import_jobs: ensure site_id is NOT NULL when the watcher creates a job
-- ---------------------------------------------------------------------------

-- The column already exists as nullable; we make it a hard constraint
-- in the application layer (the watcher always provides site_id now).
-- For existing rows, default to site 1.
UPDATE import_jobs SET site_id = 1 WHERE site_id IS NULL;

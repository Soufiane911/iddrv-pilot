-- =============================================================
-- Migration 001 : Multi-site support and transactional status
-- =============================================================

-- Track the schema version so an older setup script cannot overwrite a newer database.
CREATE TABLE IF NOT EXISTS schema_version (
    version VARCHAR(50) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO schema_version (version)
VALUES ('1.0.0')
ON CONFLICT (version) DO NOTHING;

-- 1. Create sites table if not exists
CREATE TABLE IF NOT EXISTS sites (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Insert default site
INSERT INTO sites (id, name, timezone) 
VALUES (1, 'Usine Principale', 'Europe/Paris') 
ON CONFLICT (id) DO NOTHING;

-- Fix the sequence for sites id
SELECT setval(pg_get_serial_sequence('sites', 'id'), COALESCE(max(id), 1)) FROM sites;

-- 3. Add site_id column to machines if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='machines' AND column_name='site_id') THEN
        ALTER TABLE machines ADD COLUMN site_id INT NOT NULL REFERENCES sites(id) DEFAULT 1;
    END IF;
END $$;

-- 4. Drop old UNIQUE constraint on erp_ref if exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'machines_erp_ref_key') THEN
        ALTER TABLE machines DROP CONSTRAINT machines_erp_ref_key;
    END IF;
END $$;

-- 5. Add UNIQUE (site_id, erp_ref) constraint if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'machines_site_id_erp_ref_key') THEN
        ALTER TABLE machines ADD CONSTRAINT machines_site_id_erp_ref_key UNIQUE (site_id, erp_ref);
    END IF;
END $$;

-- 6. Add status column to import_passports if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='import_passports' AND column_name='status') THEN
        ALTER TABLE import_passports ADD COLUMN status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed'));
    END IF;
END $$;

-- 7. Update foreign keys in machine_cycles (shift_id and production_order_id)
-- First drop existing constraint if exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'machine_cycles_shift_id_fkey') THEN
        ALTER TABLE machine_cycles DROP CONSTRAINT machine_cycles_shift_id_fkey;
    END IF;
END $$;

-- Add new constraint with ON DELETE SET NULL
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'machine_cycles_shift_id_fkey') THEN
        ALTER TABLE machine_cycles ADD CONSTRAINT machine_cycles_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES shifts(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Also add foreign key constraint on production_order_id if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'machine_cycles_production_order_id_fkey')
       AND EXISTS (
           SELECT 1
           FROM pg_constraint c
           JOIN pg_class t ON t.oid = c.conrelid
           JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = c.conkey[1]
           WHERE t.relname = 'production_orders'
             AND c.contype IN ('p', 'u')
             AND cardinality(c.conkey) = 1
             AND a.attname = 'id'
       ) THEN
        ALTER TABLE machine_cycles ADD CONSTRAINT machine_cycles_production_order_id_fkey FOREIGN KEY (production_order_id) REFERENCES production_orders(id) ON DELETE SET NULL;
    END IF;
END $$;

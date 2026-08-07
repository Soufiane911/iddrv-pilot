-- Migration 011: make machine aliases explicitly site-scoped and unambiguous.

ALTER TABLE machine_aliases ADD COLUMN IF NOT EXISTS site_id INT;

UPDATE machine_aliases ma
SET site_id = m.site_id
FROM machines m
WHERE m.id = ma.machine_id
  AND ma.site_id IS NULL;

ALTER TABLE machine_aliases ALTER COLUMN site_id SET NOT NULL;

ALTER TABLE machine_aliases
    DROP CONSTRAINT IF EXISTS machine_aliases_machine_context_value_key;
ALTER TABLE machine_aliases
    DROP CONSTRAINT IF EXISTS machine_aliases_alias_context_alias_value_key;

DO $$
DECLARE duplicate_alias TEXT;
BEGIN
    SELECT format('site=%s context=%s value=%s',site_id,alias_context,alias_value)
      INTO duplicate_alias
      FROM machine_aliases
     GROUP BY site_id,alias_context,alias_value
    HAVING COUNT(DISTINCT machine_id) > 1
     LIMIT 1;
    IF duplicate_alias IS NOT NULL THEN
        RAISE EXCEPTION 'Ambiguous machine aliases prevent migration 011: %', duplicate_alias
            USING HINT='Resolve the duplicate alias to one machine, then restart setup_db.';
    END IF;
END $$;

DO $$ BEGIN
    ALTER TABLE machine_aliases
        ADD CONSTRAINT machine_aliases_site_machine_fkey
        FOREIGN KEY (site_id, machine_id)
        REFERENCES machines(site_id, id)
        ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='machine_aliases'::regclass
          AND conname='machine_aliases_site_context_value_key'
    ) THEN
        ALTER TABLE machine_aliases
            ADD CONSTRAINT machine_aliases_site_context_value_key
            UNIQUE (site_id, alias_context, alias_value);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_machine_aliases_site_value
    ON machine_aliases(site_id, alias_value);

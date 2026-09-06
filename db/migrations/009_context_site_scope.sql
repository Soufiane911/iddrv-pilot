-- Migration 009: site-scope external context identifiers.

ALTER TABLE quality_checks ADD COLUMN IF NOT EXISTS site_id INT;
ALTER TABLE maintenance_events ADD COLUMN IF NOT EXISTS site_id INT;
ALTER TABLE operator_notes ADD COLUMN IF NOT EXISTS site_id INT;

UPDATE quality_checks q SET site_id=m.site_id
FROM machines m WHERE q.machine_id=m.id AND q.site_id IS NULL;
UPDATE maintenance_events e SET site_id=m.site_id
FROM machines m WHERE e.machine_id=m.id AND e.site_id IS NULL;
UPDATE operator_notes n SET site_id=m.site_id
FROM machines m WHERE n.machine_id=m.id AND n.site_id IS NULL;

UPDATE quality_checks SET site_id=COALESCE(order_site_id,1) WHERE site_id IS NULL;
UPDATE maintenance_events SET site_id=COALESCE(order_site_id,1) WHERE site_id IS NULL;
UPDATE operator_notes SET site_id=COALESCE(order_site_id,1) WHERE site_id IS NULL;

ALTER TABLE quality_checks ALTER COLUMN site_id SET NOT NULL;
ALTER TABLE maintenance_events ALTER COLUMN site_id SET NOT NULL;
ALTER TABLE operator_notes ALTER COLUMN site_id SET NOT NULL;

DO $$ BEGIN
    ALTER TABLE quality_checks ADD CONSTRAINT quality_checks_site_fkey
        FOREIGN KEY (site_id) REFERENCES sites(id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE maintenance_events ADD CONSTRAINT maintenance_events_site_fkey
        FOREIGN KEY (site_id) REFERENCES sites(id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE operator_notes ADD CONSTRAINT operator_notes_site_fkey
        FOREIGN KEY (site_id) REFERENCES sites(id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

ALTER TABLE quality_checks DROP CONSTRAINT IF EXISTS quality_checks_pkey;
ALTER TABLE maintenance_events DROP CONSTRAINT IF EXISTS maintenance_events_pkey;
ALTER TABLE operator_notes DROP CONSTRAINT IF EXISTS operator_notes_pkey;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='quality_checks'::regclass AND contype='p') THEN
        ALTER TABLE quality_checks ADD PRIMARY KEY (site_id, quality_check_id);
    END IF;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='maintenance_events'::regclass AND contype='p') THEN
        ALTER TABLE maintenance_events ADD PRIMARY KEY (site_id, event_id);
    END IF;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='operator_notes'::regclass AND contype='p') THEN
        ALTER TABLE operator_notes ADD PRIMARY KEY (site_id, note_id);
    END IF;
END $$;

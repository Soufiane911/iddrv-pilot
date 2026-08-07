-- Migration 010: enforce machine/site coherence at the database boundary.

CREATE UNIQUE INDEX IF NOT EXISTS uq_machines_site_id_id ON machines(site_id, id);

DO $$
DECLARE mismatches BIGINT;
BEGIN
    SELECT COUNT(*) INTO mismatches FROM production_orders po JOIN machines m ON m.id=po.machine_id WHERE po.site_id<>m.site_id;
    IF mismatches>0 THEN RAISE EXCEPTION 'production_orders machine/site mismatches: %', mismatches; END IF;
    SELECT COUNT(*) INTO mismatches FROM incidents i JOIN machines m ON m.id=i.machine_id WHERE i.site_id<>m.site_id;
    IF mismatches>0 THEN RAISE EXCEPTION 'incidents machine/site mismatches: %', mismatches; END IF;
    SELECT COUNT(*) INTO mismatches FROM machine_cycles c JOIN machines m ON m.id=c.machine_id WHERE c.order_site_id IS NOT NULL AND c.order_site_id<>m.site_id;
    IF mismatches>0 THEN RAISE EXCEPTION 'machine_cycles machine/site mismatches: %', mismatches; END IF;
    SELECT COUNT(*) INTO mismatches FROM shifts s JOIN machines m ON m.id=s.machine_id WHERE s.order_site_id IS NOT NULL AND s.order_site_id<>m.site_id;
    IF mismatches>0 THEN RAISE EXCEPTION 'shifts machine/site mismatches: %', mismatches; END IF;
END $$;

DO $$ BEGIN
    ALTER TABLE production_orders ADD CONSTRAINT production_orders_machine_site_fkey
        FOREIGN KEY (site_id,machine_id) REFERENCES machines(site_id,id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE incidents ADD CONSTRAINT incidents_machine_site_fkey
        FOREIGN KEY (site_id,machine_id) REFERENCES machines(site_id,id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE machine_cycles ADD CONSTRAINT machine_cycles_machine_site_fkey
        FOREIGN KEY (order_site_id,machine_id) REFERENCES machines(site_id,id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE shifts ADD CONSTRAINT shifts_machine_site_fkey
        FOREIGN KEY (order_site_id,machine_id) REFERENCES machines(site_id,id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE quality_checks ADD CONSTRAINT quality_checks_machine_site_fkey
        FOREIGN KEY (site_id,machine_id) REFERENCES machines(site_id,id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE maintenance_events ADD CONSTRAINT maintenance_events_machine_site_fkey
        FOREIGN KEY (site_id,machine_id) REFERENCES machines(site_id,id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE operator_notes ADD CONSTRAINT operator_notes_machine_site_fkey
        FOREIGN KEY (site_id,machine_id) REFERENCES machines(site_id,id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

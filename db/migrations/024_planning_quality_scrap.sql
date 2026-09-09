-- Actual quality is entered at OF + press grain.  Slot columns are not a
-- source of truth because one OF may have several overlapping historical
-- slots on the same press.
CREATE TABLE IF NOT EXISTS planning_scrap_actuals (
 site_id integer NOT NULL,
 work_order_id uuid NOT NULL,
 machine_id integer NOT NULL,
 actual_scrap_count integer,
 comment text,
 row_version integer NOT NULL DEFAULT 1 CHECK (row_version > 0),
 updated_by text,
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (site_id, work_order_id, machine_id),
 FOREIGN KEY (site_id, work_order_id) REFERENCES work_orders(site_id, id) ON DELETE CASCADE,
 FOREIGN KEY (site_id, machine_id) REFERENCES machines(site_id, id),
 CHECK (actual_scrap_count IS NULL OR actual_scrap_count >= 0)
);
CREATE INDEX IF NOT EXISTS planning_scrap_actuals_site_order
 ON planning_scrap_actuals(site_id, work_order_id, machine_id);

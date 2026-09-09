CREATE TABLE IF NOT EXISTS machine_hdt_controls (
 machine_id integer PRIMARY KEY,
 site_id integer NOT NULL,
 desired_state text NOT NULL CHECK (desired_state IN ('stopped','active')),
 effective_state text NOT NULL CHECK (effective_state IN ('stopped','starting','active','blocked')),
 blocking_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
 model_profile text,
 updated_by text,
 updated_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY (machine_id, site_id) REFERENCES machines(id, site_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS machine_hdt_controls_site ON machine_hdt_controls(site_id);

-- Append-only audit for requested/effective HDT lifecycle transitions.  The
-- control row is the current state; this table is the durable operator trace.
CREATE TABLE IF NOT EXISTS machine_hdt_control_audit (
 audit_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
 machine_id integer NOT NULL,
 site_id integer NOT NULL,
 desired_state text NOT NULL CHECK (desired_state IN ('stopped','active')),
 effective_state text NOT NULL CHECK (effective_state IN ('stopped','starting','active','blocked')),
 blocking_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
 actor_id text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY (machine_id, site_id) REFERENCES machines(id, site_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS machine_hdt_control_audit_machine
 ON machine_hdt_control_audit(site_id, machine_id, created_at DESC);

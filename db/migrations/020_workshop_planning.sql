-- Migration 020: workshop planning foundation.
-- Planning deliberately lives beside the legacy production_orders table: the
-- latter has a single machine_id and therefore cannot represent one OF on
-- several presses.  ERP quantities are intentionally absent from this model.

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE IF NOT EXISTS work_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id INT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    order_number VARCHAR(50) NOT NULL,
    order_number_normalized VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'cancelled', 'completed')),
    note TEXT,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (site_id, order_number_normalized),
    UNIQUE (site_id, id),
    CHECK (btrim(order_number) <> ''),
    CHECK (btrim(order_number_normalized) <> ''),
    CHECK (order_number_normalized = lower(btrim(order_number)))
);

CREATE INDEX IF NOT EXISTS work_orders_site_status_idx
    ON work_orders(site_id, status, order_number_normalized);

CREATE TABLE IF NOT EXISTS work_order_allocations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id INT NOT NULL,
    work_order_id UUID NOT NULL,
    machine_id INT NOT NULL,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (site_id, work_order_id, machine_id),
    UNIQUE (site_id, id),
    UNIQUE (site_id, id, machine_id),
    FOREIGN KEY (site_id, work_order_id)
        REFERENCES work_orders(site_id, id) ON DELETE CASCADE,
    FOREIGN KEY (site_id, machine_id)
        REFERENCES machines(site_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS work_order_allocations_machine_idx
    ON work_order_allocations(site_id, machine_id, work_order_id);

CREATE TABLE IF NOT EXISTS planning_slots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id INT NOT NULL,
    allocation_id UUID NOT NULL,
    machine_id INT NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    note TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'cancelled')),
    row_version INT NOT NULL DEFAULT 1 CHECK (row_version > 0),
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id, site_id),
    CHECK (ends_at > starts_at),
    FOREIGN KEY (site_id, allocation_id, machine_id)
        REFERENCES work_order_allocations(site_id, id, machine_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS planning_slots_site_period_idx
    ON planning_slots(site_id, starts_at, ends_at)
    WHERE status <> 'cancelled';

-- A press cannot have two live OF slots at once.  Cancelled history does not
-- reserve time, and the half-open range permits an immediate hand-off.
ALTER TABLE planning_slots
    DROP CONSTRAINT IF EXISTS planning_slots_machine_time_no_overlap;
ALTER TABLE planning_slots
    ADD CONSTRAINT planning_slots_machine_time_no_overlap
    EXCLUDE USING gist (
        machine_id WITH =,
        tstzrange(starts_at, ends_at, '[)') WITH &&
    ) WHERE (status <> 'cancelled');

-- Append-only application audit trail for planning changes.  actor_id is text
-- because local installations may use non-UUID identities while users.id is
-- UUID in the current control plane.
CREATE TABLE IF NOT EXISTS planning_audit_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id INT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    actor_id TEXT,
    action VARCHAR(40) NOT NULL,
    entity_type VARCHAR(40) NOT NULL,
    entity_id UUID NOT NULL,
    before_state JSONB,
    after_state JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS planning_audit_site_entity_idx
    ON planning_audit_events(site_id, entity_type, entity_id, created_at DESC);

-- Repair impossible legacy whitespace values before adding the checks below.
UPDATE work_orders
   SET order_number = 'OF-' || id::text,
       order_number_normalized = lower('OF-' || id::text)
 WHERE btrim(order_number) = '' OR btrim(order_number_normalized) = '';

-- Keep the invariant when this migration is applied to an existing prototype
-- database (CREATE TABLE IF NOT EXISTS does not revisit old constraints).
DO $$
BEGIN
    ALTER TABLE work_orders ADD CONSTRAINT work_orders_order_number_nonempty
        CHECK (btrim(order_number) <> '');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$
BEGIN
    ALTER TABLE work_orders ADD CONSTRAINT work_orders_order_number_normalized_nonempty
        CHECK (btrim(order_number_normalized) <> '');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Durable OF identity, immutable team results and confirmed upload requests.
-- Existing legacy totals are retained for an explicitly labelled fallback.
ALTER TABLE machine_cycles ALTER COLUMN scrap_flag DROP DEFAULT;
ALTER TABLE machine_cycles ALTER COLUMN good_parts DROP DEFAULT;
ALTER TABLE production_orders ALTER COLUMN erp_good_parts DROP DEFAULT;
ALTER TABLE production_orders ALTER COLUMN erp_scrap_count DROP DEFAULT;
ALTER TABLE shifts DROP CONSTRAINT IF EXISTS shifts_shift_number_check;
ALTER TABLE shifts ADD CONSTRAINT shifts_shift_number_check CHECK (shift_number > 0);

CREATE UNIQUE INDEX IF NOT EXISTS import_passports_site_id_id_key ON import_passports(site_id,id);
CREATE TABLE IF NOT EXISTS site_shift_calendars (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id INT NOT NULL REFERENCES sites(id), version INT NOT NULL CHECK (version > 0),
    valid_from DATE NOT NULL, valid_to DATE, timezone TEXT NOT NULL,
    shifts JSONB NOT NULL CHECK (jsonb_typeof(shifts) = 'array'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), author_id UUID NOT NULL REFERENCES users(id),
    UNIQUE(site_id,version), CHECK (valid_to IS NULL OR valid_to >= valid_from)
);
CREATE TABLE IF NOT EXISTS erp_declarations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), site_id INT NOT NULL REFERENCES sites(id),
    machine_id INT NOT NULL, production_order_id VARCHAR(50) NOT NULL,
    declaration_key TEXT NOT NULL, current_revision_id UUID,
    superseded_by UUID, superseded_recorded_at TIMESTAMPTZ,
    UNIQUE(site_id,declaration_key), UNIQUE(site_id,id), UNIQUE(site_id,production_order_id,id),
    FOREIGN KEY (site_id,machine_id) REFERENCES machines(site_id,id),
    FOREIGN KEY (site_id,production_order_id) REFERENCES production_orders(site_id,id),
    FOREIGN KEY (site_id,superseded_by) REFERENCES erp_declarations(site_id,id),
    CHECK (superseded_by IS NULL OR superseded_by <> id)
);
CREATE TABLE IF NOT EXISTS erp_declaration_revisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), site_id INT NOT NULL,
    declaration_id UUID NOT NULL, production_order_id VARCHAR(50) NOT NULL, revision_number INT NOT NULL CHECK (revision_number > 0),
    passport_id UUID NOT NULL, sheet_name TEXT NOT NULL, source_row INT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL, shift_started_at TIMESTAMPTZ NOT NULL,
    shift_number SMALLINT NOT NULL CHECK (shift_number > 0), order_type TEXT NOT NULL,
    tool_ref TEXT, product_ref TEXT, production_started_at TIMESTAMPTZ, production_ended_at TIMESTAMPTZ,
    bounds_origin TEXT NOT NULL CHECK (bounds_origin IN ('source','calendar','awaiting_context')),
    calendar_version INT, produced_parts BIGINT CHECK (produced_parts >= 0),
    good_parts BIGINT, scrap_parts BIGINT CHECK (scrap_parts >= 0),
    cycle_count BIGINT CHECK (cycle_count >= 0), cavities_actual INT CHECK (cavities_actual >= 0),
    declared_scrap_rate DOUBLE PRECISION,
    declared_trs DOUBLE PRECISION,
    available_hours DOUBLE PRECISION CHECK (available_hours >= 0),
    total_stop_hours DOUBLE PRECISION CHECK (total_stop_hours >= 0),
    running_hours DOUBLE PRECISION CHECK (running_hours >= 0),
    opening_hours DOUBLE PRECISION CHECK (opening_hours >= 0), cycle_time_s DOUBLE PRECISION,
    raw_data JSONB NOT NULL, warnings JSONB NOT NULL DEFAULT '[]', content_hash TEXT NOT NULL,
    UNIQUE(declaration_id,revision_number), UNIQUE(declaration_id,id), UNIQUE(site_id,production_order_id,id),
    FOREIGN KEY (site_id,production_order_id,declaration_id) REFERENCES erp_declarations(site_id,production_order_id,id),
    FOREIGN KEY (site_id,passport_id) REFERENCES import_passports(site_id,id),
    CHECK (production_ended_at IS NULL OR production_ended_at > production_started_at)
);
DO $$ BEGIN
    ALTER TABLE erp_declarations ADD CONSTRAINT erp_declarations_current_revision_fkey
      FOREIGN KEY (id,current_revision_id) REFERENCES erp_declaration_revisions(declaration_id,id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS erp_declarations_site_machine_idx ON erp_declarations(site_id,machine_id,production_order_id);
CREATE INDEX IF NOT EXISTS erp_revisions_period_idx ON erp_declaration_revisions(site_id,shift_started_at,recorded_at);
CREATE INDEX IF NOT EXISTS erp_revisions_import_idx ON erp_declaration_revisions(passport_id);
CREATE TABLE IF NOT EXISTS production_order_revisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), site_id INT NOT NULL,
    production_order_id VARCHAR(50) NOT NULL, passport_id UUID NOT NULL,
    declaration_revision_id UUID NOT NULL,
    effective_at TIMESTAMPTZ, recorded_at TIMESTAMPTZ NOT NULL,
    values JSONB NOT NULL, content_hash TEXT NOT NULL,
    UNIQUE(site_id,production_order_id,content_hash),
    FOREIGN KEY (site_id,production_order_id,declaration_revision_id) REFERENCES erp_declaration_revisions(site_id,production_order_id,id),
    FOREIGN KEY (site_id,production_order_id) REFERENCES production_orders(site_id,id),
    FOREIGN KEY (site_id,passport_id) REFERENCES import_passports(site_id,id)
);
CREATE INDEX IF NOT EXISTS order_revision_knowledge_idx ON production_order_revisions(site_id,production_order_id,recorded_at,effective_at);
CREATE TABLE IF NOT EXISTS erp_import_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), site_id INT NOT NULL REFERENCES sites(id),
    creator_id UUID NOT NULL REFERENCES users(id), raw_path TEXT NOT NULL,
    original_name TEXT NOT NULL, file_hash TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('uploaded','profiling','preview_ready','queued','processing','completed','failed')),
    preview_version INT NOT NULL DEFAULT 0, choices JSONB NOT NULL DEFAULT '{}',
    preview JSONB NOT NULL DEFAULT '{}', passport_id UUID,
    result JSONB, public_error TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
    FOREIGN KEY (site_id,passport_id) REFERENCES import_passports(site_id,id)
);
CREATE INDEX IF NOT EXISTS erp_import_requests_pending_idx ON erp_import_requests(created_at) WHERE state IN ('queued','processing');
CREATE INDEX IF NOT EXISTS erp_import_requests_site_idx ON erp_import_requests(site_id,created_at DESC);

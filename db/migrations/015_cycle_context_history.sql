-- Separate ALTER is required for the existing Timescale columnstore.
ALTER TABLE machine_source_events ADD CONSTRAINT source_events_cycle_identity UNIQUE(id,machine_id,cycle_ended_at);
ALTER TABLE machine_cycles ADD CONSTRAINT machine_cycles_source_identity_fk
 FOREIGN KEY(source_event_id,machine_id,time) REFERENCES machine_source_events(id,machine_id,cycle_ended_at);
ALTER TABLE erp_declaration_revisions ADD COLUMN estimated_bounds JSONB;
CREATE UNIQUE INDEX erp_declarations_context_scope ON erp_declarations(id,site_id,machine_id);
CREATE UNIQUE INDEX erp_revisions_context_scope ON erp_declaration_revisions(id,declaration_id,site_id);
CREATE TABLE cycle_context_links (
 id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), site_id INT NOT NULL, machine_id INT NOT NULL,
 cycle_time TIMESTAMPTZ NOT NULL, source_event_id UUID,
 declaration_id UUID, revision_id UUID,
 status TEXT NOT NULL CHECK(status IN ('awaiting_erp','matched','provisional','ambiguous')),
 method TEXT NOT NULL DEFAULT 'production_interval_v1', candidate_ids JSONB NOT NULL,
 candidate_revision_ids JSONB NOT NULL, confidence DOUBLE PRECISION,
 created_at TIMESTAMPTZ NOT NULL, supersedes_id UUID,
 UNIQUE(id,site_id,machine_id,cycle_time),
 FOREIGN KEY(site_id,machine_id) REFERENCES machines(site_id,id),
 FOREIGN KEY(source_event_id,site_id,machine_id) REFERENCES machine_source_events(id,site_id,machine_id),
 FOREIGN KEY(declaration_id,site_id,machine_id) REFERENCES erp_declarations(id,site_id,machine_id),
 FOREIGN KEY(revision_id,declaration_id,site_id) REFERENCES erp_declaration_revisions(id,declaration_id,site_id),
 FOREIGN KEY(supersedes_id,site_id,machine_id,cycle_time) REFERENCES cycle_context_links(id,site_id,machine_id,cycle_time),
 CHECK ((status IN ('matched','provisional')) = (declaration_id IS NOT NULL AND revision_id IS NOT NULL))
);
CREATE INDEX cycle_context_knowledge ON cycle_context_links(site_id,machine_id,cycle_time,created_at DESC);
CREATE UNIQUE INDEX cycle_context_successor ON cycle_context_links(supersedes_id) WHERE supersedes_id IS NOT NULL;
CREATE TABLE production_order_observation_sources (
 observation_id UUID NOT NULL REFERENCES production_order_revisions(id),
 declaration_revision_id UUID NOT NULL REFERENCES erp_declaration_revisions(id),
 PRIMARY KEY(observation_id,declaration_revision_id)
);

ALTER TABLE hdt_scoring_jobs ADD COLUMN input_event_ids JSONB;
ALTER TABLE hdt_scoring_jobs ADD COLUMN input_snapshot JSONB;
ALTER TABLE hdt_scoring_jobs ADD COLUMN claim_token UUID;
ALTER TABLE hdt_scoring_jobs ADD COLUMN supersedes_id UUID;
CREATE TABLE hdt_predictions (
 id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), job_id UUID NOT NULL UNIQUE REFERENCES hdt_scoring_jobs(id),
 event_id UUID NOT NULL, site_id INT NOT NULL, machine_id INT NOT NULL,
 input_event_ids JSONB NOT NULL, model_version TEXT NOT NULL,
 model_scope TEXT CHECK(model_scope IN ('machine','global')),
 mode TEXT NOT NULL CHECK(mode IN ('live','backfill')), calculation_revision INT NOT NULL CHECK(calculation_revision>0),
 supersedes_id UUID REFERENCES hdt_predictions(id), status TEXT NOT NULL,
 score DOUBLE PRECISION, threshold DOUBLE PRECISION, signals JSONB NOT NULL,
 horizon_cycles INT NOT NULL, input_count INT NOT NULL, reason TEXT,
 evaluated_through TIMESTAMPTZ NOT NULL, scored_at TIMESTAMPTZ NOT NULL,
 UNIQUE(event_id,model_version,mode,calculation_revision), UNIQUE(id,site_id,machine_id),
 FOREIGN KEY(event_id,site_id,machine_id) REFERENCES machine_source_events(id,site_id,machine_id),
 CHECK(status IN ('scored','insufficient_history','incompatible','model_unavailable')),
 CHECK((status='scored') = (score IS NOT NULL AND threshold IS NOT NULL))
);
ALTER TABLE hdt_scoring_jobs ADD CONSTRAINT scoring_supersedes_fk FOREIGN KEY(supersedes_id) REFERENCES hdt_predictions(id);
CREATE INDEX hdt_predictions_knowledge ON hdt_predictions(site_id,machine_id,evaluated_through,scored_at);
ALTER TABLE incidents ADD COLUMN origin TEXT NOT NULL DEFAULT 'quality';
CREATE UNIQUE INDEX incidents_scope_identity ON incidents(id,site_id,machine_id);
CREATE TABLE process_drift_episodes (
 incident_id UUID PRIMARY KEY, site_id INT NOT NULL, machine_id INT NOT NULL,
 below_count INT NOT NULL DEFAULT 0, closed_at TIMESTAMPTZ,
 FOREIGN KEY(incident_id,site_id,machine_id) REFERENCES incidents(id,site_id,machine_id)
);
CREATE UNIQUE INDEX process_drift_one_open ON process_drift_episodes(site_id,machine_id) WHERE closed_at IS NULL;
CREATE TABLE process_drift_episode_predictions (
 prediction_id UUID PRIMARY KEY, incident_id UUID NOT NULL, site_id INT NOT NULL, machine_id INT NOT NULL,
 FOREIGN KEY(prediction_id,site_id,machine_id) REFERENCES hdt_predictions(id,site_id,machine_id),
 FOREIGN KEY(incident_id,site_id,machine_id) REFERENCES incidents(id,site_id,machine_id)
);
ALTER TABLE diagnostic_runs ADD COLUMN context_snapshot JSONB;
-- Results, evidence links and source revisions are append-only, including owner misuse.
CREATE FUNCTION reject_history_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable_history'; END $$;
CREATE TRIGGER immutable_hdt_predictions BEFORE UPDATE OR DELETE ON hdt_predictions FOR EACH ROW EXECUTE FUNCTION reject_history_mutation();
CREATE TRIGGER immutable_cycle_context BEFORE UPDATE OR DELETE ON cycle_context_links FOR EACH ROW EXECUTE FUNCTION reject_history_mutation();

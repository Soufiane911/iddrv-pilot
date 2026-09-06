-- Distinguish accepted events sharing a timestamp and legacy rows without an event.
ALTER TABLE machine_cycles ADD COLUMN context_cycle_id UUID;
ALTER TABLE machine_cycles ALTER COLUMN context_cycle_id SET DEFAULT uuid_generate_v4();
UPDATE machine_cycles SET context_cycle_id=uuid_generate_v4() WHERE source_event_id IS NULL;
ALTER TABLE cycle_context_links ADD COLUMN cycle_key TEXT;
ALTER TABLE cycle_context_links DISABLE TRIGGER immutable_cycle_context;
UPDATE cycle_context_links SET cycle_key=source_event_id::text WHERE source_event_id IS NOT NULL;
-- A previously ambiguous legacy anchor requires operator repair, never arbitrary selection.
UPDATE cycle_context_links l SET cycle_key='legacy:' || (
 SELECT c.context_cycle_id::text FROM machine_cycles c
 WHERE c.machine_id=l.machine_id AND c.time=l.cycle_time AND c.source_event_id IS NULL
) WHERE l.source_event_id IS NULL;
ALTER TABLE cycle_context_links ENABLE TRIGGER immutable_cycle_context;
ALTER TABLE cycle_context_links ALTER COLUMN cycle_key SET NOT NULL;
ALTER TABLE cycle_context_links ADD CONSTRAINT cycle_context_same_anchor UNIQUE(id,cycle_key);
ALTER TABLE cycle_context_links ADD CONSTRAINT cycle_context_predecessor_anchor_fk
 FOREIGN KEY(supersedes_id,cycle_key) REFERENCES cycle_context_links(id,cycle_key);
ALTER TABLE cycle_context_links ADD CONSTRAINT cycle_context_event_key
 CHECK(source_event_id IS NULL OR cycle_key=source_event_id::text);
CREATE INDEX cycle_context_anchor_knowledge ON cycle_context_links(site_id,machine_id,cycle_key,created_at DESC);

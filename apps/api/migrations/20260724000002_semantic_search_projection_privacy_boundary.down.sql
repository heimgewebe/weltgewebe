-- Restore the payload-carried visibility contract expected by the previous
-- worker before dropping the canonical column. Keep the migration itself out of
-- the projection version stream in the same way as the forward migration.
ALTER TABLE domain_nodes DISABLE TRIGGER search_track_domain_nodes;

UPDATE domain_nodes
SET payload = jsonb_set(payload, '{search_visibility}', to_jsonb(search_visibility), true);

CREATE OR REPLACE FUNCTION weltgewebe_search_enqueue_node(p_node_id TEXT, p_operation TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE current_version BIGINT; current_revision TEXT;
BEGIN
    SELECT source_version, source_revision INTO current_version, current_revision
      FROM search_node_versions WHERE node_id = p_node_id;
    IF current_version IS NULL THEN RETURN; END IF;
    INSERT INTO search_projection_jobs (generation_id, node_id, source_version, source_revision, operation)
    SELECT generation_id, p_node_id, current_version, current_revision, p_operation
      FROM search_index_generations WHERE state IN ('building', 'ready', 'active')
    ON CONFLICT DO NOTHING;
END; $$;

CREATE OR REPLACE FUNCTION weltgewebe_search_track_domain_node()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE next_version BIGINT; revision TEXT; node_identifier TEXT;
BEGIN
    IF TG_OP = 'UPDATE'
       AND OLD.kind IS NOT DISTINCT FROM NEW.kind
       AND OLD.title IS NOT DISTINCT FROM NEW.title
       AND (OLD.payload -> 'summary') IS NOT DISTINCT FROM (NEW.payload -> 'summary')
       AND (OLD.payload -> 'info') IS NOT DISTINCT FROM (NEW.payload -> 'info')
       AND (OLD.payload -> 'tags') IS NOT DISTINCT FROM (NEW.payload -> 'tags')
       AND (OLD.payload -> 'language') IS NOT DISTINCT FROM (NEW.payload -> 'language')
       AND (OLD.payload -> 'search_visibility') IS NOT DISTINCT FROM (NEW.payload -> 'search_visibility')
    THEN
        RETURN NEW;
    END IF;
    PERFORM pg_advisory_xact_lock_shared(hashtextextended('weltgewebe.search.generation.activation', 0));
    node_identifier := CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END;
    INSERT INTO search_node_versions (node_id, source_version, source_revision, deleted_at)
    VALUES (node_identifier, 1, 'node-1', CASE WHEN TG_OP = 'DELETE' THEN clock_timestamp() ELSE NULL END)
    ON CONFLICT (node_id) DO UPDATE SET
      source_version = search_node_versions.source_version + 1,
      source_revision = 'node-' || (search_node_versions.source_version + 1)::TEXT,
      deleted_at = EXCLUDED.deleted_at
    RETURNING source_version, source_revision INTO next_version, revision;
    PERFORM weltgewebe_search_enqueue_node(node_identifier, CASE WHEN TG_OP = 'DELETE' THEN 'delete' ELSE 'upsert' END);
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END; $$;

ALTER TABLE domain_nodes ENABLE TRIGGER search_track_domain_nodes;

DROP POLICY IF EXISTS search_projection_jobs_generation_binding ON search_projection_jobs;
ALTER TABLE search_projection_jobs NO FORCE ROW LEVEL SECURITY;
ALTER TABLE search_projection_jobs DISABLE ROW LEVEL SECURITY;

ALTER TABLE domain_nodes
    DROP CONSTRAINT domain_nodes_search_visibility_valid,
    DROP COLUMN search_visibility;

CREATE OR REPLACE FUNCTION weltgewebe_search_generation_activation_ready(p_generation_id TEXT)
RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
SELECT COALESCE((
    SELECT g.state IN ('building', 'ready', 'active')
       AND g.completed_nodes = g.expected_nodes
       AND NOT EXISTS (
           SELECT 1 FROM search_node_versions v
           WHERE v.deleted_at IS NULL
             AND NOT EXISTS (
                 SELECT 1 FROM search_node_projections p
                 WHERE p.generation_id = g.generation_id
                   AND p.node_id = v.node_id
                   AND p.source_version = v.source_version
                   AND p.source_revision = v.source_revision
                   AND p.semantic_state = 'ready'
                   AND cardinality(p.embedding) = g.dimension
             )
       )
       AND NOT EXISTS (
           SELECT 1 FROM search_projection_jobs j
           WHERE j.generation_id = g.generation_id
             AND j.state NOT IN ('done', 'stale')
       )
       AND NOT EXISTS (
           SELECT 1
           FROM search_node_versions v
           JOIN search_node_projections p
             ON p.generation_id = g.generation_id
            AND p.node_id = v.node_id
           WHERE v.deleted_at IS NOT NULL
       )
    FROM search_index_generations g
    WHERE g.generation_id = p_generation_id
), FALSE);
$$;

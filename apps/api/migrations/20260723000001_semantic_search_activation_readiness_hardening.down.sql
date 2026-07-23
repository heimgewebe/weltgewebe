-- Restore the pre-hardening activation function before removing the shared
-- readiness helper, then remove the additive generation/state index.

-- Atomically switches only a fully completed generation.  The old active
-- generation is retained for an explicit operator rollback via the same gate.
CREATE OR REPLACE FUNCTION weltgewebe_activate_search_generation(p_generation_id TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE target search_index_generations%ROWTYPE;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('weltgewebe.search.generation.activation', 0));
    SELECT * INTO target FROM search_index_generations WHERE generation_id = p_generation_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'unknown search generation' USING ERRCODE = '23503'; END IF;
    IF target.state NOT IN ('building', 'ready', 'active')
       OR target.completed_nodes <> target.expected_nodes
       OR EXISTS (
           SELECT 1 FROM search_node_versions v
           WHERE v.deleted_at IS NULL
             AND NOT EXISTS (
                 SELECT 1 FROM search_node_projections p
                 WHERE p.generation_id = p_generation_id
                   AND p.node_id = v.node_id
                   AND p.source_version = v.source_version
                   AND p.source_revision = v.source_revision
                   AND p.semantic_state = 'ready'
                   AND cardinality(p.embedding) = target.dimension
             )
       )
       OR EXISTS (
           SELECT 1 FROM search_projection_jobs j
           WHERE j.generation_id = p_generation_id
             AND j.state NOT IN ('done', 'stale')
       )
       OR EXISTS (
           SELECT 1
           FROM search_node_versions v
           JOIN search_node_projections p
             ON p.generation_id = p_generation_id
            AND p.node_id = v.node_id
           WHERE v.deleted_at IS NOT NULL
       )
    THEN
      RAISE EXCEPTION 'generation is not complete and ready' USING ERRCODE = '23514';
    END IF;
    IF target.state = 'active' THEN RETURN; END IF;
    -- A complete building generation may activate directly.  This permits a
    -- new rebuild while the current active+ready pair remains rollback-safe.
    -- The advisory lock makes the retirement/swap atomic to every caller.
    UPDATE search_index_generations SET state = 'building' WHERE generation_id = p_generation_id;
    UPDATE search_index_generations SET state = 'retired', activated_at = NULL
      WHERE state = 'ready';
    UPDATE search_index_generations SET state = 'ready', activated_at = NULL WHERE state = 'active';
    UPDATE search_index_generations SET state = 'active', activated_at = clock_timestamp() WHERE generation_id = p_generation_id;
END; $$;

DROP FUNCTION IF EXISTS weltgewebe_search_generation_activation_ready(TEXT);
DROP INDEX IF EXISTS search_projection_jobs_generation_state;

-- P0 follow-up: keep already-applied migration 20260721000001 immutable.
-- The readiness helper and generation-state index were originally introduced
-- by editing that historical migration; they belong in this additive migration.

CREATE INDEX IF NOT EXISTS search_projection_jobs_generation_state
    ON search_projection_jobs (generation_id, state);

-- Canonical, read-only activation gate shared by worker reconciliation,
-- operational status, and the actual activation function. Keep all readiness
-- semantics here so those three surfaces cannot drift independently.
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

-- Atomically switches only a fully completed generation.  The old active
-- generation is retained for an explicit operator rollback via the same gate.
CREATE OR REPLACE FUNCTION weltgewebe_activate_search_generation(p_generation_id TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE target search_index_generations%ROWTYPE;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('weltgewebe.search.generation.activation', 0));
    SELECT * INTO target FROM search_index_generations WHERE generation_id = p_generation_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'unknown search generation' USING ERRCODE = '23503'; END IF;
    IF NOT weltgewebe_search_generation_activation_ready(p_generation_id) THEN
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

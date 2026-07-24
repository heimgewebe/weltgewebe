-- WELTGEWEBE-SEMANTIC-SEARCH-V1-T012
-- Search visibility is canonical domain state, not a projection-owned payload
-- convention. Existing ordinary nodes become public; malformed explicit legacy
-- values fail closed as hidden. Private text stays lexical-only in PostgreSQL.

ALTER TABLE domain_nodes
    ADD COLUMN search_visibility TEXT NOT NULL DEFAULT 'public';

UPDATE domain_nodes
SET search_visibility = CASE
    WHEN NOT (payload ? 'search_visibility') THEN 'public'
    WHEN jsonb_typeof(payload -> 'search_visibility') = 'string'
         AND payload ->> 'search_visibility' IN ('public', 'private', 'hidden', 'revoked')
      THEN payload ->> 'search_visibility'
    ELSE 'hidden'
END,
payload = payload - 'search_visibility';

ALTER TABLE domain_nodes
    ADD CONSTRAINT domain_nodes_search_visibility_valid
    CHECK (search_visibility IN ('public', 'private', 'hidden', 'revoked'));

-- Purge recoverable non-public and orphaned content left by older generations.
-- Canonical domain rows remain untouched; projections are regenerable state.
DELETE FROM search_node_projections p
USING domain_nodes n
WHERE p.node_id = n.id
  AND n.search_visibility <> 'public';

DELETE FROM search_node_projections p
WHERE NOT EXISTS (SELECT 1 FROM domain_nodes n WHERE n.id = p.node_id);

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
       AND (OLD.payload -> 'created_by_account_id') IS NOT DISTINCT FROM (NEW.payload -> 'created_by_account_id')
       AND OLD.search_visibility IS NOT DISTINCT FROM NEW.search_visibility
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

CREATE OR REPLACE FUNCTION weltgewebe_search_generation_activation_ready(p_generation_id TEXT)
RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
SELECT COALESCE((
    SELECT g.state IN ('building', 'ready', 'active')
       AND g.document_revision = 'node-document-v4-canonical-visibility'
       AND g.completed_nodes = g.expected_nodes
       AND NOT EXISTS (
           SELECT 1
           FROM search_node_versions v
           LEFT JOIN domain_nodes n ON n.id = v.node_id
           WHERE v.deleted_at IS NULL
             AND (
                 n.id IS NULL
                 OR NOT EXISTS (
                     SELECT 1
                     FROM search_node_projections p
                     WHERE p.generation_id = g.generation_id
                       AND p.node_id = v.node_id
                       AND p.source_version = v.source_version
                       AND p.source_revision = v.source_revision
                       AND (
                           (n.search_visibility = 'public'
                            AND p.status = 'active'
                            AND p.semantic_state = 'ready'
                            AND p.visibility_scopes = ARRAY['public']::TEXT[]
                            AND cardinality(p.embedding) = g.dimension)
                           OR
                           (n.search_visibility = 'private'
                            AND jsonb_typeof(n.payload -> 'created_by_account_id') = 'string'
                            AND regexp_replace(n.payload ->> 'created_by_account_id', '[[:space:]]', '', 'g') <> ''
                            AND p.status = 'active'
                            AND p.semantic_state = 'unavailable'
                            AND p.visibility_scopes = ARRAY['owner']::TEXT[]
                            AND p.embedding IS NULL)
                           OR
                           ((n.search_visibility IN ('hidden', 'revoked')
                             OR (n.search_visibility = 'private'
                                 AND NOT (
                                     jsonb_typeof(n.payload -> 'created_by_account_id') = 'string'
                                     AND regexp_replace(n.payload ->> 'created_by_account_id', '[[:space:]]', '', 'g') <> ''
                                 )))
                            AND p.status = 'hidden'
                            AND p.semantic_state = 'unavailable'
                            AND p.visibility_scopes = '{}'::TEXT[]
                            AND p.embedding IS NULL
                            AND p.title = '[nicht öffentlich]'
                            AND p.searchable_text = '[nicht öffentlich]'
                            AND p.language = 'und'
                            AND p.kind = '[nicht öffentlich]'
                            AND p.tags = '{}'::TEXT[])
                       )
                 )
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

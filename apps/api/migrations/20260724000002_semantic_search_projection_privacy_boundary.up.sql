-- WELTGEWEBE-SEMANTIC-SEARCH-V1-T012
-- Public nodes receive semantic embeddings. Private nodes with a canonical
-- owner remain lexical-only inside PostgreSQL. Every other visibility state is
-- represented by a content-free sentinel. Unknown states fail closed.

CREATE OR REPLACE FUNCTION weltgewebe_search_generation_activation_ready(p_generation_id TEXT)
RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
SELECT COALESCE((
    SELECT g.state IN ('building', 'ready', 'active')
       AND g.document_revision = 'node-document-v3-public-semantic-private-lexical'
       AND g.completed_nodes = g.expected_nodes
       AND NOT EXISTS (
           SELECT 1
           FROM search_node_versions v
           JOIN domain_nodes n ON n.id = v.node_id
           WHERE v.deleted_at IS NULL
             AND NOT EXISTS (
                 SELECT 1
                 FROM search_node_projections p
                 WHERE p.generation_id = g.generation_id
                   AND p.node_id = v.node_id
                   AND p.source_version = v.source_version
                   AND p.source_revision = v.source_revision
                   AND (
                       (n.payload ->> 'search_visibility' = 'public'
                        AND p.status = 'active'
                        AND p.semantic_state = 'ready'
                        AND p.visibility_scopes = ARRAY['public']::TEXT[]
                        AND cardinality(p.embedding) = g.dimension)
                       OR
                       (n.payload ->> 'search_visibility' = 'private'
                        AND nullif(btrim(n.payload ->> 'created_by_account_id'), '') IS NOT NULL
                        AND p.status = 'active'
                        AND p.semantic_state = 'unavailable'
                        AND p.visibility_scopes = ARRAY['owner']::TEXT[]
                        AND p.embedding IS NULL
                        AND p.title <> '[nicht öffentlich]'
                        AND p.searchable_text <> '[nicht öffentlich]')
                       OR
                       (NOT (coalesce(n.payload ->> 'search_visibility', '') = 'public'
                             OR (n.payload ->> 'search_visibility' = 'private'
                                 AND nullif(btrim(n.payload ->> 'created_by_account_id'), '') IS NOT NULL))
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

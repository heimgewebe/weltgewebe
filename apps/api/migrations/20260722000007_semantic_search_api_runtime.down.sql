DROP TRIGGER IF EXISTS search_node_projections_refresh_lexical_vectors
    ON search_node_projections;
DROP FUNCTION IF EXISTS weltgewebe_search_refresh_lexical_vectors();

DROP INDEX IF EXISTS search_node_projections_t006_eligible;
DROP INDEX IF EXISTS search_node_projections_t006_tags;
DROP INDEX IF EXISTS search_node_projections_t006_title_trigram;
DROP INDEX IF EXISTS search_node_projections_t006_searchable_text_trigram;
DROP INDEX IF EXISTS search_node_projections_t006_fts_simple;
DROP INDEX IF EXISTS search_node_projections_t006_fts;

ALTER TABLE search_node_projections
    DROP COLUMN IF EXISTS search_vector_simple,
    DROP COLUMN IF EXISTS search_vector;

-- pg_trgm is a shared database capability and may predate T006.
-- Deliberately retain it on rollback rather than dropping a shared extension.
SELECT 1;

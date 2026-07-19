-- T003 proof rollback removes only the disposable search projection foundation.
-- Shared extensions are intentionally retained.

DROP FUNCTION IF EXISTS weltgewebe_search_lexical_candidates(TEXT, TEXT, TEXT[], TEXT, TEXT[], TEXT[], TEXT[], INTEGER);
DROP FUNCTION IF EXISTS weltgewebe_put_search_projection(TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, TEXT[], TEXT, TEXT, TEXT, TEXT, TEXT[], DOUBLE PRECISION[]);
DROP FUNCTION IF EXISTS weltgewebe_activate_search_generation(TEXT);
DROP TRIGGER IF EXISTS search_node_projections_validate ON search_node_projections;
DROP FUNCTION IF EXISTS weltgewebe_validate_search_projection();
DROP TABLE IF EXISTS search_node_projections;
DROP TABLE IF EXISTS search_index_generations;

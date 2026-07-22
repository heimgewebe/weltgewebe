DROP TRIGGER IF EXISTS search_track_domain_nodes ON domain_nodes;
DROP FUNCTION IF EXISTS weltgewebe_search_track_domain_node();
DROP FUNCTION IF EXISTS weltgewebe_search_enqueue_node(TEXT, TEXT);
DROP FUNCTION IF EXISTS weltgewebe_activate_search_generation(TEXT);
DROP TABLE IF EXISTS search_projection_jobs;
DROP TABLE IF EXISTS search_node_projections;
DROP TABLE IF EXISTS search_node_versions;
DROP TABLE IF EXISTS search_index_generations;

DROP TRIGGER IF EXISTS domain_accounts_outbox ON domain_accounts;
DROP TRIGGER IF EXISTS domain_edges_outbox ON domain_edges;
DROP TRIGGER IF EXISTS domain_nodes_outbox ON domain_nodes;
DROP FUNCTION IF EXISTS weltgewebe_enqueue_domain_event();
DROP TABLE IF EXISTS domain_projection_state;
DROP TABLE IF EXISTS domain_event_consumptions;
DROP TABLE IF EXISTS domain_outbox;
DROP TABLE IF EXISTS auth_rate_limit_counters;
DROP TABLE IF EXISTS auth_ephemeral_state;

DROP INDEX IF EXISTS domain_edges_create_operation_unique;
ALTER TABLE domain_edges
    DROP CONSTRAINT IF EXISTS domain_edges_create_operation_pair,
    DROP COLUMN IF EXISTS create_operation_id,
    DROP COLUMN IF EXISTS create_actor_id;

DROP INDEX IF EXISTS domain_nodes_create_operation_unique;
ALTER TABLE domain_nodes
    DROP CONSTRAINT IF EXISTS domain_nodes_create_operation_pair,
    DROP COLUMN IF EXISTS create_operation_id,
    DROP COLUMN IF EXISTS create_actor_id;

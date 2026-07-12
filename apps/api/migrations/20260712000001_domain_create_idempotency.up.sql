-- Durable idempotency keys for user-initiated node and edge creation.
--
-- The pair is scoped to the authenticated account and resource table. Existing
-- rows remain NULL/NULL and preserve their historical semantics. New callers
-- may omit operation_id; those writes also remain NULL/NULL.

ALTER TABLE domain_nodes
    ADD COLUMN create_actor_id TEXT,
    ADD COLUMN create_operation_id TEXT,
    ADD CONSTRAINT domain_nodes_create_operation_pair
        CHECK (
            (create_actor_id IS NULL AND create_operation_id IS NULL)
            OR
            (
                create_actor_id IS NOT NULL
                AND btrim(create_actor_id) <> ''
                AND create_operation_id IS NOT NULL
                AND create_operation_id ~
                    '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            )
        );

CREATE UNIQUE INDEX domain_nodes_create_operation_unique
    ON domain_nodes (create_actor_id, create_operation_id)
    WHERE create_operation_id IS NOT NULL;

ALTER TABLE domain_edges
    ADD COLUMN create_actor_id TEXT,
    ADD COLUMN create_operation_id TEXT,
    ADD CONSTRAINT domain_edges_create_operation_pair
        CHECK (
            (create_actor_id IS NULL AND create_operation_id IS NULL)
            OR
            (
                create_actor_id IS NOT NULL
                AND btrim(create_actor_id) <> ''
                AND create_operation_id IS NOT NULL
                AND create_operation_id ~
                    '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            )
        );

CREATE UNIQUE INDEX domain_edges_create_operation_unique
    ON domain_edges (create_actor_id, create_operation_id)
    WHERE create_operation_id IS NOT NULL;

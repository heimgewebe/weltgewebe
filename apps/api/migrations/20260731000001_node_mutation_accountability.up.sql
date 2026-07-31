CREATE TABLE domain_node_mutation_audit (
    operation_id UUID PRIMARY KEY,
    node_id TEXT NOT NULL,
    actor_subject_hash TEXT NOT NULL CHECK (actor_subject_hash ~ '^[0-9a-f]{64}$'),
    operation TEXT NOT NULL CHECK (operation IN ('replace', 'delete')),
    before_hash TEXT NOT NULL CHECK (before_hash ~ '^[0-9a-f]{64}$'),
    after_hash TEXT CHECK (after_hash IS NULL OR after_hash ~ '^[0-9a-f]{64}$'),
    occurred_at TIMESTAMPTZ NOT NULL,
    CHECK ((operation = 'replace' AND after_hash IS NOT NULL)
        OR (operation = 'delete' AND after_hash IS NULL))
);

CREATE INDEX domain_node_mutation_audit_node_time
    ON domain_node_mutation_audit (node_id, occurred_at DESC);

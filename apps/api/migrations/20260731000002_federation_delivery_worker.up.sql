ALTER TABLE federation_peer_relationships
    ADD COLUMN delivery_base_url TEXT,
    ADD COLUMN delivery_policy_sha256 TEXT
        CHECK (delivery_policy_sha256 IS NULL OR delivery_policy_sha256 ~ '^[0-9a-f]{64}$');

CREATE TABLE federation_delivery_attempts (
    event_id UUID NOT NULL REFERENCES federation_outbox(event_id) ON DELETE CASCADE,
    target_cell_id TEXT NOT NULL REFERENCES federation_peer_relationships(remote_cell_id) ON DELETE CASCADE,
    state TEXT NOT NULL DEFAULT 'pending'
        CHECK (state IN ('pending', 'in_flight', 'retry', 'delivered', 'dead')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lease_owner UUID,
    lease_expires_at TIMESTAMPTZ,
    last_http_status INTEGER CHECK (last_http_status BETWEEN 100 AND 599),
    last_error_class TEXT CHECK (last_error_class IS NULL OR length(last_error_class) BETWEEN 1 AND 128),
    delivered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (event_id, target_cell_id),
    CHECK ((state = 'in_flight') = (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)),
    CHECK ((state = 'delivered') = (delivered_at IS NOT NULL))
);

CREATE INDEX federation_delivery_due
    ON federation_delivery_attempts (next_attempt_at, event_id, target_cell_id)
    WHERE state IN ('pending', 'retry', 'in_flight');

CREATE INDEX federation_outbox_delivery_order
    ON federation_outbox (object_address, object_version, created_at, event_id);

CREATE INDEX federation_delivery_target_state
    ON federation_delivery_attempts (target_cell_id, state, updated_at DESC);

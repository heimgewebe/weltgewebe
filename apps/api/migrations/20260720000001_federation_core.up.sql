CREATE TABLE federation_peer_relationships (
    remote_cell_id TEXT PRIMARY KEY,
    state TEXT NOT NULL CHECK (state IN ('trusted', 'blocked')),
    allow_neighbourhood BOOLEAN NOT NULL DEFAULT FALSE,
    allowed_event_types JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(allowed_event_types) = 'array'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE federation_peer_keys (
    remote_cell_id TEXT NOT NULL REFERENCES federation_peer_relationships(remote_cell_id) ON DELETE CASCADE,
    key_id TEXT NOT NULL,
    public_key BYTEA NOT NULL CHECK (octet_length(public_key) = 32),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retired_at TIMESTAMPTZ,
    PRIMARY KEY (remote_cell_id, key_id),
    CHECK (NOT (active AND retired_at IS NOT NULL))
);

CREATE TABLE federation_objects (
    object_address TEXT PRIMARY KEY,
    origin_cell_id TEXT NOT NULL,
    object_kind TEXT NOT NULL CHECK (object_kind IN ('node', 'edge', 'shared-room')),
    object_version BIGINT NOT NULL CHECK (object_version > 0),
    scope TEXT NOT NULL CHECK (scope IN ('neighbourhood', 'global')),
    payload JSONB NOT NULL,
    deleted_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX federation_objects_origin_kind
    ON federation_objects (origin_cell_id, object_kind, object_version);

CREATE TABLE federation_inbox (
    event_id UUID PRIMARY KEY,
    origin_cell_id TEXT NOT NULL,
    object_address TEXT NOT NULL,
    object_version BIGINT NOT NULL CHECK (object_version > 0),
    event_type TEXT NOT NULL,
    schema_version INTEGER NOT NULL CHECK (schema_version > 0),
    scope TEXT NOT NULL,
    envelope_sha256 TEXT NOT NULL CHECK (length(envelope_sha256) = 64),
    envelope JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX federation_inbox_origin_received
    ON federation_inbox (origin_cell_id, received_at DESC);

CREATE TABLE federation_quarantine (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID NOT NULL,
    origin_cell_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    envelope_sha256 TEXT NOT NULL CHECK (length(envelope_sha256) = 64),
    envelope JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX federation_quarantine_origin_received
    ON federation_quarantine (origin_cell_id, received_at DESC);

CREATE INDEX federation_quarantine_event
    ON federation_quarantine (event_id, received_at DESC);

CREATE TABLE federation_outbox (
    event_id UUID PRIMARY KEY,
    object_address TEXT NOT NULL,
    object_version BIGINT NOT NULL CHECK (object_version > 0),
    envelope_sha256 TEXT NOT NULL CHECK (length(envelope_sha256) = 64),
    envelope JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX federation_outbox_created
    ON federation_outbox (created_at, event_id);

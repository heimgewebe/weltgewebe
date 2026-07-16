CREATE TABLE auth_ephemeral_state (
    state_kind TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    context_key TEXT,
    account_id TEXT,
    device_id TEXT,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (state_kind, key_hash)
);

CREATE UNIQUE INDEX auth_ephemeral_state_context_unique
    ON auth_ephemeral_state (state_kind, context_key)
    WHERE context_key IS NOT NULL;

CREATE INDEX auth_ephemeral_state_expiry
    ON auth_ephemeral_state (expires_at);

CREATE TABLE auth_rate_limit_counters (
    scope TEXT NOT NULL,
    subject_hash TEXT NOT NULL,
    window_start BIGINT NOT NULL,
    window_seconds INTEGER NOT NULL CHECK (window_seconds > 0),
    request_count BIGINT NOT NULL CHECK (request_count > 0),
    expires_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (scope, subject_hash, window_start, window_seconds)
);

CREATE INDEX auth_rate_limit_counters_expiry
    ON auth_rate_limit_counters (expires_at);

CREATE TABLE domain_outbox (
    id BIGSERIAL PRIMARY KEY,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    published_at TIMESTAMPTZ,
    quarantined_at TIMESTAMPTZ,
    last_error TEXT,
    CHECK (NOT (published_at IS NOT NULL AND quarantined_at IS NOT NULL))
);

CREATE INDEX domain_outbox_pending
    ON domain_outbox (available_at, id)
    WHERE published_at IS NULL AND quarantined_at IS NULL;

CREATE TABLE domain_event_consumptions (
    consumer_name TEXT NOT NULL,
    event_id BIGINT NOT NULL,
    consumed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (consumer_name, event_id)
);

CREATE TABLE domain_projection_state (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    version BIGINT NOT NULL DEFAULT 0 CHECK (version >= 0)
);

INSERT INTO domain_projection_state (singleton, version) VALUES (TRUE, 0)
ON CONFLICT (singleton) DO NOTHING;

CREATE OR REPLACE FUNCTION weltgewebe_enqueue_domain_event()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    aggregate_kind TEXT;
    aggregate_identifier TEXT;
    action_name TEXT;
BEGIN
    IF TG_OP = 'UPDATE' AND NEW IS NOT DISTINCT FROM OLD THEN
        RETURN NEW;
    END IF;

    CASE TG_TABLE_NAME
        WHEN 'domain_nodes' THEN aggregate_kind := 'node';
        WHEN 'domain_edges' THEN aggregate_kind := 'edge';
        WHEN 'domain_accounts' THEN aggregate_kind := 'account';
        ELSE RAISE EXCEPTION 'unsupported outbox table: %', TG_TABLE_NAME;
    END CASE;

    IF TG_OP = 'DELETE' THEN
        aggregate_identifier := OLD.id;
    ELSE
        aggregate_identifier := NEW.id;
    END IF;

    CASE TG_OP
        WHEN 'INSERT' THEN action_name := 'created';
        WHEN 'UPDATE' THEN action_name := 'updated';
        WHEN 'DELETE' THEN action_name := 'deleted';
        ELSE RAISE EXCEPTION 'unsupported outbox operation: %', TG_OP;
    END CASE;

    UPDATE domain_projection_state
       SET version = version + 1
     WHERE singleton = TRUE;

    INSERT INTO domain_outbox (
        aggregate_type,
        aggregate_id,
        event_type,
        payload
    ) VALUES (
        aggregate_kind,
        aggregate_identifier,
        'domain.' || aggregate_kind || '.' || action_name,
        jsonb_build_object(
            'schema_version', 1,
            'aggregate_type', aggregate_kind,
            'aggregate_id', aggregate_identifier,
            'event_type', 'domain.' || aggregate_kind || '.' || action_name
        )
    );

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER domain_nodes_outbox
AFTER INSERT OR UPDATE OR DELETE ON domain_nodes
FOR EACH ROW EXECUTE FUNCTION weltgewebe_enqueue_domain_event();

CREATE TRIGGER domain_edges_outbox
AFTER INSERT OR UPDATE OR DELETE ON domain_edges
FOR EACH ROW EXECUTE FUNCTION weltgewebe_enqueue_domain_event();

CREATE TRIGGER domain_accounts_outbox
AFTER INSERT OR UPDATE OR DELETE ON domain_accounts
FOR EACH ROW EXECUTE FUNCTION weltgewebe_enqueue_domain_event();

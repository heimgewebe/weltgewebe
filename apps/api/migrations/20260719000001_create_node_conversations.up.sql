-- One canonical public conversation per PostgreSQL-backed node.
--
-- Existing nodes receive a deterministic UUIDv5-shaped identifier derived
-- from the node id. A database trigger applies the same derivation to every
-- later node insert, so node + conversation + both outbox records commit (or
-- roll back) together regardless of which application path inserted the node.

-- New and updated account titles must already satisfy the public author
-- snapshot contract. NOT VALID avoids turning pre-existing legacy rows into a
-- deployment blocker while still enforcing the rule for later writes.
ALTER TABLE domain_accounts
    ADD CONSTRAINT domain_accounts_conversation_author_title
    CHECK (
        char_length(title) BETWEEN 1 AND 200
        AND title ~ '[^[:space:]]'
    ) NOT VALID;

CREATE TABLE domain_conversations (
    id                UUID        PRIMARY KEY,
    node_id           TEXT        NOT NULL UNIQUE
                                  REFERENCES domain_nodes (id) ON DELETE CASCADE,
    conversation_type TEXT        NOT NULL DEFAULT 'node'
                                  CHECK (conversation_type = 'node'),
    visibility        TEXT        NOT NULL DEFAULT 'public'
                                  CHECK (visibility = 'public'),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at        TIMESTAMPTZ,
    CHECK (updated_at >= created_at),
    CHECK (deleted_at IS NULL OR deleted_at >= created_at)
);

CREATE TABLE domain_messages (
    id                UUID        PRIMARY KEY,
    conversation_id   UUID        NOT NULL
                                  REFERENCES domain_conversations (id) ON DELETE CASCADE,
    -- The live account reference is nulled on account deletion. This prevents a
    -- later account that happens to reuse the same textual id from inheriting
    -- edit/remove authority over historical contributions. author_title remains
    -- the durable public snapshot that keeps the contribution readable.
    author_account_id TEXT        REFERENCES domain_accounts (id) ON DELETE SET NULL,
    author_title      TEXT        NOT NULL
                                  CHECK (char_length(btrim(author_title)) BETWEEN 1 AND 200),
    content           TEXT,
    idempotency_key   UUID        NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at        TIMESTAMPTZ,
    -- Idempotency is bound to the conversation as well as the author so that the
    -- same client-generated key cannot silently collapse posts made to two
    -- different node conversations.
    CONSTRAINT domain_messages_author_idempotency_unique
        UNIQUE (conversation_id, author_account_id, idempotency_key),
    CHECK (
        (deleted_at IS NULL AND content IS NOT NULL
         AND char_length(content) BETWEEN 1 AND 4000
         AND content ~ '[^[:space:]]')
        OR (deleted_at IS NOT NULL AND content IS NULL)
    ),
    CHECK (updated_at >= created_at),
    CHECK (deleted_at IS NULL OR deleted_at >= created_at)
);

CREATE INDEX domain_messages_stable_order
    ON domain_messages (conversation_id, created_at, id);

CREATE INDEX domain_messages_author_rate_window
    ON domain_messages (conversation_id, author_account_id, created_at DESC);

CREATE OR REPLACE FUNCTION weltgewebe_node_conversation_id(node_identifier TEXT)
RETURNS UUID
LANGUAGE SQL
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
    SELECT (
        substr(digest, 1, 8) || '-' ||
        substr(digest, 9, 4) || '-' ||
        '5' || substr(digest, 14, 3) || '-' ||
        '8' || substr(digest, 18, 3) || '-' ||
        substr(digest, 21, 12)
    )::uuid
    FROM (
        SELECT md5('weltgewebe:node-conversation:v1:' || node_identifier) AS digest
    ) AS deterministic_hash;
$$;

CREATE OR REPLACE FUNCTION weltgewebe_enqueue_conversation_event()
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
        WHEN 'domain_conversations' THEN aggregate_kind := 'conversation';
        WHEN 'domain_messages' THEN aggregate_kind := 'message';
        ELSE RAISE EXCEPTION 'unsupported conversation outbox table: %', TG_TABLE_NAME;
    END CASE;

    IF TG_OP = 'DELETE' THEN
        aggregate_identifier := OLD.id::text;
    ELSE
        aggregate_identifier := NEW.id::text;
    END IF;

    IF TG_OP = 'UPDATE'
       AND OLD.deleted_at IS NULL
       AND NEW.deleted_at IS NOT NULL THEN
        action_name := 'deleted';
    ELSE
        CASE TG_OP
            WHEN 'INSERT' THEN action_name := 'created';
            WHEN 'UPDATE' THEN action_name := 'updated';
            WHEN 'DELETE' THEN action_name := 'deleted';
            ELSE RAISE EXCEPTION 'unsupported conversation outbox operation: %', TG_OP;
        END CASE;
    END IF;

    -- Conversation activity is deliberately not map-domain state. Unlike
    -- weltgewebe_enqueue_domain_event(), this function never increments
    -- domain_projection_state and never places content or author data in the
    -- outbox payload.
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

CREATE TRIGGER domain_conversations_outbox
AFTER INSERT OR UPDATE OR DELETE ON domain_conversations
FOR EACH ROW EXECUTE FUNCTION weltgewebe_enqueue_conversation_event();

CREATE TRIGGER domain_messages_outbox
AFTER INSERT OR UPDATE OR DELETE ON domain_messages
FOR EACH ROW EXECUTE FUNCTION weltgewebe_enqueue_conversation_event();

INSERT INTO domain_conversations (
    id,
    node_id,
    created_at,
    updated_at
)
SELECT
    weltgewebe_node_conversation_id(id),
    id,
    COALESCE(created_at, TIMESTAMPTZ '1970-01-01 00:00:00+00'),
    GREATEST(
        COALESCE(created_at, TIMESTAMPTZ '1970-01-01 00:00:00+00'),
        COALESCE(updated_at, created_at, TIMESTAMPTZ '1970-01-01 00:00:00+00')
    )
FROM domain_nodes
ON CONFLICT (node_id) DO NOTHING;

CREATE OR REPLACE FUNCTION weltgewebe_create_node_conversation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO domain_conversations (
        id,
        node_id,
        created_at,
        updated_at
    ) VALUES (
        weltgewebe_node_conversation_id(NEW.id),
        NEW.id,
        COALESCE(NEW.created_at, NOW()),
        GREATEST(
            COALESCE(NEW.created_at, NOW()),
            COALESCE(NEW.updated_at, NEW.created_at, NOW())
        )
    );
    RETURN NEW;
END;
$$;

CREATE TRIGGER domain_nodes_create_conversation
AFTER INSERT ON domain_nodes
FOR EACH ROW EXECUTE FUNCTION weltgewebe_create_node_conversation();

-- A node may be removed while its generated conversation is still empty. Once
-- public contributions exist, deletion must not bypass message ownership and
-- tombstone semantics by cascading the complete history away. Locking the
-- conversation row also serializes this decision against concurrent inserts:
-- the message foreign-key lock and this FOR UPDATE lock cannot pass each other.
CREATE OR REPLACE FUNCTION weltgewebe_protect_node_conversation_history()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    conversation_identifier UUID;
BEGIN
    SELECT id INTO conversation_identifier
    FROM domain_conversations
    WHERE node_id = OLD.id
    FOR UPDATE;

    IF conversation_identifier IS NOT NULL AND EXISTS (
        SELECT 1 FROM domain_messages
        WHERE conversation_id = conversation_identifier
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23503',
            CONSTRAINT = 'domain_nodes_conversation_history_guard',
            MESSAGE = 'node deletion blocked by existing conversation messages';
    END IF;

    RETURN OLD;
END;
$$;

CREATE TRIGGER domain_nodes_protect_conversation_history
BEFORE DELETE ON domain_nodes
FOR EACH ROW EXECUTE FUNCTION weltgewebe_protect_node_conversation_history();

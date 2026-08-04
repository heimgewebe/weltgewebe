-- Optional Web Push delivery for private direct messages.
--
-- The canonical message store remains the source of truth. These tables only
-- remember an account preference, browser-owned push subscriptions and the
-- retryable delivery receipts derived from committed message outbox events.

CREATE TABLE notification_preferences (
    account_id            TEXT        PRIMARY KEY
                                      REFERENCES domain_accounts (id) ON DELETE CASCADE,
    direct_messages_push  BOOLEAN     NOT NULL DEFAULT FALSE,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE web_push_subscriptions (
    id             UUID        PRIMARY KEY,
    account_id     TEXT        NOT NULL
                               REFERENCES domain_accounts (id) ON DELETE CASCADE,
    endpoint       TEXT        NOT NULL
                               CHECK (char_length(endpoint) BETWEEN 16 AND 2048),
    endpoint_hash  CHAR(64)    NOT NULL UNIQUE
                               CHECK (endpoint_hash ~ '^[0-9a-f]{64}$'),
    p256dh         TEXT        NOT NULL
                               CHECK (char_length(p256dh) BETWEEN 80 AND 128),
    auth_secret    TEXT        NOT NULL
                               CHECK (char_length(auth_secret) BETWEEN 16 AND 64),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    disabled_at    TIMESTAMPTZ,
    last_error     TEXT        CHECK (last_error IS NULL OR char_length(last_error) <= 2000),
    CHECK (disabled_at IS NULL OR disabled_at >= created_at)
);

CREATE INDEX web_push_subscriptions_by_account
    ON web_push_subscriptions (account_id, created_at DESC)
    WHERE disabled_at IS NULL;

CREATE TABLE web_push_deliveries (
    source_event_id  BIGINT      NOT NULL
                                 REFERENCES domain_outbox (id) ON DELETE CASCADE,
    subscription_id  UUID        NOT NULL
                                 REFERENCES web_push_subscriptions (id) ON DELETE CASCADE,
    conversation_id  UUID        NOT NULL
                                 REFERENCES domain_conversations (id) ON DELETE CASCADE,
    notification_kind TEXT       NOT NULL DEFAULT 'direct_message'
                                 CHECK (notification_kind IN ('direct_message')),
    status           TEXT        NOT NULL DEFAULT 'pending'
                                 CHECK (status IN ('pending', 'sending', 'retry', 'sent', 'gone', 'cancelled', 'quarantined')),
    attempt_count    INTEGER     NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    available_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_until    TIMESTAMPTZ,
    sent_at          TIMESTAMPTZ,
    last_error       TEXT        CHECK (last_error IS NULL OR char_length(last_error) <= 2000),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_event_id, subscription_id),
    CHECK (sent_at IS NULL OR status = 'sent')
);

CREATE INDEX web_push_deliveries_ready
    ON web_push_deliveries (available_at, source_event_id, subscription_id)
    WHERE status IN ('pending', 'retry', 'sending');

-- Guest exit anonymizes retained conversation contributions by account id.
-- PostgreSQL does not automatically index referencing FK columns, and the
-- existing domain_messages index begins with conversation_id, so neither table
-- has an efficient account-first lookup for exit cleanup / ON DELETE SET NULL.
CREATE INDEX IF NOT EXISTS governance_messages_author_account_id_idx
    ON governance_messages (author_account_id);

CREATE INDEX IF NOT EXISTS domain_messages_author_account_id_idx
    ON domain_messages (author_account_id);

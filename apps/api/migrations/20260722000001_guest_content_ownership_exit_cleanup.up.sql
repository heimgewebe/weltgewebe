-- Guests may now contribute to proposal discussions before becoming Weber.
-- Keep the historical contribution when an eligible guest deletes the account,
-- but remove the live authority binding exactly like node-conversation messages.
ALTER TABLE governance_messages
    ALTER COLUMN author_account_id DROP NOT NULL;

-- The legacy table had no foreign key. Preserve any already orphaned
-- historical contribution by anonymizing its live binding before enforcing
-- the new invariant.
UPDATE governance_messages AS message
SET author_account_id = NULL
WHERE author_account_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM domain_accounts AS account
      WHERE account.id = message.author_account_id
  );

ALTER TABLE governance_messages
    ADD CONSTRAINT governance_messages_author_account_fk
    FOREIGN KEY (author_account_id)
    REFERENCES domain_accounts (id)
    ON DELETE SET NULL;

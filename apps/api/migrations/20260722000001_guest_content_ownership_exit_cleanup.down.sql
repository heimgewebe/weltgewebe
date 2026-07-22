-- Rollback is deliberately fail-closed: once an account deletion has
-- anonymized a historical contribution, NOT NULL cannot be restored without
-- inventing an author.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM governance_messages WHERE author_account_id IS NULL
    ) THEN
        RAISE EXCEPTION
            'cannot restore governance_messages.author_account_id NOT NULL after anonymization';
    END IF;
END
$$;

ALTER TABLE governance_messages
    DROP CONSTRAINT IF EXISTS governance_messages_author_account_fk;

ALTER TABLE governance_messages
    ALTER COLUMN author_account_id SET NOT NULL;

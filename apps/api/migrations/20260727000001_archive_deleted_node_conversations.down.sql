-- Rollback is safe only before any node conversation or governance applicant
-- binding has been detached. Once a parent identity is gone, the old NOT NULL
-- and cascade contracts cannot be restored without inventing or erasing public
-- history, so the migration fails closed.

DROP TRIGGER IF EXISTS domain_conversations_archived_outbox ON domain_conversations;
DROP FUNCTION IF EXISTS weltgewebe_enqueue_conversation_archived_event();
DROP TRIGGER IF EXISTS domain_messages_conversation_lifecycle_guard ON domain_messages;
DROP FUNCTION IF EXISTS weltgewebe_protect_conversation_messages();
DROP TRIGGER IF EXISTS domain_conversations_history_guard ON domain_conversations;
DROP FUNCTION IF EXISTS weltgewebe_protect_conversation_record_history();

LOCK TABLE domain_accounts IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE governance_proposals IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE domain_nodes IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE domain_conversations IN SHARE ROW EXCLUSIVE MODE;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM domain_conversations
        WHERE conversation_type = 'node'
          AND node_id IS NULL
          AND archived_at IS NOT NULL
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'cannot roll back archived node conversations after their nodes were deleted';
    END IF;
END;
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM governance_proposals
        WHERE applicant_account_id IS NULL
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'cannot roll back detached governance applicant history after account deletion';
    END IF;
END;
$$;

DROP TRIGGER IF EXISTS domain_accounts_detach_governance_history ON domain_accounts;
DROP FUNCTION IF EXISTS weltgewebe_detach_governance_history_on_account_delete();

ALTER TABLE governance_proposals
    DROP CONSTRAINT governance_proposals_applicant_lifecycle,
    ALTER COLUMN applicant_account_id SET NOT NULL;

ALTER TABLE domain_conversations
    DROP CONSTRAINT domain_conversations_subject_kind;

ALTER TABLE domain_conversations
    ADD CONSTRAINT domain_conversations_subject_kind CHECK (
        (conversation_type = 'node'
         AND node_id IS NOT NULL
         AND proposal_id IS NULL)
        OR
        (conversation_type = 'governance_proposal'
         AND node_id IS NULL
         AND proposal_id IS NOT NULL)
    );

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

ALTER TABLE domain_conversations
    DROP COLUMN archived_at,
    DROP COLUMN node_title_snapshot,
    DROP COLUMN node_id_snapshot;

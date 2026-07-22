-- T018 Release-A rollback. This down migration is intentionally fail-closed:
-- it is only safe while governance still reads and writes the legacy table and
-- no canonical governance message exists.

DO $$
DECLARE
    current_governance_source TEXT;
BEGIN
    -- Serialize rollback against both cutover flips and canonical writers. The
    -- row lock is held for the surrounding migration transaction, so the state
    -- cannot change after this guard succeeds and before the schema is removed.
    SELECT governance_source
    INTO current_governance_source
    FROM domain_conversation_cutover_state
    WHERE singleton
    FOR UPDATE;

    IF current_governance_source IS NULL THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'cannot roll back governance conversation target without cutover state';
    END IF;

    IF current_governance_source <> 'legacy' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'cannot roll back governance conversation target after canonical cutover';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM domain_messages AS message
        JOIN domain_conversations AS conversation
          ON conversation.id = message.conversation_id
        WHERE conversation.conversation_type = 'governance_proposal'
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'cannot roll back governance conversation target with canonical messages';
    END IF;
END;
$$;

DROP TRIGGER IF EXISTS governance_proposals_protect_conversation_history
    ON governance_proposals;
DROP FUNCTION IF EXISTS weltgewebe_protect_governance_conversation_history();

DROP TRIGGER IF EXISTS governance_proposals_create_conversation
    ON governance_proposals;
DROP FUNCTION IF EXISTS weltgewebe_create_governance_proposal_conversation();

-- Deleting the additive targets emits domain.conversation.deleted events. Keep
-- both the earlier created events and these compensating deletes in the outbox:
-- already-published events cannot be retracted from JetStream, and unpublished
-- events must retain their ordered create/delete history instead of leaving a
-- downstream ghost conversation.
DELETE FROM domain_conversations
WHERE conversation_type = 'governance_proposal';

DROP TABLE domain_conversation_cutover_state;

DROP INDEX domain_conversations_one_per_governance_proposal;
DROP INDEX domain_conversations_one_per_node;

ALTER TABLE domain_conversations
    DROP CONSTRAINT domain_conversations_subject_kind;

ALTER TABLE domain_conversations
    DROP COLUMN proposal_id;

ALTER TABLE domain_conversations
    ALTER COLUMN node_id SET NOT NULL;

ALTER TABLE domain_conversations
    ADD CONSTRAINT domain_conversations_conversation_type_check
    CHECK (conversation_type = 'node');

ALTER TABLE domain_conversations
    ADD CONSTRAINT domain_conversations_node_id_key UNIQUE (node_id);

DROP FUNCTION weltgewebe_governance_proposal_conversation_id(UUID);

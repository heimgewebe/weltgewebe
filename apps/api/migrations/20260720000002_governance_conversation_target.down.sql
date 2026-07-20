-- T018 Release-A rollback. This down migration is intentionally fail-closed:
-- it is only safe while governance still reads and writes the legacy table and
-- no canonical governance message exists.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM domain_conversation_cutover_state
        WHERE singleton
          AND governance_source <> 'legacy'
    ) THEN
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

CREATE TEMP TABLE t018_governance_conversation_ids
ON COMMIT DROP
AS
SELECT id::text AS aggregate_id
FROM domain_conversations
WHERE conversation_type = 'governance_proposal';

DELETE FROM domain_conversations
WHERE conversation_type = 'governance_proposal';

-- The conversation outbox trigger emits a delete event. Remove every event for
-- the temporary additive targets so rollback restores the pre-migration truth.
DELETE FROM domain_outbox
WHERE aggregate_type = 'conversation'
  AND aggregate_id IN (
      SELECT aggregate_id FROM t018_governance_conversation_ids
  );

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

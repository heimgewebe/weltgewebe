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

    -- Stop proposal inserts/deletes while the rollback snapshots and removes the
    -- additive targets. Transactions that started earlier must finish before this
    -- lock is granted, so their conversation/outbox rows are visible below.
    LOCK TABLE governance_proposals IN SHARE ROW EXCLUSIVE MODE;

    -- Fence the relay before deciding that rollback is still local-only. The
    -- relay claims rows with FOR UPDATE SKIP LOCKED and increments attempt_count
    -- before publishing, so these locks prevent new claims while attempt_count > 0
    -- covers both in-flight and previously attempted delivery.
    PERFORM event.id
    FROM domain_outbox AS event
    JOIN domain_conversations AS conversation
      ON conversation.id::text = event.aggregate_id
    WHERE event.aggregate_type = 'conversation'
      AND conversation.conversation_type = 'governance_proposal'
    FOR UPDATE OF event;

    IF EXISTS (
        SELECT 1
        FROM domain_outbox AS event
        JOIN domain_conversations AS conversation
          ON conversation.id::text = event.aggregate_id
        WHERE event.aggregate_type = 'conversation'
          AND conversation.conversation_type = 'governance_proposal'
          AND (event.published_at IS NOT NULL OR event.attempt_count > 0)
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'cannot roll back governance conversation target after outbox delivery started';
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

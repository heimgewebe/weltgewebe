-- Allow a node to leave the active map while preserving contributed public
-- conversation history under an explicit lifecycle contract.
--
-- Active node conversations remain attached through node_id. When a node with
-- messages is removed, the deletion trigger snapshots the node identity and
-- title, detaches the conversation from the cascading foreign key, and marks it
-- archived in the same transaction. Empty generated conversations still follow
-- the existing ON DELETE CASCADE path and disappear with their node.
--
-- A contribution is never physically deleted through ordinary SQL. Active and
-- archived contributions use tombstones; archives additionally reject new
-- messages and ordinary content edits. Account deletion may still sever only the
-- live author_account_id binding.

ALTER TABLE domain_conversations
    ADD COLUMN node_id_snapshot TEXT,
    ADD COLUMN node_title_snapshot TEXT,
    ADD COLUMN archived_at TIMESTAMPTZ;

-- Applicant identity is an active binding, while applicant_title is the durable
-- procedural snapshot. Account deletion may therefore detach only proposals
-- that already carry public or procedural history. Empty open proposals remain
-- attached and continue to follow the existing ON DELETE CASCADE contract.
ALTER TABLE governance_proposals
    ALTER COLUMN applicant_account_id DROP NOT NULL;

ALTER TABLE governance_proposals
    ADD CONSTRAINT governance_proposals_applicant_lifecycle CHECK (
        applicant_account_id IS NOT NULL
        OR (status IN ('accepted', 'rejected') AND finalized_at IS NOT NULL)
    );

CREATE OR REPLACE FUNCTION weltgewebe_detach_governance_history_on_account_delete()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    detach_timestamp TIMESTAMPTZ := clock_timestamp();
BEGIN
    UPDATE governance_proposals AS proposal
    SET applicant_account_id = NULL,
        status = CASE
            WHEN proposal.status IN ('consent', 'voting') THEN 'rejected'
            ELSE proposal.status
        END,
        finalized_at = CASE
            WHEN proposal.status IN ('consent', 'voting') THEN detach_timestamp
            ELSE proposal.finalized_at
        END
    WHERE proposal.applicant_account_id = OLD.id
      AND (
          proposal.status IN ('accepted', 'rejected')
          OR EXISTS (
              SELECT 1 FROM governance_vetoes AS veto
              WHERE veto.proposal_id = proposal.id
          )
          OR EXISTS (
              SELECT 1 FROM governance_votes AS vote
              WHERE vote.proposal_id = proposal.id
          )
          OR EXISTS (
              SELECT 1 FROM governance_messages AS legacy_message
              WHERE legacy_message.proposal_id = proposal.id
          )
          OR EXISTS (
              SELECT 1
              FROM domain_conversations AS conversation
              JOIN domain_messages AS message
                ON message.conversation_id = conversation.id
              WHERE conversation.proposal_id = proposal.id
          )
      );

    RETURN OLD;
END;
$$;

CREATE TRIGGER domain_accounts_detach_governance_history
BEFORE DELETE ON domain_accounts
FOR EACH ROW EXECUTE FUNCTION weltgewebe_detach_governance_history_on_account_delete();

ALTER TABLE domain_conversations
    DROP CONSTRAINT domain_conversations_subject_kind;

ALTER TABLE domain_conversations
    ADD CONSTRAINT domain_conversations_subject_kind CHECK (
        (
            conversation_type = 'node'
            AND proposal_id IS NULL
            AND (
                (
                    node_id IS NOT NULL
                    AND node_id_snapshot IS NULL
                    AND node_title_snapshot IS NULL
                    AND archived_at IS NULL
                )
                OR
                (
                    node_id IS NULL
                    AND node_id_snapshot IS NOT NULL
                    AND node_title_snapshot IS NOT NULL
                    AND archived_at IS NOT NULL
                )
            )
        )
        OR
        (
            conversation_type = 'governance_proposal'
            AND node_id IS NULL
            AND proposal_id IS NOT NULL
            AND node_id_snapshot IS NULL
            AND node_title_snapshot IS NULL
            AND archived_at IS NULL
        )
    );

CREATE OR REPLACE FUNCTION weltgewebe_protect_node_conversation_history()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    conversation_identifier UUID;
    archive_timestamp TIMESTAMPTZ;
BEGIN
    SELECT id INTO conversation_identifier
    FROM domain_conversations
    WHERE node_id = OLD.id
    FOR UPDATE;

    IF conversation_identifier IS NOT NULL AND EXISTS (
        SELECT 1 FROM domain_messages
        WHERE conversation_id = conversation_identifier
    ) THEN
        archive_timestamp := clock_timestamp();
        UPDATE domain_conversations
        SET node_id = NULL,
            node_id_snapshot = OLD.id,
            node_title_snapshot = OLD.title,
            archived_at = archive_timestamp,
            updated_at = GREATEST(updated_at, archive_timestamp)
        WHERE id = conversation_identifier;
    END IF;

    RETURN OLD;
END;
$$;

-- Hard deletion is valid only for an empty active generated conversation. A
-- non-empty active conversation and every archive are durable history records.
-- The active -> archived transition remains possible because UPDATE is rejected
-- only after OLD.archived_at is already set.
CREATE OR REPLACE FUNCTION weltgewebe_protect_conversation_record_history()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' AND (
        OLD.archived_at IS NOT NULL
        OR EXISTS (
            SELECT 1 FROM domain_messages
            WHERE conversation_id = OLD.id
        )
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            CONSTRAINT = 'domain_conversations_history_guard',
            MESSAGE = 'non-empty or archived conversations cannot be physically deleted';
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.archived_at IS NOT NULL THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            CONSTRAINT = 'domain_conversations_history_guard',
            MESSAGE = 'archived conversation records are immutable';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER domain_conversations_history_guard
BEFORE UPDATE OR DELETE ON domain_conversations
FOR EACH ROW EXECUTE FUNCTION weltgewebe_protect_conversation_record_history();

CREATE OR REPLACE FUNCTION weltgewebe_protect_conversation_messages()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    target_archived BOOLEAN;
    source_archived BOOLEAN := FALSE;
BEGIN
    -- Public history is removed through a tombstone UPDATE, never a physical
    -- row DELETE. This also makes parent-cascade behavior fail closed.
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            CONSTRAINT = 'domain_messages_physical_delete_guard',
            MESSAGE = 'conversation messages must be tombstoned, not physically deleted';
    END IF;

    SELECT archived_at IS NOT NULL INTO target_archived
    FROM domain_conversations
    WHERE id = NEW.conversation_id
    FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING
            ERRCODE = '23503',
            CONSTRAINT = 'domain_messages_conversation_required',
            MESSAGE = 'message conversation does not exist';
    END IF;

    IF TG_OP = 'UPDATE'
       AND OLD.conversation_id IS DISTINCT FROM NEW.conversation_id THEN
        SELECT archived_at IS NOT NULL INTO source_archived
        FROM domain_conversations
        WHERE id = OLD.conversation_id
        FOR SHARE;
        IF NOT FOUND THEN
            RAISE EXCEPTION USING
                ERRCODE = '23503',
                CONSTRAINT = 'domain_messages_conversation_required',
                MESSAGE = 'source conversation does not exist';
        END IF;
    END IF;

    IF NOT target_archived AND NOT source_archived THEN
        RETURN NEW;
    END IF;

    -- Account deletion may sever only the live ownership link.
    IF TG_OP = 'UPDATE'
       AND OLD.author_account_id IS NOT NULL
       AND NEW.author_account_id IS NULL
       AND NEW.id = OLD.id
       AND NEW.conversation_id = OLD.conversation_id
       AND NEW.author_title = OLD.author_title
       AND NEW.content IS NOT DISTINCT FROM OLD.content
       AND NEW.idempotency_key = OLD.idempotency_key
       AND NEW.created_at = OLD.created_at
       AND NEW.updated_at = OLD.updated_at
       AND NEW.deleted_at IS NOT DISTINCT FROM OLD.deleted_at THEN
        RETURN NEW;
    END IF;

    -- Author withdrawal and administrative moderation remain available after
    -- archival, but only as the canonical one-way content -> tombstone change.
    IF TG_OP = 'UPDATE'
       AND OLD.deleted_at IS NULL
       AND OLD.content IS NOT NULL
       AND NEW.content IS NULL
       AND NEW.deleted_at IS NOT NULL
       AND NEW.updated_at >= NEW.deleted_at
       AND NEW.updated_at > OLD.updated_at
       AND NEW.id = OLD.id
       AND NEW.conversation_id = OLD.conversation_id
       AND NEW.author_account_id IS NOT DISTINCT FROM OLD.author_account_id
       AND NEW.author_title = OLD.author_title
       AND NEW.idempotency_key = OLD.idempotency_key
       AND NEW.created_at = OLD.created_at THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION USING
        ERRCODE = '55000',
        CONSTRAINT = 'domain_messages_archived_conversation_guard',
        MESSAGE = 'archived conversations reject new messages and ordinary edits';
END;
$$;

CREATE TRIGGER domain_messages_conversation_lifecycle_guard
BEFORE INSERT OR UPDATE OR DELETE ON domain_messages
FOR EACH ROW EXECUTE FUNCTION weltgewebe_protect_conversation_messages();

CREATE OR REPLACE FUNCTION weltgewebe_enqueue_conversation_archived_event()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO domain_outbox (
        aggregate_type,
        aggregate_id,
        event_type,
        payload
    ) VALUES (
        'conversation',
        NEW.id::text,
        'domain.conversation.archived',
        jsonb_build_object(
            'schema_version', 1,
            'aggregate_type', 'conversation',
            'aggregate_id', NEW.id::text,
            'event_type', 'domain.conversation.archived',
            'lifecycle_state', 'archived'
        )
    );
    RETURN NEW;
END;
$$;

CREATE TRIGGER domain_conversations_archived_outbox
AFTER UPDATE OF archived_at ON domain_conversations
FOR EACH ROW
WHEN (OLD.archived_at IS NULL AND NEW.archived_at IS NOT NULL)
EXECUTE FUNCTION weltgewebe_enqueue_conversation_archived_event();

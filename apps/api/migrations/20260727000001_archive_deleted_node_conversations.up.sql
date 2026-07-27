-- Allow a node to leave the active map while preserving its contributed public
-- conversation as an immutable historical record.
--
-- Active node conversations remain attached only through node_id. When a node
-- with messages is deleted, the deletion trigger snapshots the node identity
-- and title, detaches the conversation from the cascading foreign key, and
-- marks it archived in the same transaction. Empty generated conversations
-- still follow the existing ON DELETE CASCADE path and disappear with their
-- node. Snapshot columns stay NULL before archival, avoiding a second mutable
-- copy of active node data.

ALTER TABLE domain_conversations
    ADD COLUMN node_id_snapshot TEXT,
    ADD COLUMN node_title_snapshot TEXT,
    ADD COLUMN archived_at TIMESTAMPTZ;

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

CREATE OR REPLACE FUNCTION weltgewebe_protect_archived_conversation_messages()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    archived BOOLEAN;
    conversation_identifier UUID;
BEGIN
    IF TG_OP = 'DELETE' THEN
        conversation_identifier := OLD.conversation_id;
    ELSE
        conversation_identifier := NEW.conversation_id;
    END IF;

    SELECT archived_at IS NOT NULL INTO archived
    FROM domain_conversations
    WHERE id = conversation_identifier
    FOR SHARE;

    IF NOT COALESCE(archived, FALSE) AND TG_OP = 'UPDATE'
       AND OLD.conversation_id IS DISTINCT FROM NEW.conversation_id THEN
        SELECT archived_at IS NOT NULL INTO archived
        FROM domain_conversations
        WHERE id = OLD.conversation_id
        FOR SHARE;
    END IF;

    IF NOT COALESCE(archived, FALSE) THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;

    -- Account deletion may still sever the live ownership link. This is the
    -- only permitted mutation of an archived contribution: content, snapshot,
    -- timestamps, idempotency and conversation membership remain unchanged.
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

    RAISE EXCEPTION USING
        ERRCODE = '55000',
        CONSTRAINT = 'domain_messages_archived_conversation_guard',
        MESSAGE = 'archived conversation messages are immutable';
END;
$$;

CREATE TRIGGER domain_messages_archived_conversation_guard
BEFORE INSERT OR UPDATE OR DELETE ON domain_messages
FOR EACH ROW EXECUTE FUNCTION weltgewebe_protect_archived_conversation_messages();

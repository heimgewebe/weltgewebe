-- Private 1:1 conversations reuse the canonical conversation/message store,
-- but add an explicit participant boundary. Public conversations remain public;
-- direct conversations are readable and writable only by their two participants.

ALTER TABLE domain_conversations
    ADD COLUMN direct_pair_key TEXT,
    ADD COLUMN direct_created_by_account_id TEXT
        REFERENCES domain_accounts (id) ON DELETE SET NULL;

ALTER TABLE domain_conversations
    DROP CONSTRAINT domain_conversations_visibility_check;

ALTER TABLE domain_conversations
    DROP CONSTRAINT domain_conversations_subject_kind;

ALTER TABLE domain_conversations
    ADD CONSTRAINT domain_conversations_visibility_check CHECK (
        (conversation_type IN ('node', 'governance_proposal') AND visibility = 'public')
        OR (conversation_type = 'direct' AND visibility = 'participants')
    );

ALTER TABLE domain_conversations
    ADD CONSTRAINT domain_conversations_subject_kind CHECK (
        (
            conversation_type = 'node'
            AND visibility = 'public'
            AND proposal_id IS NULL
            AND direct_pair_key IS NULL
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
            AND visibility = 'public'
            AND node_id IS NULL
            AND proposal_id IS NOT NULL
            AND direct_pair_key IS NULL
            AND node_id_snapshot IS NULL
            AND node_title_snapshot IS NULL
            AND archived_at IS NULL
        )
        OR
        (
            conversation_type = 'direct'
            AND visibility = 'participants'
            AND node_id IS NULL
            AND proposal_id IS NULL
            AND direct_pair_key IS NOT NULL
            AND char_length(direct_pair_key) > 0
            AND node_id_snapshot IS NULL
            AND node_title_snapshot IS NULL
            AND archived_at IS NULL
        )
    );

CREATE UNIQUE INDEX domain_conversations_one_per_direct_pair
    ON domain_conversations (direct_pair_key)
    WHERE conversation_type = 'direct';

CREATE INDEX domain_conversations_direct_creator_rate_window
    ON domain_conversations (direct_created_by_account_id, created_at DESC)
    WHERE conversation_type = 'direct'
      AND direct_created_by_account_id IS NOT NULL;

CREATE TABLE domain_direct_conversation_participants (
    conversation_id       UUID        NOT NULL
                                      REFERENCES domain_conversations (id) ON DELETE CASCADE,
    slot                  SMALLINT    NOT NULL CHECK (slot IN (1, 2)),
    -- The live account binding is severed on account deletion. The title snapshot
    -- remains so the surviving participant can still understand retained history,
    -- while a later account reusing the textual id receives no authority.
    account_id            TEXT        REFERENCES domain_accounts (id) ON DELETE SET NULL,
    account_title_snapshot TEXT       NOT NULL
                                      CHECK (char_length(btrim(account_title_snapshot)) BETWEEN 1 AND 200),
    last_read_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    blocked_at            TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (conversation_id, slot),
    UNIQUE (conversation_id, account_id),
    CHECK (last_read_at >= created_at),
    CHECK (blocked_at IS NULL OR blocked_at >= created_at)
);

CREATE INDEX domain_direct_participants_account_conversations
    ON domain_direct_conversation_participants (account_id, conversation_id)
    WHERE account_id IS NOT NULL;

CREATE OR REPLACE FUNCTION weltgewebe_validate_direct_conversation_participants(
    target_conversation_id UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    target_type TEXT;
    participant_count BIGINT;
    distinct_slot_count BIGINT;
    minimum_slot SMALLINT;
    maximum_slot SMALLINT;
BEGIN
    SELECT conversation_type INTO target_type
    FROM domain_conversations
    WHERE id = target_conversation_id;

    IF target_type IS NULL THEN
        RETURN;
    END IF;

    IF target_type <> 'direct' THEN
        IF EXISTS (
            SELECT 1
            FROM domain_direct_conversation_participants
            WHERE conversation_id = target_conversation_id
        ) THEN
            RAISE EXCEPTION USING
                ERRCODE = '23514',
                CONSTRAINT = 'domain_direct_participants_direct_only',
                MESSAGE = 'only direct conversations may have private participants';
        END IF;
        RETURN;
    END IF;

    SELECT count(*), count(DISTINCT slot), min(slot), max(slot)
    INTO participant_count, distinct_slot_count, minimum_slot, maximum_slot
    FROM domain_direct_conversation_participants
    WHERE conversation_id = target_conversation_id;

    IF participant_count <> 2
       OR distinct_slot_count <> 2
       OR minimum_slot <> 1
       OR maximum_slot <> 2 THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            CONSTRAINT = 'domain_direct_conversations_two_participants',
            MESSAGE = 'a direct conversation must have exactly participant slots 1 and 2';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION weltgewebe_check_direct_conversation_row()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM weltgewebe_validate_direct_conversation_participants(NEW.id);
    RETURN NEW;
END;
$$;

CREATE CONSTRAINT TRIGGER domain_direct_conversation_participant_count
AFTER INSERT OR UPDATE ON domain_conversations
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION weltgewebe_check_direct_conversation_row();

CREATE OR REPLACE FUNCTION weltgewebe_check_direct_participant_row()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        PERFORM weltgewebe_validate_direct_conversation_participants(OLD.conversation_id);
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        PERFORM weltgewebe_validate_direct_conversation_participants(NEW.conversation_id);
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE CONSTRAINT TRIGGER domain_direct_participant_membership_guard
AFTER INSERT OR UPDATE OR DELETE ON domain_direct_conversation_participants
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION weltgewebe_check_direct_participant_row();

CREATE OR REPLACE FUNCTION weltgewebe_touch_direct_conversation_from_message()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    target_conversation_id UUID;
BEGIN
    target_conversation_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.conversation_id ELSE NEW.conversation_id END;
    UPDATE domain_conversations
    SET updated_at = GREATEST(clock_timestamp(), updated_at + INTERVAL '1 microsecond')
    WHERE id = target_conversation_id
      AND conversation_type = 'direct';
    RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE TRIGGER domain_messages_touch_direct_conversation
AFTER INSERT OR UPDATE OR DELETE ON domain_messages
FOR EACH ROW
EXECUTE FUNCTION weltgewebe_touch_direct_conversation_from_message();

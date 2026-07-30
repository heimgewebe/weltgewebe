DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM domain_conversations WHERE conversation_type = 'direct'
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'cannot roll back private conversations while direct conversation data exists';
    END IF;
END;
$$;

DROP TRIGGER IF EXISTS domain_messages_touch_direct_conversation ON domain_messages;
DROP FUNCTION IF EXISTS weltgewebe_touch_direct_conversation_from_message();

DROP TRIGGER IF EXISTS domain_direct_participant_membership_guard
    ON domain_direct_conversation_participants;
DROP FUNCTION IF EXISTS weltgewebe_check_direct_participant_row();

DROP TRIGGER IF EXISTS domain_direct_conversation_participant_count
    ON domain_conversations;
DROP FUNCTION IF EXISTS weltgewebe_check_direct_conversation_row();
DROP FUNCTION IF EXISTS weltgewebe_validate_direct_conversation_participants(UUID);

DROP INDEX IF EXISTS domain_direct_participants_account_conversations;
DROP TABLE domain_direct_conversation_participants;
DROP INDEX IF EXISTS domain_conversations_direct_creator_rate_window;
DROP INDEX IF EXISTS domain_conversations_one_per_direct_pair;

ALTER TABLE domain_conversations
    DROP CONSTRAINT domain_conversations_subject_kind;
ALTER TABLE domain_conversations
    DROP CONSTRAINT domain_conversations_visibility_check;
ALTER TABLE domain_conversations
    DROP COLUMN direct_pair_key,
    DROP COLUMN direct_created_by_account_id;

ALTER TABLE domain_conversations
    ADD CONSTRAINT domain_conversations_visibility_check CHECK (visibility = 'public');

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

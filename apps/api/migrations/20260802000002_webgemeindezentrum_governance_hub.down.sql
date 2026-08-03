DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM domain_messages m
        JOIN domain_conversations c ON c.id=m.conversation_id
        WHERE c.conversation_type='webgemeindezentrum'
    ) THEN
        RAISE EXCEPTION USING ERRCODE='23503',
            MESSAGE='cannot roll back Webgemeindezentrum conversations with public messages';
    END IF;
END;
$$;

DROP TRIGGER IF EXISTS webgemeindezentren_create_conversation ON webgemeindezentren;
DROP FUNCTION IF EXISTS weltgewebe_create_webgemeindezentrum_conversation();
DELETE FROM domain_conversations WHERE conversation_type='webgemeindezentrum';
DROP INDEX IF EXISTS domain_conversations_one_per_webgemeindezentrum;
DROP FUNCTION IF EXISTS weltgewebe_webgemeindezentrum_conversation_id(TEXT);

ALTER TABLE domain_conversations
    DROP CONSTRAINT domain_conversations_visibility_check,
    DROP CONSTRAINT domain_conversations_subject_kind,
    DROP COLUMN webgemeindezentrum_id;
ALTER TABLE domain_conversations ADD CONSTRAINT domain_conversations_visibility_check CHECK (
    (conversation_type IN ('node','governance_proposal') AND visibility='public')
    OR (conversation_type='direct' AND visibility='participants')
);
ALTER TABLE domain_conversations ADD CONSTRAINT domain_conversations_subject_kind CHECK (
    (conversation_type='node' AND visibility='public' AND proposal_id IS NULL AND direct_pair_key IS NULL
     AND ((node_id IS NOT NULL AND node_id_snapshot IS NULL AND node_title_snapshot IS NULL AND archived_at IS NULL)
       OR (node_id IS NULL AND node_id_snapshot IS NOT NULL AND node_title_snapshot IS NOT NULL AND archived_at IS NOT NULL)))
    OR (conversation_type='governance_proposal' AND visibility='public' AND node_id IS NULL
        AND proposal_id IS NOT NULL AND direct_pair_key IS NULL AND node_id_snapshot IS NULL
        AND node_title_snapshot IS NULL AND archived_at IS NULL)
    OR (conversation_type='direct' AND visibility='participants' AND node_id IS NULL
        AND proposal_id IS NULL AND direct_pair_key IS NOT NULL AND char_length(direct_pair_key)>0
        AND node_id_snapshot IS NULL AND node_title_snapshot IS NULL AND archived_at IS NULL)
);

ALTER TABLE governance_proposals DROP COLUMN webgemeindezentrum_id;
ALTER TABLE webgemeindezentren
    DROP CONSTRAINT webgemeindezentren_faden_endpoint_id_unique,
    DROP COLUMN faden_endpoint_id;
DROP FUNCTION IF EXISTS weltgewebe_webgemeindezentrum_faden_endpoint_id(TEXT);

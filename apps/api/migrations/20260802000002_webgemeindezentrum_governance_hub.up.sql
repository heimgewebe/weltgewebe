-- Bind governance, public conversation and typed Fäden to each Webgemeindezentrum.
CREATE OR REPLACE FUNCTION weltgewebe_webgemeindezentrum_faden_endpoint_id(center_identifier TEXT)
RETURNS UUID LANGUAGE SQL IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT (substr(digest,1,8)||'-'||substr(digest,9,4)||'-5'||substr(digest,14,3)||'-8'||substr(digest,18,3)||'-'||substr(digest,21,12))::uuid
    FROM (SELECT md5('weltgewebe:webgemeindezentrum-faden-endpoint:v1:'||center_identifier) AS digest) AS deterministic_hash;
$$;

ALTER TABLE webgemeindezentren ADD COLUMN faden_endpoint_id UUID;
UPDATE webgemeindezentren SET faden_endpoint_id = weltgewebe_webgemeindezentrum_faden_endpoint_id(id);
ALTER TABLE webgemeindezentren
    ALTER COLUMN faden_endpoint_id SET NOT NULL,
    ADD CONSTRAINT webgemeindezentren_faden_endpoint_id_unique UNIQUE (faden_endpoint_id);

ALTER TABLE governance_proposals
    ADD COLUMN webgemeindezentrum_id TEXT REFERENCES webgemeindezentren(id) ON DELETE RESTRICT;

DO $$
DECLARE active_center_count BIGINT; active_center_id TEXT;
BEGIN
    SELECT count(*), min(c.id) INTO active_center_count, active_center_id
    FROM ortswebereien o
    JOIN gewebezellen g ON g.id=o.gewebezelle_id
    JOIN webgemeindezentren c ON c.id=o.active_webgemeindezentrum_id AND c.ortsweberei_id=o.id
    WHERE o.lifecycle_state='active' AND g.lifecycle_state='active';
    IF EXISTS (SELECT 1 FROM governance_proposals WHERE webgemeindezentrum_id IS NULL) THEN
        IF active_center_count <> 1 THEN
            RAISE EXCEPTION 'legacy governance proposals require exactly one active Webgemeindezentrum for deterministic backfill, found %', active_center_count;
        END IF;
        UPDATE governance_proposals
        SET webgemeindezentrum_id=active_center_id
        WHERE webgemeindezentrum_id IS NULL;
    END IF;
END;
$$;
ALTER TABLE governance_proposals ALTER COLUMN webgemeindezentrum_id SET NOT NULL;

ALTER TABLE domain_conversations
    ADD COLUMN webgemeindezentrum_id TEXT REFERENCES webgemeindezentren(id) ON DELETE RESTRICT;
ALTER TABLE domain_conversations
    DROP CONSTRAINT domain_conversations_visibility_check,
    DROP CONSTRAINT domain_conversations_subject_kind;
ALTER TABLE domain_conversations ADD CONSTRAINT domain_conversations_visibility_check CHECK (
    (conversation_type IN ('node','governance_proposal','webgemeindezentrum') AND visibility='public')
    OR (conversation_type='direct' AND visibility='participants')
);

ALTER TABLE domain_conversations ADD CONSTRAINT domain_conversations_subject_kind CHECK (
    (
        conversation_type='node' AND visibility='public'
        AND proposal_id IS NULL AND webgemeindezentrum_id IS NULL AND direct_pair_key IS NULL
        AND (
            (node_id IS NOT NULL AND node_id_snapshot IS NULL AND node_title_snapshot IS NULL AND archived_at IS NULL)
            OR
            (node_id IS NULL AND node_id_snapshot IS NOT NULL AND node_title_snapshot IS NOT NULL AND archived_at IS NOT NULL)
        )
    ) OR (
        conversation_type='governance_proposal' AND visibility='public'
        AND node_id IS NULL AND proposal_id IS NOT NULL AND webgemeindezentrum_id IS NULL
        AND direct_pair_key IS NULL AND node_id_snapshot IS NULL AND node_title_snapshot IS NULL AND archived_at IS NULL
    ) OR (
        conversation_type='webgemeindezentrum' AND visibility='public'
        AND node_id IS NULL AND proposal_id IS NULL AND webgemeindezentrum_id IS NOT NULL
        AND direct_pair_key IS NULL AND node_id_snapshot IS NULL AND node_title_snapshot IS NULL AND archived_at IS NULL
    ) OR (
        conversation_type='direct' AND visibility='participants'
        AND node_id IS NULL AND proposal_id IS NULL AND webgemeindezentrum_id IS NULL
        AND direct_pair_key IS NOT NULL AND char_length(direct_pair_key)>0
        AND node_id_snapshot IS NULL AND node_title_snapshot IS NULL AND archived_at IS NULL
    )
);

CREATE UNIQUE INDEX domain_conversations_one_per_webgemeindezentrum
    ON domain_conversations(webgemeindezentrum_id)
    WHERE conversation_type='webgemeindezentrum';

CREATE OR REPLACE FUNCTION weltgewebe_webgemeindezentrum_conversation_id(center_identifier TEXT)
RETURNS UUID LANGUAGE SQL IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT (substr(digest,1,8)||'-'||substr(digest,9,4)||'-5'||substr(digest,14,3)||'-8'||substr(digest,18,3)||'-'||substr(digest,21,12))::uuid
    FROM (SELECT md5('weltgewebe:webgemeindezentrum-conversation:v1:'||center_identifier) AS digest) AS deterministic_hash;
$$;

INSERT INTO domain_conversations(
    id,webgemeindezentrum_id,conversation_type,visibility,created_at,updated_at
)
SELECT weltgewebe_webgemeindezentrum_conversation_id(id),id,'webgemeindezentrum','public',created_at,GREATEST(created_at,updated_at)
FROM webgemeindezentren
ON CONFLICT (webgemeindezentrum_id) WHERE conversation_type='webgemeindezentrum' DO NOTHING;

CREATE OR REPLACE FUNCTION weltgewebe_create_webgemeindezentrum_conversation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO domain_conversations(
        id,webgemeindezentrum_id,conversation_type,visibility,created_at,updated_at
    ) VALUES (
        weltgewebe_webgemeindezentrum_conversation_id(NEW.id),NEW.id,'webgemeindezentrum','public',
        COALESCE(NEW.created_at,NOW()),
        GREATEST(COALESCE(NEW.created_at,NOW()),COALESCE(NEW.updated_at,NEW.created_at,NOW()))
    );
    RETURN NEW;
END;
$$;
CREATE TRIGGER webgemeindezentren_create_conversation
AFTER INSERT ON webgemeindezentren FOR EACH ROW
EXECUTE FUNCTION weltgewebe_create_webgemeindezentrum_conversation();

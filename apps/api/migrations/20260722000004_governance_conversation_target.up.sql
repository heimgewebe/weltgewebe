-- T018 Release A: add the governance proposal conversation target without
-- changing the active governance read or write path.
--
-- The migration is deliberately additive. It creates deterministic canonical
-- conversations for existing and future proposals, but the cutover marker stays
-- on `legacy`; no message is copied and no request is routed to domain_messages.

ALTER TABLE domain_conversations
    ADD COLUMN proposal_id UUID
        REFERENCES governance_proposals (id) ON DELETE CASCADE;

ALTER TABLE domain_conversations
    ALTER COLUMN node_id DROP NOT NULL;

ALTER TABLE domain_conversations
    DROP CONSTRAINT domain_conversations_node_id_key;

ALTER TABLE domain_conversations
    DROP CONSTRAINT domain_conversations_conversation_type_check;

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

CREATE UNIQUE INDEX domain_conversations_one_per_node
    ON domain_conversations (node_id)
    WHERE conversation_type = 'node';

CREATE UNIQUE INDEX domain_conversations_one_per_governance_proposal
    ON domain_conversations (proposal_id);

CREATE OR REPLACE FUNCTION weltgewebe_governance_proposal_conversation_id(
    proposal_identifier UUID
)
RETURNS UUID
LANGUAGE SQL
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
    SELECT (
        substr(digest, 1, 8) || '-' ||
        substr(digest, 9, 4) || '-' ||
        '5' || substr(digest, 14, 3) || '-' ||
        '8' || substr(digest, 18, 3) || '-' ||
        substr(digest, 21, 12)
    )::uuid
    FROM (
        SELECT md5(
            'weltgewebe:governance-proposal-conversation:v1:' ||
            proposal_identifier::text
        ) AS digest
    ) AS deterministic_hash;
$$;

-- This singleton is the database-bound switch used by later Release-A runtime.
-- It begins on `legacy` and this migration never advances it.
CREATE TABLE domain_conversation_cutover_state (
    singleton         BOOLEAN     PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    governance_source TEXT        NOT NULL DEFAULT 'legacy'
                                  CHECK (governance_source IN ('legacy', 'canonical')),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO domain_conversation_cutover_state (singleton, governance_source)
VALUES (TRUE, 'legacy');

-- Existing proposals receive deterministic empty target conversations. The
-- old governance_messages table remains the sole message truth until Release B.
INSERT INTO domain_conversations (
    id,
    node_id,
    proposal_id,
    conversation_type,
    visibility,
    created_at,
    updated_at
)
SELECT
    weltgewebe_governance_proposal_conversation_id(id),
    NULL,
    id,
    'governance_proposal',
    'public',
    created_at,
    created_at
FROM governance_proposals
ON CONFLICT (proposal_id)
DO NOTHING;

CREATE OR REPLACE FUNCTION weltgewebe_create_governance_proposal_conversation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO domain_conversations (
        id,
        node_id,
        proposal_id,
        conversation_type,
        visibility,
        created_at,
        updated_at
    ) VALUES (
        weltgewebe_governance_proposal_conversation_id(NEW.id),
        NULL,
        NEW.id,
        'governance_proposal',
        'public',
        NEW.created_at,
        NEW.created_at
    )
    ON CONFLICT (proposal_id)
    DO NOTHING;

    RETURN NEW;
END;
$$;

CREATE TRIGGER governance_proposals_create_conversation
AFTER INSERT ON governance_proposals
FOR EACH ROW EXECUTE FUNCTION weltgewebe_create_governance_proposal_conversation();

-- A proposal may be removed while its generated target conversation is still
-- empty. Once contributions exist, deletion must not cascade through the
-- conversation and erase public history. The row lock serializes this decision
-- against concurrent message inserts through the conversation foreign key.
CREATE OR REPLACE FUNCTION weltgewebe_protect_governance_conversation_history()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    conversation_identifier UUID;
BEGIN
    SELECT id INTO conversation_identifier
    FROM domain_conversations
    WHERE proposal_id = OLD.id
    FOR UPDATE;

    IF conversation_identifier IS NOT NULL AND EXISTS (
        SELECT 1 FROM domain_messages
        WHERE conversation_id = conversation_identifier
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23503',
            CONSTRAINT = 'governance_proposals_conversation_history_guard',
            MESSAGE = 'proposal deletion blocked by existing conversation messages';
    END IF;

    RETURN OLD;
END;
$$;

CREATE TRIGGER governance_proposals_protect_conversation_history
BEFORE DELETE ON governance_proposals
FOR EACH ROW EXECUTE FUNCTION weltgewebe_protect_governance_conversation_history();

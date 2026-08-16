-- Governance revision contract:
-- - open proposals may be withdrawn without deleting their procedural history;
-- - an accepted Sachantrag is repealed only by a later Sachantrag that passes
--   through the same consent/veto/voting engine.
--
-- The original accepted decision is never rewritten. Its later repeal is
-- derived from the accepted self-reference below, preserving both decisions.

ALTER TABLE governance_proposals
    DROP CONSTRAINT governance_proposals_status_check,
    DROP CONSTRAINT governance_proposals_phase_consistent,
    DROP CONSTRAINT governance_proposals_applicant_lifecycle;

ALTER TABLE governance_proposals
    ADD COLUMN repeals_proposal_id UUID
        REFERENCES governance_proposals(id) ON DELETE RESTRICT,
    ADD CONSTRAINT governance_proposals_status_check
        CHECK (status IN ('consent', 'voting', 'accepted', 'rejected', 'withdrawn')),
    ADD CONSTRAINT governance_proposals_phase_consistent CHECK (
        (status = 'consent' AND voting_until IS NULL AND finalized_at IS NULL)
        OR (status = 'voting' AND voting_until IS NOT NULL AND finalized_at IS NULL)
        OR (status IN ('accepted', 'rejected', 'withdrawn') AND finalized_at IS NOT NULL)
    ),
    ADD CONSTRAINT governance_proposals_applicant_lifecycle CHECK (
        applicant_account_id IS NOT NULL
        OR (status IN ('accepted', 'rejected', 'withdrawn') AND finalized_at IS NOT NULL)
    ),
    ADD CONSTRAINT governance_proposals_repeal_shape CHECK (
        repeals_proposal_id IS NULL
        OR (kind = 'sachantrag' AND repeals_proposal_id <> id)
    );

-- A rejected or withdrawn repeal attempt does not block a later attempt. While
-- a repeal is open or already accepted, however, a second parallel/effective
-- repeal of the same decision is forbidden at the database boundary.
CREATE UNIQUE INDEX governance_proposals_one_active_repeal
    ON governance_proposals (repeals_proposal_id)
    WHERE repeals_proposal_id IS NOT NULL
      AND status IN ('consent', 'voting', 'accepted');

-- The foreign-key lookup must also cover rejected and withdrawn historical
-- repeal attempts. PostgreSQL does not create this child-side index for us.
CREATE INDEX governance_proposals_repeals_lookup
    ON governance_proposals (repeals_proposal_id)
    WHERE repeals_proposal_id IS NOT NULL;

-- Account deletion must preserve an explicitly withdrawn proposal even when it
-- has no veto, vote or message yet. The withdrawal itself is durable procedural
-- history; only the live applicant binding may be detached.
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
          proposal.status IN ('accepted', 'rejected', 'withdrawn')
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

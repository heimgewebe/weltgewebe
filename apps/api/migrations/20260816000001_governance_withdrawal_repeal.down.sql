-- Fail closed: a rollback must never erase withdrawal/repeal semantics that
-- already carry real procedural history.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM governance_proposals
        WHERE status = 'withdrawn' OR repeals_proposal_id IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'cannot roll back governance withdrawal/repeal while such proposal history exists';
    END IF;
END;
$$;

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

DROP INDEX governance_proposals_one_active_repeal;

ALTER TABLE governance_proposals
    DROP CONSTRAINT governance_proposals_repeal_shape,
    DROP CONSTRAINT governance_proposals_status_check,
    DROP CONSTRAINT governance_proposals_phase_consistent,
    DROP CONSTRAINT governance_proposals_applicant_lifecycle,
    DROP COLUMN repeals_proposal_id;

ALTER TABLE governance_proposals
    ADD CONSTRAINT governance_proposals_status_check
        CHECK (status IN ('consent', 'voting', 'accepted', 'rejected')),
    ADD CONSTRAINT governance_proposals_phase_consistent CHECK (
        (status = 'consent' AND voting_until IS NULL AND finalized_at IS NULL)
        OR (status = 'voting' AND voting_until IS NOT NULL AND finalized_at IS NULL)
        OR (status IN ('accepted', 'rejected') AND finalized_at IS NOT NULL)
    ),
    ADD CONSTRAINT governance_proposals_applicant_lifecycle CHECK (
        applicant_account_id IS NOT NULL
        OR (status IN ('accepted', 'rejected') AND finalized_at IS NOT NULL)
    );

-- Rollback is deliberately fail-closed: once an account exit has anonymized
-- a veto or vote, the old composite primary keys cannot be restored without
-- inventing an actor.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM governance_vetoes WHERE weber_account_id IS NULL)
       OR EXISTS (SELECT 1 FROM governance_votes WHERE voter_account_id IS NULL) THEN
        RAISE EXCEPTION
            'cannot restore governance veto/vote actor NOT NULL constraints after anonymization';
    END IF;
END
$$;

ALTER TABLE governance_vetoes
    DROP CONSTRAINT governance_vetoes_proposal_actor_key;
ALTER TABLE governance_vetoes
    DROP CONSTRAINT governance_vetoes_pkey;
ALTER TABLE governance_vetoes
    DROP COLUMN id;
ALTER TABLE governance_vetoes
    ALTER COLUMN weber_account_id SET NOT NULL;
ALTER TABLE governance_vetoes
    ADD CONSTRAINT governance_vetoes_pkey
    PRIMARY KEY (proposal_id, weber_account_id);

ALTER TABLE governance_votes
    DROP CONSTRAINT governance_votes_proposal_actor_key;
ALTER TABLE governance_votes
    DROP CONSTRAINT governance_votes_pkey;
ALTER TABLE governance_votes
    DROP COLUMN id;
ALTER TABLE governance_votes
    ALTER COLUMN voter_account_id SET NOT NULL;
ALTER TABLE governance_votes
    ADD CONSTRAINT governance_votes_pkey
    PRIMARY KEY (proposal_id, voter_account_id);

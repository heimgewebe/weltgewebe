-- Guests may veto and vote on other Weber applications. Preserve those
-- procedural contributions after account deletion while removing the live
-- account binding. Surrogate row ids allow the actor columns to become nullable
-- without losing the one-live-contribution-per-account invariant.
ALTER TABLE governance_vetoes
    DROP CONSTRAINT governance_vetoes_pkey;
ALTER TABLE governance_vetoes
    ADD COLUMN id BIGSERIAL PRIMARY KEY;
ALTER TABLE governance_vetoes
    ALTER COLUMN weber_account_id DROP NOT NULL;
ALTER TABLE governance_vetoes
    ADD CONSTRAINT governance_vetoes_proposal_actor_key
    UNIQUE (proposal_id, weber_account_id);

ALTER TABLE governance_votes
    DROP CONSTRAINT governance_votes_pkey;
ALTER TABLE governance_votes
    ADD COLUMN id BIGSERIAL PRIMARY KEY;
ALTER TABLE governance_votes
    ALTER COLUMN voter_account_id DROP NOT NULL;
ALTER TABLE governance_votes
    ADD CONSTRAINT governance_votes_proposal_actor_key
    UNIQUE (proposal_id, voter_account_id);

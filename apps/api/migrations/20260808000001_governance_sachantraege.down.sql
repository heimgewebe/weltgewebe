-- A rollback must never erase existing decisions or procedure history merely
-- because the previous schema cannot represent Sachantraege.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM governance_proposals WHERE kind = 'sachantrag') THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'cannot roll back Sachantraege migration while Sachantraege exist';
    END IF;
END;
$$;

DROP INDEX governance_proposals_target_node;
DROP INDEX governance_proposals_center_kind_status;
DROP INDEX governance_proposals_one_open_per_applicant;

ALTER TABLE governance_proposals
    DROP CONSTRAINT governance_proposals_kind_fields_check,
    DROP CONSTRAINT governance_proposals_kind_check,
    DROP COLUMN target_node_title,
    DROP COLUMN target_node_id,
    DROP COLUMN title;

ALTER TABLE governance_proposals
    ADD CONSTRAINT governance_proposals_kind_check CHECK (kind = 'weberantrag');

CREATE UNIQUE INDEX governance_proposals_one_open_per_applicant
    ON governance_proposals (applicant_account_id, kind)
    WHERE status IN ('consent', 'voting');

-- Extend the existing governance engine with center- and node-addressable
-- Sachantraege. Accepted Sachantraege are decisions; they do not execute
-- arbitrary node mutations.

ALTER TABLE governance_proposals
    DROP CONSTRAINT governance_proposals_kind_check;

ALTER TABLE governance_proposals
    ADD COLUMN title TEXT,
    ADD COLUMN target_node_id TEXT REFERENCES domain_nodes(id) ON DELETE SET NULL,
    ADD COLUMN target_node_title TEXT,
    ADD CONSTRAINT governance_proposals_kind_check
        CHECK (kind IN ('weberantrag', 'sachantrag')),
    ADD CONSTRAINT governance_proposals_kind_fields_check CHECK (
        (
            kind = 'weberantrag'
            AND title IS NULL
            AND target_node_id IS NULL
            AND target_node_title IS NULL
        ) OR (
            kind = 'sachantrag'
            AND title IS NOT NULL
            AND char_length(btrim(title)) BETWEEN 1 AND 200
            AND (
                target_node_title IS NULL
                OR char_length(btrim(target_node_title)) BETWEEN 1 AND 200
            )
            AND (target_node_id IS NULL OR target_node_title IS NOT NULL)
        )
    );

-- Only Weber applications are limited to one open procedure per applicant.
-- Weber and administrators may deliberately have multiple open Sachantraege.
DROP INDEX governance_proposals_one_open_per_applicant;
CREATE UNIQUE INDEX governance_proposals_one_open_per_applicant
    ON governance_proposals (applicant_account_id)
    WHERE kind = 'weberantrag' AND status IN ('consent', 'voting');

CREATE INDEX governance_proposals_center_kind_status
    ON governance_proposals (webgemeindezentrum_id, kind, status, created_at DESC);
CREATE INDEX governance_proposals_target_node
    ON governance_proposals (target_node_id, created_at DESC)
    WHERE target_node_id IS NOT NULL;

-- Rollback des Governance-Antragssystems.
DROP TABLE IF EXISTS governance_messages;
DROP TABLE IF EXISTS governance_votes;
DROP TABLE IF EXISTS governance_vetoes;
DROP TABLE IF EXISTS governance_proposals;

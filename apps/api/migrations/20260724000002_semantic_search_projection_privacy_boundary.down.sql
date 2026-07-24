-- WELTGEWEBE-SEMANTIC-SEARCH-V1-T012
-- Migration 20260724000002 (semantic_search_projection_privacy_boundary) is intentionally
-- not automatically reversible online. Private lexical-only projections cannot be safely
-- demoted back to legacy vector-mandatory contract without re-embedding.
-- Recovery procedure: Stop workers, deploy target binary/schema, rebuild target search index generation.
-- Preferred recovery path: Roll-forward.

DO $$
BEGIN
    RAISE EXCEPTION 'Migration 20260724000002 (semantic_search_projection_privacy_boundary) is intentionally not automatically reversible online. Private lexical-only projections cannot be demoted back to legacy vector-mandatory contract without re-embedding. Recovery procedure: Stop workers, deploy target binary/schema, rebuild target search index generation. Preferred recovery path: Roll-forward.';
END $$;

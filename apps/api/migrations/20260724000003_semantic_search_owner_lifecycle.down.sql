-- WELTGEWEBE-SEMANTIC-SEARCH-V1-T012
-- Migration 20260724000003 (semantic_search_owner_lifecycle) is intentionally
-- not automatically reversible online. Downgrading would restore recoverable
-- private plaintext and stored lexical vectors for missing or disabled owners
-- and remove account-lifecycle revisioning. Recovery procedure: stop search
-- workers, deploy a corrected roll-forward migration, rebuild the affected
-- generation, then reactivate it through the canonical database gate.
-- The refusal is the first statement, so a rejected downgrade mutates nothing.

DO $$
BEGIN
    RAISE EXCEPTION 'Migration 20260724000003 (semantic_search_owner_lifecycle) is intentionally not automatically reversible online. Downgrading would reopen the private-owner boundary. Recovery procedure: stop search workers, deploy a corrected roll-forward migration, rebuild the affected generation, then reactivate it through the canonical database gate.';
END $$;

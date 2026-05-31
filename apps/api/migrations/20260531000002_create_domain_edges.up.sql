-- Phase B: OPT-ARC-001 Domain Data PostgreSQL Foundation — edges schema.
--
-- Schema-only migration. No runtime cutover in this PR.
-- JSONL remains the active data source until Phase D/E.
--
-- FK decision: deferred. An orphan/reference audit is required before adding
-- foreign keys on source_id and target_id. The blueprint explicitly requires
-- this audit to determine whether strict FKs or a loose reference model with
-- an integrity guard is appropriate. Backfill must never silently discard
-- orphaned edges.
--
-- JSONB discipline:
--   payload preserves: source_type, target_type, note, and any other edge
--   fields present in JSONL records not promoted to explicit columns.
--   These fields are deferred because:
--   - source_type, target_type: optional participant type hints; no current
--     filter/index use case established.
--   - note: optional free text; not queried.
--   Later promotion or normalisation decisions remain open.

-- Note: updated_at is intentionally omitted. The Edge struct
-- (apps/api/src/routes/edges.rs) and domain contract
-- (contracts/domain/edge.schema.json) do not define updated_at.
-- If edge-mutation semantics are introduced later, a separate migration
-- must add updated_at at that point.
CREATE TABLE domain_edges (
    id         TEXT        PRIMARY KEY,
    source_id  TEXT        NOT NULL,
    target_id  TEXT        NOT NULL,
    edge_kind  TEXT        NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ,
    payload    JSONB       NOT NULL DEFAULT '{}'
);

-- Individual indexes on source_id and target_id for neighbour lookups.
CREATE INDEX domain_edges_source_id ON domain_edges (source_id);
CREATE INDEX domain_edges_target_id ON domain_edges (target_id);

-- Composite index for bidirectional edge queries (source + target together).
CREATE INDEX domain_edges_source_target ON domain_edges (source_id, target_id);

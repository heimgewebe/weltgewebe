-- Phase B: OPT-ARC-001 Domain Data PostgreSQL Foundation — nodes schema.
--
-- Schema-only migration. No runtime cutover in this PR.
-- JSONL remains the active data source until Phase D/E.
--
-- JSONB discipline:
--   payload preserves: summary, info, tags, and any other node fields present
--   in JSONL records that are not promoted to explicit columns here.
--   These fields are deferred because:
--   - summary and info: optional text; no current API filter or index use case.
--   - tags: array of strings; normalisation deferred until filter/query
--     patterns are established.
--   Later migration or normalisation decisions remain open for all three.

CREATE TABLE domain_nodes (
    id         TEXT             PRIMARY KEY,
    kind       TEXT             NOT NULL DEFAULT 'Unknown',
    title      TEXT             NOT NULL DEFAULT 'Untitled',
    lat        DOUBLE PRECISION,
    lon        DOUBLE PRECISION,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    payload    JSONB            NOT NULL DEFAULT '{}'
);

-- Index on kind for kind-filtered list queries.
CREATE INDEX domain_nodes_kind ON domain_nodes (kind);

-- Composite lat/lon index for geographic proximity queries.
-- Note: this is a plain btree index on (lat, lon).
-- PostGIS GIST/spatial index deferred to a later migration when PostGIS
-- extension and bbox/geometry representation are decided.
CREATE INDEX domain_nodes_lat_lon ON domain_nodes (lat, lon);

-- Cursor-order index: ensures stable ascending id ordering for cursor pagination.
-- The primary key index covers id lookups; this explicit index is documented
-- to make the cursor-order dependency visible for later query planners.
-- (PostgreSQL will use the PK index; kept as comment for clarity.)

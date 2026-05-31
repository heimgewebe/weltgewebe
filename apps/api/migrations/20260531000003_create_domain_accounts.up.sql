-- Phase B: OPT-ARC-001 Domain Data PostgreSQL Foundation — accounts schema.
--
-- Schema-only migration. No runtime cutover in this PR.
-- JSONL remains the active data source until Phase D/E.
--
-- Security note: accounts are auth-adjacent data. Public and private fields
-- are separated by column group and JSONB column to prevent accidental leakage
-- of private data through public API projections.
--
-- public_pos is NOT stored as a column. It is computed at read time via a
-- deterministic jitter of (location_lat, location_lon, radius_m, id). This
-- matches the current JSONL-backed runtime behaviour in calculate_jittered_pos.
-- A later migration may add a stored generated column if read performance
-- warrants it; that decision is deferred.
--
-- JSONB discipline:
--   public_payload preserves: summary, tags, and any other public fields from
--   JSONL records not promoted to explicit columns. Deferred because:
--   - summary: optional text; no current API filter.
--   - tags: array; normalisation deferred until query patterns are established.
--   private_payload preserves: any remaining private/operational JSONL fields
--   not covered by explicit columns. Deferred until the full account write-path
--   cutover (Phase E) clarifies which fields need individual column treatment.
--   Later migration or normalisation decisions remain open for both columns.

CREATE TABLE domain_accounts (
    id               TEXT             PRIMARY KEY,
    -- Public projection fields (safe to expose via API)
    kind             TEXT             NOT NULL DEFAULT 'ron',
    title            TEXT             NOT NULL DEFAULT 'Untitled',
    mode             TEXT             NOT NULL DEFAULT 'ron',
    radius_m         BIGINT           NOT NULL DEFAULT 0
                                      CHECK (radius_m >= 0 AND radius_m <= 4294967295),
    disabled         BOOLEAN          NOT NULL DEFAULT FALSE,
    -- Private location: real residence, never exposed directly.
    -- public_pos is derived at runtime from (location_lat, location_lon,
    -- radius_m, id) using a deterministic jitter; it is not stored here.
    location_lat     DOUBLE PRECISION,
    location_lon     DOUBLE PRECISION,
    -- Auth-sensitive operational fields
    role             TEXT             NOT NULL DEFAULT 'gast',
    email            TEXT,
    webauthn_user_id UUID,
    -- Timestamps
    created_at       TIMESTAMPTZ,
    updated_at       TIMESTAMPTZ,
    -- JSONB payloads (see JSONB discipline above)
    public_payload   JSONB            NOT NULL DEFAULT '{}',
    private_payload  JSONB            NOT NULL DEFAULT '{}'
);

-- Case-insensitive lookup index on email for login/lookup.
-- Non-unique by design in Phase B to avoid rejecting currently tolerated
-- duplicate emails before Phase C duplicate-audit/quarantine decisions.
CREATE INDEX domain_accounts_email_lookup
    ON domain_accounts (lower(email))
    WHERE email IS NOT NULL;

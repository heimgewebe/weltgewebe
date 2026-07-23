-- WELTGEWEBE-SEMANTIC-SEARCH-V1-T005
-- PostgreSQL remains canonical.  These tables are a fully regenerable, internal
-- search projection and work ledger; this migration adds neither an HTTP search
-- route nor an embedding provider.

CREATE TABLE search_index_generations (
    generation_id TEXT PRIMARY KEY CHECK (btrim(generation_id) <> ''),
    provider TEXT NOT NULL CHECK (btrim(provider) <> ''),
    model_id TEXT NOT NULL CHECK (btrim(model_id) <> ''),
    model_revision TEXT NOT NULL CHECK (btrim(model_revision) <> ''),
    runtime_identity TEXT NOT NULL CHECK (btrim(runtime_identity) <> ''),
    dimension INTEGER NOT NULL CHECK (dimension > 0 AND dimension <= 8192),
    document_revision TEXT NOT NULL CHECK (btrim(document_revision) <> ''),
    normalization_revision TEXT NOT NULL CHECK (btrim(normalization_revision) <> ''),
    ranking_revision TEXT NOT NULL CHECK (btrim(ranking_revision) <> ''),
    state TEXT NOT NULL DEFAULT 'building' CHECK (state IN ('building', 'ready', 'active', 'retired', 'failed')),
    expected_nodes BIGINT NOT NULL DEFAULT 0 CHECK (expected_nodes >= 0),
    completed_nodes BIGINT NOT NULL DEFAULT 0 CHECK (completed_nodes >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    activated_at TIMESTAMPTZ,
    CHECK ((state = 'active') = (activated_at IS NOT NULL))
);
CREATE UNIQUE INDEX search_index_generations_one_active ON search_index_generations ((state)) WHERE state = 'active';
CREATE UNIQUE INDEX search_index_generations_one_ready ON search_index_generations ((state)) WHERE state = 'ready';

CREATE TABLE search_node_versions (
    node_id TEXT PRIMARY KEY,
    source_version BIGINT NOT NULL CHECK (source_version >= 1),
    source_revision TEXT NOT NULL CHECK (btrim(source_revision) <> ''),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE search_node_projections (
    generation_id TEXT NOT NULL REFERENCES search_index_generations(generation_id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,
    source_version BIGINT NOT NULL CHECK (source_version >= 1),
    source_revision TEXT NOT NULL CHECK (btrim(source_revision) <> ''),
    content_sha256 TEXT NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    title TEXT NOT NULL CHECK (btrim(title) <> ''),
    tags TEXT[] NOT NULL DEFAULT '{}',
    searchable_text TEXT NOT NULL CHECK (btrim(searchable_text) <> ''),
    language TEXT NOT NULL CHECK (btrim(language) <> ''),
    kind TEXT NOT NULL CHECK (btrim(kind) <> ''),
    status TEXT NOT NULL CHECK (status IN ('active', 'hidden')),
    visibility_scopes TEXT[] NOT NULL DEFAULT '{}',
    semantic_state TEXT NOT NULL CHECK (semantic_state IN ('pending', 'ready', 'unavailable')),
    embedding DOUBLE PRECISION[],
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (generation_id, node_id)
);
CREATE INDEX search_node_projections_eligible ON search_node_projections (generation_id, status, node_id);

CREATE TABLE search_projection_jobs (
    id BIGSERIAL PRIMARY KEY,
    generation_id TEXT NOT NULL REFERENCES search_index_generations(generation_id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,
    source_version BIGINT NOT NULL CHECK (source_version >= 1),
    source_revision TEXT NOT NULL CHECK (btrim(source_revision) <> ''),
    operation TEXT NOT NULL CHECK (operation IN ('upsert', 'delete')),
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'claimed', 'retry', 'done', 'stale', 'failed')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    available_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    claimed_by TEXT,
    claim_until TIMESTAMPTZ,
    last_error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    completed_at TIMESTAMPTZ,
    UNIQUE (generation_id, node_id, source_version, operation),
    CHECK ((state = 'claimed') = (claimed_by IS NOT NULL AND claim_until IS NOT NULL))
);
CREATE INDEX search_projection_jobs_claimable ON search_projection_jobs (available_at, id)
    WHERE state IN ('pending', 'retry', 'claimed');
CREATE INDEX search_projection_jobs_generation_state ON search_projection_jobs (generation_id, state);

CREATE OR REPLACE FUNCTION weltgewebe_search_enqueue_node(p_node_id TEXT, p_operation TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE current_version BIGINT; current_revision TEXT;
BEGIN
    SELECT source_version, source_revision INTO current_version, current_revision
      FROM search_node_versions WHERE node_id = p_node_id;
    IF current_version IS NULL THEN RETURN; END IF;
    INSERT INTO search_projection_jobs (generation_id, node_id, source_version, source_revision, operation)
    SELECT generation_id, p_node_id, current_version, current_revision, p_operation
      FROM search_index_generations WHERE state IN ('building', 'ready', 'active')
    ON CONFLICT DO NOTHING;
END; $$;

CREATE OR REPLACE FUNCTION weltgewebe_search_track_domain_node()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE next_version BIGINT; revision TEXT; node_identifier TEXT;
BEGIN
    -- Location, address and arbitrary JSON payload keys are not part of the
    -- fail-closed search document.  They must not create projection or
    -- embedding work.  Deletion and every field consumed by SearchDocument
    -- remain revisioned.
    IF TG_OP = 'UPDATE'
       AND OLD.kind IS NOT DISTINCT FROM NEW.kind
       AND OLD.title IS NOT DISTINCT FROM NEW.title
       AND (OLD.payload -> 'summary') IS NOT DISTINCT FROM (NEW.payload -> 'summary')
       AND (OLD.payload -> 'info') IS NOT DISTINCT FROM (NEW.payload -> 'info')
       AND (OLD.payload -> 'tags') IS NOT DISTINCT FROM (NEW.payload -> 'tags')
       AND (OLD.payload -> 'language') IS NOT DISTINCT FROM (NEW.payload -> 'language')
       AND (OLD.payload -> 'search_visibility') IS NOT DISTINCT FROM (NEW.payload -> 'search_visibility')
    THEN
        RETURN NEW;
    END IF;
    -- Domain mutations take a shared transaction lock. Generation creation
    -- and activation take the matching exclusive lock, so a mutation either
    -- commits before their snapshot/gate or is ordered strictly after it.
    PERFORM pg_advisory_xact_lock_shared(hashtextextended('weltgewebe.search.generation.activation', 0));
    node_identifier := CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END;
    INSERT INTO search_node_versions (node_id, source_version, source_revision, deleted_at)
    VALUES (node_identifier, 1, 'node-1', CASE WHEN TG_OP = 'DELETE' THEN clock_timestamp() ELSE NULL END)
    ON CONFLICT (node_id) DO UPDATE SET
      source_version = search_node_versions.source_version + 1,
      source_revision = 'node-' || (search_node_versions.source_version + 1)::TEXT,
      deleted_at = EXCLUDED.deleted_at
    RETURNING source_version, source_revision INTO next_version, revision;
    PERFORM weltgewebe_search_enqueue_node(node_identifier, CASE WHEN TG_OP = 'DELETE' THEN 'delete' ELSE 'upsert' END);
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END; $$;
CREATE TRIGGER search_track_domain_nodes AFTER INSERT OR UPDATE OR DELETE ON domain_nodes
FOR EACH ROW EXECUTE FUNCTION weltgewebe_search_track_domain_node();

-- Canonical, read-only activation gate shared by worker reconciliation,
-- operational status, and the actual activation function. Keep all readiness
-- semantics here so those three surfaces cannot drift independently.
CREATE OR REPLACE FUNCTION weltgewebe_search_generation_activation_ready(p_generation_id TEXT)
RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
SELECT COALESCE((
    SELECT g.state IN ('building', 'ready', 'active')
       AND g.completed_nodes = g.expected_nodes
       AND NOT EXISTS (
           SELECT 1 FROM search_node_versions v
           WHERE v.deleted_at IS NULL
             AND NOT EXISTS (
                 SELECT 1 FROM search_node_projections p
                 WHERE p.generation_id = g.generation_id
                   AND p.node_id = v.node_id
                   AND p.source_version = v.source_version
                   AND p.source_revision = v.source_revision
                   AND p.semantic_state = 'ready'
                   AND cardinality(p.embedding) = g.dimension
             )
       )
       AND NOT EXISTS (
           SELECT 1 FROM search_projection_jobs j
           WHERE j.generation_id = g.generation_id
             AND j.state NOT IN ('done', 'stale')
       )
       AND NOT EXISTS (
           SELECT 1
           FROM search_node_versions v
           JOIN search_node_projections p
             ON p.generation_id = g.generation_id
            AND p.node_id = v.node_id
           WHERE v.deleted_at IS NOT NULL
       )
    FROM search_index_generations g
    WHERE g.generation_id = p_generation_id
), FALSE);
$$;

-- Atomically switches only a fully completed generation.  The old active
-- generation is retained for an explicit operator rollback via the same gate.
CREATE OR REPLACE FUNCTION weltgewebe_activate_search_generation(p_generation_id TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE target search_index_generations%ROWTYPE;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('weltgewebe.search.generation.activation', 0));
    SELECT * INTO target FROM search_index_generations WHERE generation_id = p_generation_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'unknown search generation' USING ERRCODE = '23503'; END IF;
    IF NOT weltgewebe_search_generation_activation_ready(p_generation_id) THEN
      RAISE EXCEPTION 'generation is not complete and ready' USING ERRCODE = '23514';
    END IF;
    IF target.state = 'active' THEN RETURN; END IF;
    -- A complete building generation may activate directly.  This permits a
    -- new rebuild while the current active+ready pair remains rollback-safe.
    -- The advisory lock makes the retirement/swap atomic to every caller.
    UPDATE search_index_generations SET state = 'building' WHERE generation_id = p_generation_id;
    UPDATE search_index_generations SET state = 'retired', activated_at = NULL
      WHERE state = 'ready';
    UPDATE search_index_generations SET state = 'ready', activated_at = NULL WHERE state = 'active';
    UPDATE search_index_generations SET state = 'active', activated_at = clock_timestamp() WHERE generation_id = p_generation_id;
END; $$;

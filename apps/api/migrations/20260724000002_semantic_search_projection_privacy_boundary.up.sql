-- WELTGEWEBE-SEMANTIC-SEARCH-V1-T012
-- Search visibility is canonical domain state, not a projection-owned payload
-- convention. Existing ordinary nodes become public; malformed explicit legacy
-- values fail closed as hidden. Private text stays lexical-only in PostgreSQL.

ALTER TABLE domain_nodes
    ADD COLUMN search_visibility TEXT NOT NULL DEFAULT 'public';

-- The historical trigger treats payload.search_visibility as indexed content.
-- Disable only that user trigger while moving the field so the migration cannot
-- version every node or enqueue work under a legacy generation identity.
ALTER TABLE domain_nodes DISABLE TRIGGER search_track_domain_nodes;

UPDATE domain_nodes
SET search_visibility = CASE
    WHEN NOT (payload ? 'search_visibility') THEN 'public'
    WHEN jsonb_typeof(payload -> 'search_visibility') = 'string'
         AND payload ->> 'search_visibility' IN ('public', 'private', 'hidden', 'revoked')
      THEN payload ->> 'search_visibility'
    ELSE 'hidden'
END,
payload = payload - 'search_visibility';

-- Resolve ownership once and reuse the same active-account rule at every search
-- boundary. Surrounding whitespace is malformed rather than silently normalized,
-- because request authorization compares the canonical account id byte-for-byte.
CREATE OR REPLACE FUNCTION weltgewebe_search_owner_account_id(p_payload JSONB)
RETURNS TEXT LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
SELECT CASE
    WHEN jsonb_typeof(p_payload -> 'created_by_account_id') = 'string'
     AND p_payload ->> 'created_by_account_id' = btrim(p_payload ->> 'created_by_account_id')
     AND btrim(p_payload ->> 'created_by_account_id') <> ''
      THEN p_payload ->> 'created_by_account_id'
    ELSE NULL
END;
$$;

CREATE OR REPLACE FUNCTION weltgewebe_search_owner_is_active(p_payload JSONB)
RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
SELECT EXISTS (
    SELECT 1
    FROM domain_accounts a
    WHERE a.id = weltgewebe_search_owner_account_id(p_payload)
      AND a.disabled = FALSE
);
$$;

-- Legacy document generations are immutable after this cutover. Future domain
-- mutations enqueue only generations using the canonical-visibility document
-- contract; a different generation requires its own identity-bound worker.
CREATE OR REPLACE FUNCTION weltgewebe_search_enqueue_node(p_node_id TEXT, p_operation TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE current_version BIGINT; current_revision TEXT;
BEGIN
    SELECT source_version, source_revision INTO current_version, current_revision
      FROM search_node_versions WHERE node_id = p_node_id;
    IF current_version IS NULL THEN RETURN; END IF;
    INSERT INTO search_projection_jobs (generation_id, node_id, source_version, source_revision, operation)
    SELECT generation_id, p_node_id, current_version, current_revision, p_operation
      FROM search_index_generations
     WHERE state IN ('building', 'ready', 'active')
       AND document_revision = 'node-document-v4-canonical-visibility'
    ON CONFLICT DO NOTHING;
END; $$;

CREATE OR REPLACE FUNCTION weltgewebe_search_track_domain_node()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE next_version BIGINT; revision TEXT; node_identifier TEXT;
BEGIN
    IF TG_OP = 'UPDATE'
       AND OLD.kind IS NOT DISTINCT FROM NEW.kind
       AND OLD.title IS NOT DISTINCT FROM NEW.title
       AND (OLD.payload -> 'summary') IS NOT DISTINCT FROM (NEW.payload -> 'summary')
       AND (OLD.payload -> 'info') IS NOT DISTINCT FROM (NEW.payload -> 'info')
       AND (OLD.payload -> 'tags') IS NOT DISTINCT FROM (NEW.payload -> 'tags')
       AND (OLD.payload -> 'language') IS NOT DISTINCT FROM (NEW.payload -> 'language')
       AND (OLD.payload -> 'created_by_account_id') IS NOT DISTINCT FROM (NEW.payload -> 'created_by_account_id')
       AND OLD.search_visibility IS NOT DISTINCT FROM NEW.search_visibility
    THEN
        RETURN NEW;
    END IF;
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

ALTER TABLE domain_nodes ENABLE TRIGGER search_track_domain_nodes;

ALTER TABLE domain_nodes
    ADD CONSTRAINT domain_nodes_search_visibility_valid
    CHECK (search_visibility IN ('public', 'private', 'hidden', 'revoked'));

-- The database is the final worker write fence. A private projection may retain
-- plaintext only while its canonical owner account exists and is enabled. The
-- trigger also makes hidden/revoked/orphan writes content-free even if a caller
-- supplies a weaker row shape.
CREATE OR REPLACE FUNCTION weltgewebe_search_enforce_projection_owner()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    canonical_payload JSONB;
    canonical_visibility TEXT;
    must_redact BOOLEAN;
BEGIN
    SELECT n.payload, n.search_visibility
      INTO canonical_payload, canonical_visibility
      FROM domain_nodes n
     WHERE n.id = NEW.node_id;

    must_redact := NOT FOUND;
    IF NOT must_redact THEN
        must_redact := canonical_visibility IN ('hidden', 'revoked')
            OR (canonical_visibility = 'private'
                AND NOT weltgewebe_search_owner_is_active(canonical_payload));
    END IF;

    IF must_redact THEN
        NEW.content_sha256 := 'a0014e8fdbf41fbdb6be203681519f957f0fc5283c50cc48d57978c68de09b32';
        NEW.title := '[nicht öffentlich]';
        NEW.tags := '{}'::TEXT[];
        NEW.searchable_text := '[nicht öffentlich]';
        NEW.language := 'und';
        NEW.kind := '[nicht öffentlich]';
        NEW.status := 'hidden';
        NEW.visibility_scopes := '{}'::TEXT[];
        NEW.semantic_state := 'unavailable';
        NEW.embedding := NULL;
    ELSIF canonical_visibility = 'private' THEN
        NEW.status := 'active';
        NEW.visibility_scopes := ARRAY['owner']::TEXT[];
        NEW.semantic_state := 'unavailable';
        NEW.embedding := NULL;
    END IF;

    RETURN NEW;
END; $$;

CREATE TRIGGER search_enforce_projection_owner
BEFORE INSERT OR UPDATE ON search_node_projections
FOR EACH ROW EXECUTE FUNCTION weltgewebe_search_enforce_projection_owner();

-- Account activation is part of private-search authorization. Insert, disable,
-- re-enable and delete events therefore version every affected private node.
-- Inactivation also redacts all retained generations synchronously; the queued
-- current-version job then reconciles counters and the serving generation.
CREATE OR REPLACE FUNCTION weltgewebe_search_track_domain_account_owner()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    account_identifier TEXT;
    account_inactive BOOLEAN;
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.disabled IS NOT DISTINCT FROM NEW.disabled THEN
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        account_identifier := OLD.id;
        account_inactive := TRUE;
    ELSE
        account_identifier := NEW.id;
        account_inactive := NEW.disabled;
    END IF;

    PERFORM pg_advisory_xact_lock_shared(hashtextextended('weltgewebe.search.generation.activation', 0));

    IF account_inactive THEN
        UPDATE search_node_projections p
           SET content_sha256 = 'a0014e8fdbf41fbdb6be203681519f957f0fc5283c50cc48d57978c68de09b32',
               title = '[nicht öffentlich]',
               tags = '{}'::TEXT[],
               searchable_text = '[nicht öffentlich]',
               language = 'und',
               kind = '[nicht öffentlich]',
               status = 'hidden',
               visibility_scopes = '{}'::TEXT[],
               semantic_state = 'unavailable',
               embedding = NULL,
               indexed_at = clock_timestamp()
          FROM domain_nodes n
         WHERE p.node_id = n.id
           AND n.search_visibility = 'private'
           AND weltgewebe_search_owner_account_id(n.payload) = account_identifier;
    END IF;

    WITH affected AS (
        SELECT n.id
          FROM domain_nodes n
         WHERE n.search_visibility = 'private'
           AND weltgewebe_search_owner_account_id(n.payload) = account_identifier
    ), bumped AS (
        INSERT INTO search_node_versions AS current_version
            (node_id, source_version, source_revision, deleted_at)
        SELECT id, 1, 'node-1', NULL
          FROM affected
        ON CONFLICT (node_id) DO UPDATE SET
          source_version = current_version.source_version + 1,
          source_revision = 'node-' || (current_version.source_version + 1)::TEXT,
          deleted_at = NULL
        RETURNING node_id, source_version, source_revision
    )
    INSERT INTO search_projection_jobs
        (generation_id, node_id, source_version, source_revision, operation)
    SELECT g.generation_id, b.node_id, b.source_version, b.source_revision, 'upsert'
      FROM bumped b
      CROSS JOIN search_index_generations g
     WHERE g.state IN ('building', 'ready', 'active')
       AND g.document_revision = 'node-document-v4-canonical-visibility'
    ON CONFLICT DO NOTHING;

    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END; $$;

CREATE TRIGGER search_track_domain_account_owner_insert_delete
AFTER INSERT OR DELETE ON domain_accounts
FOR EACH ROW EXECUTE FUNCTION weltgewebe_search_track_domain_account_owner();

CREATE TRIGGER search_track_domain_account_owner_disabled
AFTER UPDATE OF disabled ON domain_accounts
FOR EACH ROW EXECUTE FUNCTION weltgewebe_search_track_domain_account_owner();

-- Purge recoverable non-public and orphaned content left by older generations.
-- Canonical domain rows remain untouched; projections are regenerable state.
DELETE FROM search_node_projections p
USING domain_nodes n
WHERE p.node_id = n.id
  AND n.search_visibility <> 'public';

DELETE FROM search_node_projections p
WHERE NOT EXISTS (SELECT 1 FROM domain_nodes n WHERE n.id = p.node_id);

CREATE OR REPLACE FUNCTION weltgewebe_search_generation_activation_ready(p_generation_id TEXT)
RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
SELECT COALESCE((
    SELECT g.state IN ('building', 'ready', 'active')
       AND g.document_revision = 'node-document-v4-canonical-visibility'
       AND g.completed_nodes = g.expected_nodes
       AND NOT EXISTS (
           SELECT 1
           FROM search_node_versions v
           LEFT JOIN domain_nodes n ON n.id = v.node_id
           WHERE v.deleted_at IS NULL
             AND (
                 n.id IS NULL
                 OR NOT EXISTS (
                     SELECT 1
                     FROM search_node_projections p
                     WHERE p.generation_id = g.generation_id
                       AND p.node_id = v.node_id
                       AND p.source_version = v.source_version
                       AND p.source_revision = v.source_revision
                       AND (
                           (n.search_visibility = 'public'
                            AND p.status = 'active'
                            AND p.semantic_state = 'ready'
                            AND p.visibility_scopes = ARRAY['public']::TEXT[]
                            AND cardinality(p.embedding) = g.dimension)
                           OR
                           (n.search_visibility = 'private'
                            AND weltgewebe_search_owner_is_active(n.payload)
                            AND p.status = 'active'
                            AND p.semantic_state = 'unavailable'
                            AND p.visibility_scopes = ARRAY['owner']::TEXT[]
                            AND p.embedding IS NULL)
                           OR
                           ((n.search_visibility IN ('hidden', 'revoked')
                             OR (n.search_visibility = 'private'
                                 AND NOT weltgewebe_search_owner_is_active(n.payload)))
                            AND p.status = 'hidden'
                            AND p.semantic_state = 'unavailable'
                            AND p.visibility_scopes = '{}'::TEXT[]
                            AND p.embedding IS NULL
                            AND p.title = '[nicht öffentlich]'
                            AND p.searchable_text = '[nicht öffentlich]'
                            AND p.language = 'und'
                            AND p.kind = '[nicht öffentlich]'
                            AND p.tags = '{}'::TEXT[])
                       )
                 )
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

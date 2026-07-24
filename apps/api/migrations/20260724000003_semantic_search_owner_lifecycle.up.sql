-- WELTGEWEBE-SEMANTIC-SEARCH-V1-T012 owner lifecycle hardening.
--
-- A private search projection may retain plaintext only while its declared
-- owner exists in the canonical account table and is enabled. Account lifecycle
-- changes are therefore revision-producing search mutations.

CREATE OR REPLACE FUNCTION weltgewebe_search_declared_owner_account_id(p_payload JSONB)
RETURNS TEXT LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
SELECT CASE
    WHEN jsonb_typeof(p_payload -> 'created_by_account_id') = 'string' THEN
        NULLIF(trim(p_payload ->> 'created_by_account_id'), '')
    ELSE NULL
END;
$$;

-- Preserve the existing function name used by worker, repository and activation
-- gate, but strengthen its meaning from "non-empty string" to "active canonical
-- account". This makes every existing caller share one authorization rule.
CREATE OR REPLACE FUNCTION weltgewebe_search_node_owner_account_id(p_payload JSONB)
RETURNS TEXT LANGUAGE sql STABLE AS $$
SELECT declared.owner_account_id
FROM (
    SELECT weltgewebe_search_declared_owner_account_id(p_payload) AS owner_account_id
) AS declared
WHERE EXISTS (
    SELECT 1
    FROM domain_accounts a
    WHERE a.id = declared.owner_account_id
      AND a.disabled = FALSE
);
$$;

-- Final database write fence: even a stale or non-Rust writer cannot persist
-- recoverable private plaintext once the owner is absent or disabled.
CREATE OR REPLACE FUNCTION weltgewebe_search_enforce_projection_owner()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    canonical_visibility TEXT;
    active_owner_account_id TEXT;
BEGIN
    SELECT n.search_visibility,
           weltgewebe_search_node_owner_account_id(n.payload)
      INTO canonical_visibility, active_owner_account_id
      FROM domain_nodes n
     WHERE n.id = NEW.node_id;

    IF NOT FOUND
       OR canonical_visibility IN ('hidden', 'revoked')
       OR (canonical_visibility = 'private' AND active_owner_account_id IS NULL)
    THEN
        NEW.content_sha256 := 'e0f631f5602e764ef8a5f14e36d2d81663b20cd305a30af0dad6c0d759e5a955';
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
END;
$$;

CREATE TRIGGER search_enforce_projection_owner
BEFORE INSERT OR UPDATE ON search_node_projections
FOR EACH ROW EXECUTE FUNCTION weltgewebe_search_enforce_projection_owner();

-- Redact already retained plaintext for missing or disabled owners during the
-- cutover. Touching indexed_at is sufficient because the write fence replaces
-- every sensitive projection field before the UPDATE reaches the table.
UPDATE search_node_projections p
SET indexed_at = clock_timestamp()
FROM domain_nodes n
WHERE p.node_id = n.id
  AND n.search_visibility = 'private'
  AND weltgewebe_search_node_owner_account_id(n.payload) IS NULL;

-- Insert, disable, re-enable and delete events change the authorization state of
-- all private nodes declaring this account. The trigger first removes retained
-- plaintext synchronously on inactivation, then creates a new node revision and
-- one current-generation job per affected node.
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

    PERFORM pg_advisory_xact_lock_shared(
        hashtextextended('weltgewebe.search.generation.activation', 0)
    );

    IF account_inactive THEN
        UPDATE search_node_projections p
           SET indexed_at = clock_timestamp()
          FROM domain_nodes n
         WHERE p.node_id = n.id
           AND n.search_visibility = 'private'
           AND weltgewebe_search_declared_owner_account_id(n.payload) = account_identifier;
    END IF;

    WITH affected AS (
        SELECT n.id
          FROM domain_nodes n
         WHERE n.search_visibility = 'private'
           AND weltgewebe_search_declared_owner_account_id(n.payload) = account_identifier
    ), bumped AS (
        INSERT INTO search_node_versions
            (node_id, source_version, source_revision, deleted_at)
        SELECT id, 1, 'node-1', NULL
          FROM affected
        ON CONFLICT (node_id) DO UPDATE SET
          source_version = search_node_versions.source_version + 1,
          source_revision = 'node-' || (search_node_versions.source_version + 1)::TEXT,
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
END;
$$;

CREATE TRIGGER search_track_domain_account_owner_insert_delete
AFTER INSERT OR DELETE ON domain_accounts
FOR EACH ROW EXECUTE FUNCTION weltgewebe_search_track_domain_account_owner();

CREATE TRIGGER search_track_domain_account_owner_disabled
AFTER UPDATE OF disabled ON domain_accounts
FOR EACH ROW EXECUTE FUNCTION weltgewebe_search_track_domain_account_owner();

-- Reinstall the canonical activation gate so its private branch now resolves
-- through the strengthened active-owner function above.
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
                            AND weltgewebe_search_node_owner_account_id(n.payload) IS NOT NULL
                            AND p.status = 'active'
                            AND p.semantic_state = 'unavailable'
                            AND p.visibility_scopes = ARRAY['owner']::TEXT[]
                            AND p.embedding IS NULL)
                           OR
                           ((n.search_visibility IN ('hidden', 'revoked')
                             OR (n.search_visibility = 'private'
                                 AND weltgewebe_search_node_owner_account_id(n.payload) IS NULL))
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

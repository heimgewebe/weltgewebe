-- WELTGEWEBE-SEMANTIC-SEARCH-V1-T003
-- Executable PostgreSQL proof contract for a fully regenerable search projection.
-- It is deliberately outside apps/api/migrations: T003 does not mutate production.
-- No API route, worker, backfill or runtime activation is introduced.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE search_index_generations (
    generation_id TEXT PRIMARY KEY CHECK (btrim(generation_id) <> ''),
    provider TEXT NOT NULL CHECK (btrim(provider) <> ''),
    model_id TEXT NOT NULL CHECK (btrim(model_id) <> ''),
    model_revision TEXT NOT NULL CHECK (btrim(model_revision) <> ''),
    dimension INTEGER NOT NULL CHECK (dimension > 0),
    document_revision TEXT NOT NULL CHECK (btrim(document_revision) <> ''),
    normalization_revision TEXT NOT NULL CHECK (btrim(normalization_revision) <> ''),
    state TEXT NOT NULL DEFAULT 'building'
        CHECK (state IN ('building', 'ready', 'active', 'retired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    activated_at TIMESTAMPTZ,
    CHECK ((state = 'active') = (activated_at IS NOT NULL)),
    UNIQUE (
        provider,
        model_id,
        model_revision,
        dimension,
        document_revision,
        normalization_revision
    )
);

CREATE UNIQUE INDEX search_index_generations_one_active
    ON search_index_generations ((state))
    WHERE state = 'active';

CREATE TABLE search_node_projections (
    generation_id TEXT NOT NULL
        REFERENCES search_index_generations(generation_id) ON DELETE CASCADE,
    node_id TEXT NOT NULL
        REFERENCES domain_nodes(id) ON DELETE CASCADE,
    source_version BIGINT NOT NULL CHECK (source_version >= 0),
    source_revision TEXT NOT NULL CHECK (btrim(source_revision) <> ''),
    content_sha256 TEXT NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    title TEXT NOT NULL CHECK (btrim(title) <> ''),
    tags TEXT[] NOT NULL DEFAULT '{}',
    searchable_text TEXT NOT NULL CHECK (btrim(searchable_text) <> ''),
    language TEXT NOT NULL CHECK (btrim(language) <> ''),
    kind TEXT NOT NULL CHECK (btrim(kind) <> ''),
    status TEXT NOT NULL CHECK (status IN ('active', 'hidden', 'deleted')),
    visibility_scopes TEXT[] NOT NULL DEFAULT '{}',
    embedding DOUBLE PRECISION[],
    search_vector TSVECTOR NOT NULL,
    search_vector_simple TSVECTOR NOT NULL,
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (generation_id, node_id)
);

CREATE INDEX search_node_projections_fts
    ON search_node_projections USING GIN (search_vector);
CREATE INDEX search_node_projections_fts_simple
    ON search_node_projections USING GIN (search_vector_simple);
CREATE INDEX search_node_projections_trigram
    ON search_node_projections USING GIN (searchable_text gin_trgm_ops);
CREATE INDEX search_node_projections_title_trigram
    ON search_node_projections USING GIN (title gin_trgm_ops);
CREATE INDEX search_node_projections_tags
    ON search_node_projections USING GIN (tags);
CREATE INDEX search_node_projections_visibility
    ON search_node_projections (generation_id, status, language, kind, node_id);

CREATE OR REPLACE FUNCTION weltgewebe_validate_search_projection()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    expected_dimension INTEGER;
    actual_dimension INTEGER;
BEGIN
    SELECT dimension
      INTO expected_dimension
      FROM search_index_generations
     WHERE generation_id = NEW.generation_id;

    IF expected_dimension IS NULL THEN
        RAISE EXCEPTION 'unknown search generation: %', NEW.generation_id
            USING ERRCODE = '23503';
    END IF;

    IF NEW.embedding IS NOT NULL THEN
        IF array_ndims(NEW.embedding) <> 1 THEN
            RAISE EXCEPTION 'embedding must be one-dimensional'
                USING ERRCODE = '23514';
        END IF;
        actual_dimension := cardinality(NEW.embedding);
        IF actual_dimension <> expected_dimension THEN
            RAISE EXCEPTION 'embedding dimension % does not match generation dimension %',
                actual_dimension, expected_dimension
                USING ERRCODE = '23514';
        END IF;
        IF EXISTS (
            SELECT 1
              FROM unnest(NEW.embedding) AS value
             WHERE value IS NULL
                OR value::TEXT IN ('NaN', 'Infinity', '-Infinity')
        ) THEN
            RAISE EXCEPTION 'embedding contains a null or non-finite value'
                USING ERRCODE = '23514';
        END IF;
    END IF;

    NEW.tags := ARRAY(
        SELECT DISTINCT btrim(value)
          FROM unnest(NEW.tags) AS value
         WHERE btrim(value) <> ''
         ORDER BY btrim(value)
    );
    NEW.visibility_scopes := ARRAY(
        SELECT DISTINCT btrim(value)
          FROM unnest(NEW.visibility_scopes) AS value
         WHERE btrim(value) <> ''
         ORDER BY btrim(value)
    );
    NEW.search_vector :=
        setweight(to_tsvector('german'::regconfig, coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('german'::regconfig, coalesce(array_to_string(NEW.tags, ' '), '')), 'B') ||
        setweight(to_tsvector('german'::regconfig, coalesce(NEW.searchable_text, '')), 'C') ||
        setweight(to_tsvector('simple'::regconfig, coalesce(NEW.kind, '') || ' ' || coalesce(NEW.language, '')), 'D');
    NEW.search_vector_simple :=
        setweight(to_tsvector('simple'::regconfig, coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('simple'::regconfig, coalesce(array_to_string(NEW.tags, ' '), '')), 'B') ||
        setweight(to_tsvector('simple'::regconfig, coalesce(NEW.searchable_text, '')), 'C') ||
        setweight(to_tsvector('simple'::regconfig, coalesce(NEW.kind, '') || ' ' || coalesce(NEW.language, '')), 'D');
    NEW.indexed_at := clock_timestamp();
    RETURN NEW;
END;
$$;

CREATE TRIGGER search_node_projections_validate
BEFORE INSERT OR UPDATE ON search_node_projections
FOR EACH ROW EXECUTE FUNCTION weltgewebe_validate_search_projection();

CREATE OR REPLACE FUNCTION weltgewebe_activate_search_generation(p_generation_id TEXT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    target_state TEXT;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('weltgewebe.search.generation.activation', 0));

    SELECT state INTO target_state
      FROM search_index_generations
     WHERE generation_id = p_generation_id
     FOR UPDATE;

    IF target_state IS NULL THEN
        RAISE EXCEPTION 'unknown search generation: %', p_generation_id
            USING ERRCODE = '23503';
    END IF;
    IF target_state NOT IN ('ready', 'active') THEN
        RAISE EXCEPTION 'search generation % is not ready', p_generation_id
            USING ERRCODE = '23514';
    END IF;
    IF target_state = 'active' THEN
        RETURN;
    END IF;

    UPDATE search_index_generations
       SET state = 'retired', activated_at = NULL
     WHERE state = 'active';

    UPDATE search_index_generations
       SET state = 'active', activated_at = clock_timestamp()
     WHERE generation_id = p_generation_id;
END;
$$;

CREATE OR REPLACE FUNCTION weltgewebe_put_search_projection(
    p_generation_id TEXT,
    p_node_id TEXT,
    p_source_version BIGINT,
    p_source_revision TEXT,
    p_content_sha256 TEXT,
    p_title TEXT,
    p_tags TEXT[],
    p_searchable_text TEXT,
    p_language TEXT,
    p_kind TEXT,
    p_status TEXT,
    p_visibility_scopes TEXT[],
    p_embedding DOUBLE PRECISION[] DEFAULT NULL
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    current_row search_node_projections%ROWTYPE;
    normalized_tags TEXT[];
    normalized_visibility_scopes TEXT[];
BEGIN
    normalized_tags := ARRAY(
        SELECT DISTINCT btrim(value)
          FROM unnest(coalesce(p_tags, '{}'::TEXT[])) AS value
         WHERE btrim(value) <> ''
         ORDER BY btrim(value)
    );
    normalized_visibility_scopes := ARRAY(
        SELECT DISTINCT btrim(value)
          FROM unnest(coalesce(p_visibility_scopes, '{}'::TEXT[])) AS value
         WHERE btrim(value) <> ''
         ORDER BY btrim(value)
    );

    PERFORM pg_advisory_xact_lock(
        hashtextextended('weltgewebe.search.projection:' || p_generation_id || ':' || p_node_id, 0)
    );

    SELECT * INTO current_row
      FROM search_node_projections
     WHERE generation_id = p_generation_id
       AND node_id = p_node_id
     FOR UPDATE;

    IF FOUND THEN
        IF p_source_version < current_row.source_version THEN
            RETURN 'stale';
        END IF;
        IF p_source_version = current_row.source_version THEN
            IF p_source_revision IS NOT DISTINCT FROM current_row.source_revision
               AND p_content_sha256 IS NOT DISTINCT FROM current_row.content_sha256
               AND p_title IS NOT DISTINCT FROM current_row.title
               AND normalized_tags IS NOT DISTINCT FROM current_row.tags
               AND p_searchable_text IS NOT DISTINCT FROM current_row.searchable_text
               AND p_language IS NOT DISTINCT FROM current_row.language
               AND p_kind IS NOT DISTINCT FROM current_row.kind
               AND p_status IS NOT DISTINCT FROM current_row.status
               AND normalized_visibility_scopes IS NOT DISTINCT FROM current_row.visibility_scopes
               AND p_embedding IS NOT DISTINCT FROM current_row.embedding THEN
                RETURN 'idempotent';
            END IF;
            RAISE EXCEPTION 'conflicting projection identity for generation %, node %, source version %',
                p_generation_id, p_node_id, p_source_version
                USING ERRCODE = '40001';
        END IF;
    END IF;

    INSERT INTO search_node_projections (
        generation_id,
        node_id,
        source_version,
        source_revision,
        content_sha256,
        title,
        tags,
        searchable_text,
        language,
        kind,
        status,
        visibility_scopes,
        embedding
    ) VALUES (
        p_generation_id,
        p_node_id,
        p_source_version,
        p_source_revision,
        p_content_sha256,
        p_title,
        normalized_tags,
        p_searchable_text,
        p_language,
        p_kind,
        p_status,
        normalized_visibility_scopes,
        p_embedding
    )
    ON CONFLICT (generation_id, node_id) DO UPDATE SET
        source_version = EXCLUDED.source_version,
        source_revision = EXCLUDED.source_revision,
        content_sha256 = EXCLUDED.content_sha256,
        title = EXCLUDED.title,
        tags = EXCLUDED.tags,
        searchable_text = EXCLUDED.searchable_text,
        language = EXCLUDED.language,
        kind = EXCLUDED.kind,
        status = EXCLUDED.status,
        visibility_scopes = EXCLUDED.visibility_scopes,
        embedding = EXCLUDED.embedding;

    RETURN CASE WHEN current_row.node_id IS NULL THEN 'inserted' ELSE 'updated' END;
END;
$$;

CREATE OR REPLACE FUNCTION weltgewebe_search_lexical_candidates(
    p_generation_id TEXT,
    p_viewer_scope TEXT,
    p_allowed_node_ids TEXT[],
    p_query TEXT,
    p_kinds TEXT[] DEFAULT '{}',
    p_tags TEXT[] DEFAULT '{}',
    p_languages TEXT[] DEFAULT '{}',
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    node_id TEXT,
    rank_class INTEGER,
    rank_score DOUBLE PRECISION
)
LANGUAGE sql
STABLE
AS $search$
    WITH query_terms AS (
        SELECT DISTINCT lower(debug.token) AS simple_term,
                        lexeme AS german_term
          FROM ts_debug('german'::regconfig, coalesce(p_query, '')) AS debug
          CROSS JOIN LATERAL unnest(debug.lexemes) AS lexeme
         WHERE debug.alias IN (
             'asciiword', 'word', 'numword', 'hword', 'hword_part',
             'hword_asciipart', 'hword_numpart'
         )
           AND length(debug.token) >= 2
    ), query_stats AS (
        SELECT count(*)::INTEGER AS term_count FROM query_terms
    ), authorized AS (
        SELECT projection.*
          FROM search_node_projections AS projection
          JOIN search_index_generations AS generation
            ON generation.generation_id = projection.generation_id
           AND generation.state = 'active'
         WHERE btrim(coalesce(p_query, '')) <> ''
           AND projection.generation_id = p_generation_id
           AND projection.status = 'active'
           AND p_viewer_scope = ANY(projection.visibility_scopes)
           AND p_allowed_node_ids IS NOT NULL
           AND projection.node_id = ANY(p_allowed_node_ids)
           AND (cardinality(p_kinds) = 0 OR projection.kind = ANY(p_kinds))
           AND (cardinality(p_tags) = 0 OR projection.tags && p_tags)
           AND (cardinality(p_languages) = 0 OR projection.language = ANY(p_languages))
    ), scored AS (
        SELECT authorized.node_id,
               CASE
                   WHEN lower(btrim(authorized.title)) = lower(btrim(p_query)) THEN 0
                   WHEN EXISTS (
                       SELECT 1 FROM unnest(authorized.tags) AS tag
                        WHERE lower(btrim(tag)) = lower(btrim(p_query))
                   ) THEN 1
                   WHEN lower(authorized.title) LIKE lower(btrim(p_query)) || '%' THEN 2
                   WHEN trigram.score >= 0.30
                        AND lexical.matched_terms >= least(2, greatest(query_stats.term_count, 1)) THEN 3
                   WHEN lexical.matched_terms >= CASE WHEN query_stats.term_count <= 2 THEN 1 ELSE 2 END THEN 4
                   WHEN trigram.score >= 0.30 THEN 5
                   ELSE NULL
               END AS rank_class,
               CASE
                   WHEN lower(btrim(authorized.title)) = lower(btrim(p_query)) THEN 1.0
                   WHEN EXISTS (
                       SELECT 1 FROM unnest(authorized.tags) AS tag
                        WHERE lower(btrim(tag)) = lower(btrim(p_query))
                   ) THEN 1.0
                   WHEN lower(authorized.title) LIKE lower(btrim(p_query)) || '%' THEN
                       length(btrim(p_query))::DOUBLE PRECISION / greatest(length(authorized.title), 1)
                   WHEN lexical.matched_terms > 0 THEN
                       lexical.matched_terms::DOUBLE PRECISION / greatest(query_stats.term_count, 1)
                       + lexical.score / greatest(query_stats.term_count, 1)
                       + trigram.score / 10.0
                   ELSE trigram.score
               END AS rank_score
          FROM authorized
          CROSS JOIN query_stats
          CROSS JOIN LATERAL (
              SELECT greatest(
                  similarity(authorized.title, p_query),
                  word_similarity(p_query, authorized.title),
                  word_similarity(p_query, authorized.searchable_text),
                  coalesce((
                      SELECT max(greatest(similarity(tag, p_query), word_similarity(p_query, tag)))
                        FROM unnest(authorized.tags) AS tag
                  ), 0)
              )::DOUBLE PRECISION AS score
          ) AS trigram
          CROSS JOIN LATERAL (
              SELECT count(*) FILTER (
                         WHERE authorized.search_vector_simple @@ plainto_tsquery('simple'::regconfig, simple_term)
                            OR authorized.search_vector @@ plainto_tsquery('german'::regconfig, german_term)
                     )::INTEGER AS matched_terms,
                     coalesce(sum(greatest(
                         ts_rank_cd(authorized.search_vector_simple, plainto_tsquery('simple'::regconfig, simple_term), 32),
                         ts_rank_cd(authorized.search_vector, plainto_tsquery('german'::regconfig, german_term), 32)
                     )), 0)::DOUBLE PRECISION AS score
                FROM query_terms
          ) AS lexical
    )
    SELECT scored.node_id, scored.rank_class, scored.rank_score
      FROM scored
     WHERE scored.rank_class IS NOT NULL
     ORDER BY scored.rank_class ASC, scored.rank_score DESC, scored.node_id ASC
     LIMIT greatest(0, least(coalesce(p_limit, 10), 10));
$search$;

COMMENT ON TABLE search_node_projections IS
    'Regenerable PostgreSQL search projection. It is not a canonical domain truth and has no runtime consumer in T003.';
COMMENT ON COLUMN search_node_projections.embedding IS
    'Exact bounded reference vector storage only. pgvector/ANN is not assumed or activated by T003.';
COMMENT ON FUNCTION weltgewebe_search_lexical_candidates IS
    'Visibility, deletion, generation and explicit authorization are applied before lexical scoring.';

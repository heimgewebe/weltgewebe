//! PostgreSQL-backed search candidate retrieval for T006.
//!
//! Authorization is derived from the canonical domain row and request auth context
//! before any lexical or semantic candidate can enter the result set. The search
//! projection is treated as regenerable data, never as an authorization source.
use chrono::{DateTime, Utc};
use serde_json::Value;
use sqlx::{PgPool, Row};

use crate::{
    middleware::auth::AuthContext,
    routes::nodes::{Location, Node},
    search::ranking::ScoredNode,
};

#[derive(Debug, Clone, Default)]
pub struct SearchFilters {
    pub kinds: Vec<String>,
    pub tags: Vec<String>,
    pub languages: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct ActiveSearchGeneration {
    pub generation_id: String,
    pub provider: String,
    pub model_id: String,
    pub model_revision: String,
    pub runtime_identity: String,
    pub dimension: i32,
    pub document_revision: String,
    pub normalization_revision: String,
    pub ranking_revision: String,
}

#[derive(Debug, Clone)]
pub struct SearchCandidateSet {
    pub generation: ActiveSearchGeneration,
    /// PostgreSQL order is authoritative: lexical matches first in T003 order,
    /// followed by non-lexical authorized candidates in node-id order for the
    /// bounded semantic append decision.
    pub candidates: Vec<ScoredNode>,
}

/// Fetches exactly one active generation and candidates authorized by the current
/// canonical domain state. Unknown or legacy visibility values fail closed.
/// Stale projections are excluded by exact source version/revision equality.
pub async fn fetch_postgres_candidates(
    pool: &PgPool,
    query: &str,
    filters: &SearchFilters,
    auth: &AuthContext,
) -> anyhow::Result<Option<SearchCandidateSet>> {
    let generation_row = sqlx::query(
        "SELECT generation_id, provider, model_id, model_revision, runtime_identity, dimension, \
                document_revision, normalization_revision, ranking_revision \
         FROM search_index_generations WHERE state = 'active'",
    )
    .fetch_optional(pool)
    .await?;

    let Some(generation_row) = generation_row else {
        return Ok(None);
    };

    let generation = ActiveSearchGeneration {
        generation_id: generation_row.try_get("generation_id")?,
        provider: generation_row.try_get("provider")?,
        model_id: generation_row.try_get("model_id")?,
        model_revision: generation_row.try_get("model_revision")?,
        runtime_identity: generation_row.try_get("runtime_identity")?,
        dimension: generation_row.try_get("dimension")?,
        document_revision: generation_row.try_get("document_revision")?,
        normalization_revision: generation_row.try_get("normalization_revision")?,
        ranking_revision: generation_row.try_get("ranking_revision")?,
    };

    let account_id = auth
        .account_id
        .as_deref()
        .filter(|_| auth.authenticated)
        .map(str::to_owned);

    let rows = sqlx::query(
        r#"
        WITH query_terms AS (
            SELECT DISTINCT lower(debug.token) AS simple_term, lexeme AS german_term
              FROM ts_debug('german'::regconfig, coalesce($2, '')) AS debug
              CROSS JOIN LATERAL unnest(debug.lexemes) AS lexeme
             WHERE debug.alias IN (
                 'asciiword', 'word', 'numword', 'hword', 'hword_part',
                 'hword_asciipart', 'hword_numpart'
             )
               AND length(debug.token) >= 2
        ), query_stats AS (
            SELECT count(*)::INTEGER AS term_count FROM query_terms
        ), authorized AS (
            SELECT p.node_id, p.title, p.tags, p.searchable_text, p.language, p.kind,
                   p.embedding, n.created_at, n.updated_at, n.lat, n.lon, n.payload::text AS payload,
                   setweight(to_tsvector('german'::regconfig, coalesce(p.title, '')), 'A') ||
                   setweight(to_tsvector('german'::regconfig, coalesce(array_to_string(p.tags, ' '), '')), 'B') ||
                   setweight(to_tsvector('german'::regconfig, coalesce(p.searchable_text, '')), 'C') ||
                   setweight(to_tsvector('simple'::regconfig, coalesce(p.kind, '') || ' ' || coalesce(p.language, '')), 'D')
                       AS search_vector,
                   setweight(to_tsvector('simple'::regconfig, coalesce(p.title, '')), 'A') ||
                   setweight(to_tsvector('simple'::regconfig, coalesce(array_to_string(p.tags, ' '), '')), 'B') ||
                   setweight(to_tsvector('simple'::regconfig, coalesce(p.searchable_text, '')), 'C') ||
                   setweight(to_tsvector('simple'::regconfig, coalesce(p.kind, '') || ' ' || coalesce(p.language, '')), 'D')
                       AS search_vector_simple
              FROM search_node_projections p
              JOIN search_node_versions v
                ON v.node_id = p.node_id
               AND v.source_version = p.source_version
               AND v.source_revision = p.source_revision
               AND v.deleted_at IS NULL
              JOIN domain_nodes n ON n.id = p.node_id
             WHERE p.generation_id = $1
               AND p.semantic_state = 'ready'
               AND cardinality(p.embedding) = $8
               AND n.created_at IS NOT NULL
               AND n.updated_at IS NOT NULL
               AND n.lat IS NOT NULL
               AND n.lon IS NOT NULL
               AND CASE
                     WHEN jsonb_typeof(n.payload -> 'search_visibility') IS DISTINCT FROM 'string' THEN FALSE
                     WHEN n.payload ->> 'search_visibility' = 'public' THEN TRUE
                     WHEN n.payload ->> 'search_visibility' = 'private' THEN
                          $4::boolean
                          AND $3::text IS NOT NULL
                          AND nullif(btrim(n.payload ->> 'created_by_account_id'), '') = $3::text
                     WHEN n.payload ->> 'search_visibility' IN ('hidden', 'revoked', 'deleted') THEN FALSE
                     ELSE FALSE
                   END
               AND (cardinality($5::text[]) = 0 OR p.kind = ANY($5::text[]))
               AND (cardinality($6::text[]) = 0 OR p.tags && $6::text[])
               AND (cardinality($7::text[]) = 0 OR p.language = ANY($7::text[]))
        ), scored AS (
            SELECT authorized.*,
                   CASE
                     WHEN lower(btrim(authorized.title)) = lower(btrim($2)) THEN 0
                     WHEN EXISTS (
                         SELECT 1 FROM unnest(authorized.tags) AS tag
                          WHERE lower(btrim(tag)) = lower(btrim($2))
                     ) THEN 1
                     WHEN lower(authorized.title) LIKE lower(btrim($2)) || '%' THEN 2
                     WHEN trigram.score >= 0.30
                          AND lexical.matched_terms >= least(2, greatest(query_stats.term_count, 1)) THEN 3
                     WHEN lexical.matched_terms >= CASE WHEN query_stats.term_count <= 2 THEN 1 ELSE 2 END THEN 4
                     WHEN trigram.score >= 0.30 THEN 5
                     ELSE NULL
                   END AS rank_class,
                   CASE
                     WHEN lower(btrim(authorized.title)) = lower(btrim($2)) THEN 1.0
                     WHEN EXISTS (
                         SELECT 1 FROM unnest(authorized.tags) AS tag
                          WHERE lower(btrim(tag)) = lower(btrim($2))
                     ) THEN 1.0
                     WHEN lower(authorized.title) LIKE lower(btrim($2)) || '%' THEN
                          length(btrim($2))::DOUBLE PRECISION / greatest(length(authorized.title), 1)
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
                      similarity(authorized.title, $2),
                      word_similarity($2, authorized.title),
                      word_similarity($2, authorized.searchable_text),
                      coalesce((
                          SELECT max(greatest(similarity(tag, $2), word_similarity($2, tag)))
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
        SELECT node_id, title, tags, searchable_text, language, kind, embedding,
               created_at, updated_at, lat, lon, payload, rank_class, rank_score
          FROM scored
         ORDER BY rank_class ASC NULLS LAST, rank_score DESC NULLS LAST, node_id ASC
        "#,
    )
    .bind(&generation.generation_id)
    .bind(query)
    .bind(account_id)
    .bind(auth.authenticated)
    .bind(&filters.kinds)
    .bind(&filters.tags)
    .bind(&filters.languages)
    .bind(generation.dimension)
    .fetch_all(pool)
    .await?;

    let mut candidates = Vec::with_capacity(rows.len());
    for row in rows {
        let payload_text: String = row.try_get("payload")?;
        let payload: Value = serde_json::from_str(&payload_text)?;
        let created_at: DateTime<Utc> = row.try_get("created_at")?;
        let updated_at: DateTime<Utc> = row.try_get("updated_at")?;
        let lat: f64 = row.try_get("lat")?;
        let lon: f64 = row.try_get("lon")?;
        let tags: Vec<String> = row.try_get("tags")?;
        let rank_class: Option<i32> = row.try_get("rank_class")?;
        let rank_score: Option<f64> = row.try_get("rank_score")?;
        let embedding: Vec<f64> = row.try_get("embedding")?;

        let node = Node {
            id: row.try_get("node_id")?,
            kind: row.try_get("kind")?,
            title: row.try_get("title")?,
            created_at: created_at.to_rfc3339(),
            updated_at: updated_at.to_rfc3339(),
            created_by_account_id: payload
                .get("created_by_account_id")
                .and_then(Value::as_str)
                .map(str::to_owned),
            summary: payload
                .get("summary")
                .and_then(Value::as_str)
                .map(str::to_owned),
            info: payload
                .get("info")
                .and_then(Value::as_str)
                .map(str::to_owned),
            tags,
            address: payload
                .get("address")
                .and_then(Value::as_str)
                .map(str::to_owned),
            location: Location { lat, lon },
        };

        candidates.push(ScoredNode {
            node,
            rank_class: rank_class
                .and_then(|value| u8::try_from(value).ok())
                .unwrap_or(u8::MAX),
            rank_score: rank_score.unwrap_or(0.0),
            embedding: Some(embedding),
        });
    }

    Ok(Some(SearchCandidateSet {
        generation,
        candidates,
    }))
}

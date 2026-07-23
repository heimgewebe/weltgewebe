//! T006 server-side hybrid search service.
use std::{env, sync::Arc};

use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
};
use serde::{Deserialize, Serialize};

use crate::{
    config::DomainReadSource,
    middleware::auth::AuthContext,
    routes::nodes::Node,
    search::{
        ranking::{
            rank_hybrid, SearchQuery, DEFAULT_SEMANTIC_MINIMUM_COSINE,
            DEFAULT_SEMANTIC_MINIMUM_MARGIN,
        },
        repository::{fetch_postgres_candidates, ActiveSearchGeneration, SearchFilters},
        worker::{
            EmbeddingProvider, EmbeddingProviderError, GenerationSpec, OllamaEmbeddingProvider,
            DOCUMENT_REVISION, NORMALIZATION_REVISION, RANKING_REVISION,
        },
    },
    state::ApiState,
};

const DEFAULT_LIMIT: usize = 10;
const MAX_LIMIT: usize = 100;
const MAX_OFFSET: usize = 10_000;
const MAX_QUERY_CHARS: usize = 512;

#[derive(Debug, Clone, Deserialize, Default)]
pub struct SearchQueryParams {
    pub q: Option<String>,
    pub kind: Option<String>,
    pub kinds: Option<String>,
    pub tag: Option<String>,
    pub tags: Option<String>,
    pub language: Option<String>,
    pub languages: Option<String>,
    pub limit: Option<usize>,
    pub offset: Option<usize>,
}

#[derive(Debug, Serialize, Deserialize, PartialEq)]
pub struct SearchResponse {
    pub items: Vec<Node>,
    pub mode: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fallback_reason: Option<String>,
    pub generation_id: String,
    pub offset: usize,
}

#[derive(Debug, thiserror::Error)]
pub enum SearchError {
    #[error("provider contract error")]
    ProviderContractError(#[from] EmbeddingProviderError),
    #[error("search service unavailable")]
    Unavailable,
    #[error("invalid search request")]
    InvalidRequest,
    #[error("internal search error")]
    Internal,
}

impl IntoResponse for SearchError {
    fn into_response(self) -> Response {
        let (status, code) = match &self {
            SearchError::ProviderContractError(EmbeddingProviderError::Unavailable) => {
                (StatusCode::SERVICE_UNAVAILABLE, "provider_unavailable")
            }
            SearchError::ProviderContractError(error) => {
                (StatusCode::INTERNAL_SERVER_ERROR, error.code())
            }
            SearchError::Unavailable => (StatusCode::SERVICE_UNAVAILABLE, "search_unavailable"),
            SearchError::InvalidRequest => (StatusCode::BAD_REQUEST, "invalid_search_request"),
            SearchError::Internal => (StatusCode::INTERNAL_SERVER_ERROR, "search_internal_error"),
        };
        tracing::warn!(event = "search.request.failed", error_code = code, %status);
        (status, code).into_response()
    }
}

fn parse_list(single: &Option<String>, multiple: &Option<String>) -> Vec<String> {
    let mut values = Vec::new();
    for source in [single.as_deref(), multiple.as_deref()]
        .into_iter()
        .flatten()
    {
        values.extend(
            source
                .split(',')
                .map(str::trim)
                .filter(|value| !value.is_empty())
                .map(str::to_owned),
        );
    }
    values.sort();
    values.dedup();
    values
}

fn pagination(params: &SearchQueryParams) -> Result<(usize, usize), SearchError> {
    let limit = params.limit.unwrap_or(DEFAULT_LIMIT).clamp(1, MAX_LIMIT);
    let offset = params.offset.unwrap_or(0);
    if offset > MAX_OFFSET {
        return Err(SearchError::InvalidRequest);
    }
    Ok((limit, offset))
}

fn validate_generation(generation: &ActiveSearchGeneration) -> Result<(), SearchError> {
    if generation.dimension <= 0
        || generation.document_revision != DOCUMENT_REVISION
        || generation.normalization_revision != NORMALIZATION_REVISION
        || generation.ranking_revision != RANKING_REVISION
    {
        return Err(SearchError::Unavailable);
    }
    let spec = GenerationSpec {
        generation_id: &generation.generation_id,
        provider: &generation.provider,
        model_id: &generation.model_id,
        model_revision: &generation.model_revision,
        runtime_identity: &generation.runtime_identity,
        dimension: generation.dimension,
    };
    if spec.derived_id() != generation.generation_id {
        return Err(SearchError::Unavailable);
    }
    Ok(())
}

fn runtime_provider(
    generation: &ActiveSearchGeneration,
) -> Result<Arc<dyn EmbeddingProvider>, SearchError> {
    if generation.provider != "local:ollama" {
        return Err(SearchError::ProviderContractError(
            EmbeddingProviderError::Unsupported,
        ));
    }
    let base_url =
        env::var("WELTGEWEBE_SEARCH_OLLAMA_URL").map_err(|_| SearchError::Unavailable)?;
    let provider = OllamaEmbeddingProvider::new(
        &base_url,
        generation.model_id.clone(),
        generation.model_revision.clone(),
        generation.runtime_identity.clone(),
    )?;
    Ok(Arc::new(provider))
}

pub async fn execute_search(
    state: &ApiState,
    auth: &AuthContext,
    params: SearchQueryParams,
    provider_override: Option<Arc<dyn EmbeddingProvider>>,
) -> Result<SearchResponse, SearchError> {
    if state.config.domain_read_source != DomainReadSource::Postgres {
        return Err(SearchError::Unavailable);
    }
    let pool = state.db_pool.as_ref().ok_or(SearchError::Unavailable)?;

    let raw_q = params.q.as_deref().unwrap_or("").trim();
    if raw_q.is_empty() || raw_q.chars().count() > MAX_QUERY_CHARS {
        return Err(SearchError::InvalidRequest);
    }
    let query = SearchQuery::new(raw_q);
    if query.normalized.is_empty() {
        return Err(SearchError::InvalidRequest);
    }

    let (limit, offset) = pagination(&params)?;
    let filters = SearchFilters {
        kinds: parse_list(&params.kind, &params.kinds),
        tags: parse_list(&params.tag, &params.tags),
        languages: parse_list(&params.language, &params.languages),
    };

    let candidate_set = fetch_postgres_candidates(pool, &query.raw, &filters, auth)
        .await
        .map_err(|_| SearchError::Internal)?
        .ok_or(SearchError::Unavailable)?;
    validate_generation(&candidate_set.generation)?;

    let lexical_ranked = candidate_set
        .candidates
        .iter()
        .filter(|candidate| candidate.rank_class != u8::MAX)
        .cloned()
        .collect::<Vec<_>>();

    let provider = match provider_override {
        Some(provider) => provider,
        None => runtime_provider(&candidate_set.generation)?,
    };

    let query_embedding_text = query.embedding_text();
    let (ranked, mode, fallback_reason) = match provider
        .embed(
            &query_embedding_text,
            candidate_set.generation.dimension as usize,
        )
        .await
    {
        Ok(query_vector) => (
            rank_hybrid(
                Some(&query_vector),
                lexical_ranked,
                &candidate_set.candidates,
                DEFAULT_SEMANTIC_MINIMUM_COSINE,
                DEFAULT_SEMANTIC_MINIMUM_MARGIN,
            ),
            "hybrid".to_string(),
            None,
        ),
        Err(EmbeddingProviderError::Unavailable) => {
            state
                .metrics
                .search_projection_outcome("fallback_unavailable");
            (
                lexical_ranked,
                "lexical_fallback".to_string(),
                Some("provider_unavailable".to_string()),
            )
        }
        Err(error) => return Err(SearchError::ProviderContractError(error)),
    };

    let items = ranked
        .into_iter()
        .skip(offset)
        .take(limit)
        .map(|candidate| candidate.node)
        .collect();

    Ok(SearchResponse {
        items,
        mode,
        fallback_reason,
        generation_id: candidate_set.generation.generation_id,
        offset,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pagination_defaults_clamps_limit_and_rejects_excessive_offset() {
        assert_eq!(pagination(&SearchQueryParams::default()).unwrap(), (10, 0));

        let low = SearchQueryParams {
            limit: Some(0),
            ..Default::default()
        };
        assert_eq!(pagination(&low).unwrap(), (1, 0));

        let high = SearchQueryParams {
            limit: Some(MAX_LIMIT + 1),
            offset: Some(MAX_OFFSET),
            ..Default::default()
        };
        assert_eq!(pagination(&high).unwrap(), (MAX_LIMIT, MAX_OFFSET));

        let excessive = SearchQueryParams {
            offset: Some(MAX_OFFSET + 1),
            ..Default::default()
        };
        assert!(matches!(
            pagination(&excessive),
            Err(SearchError::InvalidRequest)
        ));
    }
}

//! T006 server-side hybrid search service.
use std::{env, sync::Arc, time::Instant};

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
        repository::{
            fetch_postgres_candidates, ActiveSearchGeneration, SearchFilters, SearchRepositoryError,
        },
        worker::{
            EmbeddingProvider, EmbeddingProviderError, GenerationSpec, OllamaEmbeddingProvider,
            DOCUMENT_REVISION, NORMALIZATION_REVISION, RANKING_REVISION,
        },
    },
    state::ApiState,
};

const DEFAULT_LIMIT: usize = 10;
const MAX_LIMIT: usize = 10;
const MAX_OFFSET: usize = 0;
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
    /// Bounded T003/T004 result size; T006 v1 accepts values from 1 through 10.
    pub limit: Option<usize>,
    /// Reserved for a future measured pagination contract; T006 v1 accepts only 0.
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

fn validated_query(params: &SearchQueryParams) -> Result<SearchQuery, SearchError> {
    let raw_q = params.q.as_deref().unwrap_or("").trim();
    if raw_q.is_empty() || raw_q.chars().count() > MAX_QUERY_CHARS {
        return Err(SearchError::InvalidRequest);
    }
    let query = SearchQuery::new(raw_q);
    if query.normalized.is_empty() {
        return Err(SearchError::InvalidRequest);
    }
    Ok(query)
}

fn pagination(params: &SearchQueryParams) -> Result<(usize, usize), SearchError> {
    let limit = params.limit.unwrap_or(DEFAULT_LIMIT);
    let offset = params.offset.unwrap_or(0);
    if !(1..=MAX_LIMIT).contains(&limit) || offset > MAX_OFFSET {
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
    let request_started = Instant::now();
    let result = execute_search_inner(state, auth, params, provider_override).await;
    let outcome = match &result {
        Ok(response) if response.mode == "hybrid" => "hybrid",
        Ok(response) if response.mode == "lexical_fallback" => "lexical_fallback",
        Ok(_) => "success",
        Err(SearchError::ProviderContractError(_)) => "provider_contract_error",
        Err(SearchError::Unavailable) => "unavailable",
        Err(SearchError::InvalidRequest) => "invalid_request",
        Err(SearchError::Internal) => "internal",
    };
    state.metrics.search_request_outcome(outcome);
    state
        .metrics
        .observe_search_request_duration(request_started.elapsed());
    result
}

async fn execute_search_inner(
    state: &ApiState,
    auth: &AuthContext,
    params: SearchQueryParams,
    provider_override: Option<Arc<dyn EmbeddingProvider>>,
) -> Result<SearchResponse, SearchError> {
    if state.config.domain_read_source != DomainReadSource::Postgres {
        return Err(SearchError::Unavailable);
    }
    let pool = state.db_pool.as_ref().ok_or(SearchError::Unavailable)?;

    let query = validated_query(&params)?;
    let (limit, offset) = pagination(&params)?;
    let filters = SearchFilters {
        kinds: parse_list(&params.kind, &params.kinds),
        tags: parse_list(&params.tag, &params.tags),
        languages: parse_list(&params.language, &params.languages),
    };

    let repository_started = Instant::now();
    let candidate_result = fetch_postgres_candidates(pool, &query.raw, &filters, auth).await;
    state
        .metrics
        .observe_search_repository_duration(repository_started.elapsed());
    let candidate_set = match candidate_result {
        Ok(Some(candidate_set)) => candidate_set,
        Ok(None) => return Err(SearchError::Unavailable),
        Err(SearchRepositoryError::CandidateSetTooLarge) => {
            state.metrics.search_candidate_set_overflow();
            return Err(SearchError::Unavailable);
        }
        Err(SearchRepositoryError::Database(_)) | Err(SearchRepositoryError::Json(_)) => {
            return Err(SearchError::Internal);
        }
    };
    validate_generation(&candidate_set.generation)?;

    let lexical_ranked = candidate_set
        .candidates
        .iter()
        .filter(|candidate| candidate.rank_class != u8::MAX)
        .cloned()
        .collect::<Vec<_>>();

    state
        .metrics
        .observe_search_candidate_counts(candidate_set.candidates.len(), lexical_ranked.len());

    let provider = match provider_override {
        Some(provider) => provider,
        None => runtime_provider(&candidate_set.generation)?,
    };

    let query_embedding_text = query.embedding_text();
    let provider_started = Instant::now();
    let provider_result = provider
        .embed(
            &query_embedding_text,
            candidate_set.generation.dimension as usize,
        )
        .await;
    state
        .metrics
        .observe_search_provider_duration(provider_started.elapsed());
    let (ranked, mode, fallback_reason) = match provider_result {
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
        Err(EmbeddingProviderError::Unavailable) => (
            lexical_ranked,
            "lexical_fallback".to_string(),
            Some("provider_unavailable".to_string()),
        ),
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
    fn pagination_is_a_bounded_top_ten_contract_without_offset_pages() {
        assert_eq!(pagination(&SearchQueryParams::default()).unwrap(), (10, 0));

        let exact = SearchQueryParams {
            limit: Some(MAX_LIMIT),
            offset: Some(0),
            ..Default::default()
        };
        assert_eq!(pagination(&exact).unwrap(), (MAX_LIMIT, 0));

        for invalid in [
            SearchQueryParams {
                limit: Some(0),
                ..Default::default()
            },
            SearchQueryParams {
                limit: Some(MAX_LIMIT + 1),
                ..Default::default()
            },
            SearchQueryParams {
                offset: Some(1),
                ..Default::default()
            },
        ] {
            assert!(matches!(
                pagination(&invalid),
                Err(SearchError::InvalidRequest)
            ));
        }
    }

    #[test]
    fn query_validation_rejects_empty_and_overlong_input() {
        for q in [None, Some("".to_string()), Some("   ".to_string())] {
            let params = SearchQueryParams {
                q,
                ..Default::default()
            };
            assert!(matches!(
                validated_query(&params),
                Err(SearchError::InvalidRequest)
            ));
        }

        let overlong = SearchQueryParams {
            q: Some("x".repeat(MAX_QUERY_CHARS + 1)),
            ..Default::default()
        };
        assert!(matches!(
            validated_query(&overlong),
            Err(SearchError::InvalidRequest)
        ));

        let valid = SearchQueryParams {
            q: Some("  Fahrrad Hilfe  ".to_string()),
            ..Default::default()
        };
        assert_eq!(validated_query(&valid).unwrap().raw, "Fahrrad Hilfe");
    }

    #[test]
    fn list_filters_merge_deduplicate_and_sort_single_and_plural_forms() {
        assert_eq!(
            parse_list(
                &Some("Werkstatt, Treffpunkt".to_string()),
                &Some("Treffpunkt,Bibliothek".to_string())
            ),
            vec![
                "Bibliothek".to_string(),
                "Treffpunkt".to_string(),
                "Werkstatt".to_string()
            ]
        );
    }
}

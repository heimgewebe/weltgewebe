//! T006 server-side search route.
use axum::{
    extract::{Query, State},
    Extension, Json,
};

use crate::{
    middleware::auth::AuthContext,
    search::{execute_search, SearchError, SearchQueryParams, SearchResponse},
    state::ApiState,
};

/// GET /search
///
/// Authorization comes from the request's canonical AuthContext and is applied
/// against PostgreSQL domain state before retrieval. T006 v1 returns a bounded
/// top-10 ranking and deliberately does not claim offset pagination.
pub async fn search_nodes(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
    Query(params): Query<SearchQueryParams>,
) -> Result<Json<SearchResponse>, SearchError> {
    Ok(Json(execute_search(&state, &auth, params, None).await?))
}

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
/// against PostgreSQL domain state before retrieval.
pub async fn search_nodes(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
    Query(params): Query<SearchQueryParams>,
) -> Result<Json<SearchResponse>, SearchError> {
    Ok(Json(execute_search(&state, &auth, params, None).await?))
}

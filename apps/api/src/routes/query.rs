use axum::http::StatusCode;
use std::collections::HashMap;

/// Upper bound for the `limit` query parameter on list endpoints, applied so a
/// single request cannot force an unbounded in-memory collection.
pub const MAX_PAGE_SIZE: usize = 1000;

pub fn parse_usize_param(
    params: &HashMap<String, String>,
    key: &str,
    default: usize,
) -> Result<usize, StatusCode> {
    match params.get(key) {
        Some(raw) => raw.parse().map_err(|_| StatusCode::BAD_REQUEST),
        None => Ok(default),
    }
}

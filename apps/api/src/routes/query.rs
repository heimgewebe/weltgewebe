use axum::http::StatusCode;
use std::collections::HashMap;

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

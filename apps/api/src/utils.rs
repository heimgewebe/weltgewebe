use axum::http::StatusCode;
use std::collections::HashMap;
use std::env;
use std::path::PathBuf;

pub fn in_dir() -> PathBuf {
    env::var("GEWEBE_IN_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(".gewebe/in"))
}

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

pub fn nodes_path() -> PathBuf {
    in_dir().join("demo.nodes.jsonl")
}

pub fn edges_path() -> PathBuf {
    in_dir().join("demo.edges.jsonl")
}

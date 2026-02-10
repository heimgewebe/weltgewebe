use crate::state::ApiState;
use crate::utils::edges_path;
use axum::{
    extract::{Query, State},
    Json,
};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tokio::{
    fs::File,
    io::{AsyncBufReadExt, BufReader},
};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Edge {
    pub id: String,
    pub source_id: String,
    pub target_id: String,
    #[serde(alias = "kind", alias = "edgeKind")]
    pub edge_kind: String,
}

pub async fn load_edges() -> Vec<Edge> {
    let start = std::time::Instant::now();
    let path = edges_path();
    let file = match File::open(&path).await {
        Ok(f) => f,
        Err(e) => {
            tracing::warn!(?path, ?e, "Failed to open edges file, returning empty list");
            return Vec::new();
        }
    };
    let mut lines = BufReader::new(file).lines();
    let mut edges = Vec::new();

    while let Ok(Some(line)) = lines.next_line().await {
        let edge: Edge = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(e) => {
                // Secure logging: avoid logging full payload, just length and error
                tracing::warn!(error = %e, line_len = line.len(), "failed to parse edge JSON");
                continue;
            }
        };
        edges.push(edge);
    }

    let load_ms = start.elapsed().as_millis();
    tracing::info!(
        count = edges.len(),
        load_ms,
        ?path,
        "Loaded edges into memory cache"
    );
    edges
}

pub async fn list_edges(
    State(state): State<ApiState>,
    Query(params): Query<HashMap<String, String>>,
) -> Json<Vec<Edge>> {
    let src = params.get("source_id");
    let dst = params.get("target_id");
    let limit: usize = params
        .get("limit")
        .and_then(|s| s.parse().ok())
        .unwrap_or(250);

    let edges = state.edges.read().await;

    let out: Vec<Edge> = edges
        .iter()
        .filter(|edge| {
            if let Some(s) = src {
                if edge.source_id != *s {
                    return false;
                }
            }
            if let Some(d) = dst {
                if edge.target_id != *d {
                    return false;
                }
            }
            true
        })
        .take(limit)
        .cloned()
        .collect();

    Json(out)
}

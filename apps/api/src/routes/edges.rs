use crate::state::ApiState;
use crate::utils::edges_path;
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
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
    pub source_type: Option<String>,
    pub target_id: String,
    pub target_type: Option<String>,
    #[serde(alias = "kind", alias = "edgeKind")]
    pub edge_kind: String,
    pub note: Option<String>,
    pub created_at: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
pub struct EdgeParticipantDetails {
    pub id: String,
    pub title: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub r#type: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
pub struct EdgeWithDetails {
    #[serde(flatten)]
    pub edge: Edge,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source_details: Option<EdgeParticipantDetails>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub target_details: Option<EdgeParticipantDetails>,
}

const MAX_PAGE_SIZE: usize = 1000;

pub async fn load_edges() -> HashMap<String, Edge> {
    let start = std::time::Instant::now();
    let path = edges_path();
    let file = match File::open(&path).await {
        Ok(f) => f,
        Err(e) => {
            tracing::warn!(?path, ?e, "Failed to open edges file, returning empty list");
            return HashMap::new();
        }
    };
    let mut lines = BufReader::new(file).lines();
    let mut edges = HashMap::new();

    let max_edges = match std::env::var("MAX_EDGES_CACHE") {
        Ok(val) => match val.parse::<usize>() {
            Ok(v) => v,
            Err(_) => {
                tracing::warn!(
                    value = %val,
                    "Invalid MAX_EDGES_CACHE, falling back to default 500,000"
                );
                500_000
            }
        },
        Err(_) => 500_000,
    };

    while let Ok(Some(line)) = lines.next_line().await {
        if edges.len() >= max_edges {
            tracing::warn!(
                ?path,
                max_edges,
                "Edges cache limit reached, truncating load"
            );
            break;
        }

        let edge: Edge = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(e) => {
                // Secure logging: avoid logging full payload, just length and error
                tracing::warn!(error = %e, line_len = line.len(), "failed to parse edge JSON");
                continue;
            }
        };
        edges.insert(edge.id.clone(), edge);
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
        .unwrap_or(250)
        .min(MAX_PAGE_SIZE);

    let edges = state.edges.read().await;

    let out: Vec<Edge> = edges
        .values()
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

pub async fn get_edge(
    State(state): State<ApiState>,
    Path(id): Path<String>,
) -> Result<Json<EdgeWithDetails>, StatusCode> {
    let edges = state.edges.read().await;
    let edge = edges
        .get(&id)
        .cloned()
        .ok_or(StatusCode::NOT_FOUND)?;

    let mut source_details = None;
    let mut target_details = None;

    if let Some(src_type) = &edge.source_type {
        if src_type == "account" {
            let accounts = state.accounts.read().await;
            if let Some(account) = accounts.get(&edge.source_id) {
                source_details = Some(EdgeParticipantDetails {
                    id: account.public.id.clone(),
                    title: account.public.title.clone(),
                    r#type: Some(account.public.kind.clone()),
                });
            }
        } else if src_type == "node" {
            let nodes = state.nodes.read().await;
            if let Some(node) = nodes.get(&edge.source_id) {
                source_details = Some(EdgeParticipantDetails {
                    id: node.id.clone(),
                    title: node.title.clone(),
                    r#type: Some(node.kind.clone()),
                });
            }
        }
    }

    if let Some(tgt_type) = &edge.target_type {
        if tgt_type == "account" {
            let accounts = state.accounts.read().await;
            if let Some(account) = accounts.get(&edge.target_id) {
                target_details = Some(EdgeParticipantDetails {
                    id: account.public.id.clone(),
                    title: account.public.title.clone(),
                    r#type: Some(account.public.kind.clone()),
                });
            }
        } else if tgt_type == "node" {
            let nodes = state.nodes.read().await;
            if let Some(node) = nodes.get(&edge.target_id) {
                target_details = Some(EdgeParticipantDetails {
                    id: node.id.clone(),
                    title: node.title.clone(),
                    r#type: Some(node.kind.clone()),
                });
            }
        }
    }

    Ok(Json(EdgeWithDetails {
        edge,
        source_details,
        target_details,
    }))
}

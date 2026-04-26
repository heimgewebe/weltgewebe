use crate::state::{ApiState, OrderedCache};
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

pub async fn load_edges() -> OrderedCache<Edge> {
    let start = std::time::Instant::now();
    let path = edges_path();
    let file = match File::open(&path).await {
        Ok(f) => f,
        Err(e) => {
            tracing::warn!(
                ?path,
                ?e,
                "Failed to open edges file, returning empty cache"
            );
            return OrderedCache::new();
        }
    };
    let mut lines = BufReader::new(file).lines();
    let mut edges = OrderedCache::new();
    let mut records_read = 0;
    let mut duplicates_count = 0;

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
        if records_read >= max_edges {
            tracing::warn!(
                ?path,
                max_edges,
                "Edges cache limit reached, truncating load"
            );
            break;
        }
        records_read += 1;

        let edge: Edge = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(e) => {
                // Secure logging: avoid logging full payload, just length and error
                tracing::warn!(error = %e, line_len = line.len(), "failed to parse edge JSON");
                continue;
            }
        };
        if edges.insert(edge.id.clone(), edge) {
            duplicates_count += 1;
        }
    }

    let load_ms = start.elapsed().as_millis();
    tracing::info!(
        count = edges.len(),
        duplicates_count,
        load_ms,
        ?path,
        "Loaded edges into memory cache"
    );
    edges
}

pub async fn list_edges(
    State(state): State<ApiState>,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Json<Vec<Edge>>, StatusCode> {
    let src = params.get("source_id");
    let dst = params.get("target_id");
    let limit: usize = crate::utils::parse_usize_param(&params, "limit", 250)?.min(MAX_PAGE_SIZE);
    let offset: usize = crate::utils::parse_usize_param(&params, "offset", 0)?;

    let cache = state.edges.read().await;

    let out: Vec<Edge> = cache
        .iter_in_order()
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
        .skip(offset)
        .take(limit)
        .cloned()
        .collect();

    Ok(Json(out))
}

pub async fn get_edge(
    State(state): State<ApiState>,
    Path(id): Path<String>,
) -> Result<Json<EdgeWithDetails>, StatusCode> {
    let cache = state.edges.read().await;
    let edge = cache.get(&id).cloned().ok_or(StatusCode::NOT_FOUND)?;

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
            let nodes_cache = state.nodes.read().await;
            if let Some(node) = nodes_cache.get(&edge.source_id) {
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
            let nodes_cache = state.nodes.read().await;
            if let Some(node) = nodes_cache.get(&edge.target_id) {
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

use crate::utils::edges_path;
use axum::{extract::Query, Json};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tokio::{
    fs::File,
    io::{AsyncBufReadExt, BufReader},
};

#[derive(Debug, Serialize, Deserialize)]
pub struct Edge {
    pub id: String,
    pub source_id: String,
    pub target_id: String,
    pub edge_kind: String,
}

pub async fn list_edges(Query(params): Query<HashMap<String, String>>) -> Json<Vec<Edge>> {
    let src = params.get("source_id");
    let dst = params.get("target_id");
    let limit: usize = params
        .get("limit")
        .and_then(|s| s.parse().ok())
        .unwrap_or(250);

    let path = edges_path();
    let file = match File::open(&path).await {
        Ok(f) => f,
        Err(_) => return Json(Vec::new()),
    };
    let mut lines = BufReader::new(file).lines();

    let mut out = Vec::with_capacity(limit.min(1024));
    while let Ok(Some(line)) = lines.next_line().await {
        if out.len() >= limit {
            break;
        }

        let edge: Edge = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(_) => continue,
        };

        if let Some(s) = src {
            if edge.source_id != *s {
                continue;
            }
        }
        if let Some(d) = dst {
            if edge.target_id != *d {
                continue;
            }
        }

        out.push(edge);
    }

    Json(out)
}

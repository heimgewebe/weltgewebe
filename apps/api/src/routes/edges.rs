use axum::{extract::Query, Json};
use serde::{Deserialize, Serialize};
use std::{collections::HashMap, env, path::PathBuf};
use tokio::{
    fs::File,
    io::{AsyncBufReadExt, BufReader},
};

fn in_dir() -> PathBuf {
    env::var("GEWEBE_IN_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(".gewebe/in"))
}
fn edges_path() -> PathBuf {
    in_dir().join("demo.edges.jsonl")
}

#[derive(Serialize, Deserialize, Debug)]
pub struct Edge {
    pub id: String,
    pub source_type: String,
    pub source_id: String,
    pub target_type: String,
    pub target_id: String,
    pub edge_kind: String,
    pub created_at: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expires_at: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub note: Option<String>,
}

pub async fn list_edges(Query(params): Query<HashMap<String, String>>) -> Json<Vec<Edge>> {
    let source_id = params.get("source_id");
    let target_id = params.get("target_id");
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

        if let Some(s) = source_id {
            if edge.source_id != *s {
                continue;
            }
        }
        if let Some(t) = target_id {
            if edge.target_id != *t {
                continue;
            }
        }

        out.push(edge);
    }

    Json(out)
}

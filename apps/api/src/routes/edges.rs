use axum::{extract::Query, Json};
use serde_json::Value;
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

pub async fn list_edges(Query(params): Query<HashMap<String, String>>) -> Json<Vec<Value>> {
    let src = params.get("src");
    let dst = params.get("dst");
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
        let v: Value = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(_) => continue,
        };

        if let Some(s) = src {
            if v.get("src").and_then(|x| x.as_str()) != Some(s.as_str()) {
                continue;
            }
        }
        if let Some(d) = dst {
            if v.get("dst").and_then(|x| x.as_str()) != Some(d.as_str()) {
                continue;
            }
        }

        out.push(v);
    }

    Json(out)
}

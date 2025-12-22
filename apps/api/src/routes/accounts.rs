use axum::{extract::Query, http::StatusCode, Json};
use serde::Serialize;
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

fn accounts_path() -> PathBuf {
    in_dir().join("demo.accounts.jsonl")
}

#[derive(Serialize)]
pub struct Location {
    pub lat: f64,
    pub lon: f64,
}

#[derive(Serialize)]
pub struct Account {
    pub id: String,
    #[serde(rename = "type")]
    pub kind: String,
    pub title: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub summary: Option<String>,
    pub location: Location,
    pub visibility: String,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub tags: Vec<String>,
}

fn map_json_to_account(v: &Value) -> Option<Account> {
    let id = v
        .get("id")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())?;

    let kind = v
        .get("type")
        .and_then(|v| v.as_str())
        .unwrap_or("garnrolle")
        .to_string();

    let title = v
        .get("title")
        .and_then(|v| v.as_str())
        .unwrap_or("Untitled")
        .to_string();

    let summary = v
        .get("summary")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());

    let location = v.get("location")?;
    let lon = location
        .get("lon")
        .and_then(|val| val.as_f64().or_else(|| val.as_str()?.parse().ok()))?;
    let lat = location
        .get("lat")
        .and_then(|val| val.as_f64().or_else(|| val.as_str()?.parse().ok()))?;

    let visibility = v
        .get("visibility")
        .and_then(|v| v.as_str())
        .unwrap_or("public")
        .to_string();

    let tags = v
        .get("tags")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|x| x.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default();

    Some(Account {
        id,
        kind,
        title,
        summary,
        location: Location { lat, lon },
        visibility,
        tags,
    })
}

pub async fn list_accounts(
    Query(params): Query<HashMap<String, String>>,
) -> Result<Json<Vec<Account>>, StatusCode> {
    let limit: usize = params
        .get("limit")
        .and_then(|s| s.parse().ok())
        .unwrap_or(100);

    let path = accounts_path();
    let file = match File::open(&path).await {
        Ok(f) => f,
        Err(e) => {
            tracing::warn!(
                ?path,
                ?e,
                "demo.accounts.jsonl not found or unreadable; returning empty list"
            );
            return Ok(Json(Vec::new()));
        }
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

        if let Some(account) = map_json_to_account(&v) {
            out.push(account);
        }
    }

    Ok(Json(out))
}

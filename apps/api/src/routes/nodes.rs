use axum::{extract::Query, http::StatusCode, Json};
use serde::Serialize;
use serde_json::Value;
use std::{collections::HashMap, env, path::PathBuf};
use tokio::{
    fs::File,
    io::{AsyncBufReadExt, BufReader},
};

fn in_dir() -> PathBuf {
    // Überschreibbar in Tests via GEWEBE_IN_DIR
    env::var("GEWEBE_IN_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(".gewebe/in"))
}

fn nodes_path() -> PathBuf {
    in_dir().join("demo.nodes.jsonl")
}

#[derive(Clone, Copy, Debug)]
struct BBox {
    min_lng: f64,
    min_lat: f64,
    max_lng: f64,
    max_lat: f64,
}

#[derive(Serialize)]
pub struct Location {
    pub lat: f64,
    pub lon: f64,
}

#[derive(Serialize)]
pub struct Node {
    pub id: String,
    pub kind: String,
    pub title: String,
    pub created_at: String,
    pub updated_at: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub summary: Option<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub tags: Vec<String>,
    pub location: Location,
}

fn parse_bbox(s: &str) -> Option<BBox> {
    let parts: Vec<_> = s.split(',').collect();
    let (lng1, lat1, lng2, lat2) = match parts.as_slice() {
        [lng1, lat1, lng2, lat2] => (
            lng1.trim().parse::<f64>().ok()?,
            lat1.trim().parse::<f64>().ok()?,
            lng2.trim().parse::<f64>().ok()?,
            lat2.trim().parse::<f64>().ok()?,
        ),
        _ => return None,
    };

    Some(BBox {
        min_lng: lng1.min(lng2),
        min_lat: lat1.min(lat2),
        max_lng: lng1.max(lng2),
        max_lat: lat1.max(lat2),
    })
}

fn point_in_bbox(lng: f64, lat: f64, bb: &BBox) -> bool {
    lng >= bb.min_lng && lng <= bb.max_lng && lat >= bb.min_lat && lat <= bb.max_lat
}

fn map_json_to_node(v: &Value) -> Option<Node> {
    let id = v
        .get("id")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())?;

    // Parse location object with explicit error handling
    let location = v.get("location")?;
    let lon = location.get("lon").and_then(|val| val.as_f64())?;
    let lat = location.get("lat").and_then(|val| val.as_f64())?;

    let title = v
        .get("title")
        .and_then(|v| v.as_str())
        .unwrap_or("Untitled")
        .to_string();
    let kind = v
        .get("kind")
        .and_then(|v| v.as_str())
        .unwrap_or("Unknown")
        .to_string();
    let updated_at = v
        .get("updated_at")
        .and_then(|v| v.as_str())
        .unwrap_or("1970-01-01T00:00:00Z")
        .to_string();
    let created_at = v
        .get("created_at")
        .and_then(|v| v.as_str())
        .unwrap_or(&updated_at)
        .to_string();

    let summary = v
        .get("summary")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());

    let tags = v
        .get("tags")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|x| x.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default();

    Some(Node {
        id,
        kind,
        title,
        created_at,
        updated_at,
        summary,
        tags,
        location: Location { lat, lon },
    })
}

pub async fn list_nodes(
    Query(params): Query<HashMap<String, String>>,
) -> Result<Json<Vec<Node>>, StatusCode> {
    let bbox = match params.get("bbox") {
        Some(raw_bbox) => Some(parse_bbox(raw_bbox).ok_or(StatusCode::BAD_REQUEST)?),
        None => None,
    };
    let limit: usize = params
        .get("limit")
        .and_then(|s| s.parse().ok())
        .unwrap_or(100);

    let path = nodes_path();
    let file = match File::open(&path).await {
        Ok(f) => f,
        Err(_) => return Ok(Json(Vec::new())), // robust: leer zurückgeben
    };
    let mut lines = BufReader::new(file).lines();

    let mut out = Vec::with_capacity(limit.min(1024));
    while let Ok(Some(line)) = lines.next_line().await {
        if out.len() >= limit {
            break;
        }
        let v: Value = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(_) => continue, // fehlerhafte Zeilen überspringen
        };

        if let Some(node) = map_json_to_node(&v) {
            if let Some(bb) = bbox {
                if !point_in_bbox(node.location.lon, node.location.lat, &bb) {
                    continue;
                }
            }
            out.push(node);
        }
    }

    Ok(Json(out))
}

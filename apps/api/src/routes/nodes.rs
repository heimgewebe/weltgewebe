use crate::utils::nodes_path;
use axum::{
    extract::{Path, Query},
    http::StatusCode,
    Json,
};
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use tokio::{
    fs::{File, OpenOptions},
    io::{AsyncBufReadExt, AsyncWriteExt, BufReader, BufWriter},
};
use uuid::Uuid;

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
    #[serde(skip_serializing_if = "Option::is_none")]
    pub info: Option<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub tags: Vec<String>,
    pub location: Location,
}

fn deserialize_some<'de, T, D>(deserializer: D) -> Result<Option<T>, D::Error>
where
    T: Deserialize<'de>,
    D: Deserializer<'de>,
{
    Deserialize::deserialize(deserializer).map(Some)
}

#[derive(Deserialize)]
pub struct UpdateNode {
    #[serde(default, deserialize_with = "deserialize_some")]
    pub info: Option<Option<String>>,
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
    let lon = location
        .get("lon")
        .and_then(|val| val.as_f64().or_else(|| val.as_str()?.parse().ok()))?;
    let lat = location
        .get("lat")
        .and_then(|val| val.as_f64().or_else(|| val.as_str()?.parse().ok()))?;

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
    let created_at_raw = v.get("created_at").and_then(|v| v.as_str());
    let updated_at_raw = v.get("updated_at").and_then(|v| v.as_str());
    let default_timestamp = "1970-01-01T00:00:00Z";

    let created_at = created_at_raw
        .or(updated_at_raw)
        .unwrap_or(default_timestamp)
        .to_string();
    let updated_at = updated_at_raw
        .or(created_at_raw)
        .unwrap_or(default_timestamp)
        .to_string();

    let summary = v
        .get("summary")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());

    let info = v
        .get("info")
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
        info,
        tags,
        location: Location { lat, lon },
    })
}

pub async fn get_node(Path(id): Path<String>) -> Result<Json<Node>, StatusCode> {
    let path = nodes_path();
    let file = File::open(&path).await.map_err(|_| StatusCode::NOT_FOUND)?;
    let mut lines = BufReader::new(file).lines();

    while let Ok(Some(line)) = lines.next_line().await {
        let v: Value =
            serde_json::from_str(&line).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        if let Some(node) = map_json_to_node(&v) {
            if node.id == id {
                return Ok(Json(node));
            }
        }
    }

    Err(StatusCode::NOT_FOUND)
}

pub async fn patch_node(
    Path(id): Path<String>,
    Json(payload): Json<UpdateNode>,
) -> Result<Json<Node>, StatusCode> {
    let path = nodes_path();
    // Read all lines
    let file = File::open(&path)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let mut lines = BufReader::new(file).lines();
    let mut all_lines = Vec::new();
    let mut found_node: Option<Node> = None;
    let mut updated = false;

    while let Ok(Some(line)) = lines.next_line().await {
        let mut v: Value =
            serde_json::from_str(&line).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        let current_id = v
            .get("id")
            .and_then(|s| s.as_str())
            .unwrap_or("")
            .to_string();

        if current_id == id {
            // Update the field
            let mut has_changes = false;
            match &payload.info {
                Some(Some(s)) => {
                    v["info"] = Value::String(s.clone());
                    has_changes = true;
                }
                Some(None) => {
                    v["info"] = Value::Null;
                    has_changes = true;
                }
                None => {} // No-op
            }

            // Clean up old "steckbrief" field if it exists (migration logic)
            if let Some(obj) = v.as_object_mut() {
                if obj.remove("steckbrief").is_some() {
                    has_changes = true;
                }
            }

            // Update updated_at only if we actually changed something
            if has_changes {
                let now = chrono::Utc::now().to_rfc3339();
                v["updated_at"] = Value::String(now);
            }

            if let Some(n) = map_json_to_node(&v) {
                found_node = Some(n);
            }
            all_lines
                .push(serde_json::to_string(&v).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?);
            updated = true;
        } else {
            all_lines.push(line);
        }
    }

    if !updated {
        return Err(StatusCode::NOT_FOUND);
    }

    // Write back
    // Use a unique temporary file + rename for atomic writes to prevent data corruption and race conditions
    let mut tmp_path = path.clone();
    if let Some(filename) = tmp_path.file_name() {
        let mut new_filename = filename.to_os_string();
        new_filename.push(format!(".tmp.{}", Uuid::new_v4()));
        tmp_path.set_file_name(new_filename);
    } else {
        return Err(StatusCode::INTERNAL_SERVER_ERROR);
    }

    let file = OpenOptions::new()
        .write(true)
        .create(true)
        .truncate(true)
        .open(&tmp_path)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut writer = BufWriter::new(file);

    for line in all_lines {
        writer
            .write_all(line.as_bytes())
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        writer
            .write_all(b"\n")
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    }
    writer
        .flush()
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Ensure durability
    let file = writer.into_inner();
    file.sync_all()
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    tokio::fs::rename(&tmp_path, &path)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    found_node
        .map(Json)
        .ok_or(StatusCode::INTERNAL_SERVER_ERROR)
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

        // Optimization: Check BBox *before* expensive mapping (string cloning)
        if let Some(bb) = bbox {
            // Access location directly from Value (cheap reference access)
            if let Some(loc) = v.get("location") {
                let lat = loc
                    .get("lat")
                    .and_then(|val| val.as_f64().or_else(|| val.as_str()?.parse().ok()));
                let lon = loc
                    .get("lon")
                    .and_then(|val| val.as_f64().or_else(|| val.as_str()?.parse().ok()));

                if let (Some(lat), Some(lon)) = (lat, lon) {
                    if !point_in_bbox(lon, lat, &bb) {
                        continue;
                    }
                } else {
                    // Invalid location data, skip
                    continue;
                }
            } else {
                continue;
            }
        }

        if let Some(node) = map_json_to_node(&v) {
            // Note: BBox check already done above for optimization
            out.push(node);
        }
    }

    Ok(Json(out))
}

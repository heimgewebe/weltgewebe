use crate::state::ApiState;
use crate::utils::nodes_path;
use axum::{
    extract::{Path, Query, State},
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

#[derive(Serialize, Clone)]
pub struct Location {
    pub lat: f64,
    pub lon: f64,
}

#[derive(Serialize, Clone)]
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

/// Loads nodes from the JSONL file into memory.
///
/// **Architecture Note:**
/// The in-memory cache populated by this function is considered the "Source of Truth"
/// for read operations during the API process lifetime.
/// - The file is strictly used for persistence.
/// - `patch_node` updates both the file (for durability) and this cache (for consistency).
/// - External modifications to the nodes file (e.g. via deployment or manual edit)
///   will NOT be detected until the API process is restarted.
pub async fn load_nodes() -> Vec<Node> {
    let start = std::time::Instant::now();
    let path = nodes_path();
    let file = match File::open(&path).await {
        Ok(f) => f,
        Err(e) => {
            tracing::warn!(?path, ?e, "Failed to open nodes file, returning empty list");
            return Vec::new();
        }
    };
    let mut lines = BufReader::new(file).lines();
    let mut nodes = Vec::new();

    while let Ok(Some(line)) = lines.next_line().await {
        let v: Value = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(_) => continue,
        };
        if let Some(node) = map_json_to_node(&v) {
            nodes.push(node);
        }
    }

    let load_ms = start.elapsed().as_millis();
    let file_size_bytes = tokio::fs::metadata(&path)
        .await
        .map(|m| m.len())
        .unwrap_or(0);

    tracing::info!(
        count = nodes.len(),
        load_ms,
        file_size_bytes,
        ?path,
        "Loaded nodes into memory cache"
    );
    nodes
}

pub async fn get_node(
    State(state): State<ApiState>,
    Path(id): Path<String>,
) -> Result<Json<Node>, StatusCode> {
    let nodes = state.nodes.read().await;
    nodes
        .iter()
        .find(|n| n.id == id)
        .cloned()
        .map(Json)
        .ok_or(StatusCode::NOT_FOUND)
}

pub async fn patch_node(
    State(state): State<ApiState>,
    Path(id): Path<String>,
    Json(payload): Json<UpdateNode>,
) -> Result<Json<Node>, StatusCode> {
    // Serialize PATCH commits (per-process): block node reads during file+cache commit to guarantee read-your-writes within this instance.
    let start_wait = std::time::Instant::now();
    let mut nodes_guard = state.nodes.write().await;
    let lock_contention_ms = start_wait.elapsed().as_millis();
    let start_hold = std::time::Instant::now();

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

    let start_persist = std::time::Instant::now();

    // Inner function to handle writing logic so we can catch errors and cleanup
    let write_result = async {
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
        Ok::<(), StatusCode>(())
    }
    .await;

    if let Err(e) = write_result {
        // Cleanup temp file on failure
        let _ = tokio::fs::remove_file(&tmp_path).await;
        return Err(e);
    }

    if let Err(_e) = tokio::fs::rename(&tmp_path, &path).await {
        // Cleanup temp file if rename fails
        let _ = tokio::fs::remove_file(&tmp_path).await;
        return Err(StatusCode::INTERNAL_SERVER_ERROR);
    }

    let persist_ms = start_persist.elapsed().as_millis();

    // Update in-memory cache
    if let Some(ref updated_node) = found_node {
        if let Some(idx) = nodes_guard.iter().position(|n| n.id == id) {
            nodes_guard[idx] = updated_node.clone();
        } else {
            nodes_guard.push(updated_node.clone());
        }
    }

    // Update metrics
    state
        .metrics
        .set_nodes_cache_count(nodes_guard.len() as i64);

    let lock_hold_ms = start_hold.elapsed().as_millis();
    tracing::info!(
        persist_ms,
        lock_hold_ms,
        lock_contention_ms,
        node_id = %id,
        patched = found_node.is_some(),
        "Node patch attempt finished"
    );

    found_node
        .map(Json)
        .ok_or(StatusCode::INTERNAL_SERVER_ERROR)
}

pub async fn list_nodes(
    State(state): State<ApiState>,
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

    let nodes = state.nodes.read().await;

    let out: Vec<Node> = nodes
        .iter()
        .filter(|node| {
            if let Some(bb) = &bbox {
                point_in_bbox(node.location.lon, node.location.lat, bb)
            } else {
                true
            }
        })
        .take(limit)
        .cloned()
        .collect();

    Ok(Json(out))
}

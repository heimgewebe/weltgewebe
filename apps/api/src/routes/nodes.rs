use super::{
    domain_write_guard::{
        reject_node_create_unless_writable, reject_node_patch_unless_writable,
        DOMAIN_READ_SOURCE_READ_ONLY, DOMAIN_READ_SOURCE_READ_ONLY_MESSAGE,
    },
    edges::{delete_edges_referencing_node_jsonl, edge_create_persist_lock},
    query::{
        cursor_page, parse_cursor_params, parse_usize_param, validate_cursor_limit, ListResponse,
        MAX_PAGE_SIZE,
    },
};
use crate::config::{DomainEdgeWriteSource, DomainNodeWriteSource};
use crate::domain_db::{
    delete_node_with_edges_in_postgres, insert_domain_node, patch_node_in_postgres,
    replace_node_in_postgres, CreateOperationKey, CreateWriteOutcome, NodeCreateError,
    NodePatchInput, NodeWriteError,
};
use crate::middleware::auth::AuthContext;
use crate::state::{ApiState, OrderedCache};
use crate::utils::nodes_path;
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::{IntoResponse, Response},
    Extension, Json,
};
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use tokio::{
    fs::{File, OpenOptions},
    io::{
        AsyncBufReadExt, AsyncReadExt, AsyncSeekExt, AsyncWriteExt, BufReader, BufWriter, SeekFrom,
    },
};
use uuid::Uuid;

pub enum PatchNodeError {
    Status(StatusCode),
    DomainReadSourceReadOnly,
    Message(StatusCode, String),
}

impl IntoResponse for PatchNodeError {
    fn into_response(self) -> Response {
        match self {
            PatchNodeError::Status(status) => status.into_response(),
            PatchNodeError::DomainReadSourceReadOnly => {
                let body = format!(
                    "{DOMAIN_READ_SOURCE_READ_ONLY}: {DOMAIN_READ_SOURCE_READ_ONLY_MESSAGE}"
                );
                (StatusCode::CONFLICT, body).into_response()
            }
            PatchNodeError::Message(status, body) => (status, body).into_response(),
        }
    }
}

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
    /// Human-readable address. Optional for backward compatibility with
    /// records persisted before this field existed; `POST /nodes` requires it.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub address: Option<String>,
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

/// Lightweight struct for fast-path ID checking during node updates.
///
/// Used to check if a line matches the target node ID without fully parsing
/// the entire JSON `Value`. This avoids full deserialization for non-matching
/// lines (the vast majority during PATCH) and keeps memory usage O(1).
#[derive(Deserialize)]
struct IdOnly {
    id: Option<String>,
}

#[derive(Deserialize)]
struct LocationDto {
    #[serde(deserialize_with = "deserialize_f64_or_string")]
    lat: f64,
    #[serde(deserialize_with = "deserialize_f64_or_string")]
    lon: f64,
}

const DEFAULT_KIND: &str = "Unknown";
const DEFAULT_TITLE: &str = "Untitled";

#[derive(Deserialize)]
struct NodeDto {
    id: String,
    #[serde(default, deserialize_with = "deserialize_opt_string_loose")]
    kind: Option<String>,
    #[serde(default, deserialize_with = "deserialize_opt_string_loose")]
    title: Option<String>,
    #[serde(default, deserialize_with = "deserialize_opt_string_loose")]
    created_at: Option<String>,
    #[serde(default, deserialize_with = "deserialize_opt_string_loose")]
    updated_at: Option<String>,
    #[serde(default, deserialize_with = "deserialize_opt_string_loose")]
    summary: Option<String>,
    #[serde(default, deserialize_with = "deserialize_opt_string_loose")]
    info: Option<String>,
    #[serde(default, deserialize_with = "deserialize_tags_loose")]
    tags: Vec<String>,
    #[serde(default, deserialize_with = "deserialize_opt_string_loose")]
    address: Option<String>,
    location: LocationDto,
}

fn deserialize_opt_string_loose<'de, D>(deserializer: D) -> Result<Option<String>, D::Error>
where
    D: Deserializer<'de>,
{
    let v = Option::<Value>::deserialize(deserializer)?;
    Ok(v.and_then(|x| x.as_str().map(|s| s.to_string())))
}

fn deserialize_tags_loose<'de, D>(deserializer: D) -> Result<Vec<String>, D::Error>
where
    D: Deserializer<'de>,
{
    let v = Option::<Value>::deserialize(deserializer)?;
    match v {
        Some(Value::Array(arr)) => Ok(arr
            .into_iter()
            .filter_map(|x| x.as_str().map(|s| s.to_string()))
            .collect()),
        _ => Ok(Vec::new()),
    }
}

fn deserialize_f64_or_string<'de, D>(deserializer: D) -> Result<f64, D::Error>
where
    D: Deserializer<'de>,
{
    struct F64OrStringVisitor;

    impl<'de> serde::de::Visitor<'de> for F64OrStringVisitor {
        type Value = f64;

        fn expecting(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
            formatter.write_str("a float or a string containing a float")
        }

        fn visit_f64<E>(self, v: f64) -> Result<Self::Value, E>
        where
            E: serde::de::Error,
        {
            Ok(v)
        }

        fn visit_i64<E>(self, v: i64) -> Result<Self::Value, E>
        where
            E: serde::de::Error,
        {
            Ok(v as f64)
        }

        fn visit_u64<E>(self, v: u64) -> Result<Self::Value, E>
        where
            E: serde::de::Error,
        {
            Ok(v as f64)
        }

        fn visit_str<E>(self, v: &str) -> Result<Self::Value, E>
        where
            E: serde::de::Error,
        {
            v.parse::<f64>().map_err(serde::de::Error::custom)
        }
    }

    deserializer.deserialize_any(F64OrStringVisitor)
}

impl From<NodeDto> for Node {
    fn from(dto: NodeDto) -> Self {
        let default_timestamp = "1970-01-01T00:00:00Z";

        let created_at = dto
            .created_at
            .as_deref()
            .or(dto.updated_at.as_deref())
            .unwrap_or(default_timestamp)
            .to_string();
        let updated_at = dto
            .updated_at
            .as_deref()
            .or(dto.created_at.as_deref())
            .unwrap_or(default_timestamp)
            .to_string();

        Node {
            id: dto.id,
            kind: dto.kind.unwrap_or_else(|| DEFAULT_KIND.to_string()),
            title: dto.title.unwrap_or_else(|| DEFAULT_TITLE.to_string()),
            created_at,
            updated_at,
            summary: dto.summary,
            info: dto.info,
            tags: dto.tags,
            address: dto.address,
            location: Location {
                lat: dto.location.lat,
                lon: dto.location.lon,
            },
        }
    }
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
        .unwrap_or(DEFAULT_TITLE)
        .to_string();
    let kind = v
        .get("kind")
        .and_then(|v| v.as_str())
        .unwrap_or(DEFAULT_KIND)
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

    let address = v
        .get("address")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());

    Some(Node {
        id,
        kind,
        title,
        created_at,
        updated_at,
        summary,
        info,
        tags,
        address,
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
pub async fn load_nodes() -> OrderedCache<Node> {
    let start = std::time::Instant::now();
    let path = nodes_path();
    let file = match File::open(&path).await {
        Ok(f) => f,
        Err(e) => {
            tracing::warn!(
                ?path,
                ?e,
                "Failed to open nodes file, returning empty cache"
            );
            return OrderedCache::new();
        }
    };
    let mut lines = BufReader::new(file).lines();
    let mut nodes = OrderedCache::new();
    let mut duplicates_count = 0;
    let mut skipped_count = 0;

    while let Ok(Some(line)) = lines.next_line().await {
        let dto: NodeDto = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(_) => {
                skipped_count += 1;
                continue;
            }
        };
        let node: Node = dto.into();
        if nodes.insert(node.id.clone(), node) {
            // Last-write-wins: Overwrite existing node
            duplicates_count += 1;
        }
    }

    let load_ms = start.elapsed().as_millis();
    let file_size_bytes = tokio::fs::metadata(&path)
        .await
        .map(|m| m.len())
        .unwrap_or(0);

    if skipped_count > 0 {
        tracing::warn!(
            event = "nodes.load.skipped",
            skipped_count,
            ?path,
            "Skipped nodes due to parse errors during load"
        );
    }

    tracing::info!(
        count = nodes.len(),
        duplicates_count,
        skipped_count,
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
        .get(&id)
        .cloned()
        .map(Json)
        .ok_or(StatusCode::NOT_FOUND)
}

/// Append a single node record as a JSONL line. Durability via fsync.
/// Callers MUST hold `state.nodes_persist` to serialize writes.
///
/// If the existing file does not end with a newline (e.g. a hand-written or
/// truncated fixture), a separator newline is written first so the previous
/// record and the new record are never glued into one unparseable line.
async fn append_node_line(record: &Value) -> std::io::Result<()> {
    let path = nodes_path();
    if let Some(parent) = path.parent() {
        tokio::fs::create_dir_all(parent).await?;
    }
    let line = serde_json::to_string(record)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;

    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .read(true)
        .open(&path)
        .await?;

    let len = file.metadata().await?.len();
    if len > 0 {
        file.seek(SeekFrom::Start(len - 1)).await?;
        let mut last = [0_u8; 1];
        file.read_exact(&mut last).await?;
        if last[0] != b'\n' {
            file.write_all(b"\n").await?;
        }
    }

    file.write_all(line.as_bytes()).await?;
    file.write_all(b"\n").await?;
    file.flush().await?;
    file.sync_all().await?;
    Ok(())
}

const CREATE_ACTOR_KEY: &str = "_create_actor_id";
const CREATE_OPERATION_KEY: &str = "_create_operation_id";

fn add_create_operation_metadata(record: &mut Value, operation: Option<&CreateOperationKey>) {
    let Some(operation) = operation else {
        return;
    };
    let object = record
        .as_object_mut()
        .expect("canonical node create record must be an object");
    object.insert(
        CREATE_ACTOR_KEY.to_string(),
        Value::String(operation.actor_id.clone()),
    );
    object.insert(
        CREATE_OPERATION_KEY.to_string(),
        Value::String(operation.operation_id.clone()),
    );
}

/// Find an earlier durable JSONL result for one account-scoped operation.
/// Unknown metadata remains invisible to the public `Node` projection.
async fn find_node_by_operation(operation: &CreateOperationKey) -> std::io::Result<Option<Node>> {
    let path = nodes_path();
    let file = match File::open(&path).await {
        Ok(file) => file,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error),
    };
    let mut lines = BufReader::new(file).lines();
    let mut found = None;
    while let Some(line) = lines.next_line().await? {
        let value: Value = match serde_json::from_str(&line) {
            Ok(value) => value,
            Err(_) => continue,
        };
        let actor_matches = value.get(CREATE_ACTOR_KEY).and_then(Value::as_str)
            == Some(operation.actor_id.as_str());
        let operation_matches = value.get(CREATE_OPERATION_KEY).and_then(Value::as_str)
            == Some(operation.operation_id.as_str());
        if !actor_matches || !operation_matches {
            continue;
        }
        if found.is_some() {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "duplicate node create operation metadata",
            ));
        }
        let node = map_json_to_node(&value).ok_or_else(|| {
            std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "idempotent node record cannot be projected",
            )
        })?;
        found = Some(node);
    }
    Ok(found)
}

fn node_matches_create(node: &Node, expected: &node_create::ValidatedCreateNode) -> bool {
    node.title == expected.title
        && node.kind == expected.kind
        && node.address.as_deref() == Some(expected.address.as_str())
        && node.location.lat == expected.lat
        && node.location.lon == expected.lon
        && node.summary == expected.summary
        && node.info == expected.info
        && node.tags == expected.tags
}

/// Build the in-memory `Node` and its canonical JSONL record from a validated
/// create request plus the server-owned `id` and timestamp.
fn build_node_record(
    validated: node_create::ValidatedCreateNode,
    id: String,
    now: String,
) -> (Node, Value) {
    let node = Node {
        id,
        kind: validated.kind,
        title: validated.title,
        created_at: now.clone(),
        updated_at: now,
        summary: validated.summary,
        info: validated.info,
        tags: validated.tags,
        address: Some(validated.address),
        location: Location {
            lat: validated.lat,
            lon: validated.lon,
        },
    };

    let mut record = serde_json::Map::new();
    record.insert("id".into(), json!(node.id));
    record.insert("kind".into(), json!(node.kind));
    record.insert("title".into(), json!(node.title));
    record.insert("created_at".into(), json!(node.created_at));
    record.insert("updated_at".into(), json!(node.updated_at));
    if let Some(summary) = &node.summary {
        record.insert("summary".into(), json!(summary));
    }
    if let Some(info) = &node.info {
        record.insert("info".into(), json!(info));
    }
    if !node.tags.is_empty() {
        record.insert("tags".into(), json!(node.tags));
    }
    if let Some(address) = &node.address {
        record.insert("address".into(), json!(address));
    }
    record.insert(
        "location".into(),
        json!({ "lat": node.location.lat, "lon": node.location.lon }),
    );

    (node, Value::Object(record))
}

/// Map a `NodeCreateValidationError` onto a stable message for the 400 body.
fn node_create_error_message(err: &node_create::NodeCreateValidationError) -> String {
    use node_create::NodeCreateValidationError as E;
    match err {
        E::MissingOrEmptyField(field) => format!("missing or empty field: {field}"),
        E::FieldTooLong { field, max } => format!("{field} exceeds the maximum length of {max}"),
        E::InvalidCoordinate { field } => {
            format!("{field} must be a finite number within world bounds")
        }
        E::InvalidUuid { field, value } => format!("invalid UUID for {field}: {value}"),
        E::TooManyTags { max } => format!("tags exceeds the maximum count of {max}"),
    }
}

/// Create a node.
///
/// Write path: write gate ([`reject_node_create_unless_writable`]) -> contract
/// validation -> server-generated `id` / `created_at` / `updated_at` ->
/// persistence via the configured node write source -> cache insert. A new
/// durable write returns 201; an identical durable operation replay returns the
/// existing node with 200. Failed writes never leave a phantom cache entry.
///
/// JSONL (default): durable JSONL append (fsync), serialized against
/// concurrent node persistence via `state.nodes_persist`.
/// PostgreSQL (opt-in via `WELTGEWEBE_DOMAIN_NODE_WRITE_SOURCE=postgres`,
/// requires the PostgreSQL read source): one transaction, a per-operation
/// advisory lock when `operation_id` is present, an account-scoped partial
/// unique index, and the final INSERT. No dual-write: JSONL mode never touches
/// PostgreSQL, PostgreSQL mode never appends JSONL.
pub async fn create_node(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
    Json(payload): Json<Value>,
) -> Result<(StatusCode, Json<Node>), (StatusCode, String)> {
    reject_node_create_unless_writable(&state)?;

    // Deserialize manually (instead of extracting Json<CreateNodeRequest>) so
    // contract violations (unknown fields, missing required fields and explicit
    // nulls) map to a deterministic 400 rather than an extractor-shaped 422.
    let request: node_create::CreateNodeRequest = serde_json::from_value(payload).map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("invalid node create request: {e}"),
        )
    })?;

    let validated = request.validate().map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!(
                "invalid node create request: {}",
                node_create_error_message(&e)
            ),
        )
    })?;
    let semantic_request = validated.clone();

    let operation = match validated.operation_id.as_ref() {
        Some(operation_id) => {
            let actor_id = auth.account_id.clone().ok_or_else(|| {
                (
                    StatusCode::UNAUTHORIZED,
                    "authenticated account context missing".to_string(),
                )
            })?;
            Some(CreateOperationKey {
                actor_id,
                operation_id: operation_id.clone(),
            })
        }
        None => None,
    };

    let id = Uuid::new_v4().to_string();
    let now = chrono::Utc::now().to_rfc3339();
    let (node, mut record) = build_node_record(validated, id.clone(), now);
    add_create_operation_metadata(&mut record, operation.as_ref());

    match state.config.domain_node_write_source {
        DomainNodeWriteSource::Jsonl => {
            // Serialize operation lookup and append so two retries cannot both
            // decide that the durable result is absent.
            let _persist_guard = state.nodes_persist.lock().await;

            if let Some(operation) = operation.as_ref() {
                let existing = find_node_by_operation(operation).await.map_err(|error| {
                    tracing::error!(%error, "failed to inspect node create operation");
                    (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        "failed to inspect node create operation".to_string(),
                    )
                })?;
                if let Some(existing) = existing {
                    if !node_matches_create(&existing, &semantic_request) {
                        return Err((
                            StatusCode::CONFLICT,
                            "node operation id was already used for different data".to_string(),
                        ));
                    }
                    let mut nodes = state.nodes.write().await;
                    nodes.insert(existing.id.clone(), existing.clone());
                    state.metrics.set_nodes_cache_count(nodes.len() as i64);
                    return Ok((StatusCode::OK, Json(existing)));
                }
            }

            // The id is server-generated, but keep the cache collision check
            // as a fail-closed invariant and for directly seeded test states.
            {
                let nodes = state.nodes.read().await;
                if nodes.get(&id).is_some() {
                    return Err((StatusCode::CONFLICT, "node id already exists".to_string()));
                }
            }

            // Only a successful durable append may be reflected in cache.
            if let Err(e) = append_node_line(&record).await {
                tracing::error!(error = %e, "failed to append node to JSONL");
                return Err((
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "failed to persist node".to_string(),
                ));
            }

            let mut nodes = state.nodes.write().await;
            nodes.insert(id.clone(), node.clone());
            state.metrics.set_nodes_cache_count(nodes.len() as i64);
        }
        DomainNodeWriteSource::Postgres => {
            // PostgreSQL mode never appends JSONL. The helper performs the
            // operation lookup and insert in one transaction.
            {
                let nodes = state.nodes.read().await;
                if nodes.get(&id).is_some() {
                    return Err((StatusCode::CONFLICT, "node id already exists".to_string()));
                }
            }

            // Startup validation normally guarantees this pool; missing
            // state fails closed rather than falling back to JSONL.
            let pool = state.db_pool.as_ref().ok_or_else(|| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "PostgreSQL pool unavailable for node write".to_string(),
                )
            })?;
            match insert_domain_node(pool, &node, operation.as_ref()).await {
                Ok(CreateWriteOutcome::Created) => {}
                Ok(CreateWriteOutcome::Existing(existing)) => {
                    if !node_matches_create(&existing, &semantic_request) {
                        return Err((
                            StatusCode::CONFLICT,
                            "node operation id was already used for different data".to_string(),
                        ));
                    }
                    let mut nodes = state.nodes.write().await;
                    nodes.insert(existing.id.clone(), existing.clone());
                    state.metrics.set_nodes_cache_count(nodes.len() as i64);
                    return Ok((StatusCode::OK, Json(existing)));
                }
                Err(NodeCreateError::DuplicateId) => {
                    return Err((StatusCode::CONFLICT, "node id already exists".to_string()));
                }
                Err(e) => {
                    tracing::error!(error = %e, "failed to insert node into domain_nodes");
                    return Err((
                        StatusCode::INTERNAL_SERVER_ERROR,
                        "failed to persist node".to_string(),
                    ));
                }
            }

            let mut nodes = state.nodes.write().await;
            nodes.insert(id.clone(), node.clone());
            state.metrics.set_nodes_cache_count(nodes.len() as i64);
        }
    }

    tracing::info!(
        event = "node.created",
        node_id = %node.id,
        write_source = ?state.config.domain_node_write_source,
        operation_bound = operation.is_some(),
        "Node created"
    );

    Ok((StatusCode::CREATED, Json(node)))
}

/// Node-create request contract.
///
/// Locks the accepted shape and validation rules of a `POST /nodes` create
/// request. `id`, `created_at`, `updated_at` are server-owned and therefore
/// absent from the request type; combined with `deny_unknown_fields` a client
/// that supplies them gets a deterministic 400 instead of a silently dropped
/// field. `operation_id` may be omitted, but when present must be a non-null
/// UUID and identifies only one account-scoped create action.
mod node_create {
    use serde::{de, Deserialize, Deserializer};
    use uuid::Uuid;

    fn deserialize_optional_non_null_string<'de, D>(
        deserializer: D,
    ) -> Result<Option<String>, D::Error>
    where
        D: Deserializer<'de>,
    {
        Option::<String>::deserialize(deserializer)?
            .map(Some)
            .ok_or_else(|| de::Error::custom("field must not be null"))
    }

    /// Mirrors `contracts/domain/node.schema.json` (`title.maxLength`).
    const NODE_TITLE_MAX_LEN: usize = 200;
    /// Mirrors `contracts/domain/node.schema.json` (`kind.maxLength`).
    const NODE_KIND_MAX_LEN: usize = 100;
    /// Address is not yet part of the JSON Schema's `required` set (older
    /// records may lack it), but `POST /nodes` requires it; 500 chars is a
    /// generous bound for a real-world postal address.
    const NODE_ADDRESS_MAX_LEN: usize = 500;
    /// Mirrors `contracts/domain/node.schema.json` (`summary.maxLength`).
    const NODE_SUMMARY_MAX_LEN: usize = 500;
    /// Mirrors `contracts/domain/node.schema.json` (`info.maxLength`).
    const NODE_INFO_MAX_LEN: usize = 20_000;
    /// Mirrors `contracts/domain/node.schema.json` (`tags.items.maxLength`).
    const NODE_TAG_MAX_LEN: usize = 64;
    /// The domain contract does not cap the number of tags; this bound exists
    /// only to keep a single create request bounded in size (well above any
    /// realistic UI usage).
    const NODE_TAGS_MAX_COUNT: usize = 32;

    #[derive(Debug, Deserialize)]
    #[serde(deny_unknown_fields)]
    pub(super) struct CreateLocation {
        lat: f64,
        lon: f64,
    }

    #[derive(Debug, Deserialize)]
    #[serde(deny_unknown_fields)]
    pub(super) struct CreateNodeRequest {
        title: String,
        kind: String,
        address: String,
        location: CreateLocation,
        #[serde(default)]
        summary: Option<String>,
        #[serde(default)]
        info: Option<String>,
        #[serde(default)]
        tags: Option<Vec<String>>,
        #[serde(default, deserialize_with = "deserialize_optional_non_null_string")]
        operation_id: Option<String>,
    }

    #[derive(Debug, Clone, PartialEq)]
    pub(super) struct ValidatedCreateNode {
        pub(super) title: String,
        pub(super) kind: String,
        pub(super) address: String,
        pub(super) lat: f64,
        pub(super) lon: f64,
        pub(super) summary: Option<String>,
        pub(super) info: Option<String>,
        pub(super) tags: Vec<String>,
        pub(super) operation_id: Option<String>,
    }

    #[derive(Debug, Clone, PartialEq)]
    pub(super) enum NodeCreateValidationError {
        MissingOrEmptyField(&'static str),
        FieldTooLong { field: &'static str, max: usize },
        InvalidCoordinate { field: &'static str },
        InvalidUuid { field: &'static str, value: String },
        TooManyTags { max: usize },
    }

    fn require_non_blank(
        field: &'static str,
        value: &str,
    ) -> Result<(), NodeCreateValidationError> {
        if value.trim().is_empty() {
            return Err(NodeCreateValidationError::MissingOrEmptyField(field));
        }
        Ok(())
    }

    fn require_max_len(
        field: &'static str,
        value: &str,
        max: usize,
    ) -> Result<(), NodeCreateValidationError> {
        if value.chars().count() > max {
            return Err(NodeCreateValidationError::FieldTooLong { field, max });
        }
        Ok(())
    }

    fn require_world_coordinate(
        field: &'static str,
        value: f64,
        min: f64,
        max: f64,
    ) -> Result<(), NodeCreateValidationError> {
        if !value.is_finite() || value < min || value > max {
            return Err(NodeCreateValidationError::InvalidCoordinate { field });
        }
        Ok(())
    }

    impl CreateNodeRequest {
        /// Validate into a `ValidatedCreateNode` without mutating values
        /// beyond trimming required string fields. Order: (1) required fields
        /// non-blank, (2) required field max lengths, (3) coordinates finite
        /// and within world bounds, (4) optional fields (summary/info/tags)
        /// when present.
        pub(super) fn validate(self) -> Result<ValidatedCreateNode, NodeCreateValidationError> {
            require_non_blank("title", &self.title)?;
            require_non_blank("kind", &self.kind)?;
            require_non_blank("address", &self.address)?;

            let title = self.title.trim().to_string();
            let kind = self.kind.trim().to_string();
            let address = self.address.trim().to_string();

            require_max_len("title", &title, NODE_TITLE_MAX_LEN)?;
            require_max_len("kind", &kind, NODE_KIND_MAX_LEN)?;
            require_max_len("address", &address, NODE_ADDRESS_MAX_LEN)?;

            require_world_coordinate("location.lat", self.location.lat, -90.0, 90.0)?;
            require_world_coordinate("location.lon", self.location.lon, -180.0, 180.0)?;

            let summary = match self.summary {
                Some(s) => {
                    require_non_blank("summary", &s)?;
                    let s = s.trim().to_string();
                    require_max_len("summary", &s, NODE_SUMMARY_MAX_LEN)?;
                    Some(s)
                }
                None => None,
            };

            let info = match self.info {
                Some(s) => {
                    require_max_len("info", &s, NODE_INFO_MAX_LEN)?;
                    Some(s)
                }
                None => None,
            };

            let tags = self.tags.unwrap_or_default();
            if tags.len() > NODE_TAGS_MAX_COUNT {
                return Err(NodeCreateValidationError::TooManyTags {
                    max: NODE_TAGS_MAX_COUNT,
                });
            }
            let mut validated_tags = Vec::with_capacity(tags.len());
            for tag in tags {
                require_non_blank("tags[]", &tag)?;
                let tag = tag.trim().to_string();
                require_max_len("tags[]", &tag, NODE_TAG_MAX_LEN)?;
                validated_tags.push(tag);
            }

            let operation_id = match self.operation_id {
                Some(value) => {
                    require_non_blank("operation_id", &value)?;
                    let parsed = Uuid::parse_str(&value).map_err(|_| {
                        NodeCreateValidationError::InvalidUuid {
                            field: "operation_id",
                            value: value.clone(),
                        }
                    })?;
                    Some(parsed.to_string())
                }
                None => None,
            };

            Ok(ValidatedCreateNode {
                title,
                kind,
                address,
                lat: self.location.lat,
                lon: self.location.lon,
                summary,
                info,
                tags: validated_tags,
                operation_id,
            })
        }
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        fn valid_request() -> CreateNodeRequest {
            CreateNodeRequest {
                title: "A Node".to_string(),
                kind: "Werkstatt".to_string(),
                address: "Musterstraße 1, 12345 Musterstadt".to_string(),
                location: CreateLocation {
                    lat: 53.5,
                    lon: 10.0,
                },
                summary: None,
                info: None,
                tags: None,
                operation_id: None,
            }
        }

        #[test]
        fn accepts_minimal_payload() {
            let json = r#"{"title":"A Node","kind":"Werkstatt","address":"Musterstraße 1","location":{"lat":53.5,"lon":10.0}}"#;
            let req = serde_json::from_str::<CreateNodeRequest>(json)
                .expect("minimal request must deserialize");
            let validated = req.validate().expect("minimal request must validate");
            assert_eq!(validated.title, "A Node");
            assert_eq!(validated.kind, "Werkstatt");
            assert_eq!(validated.address, "Musterstraße 1");
            assert_eq!(validated.lat, 53.5);
            assert_eq!(validated.lon, 10.0);
            assert_eq!(validated.summary, None);
            assert_eq!(validated.info, None);
            assert!(validated.tags.is_empty());
        }

        #[test]
        fn accepts_full_payload() {
            let json = r#"{"title":"A Node","kind":"Werkstatt","address":"Musterstraße 1","location":{"lat":53.5,"lon":10.0},"summary":"Short","info":"Long text","tags":["a","b"]}"#;
            let req = serde_json::from_str::<CreateNodeRequest>(json)
                .expect("full request must deserialize");
            let validated = req.validate().expect("full request must validate");
            assert_eq!(validated.summary.as_deref(), Some("Short"));
            assert_eq!(validated.info.as_deref(), Some("Long text"));
            assert_eq!(validated.tags, vec!["a".to_string(), "b".to_string()]);
        }

        #[test]
        fn trims_required_string_fields() {
            let mut req = valid_request();
            req.title = "  A Node  ".to_string();
            req.kind = "  Werkstatt  ".to_string();
            req.address = "  Musterstraße 1  ".to_string();
            let validated = req.validate().expect("must validate");
            assert_eq!(validated.title, "A Node");
            assert_eq!(validated.kind, "Werkstatt");
            assert_eq!(validated.address, "Musterstraße 1");
        }

        #[test]
        fn rejects_missing_title() {
            let json = r#"{"kind":"Werkstatt","address":"Musterstraße 1","location":{"lat":53.5,"lon":10.0}}"#;
            assert!(serde_json::from_str::<CreateNodeRequest>(json).is_err());
        }

        #[test]
        fn rejects_missing_kind() {
            let json = r#"{"title":"A Node","address":"Musterstraße 1","location":{"lat":53.5,"lon":10.0}}"#;
            assert!(serde_json::from_str::<CreateNodeRequest>(json).is_err());
        }

        #[test]
        fn rejects_missing_address() {
            let json =
                r#"{"title":"A Node","kind":"Werkstatt","location":{"lat":53.5,"lon":10.0}}"#;
            assert!(serde_json::from_str::<CreateNodeRequest>(json).is_err());
        }

        #[test]
        fn rejects_missing_location() {
            let json = r#"{"title":"A Node","kind":"Werkstatt","address":"Musterstraße 1"}"#;
            assert!(serde_json::from_str::<CreateNodeRequest>(json).is_err());
        }

        #[test]
        fn rejects_blank_title() {
            let mut req = valid_request();
            req.title = "   ".to_string();
            assert_eq!(
                req.validate(),
                Err(NodeCreateValidationError::MissingOrEmptyField("title"))
            );
        }

        #[test]
        fn rejects_blank_kind() {
            let mut req = valid_request();
            req.kind = "".to_string();
            assert_eq!(
                req.validate(),
                Err(NodeCreateValidationError::MissingOrEmptyField("kind"))
            );
        }

        #[test]
        fn rejects_blank_address() {
            let mut req = valid_request();
            req.address = "   ".to_string();
            assert_eq!(
                req.validate(),
                Err(NodeCreateValidationError::MissingOrEmptyField("address"))
            );
        }

        #[test]
        fn rejects_title_over_max_length() {
            let mut req = valid_request();
            req.title = "a".repeat(NODE_TITLE_MAX_LEN + 1);
            assert_eq!(
                req.validate(),
                Err(NodeCreateValidationError::FieldTooLong {
                    field: "title",
                    max: NODE_TITLE_MAX_LEN
                })
            );
        }

        #[test]
        fn accepts_title_at_max_length() {
            let mut req = valid_request();
            req.title = "a".repeat(NODE_TITLE_MAX_LEN);
            assert!(req.validate().is_ok());
        }

        #[test]
        fn rejects_address_over_max_length() {
            let mut req = valid_request();
            req.address = "a".repeat(NODE_ADDRESS_MAX_LEN + 1);
            assert_eq!(
                req.validate(),
                Err(NodeCreateValidationError::FieldTooLong {
                    field: "address",
                    max: NODE_ADDRESS_MAX_LEN
                })
            );
        }

        #[test]
        fn accepts_address_at_max_length() {
            let mut req = valid_request();
            req.address = "a".repeat(NODE_ADDRESS_MAX_LEN);
            assert!(req.validate().is_ok());
        }

        #[test]
        fn rejects_non_finite_and_out_of_bounds_coordinates() {
            for (lat, lon) in [
                (f64::NAN, 10.0),
                (f64::INFINITY, 10.0),
                (f64::NEG_INFINITY, 10.0),
                (91.0, 10.0),
                (-91.0, 10.0),
            ] {
                let mut req = valid_request();
                req.location = CreateLocation { lat, lon };
                assert_eq!(
                    req.validate(),
                    Err(NodeCreateValidationError::InvalidCoordinate {
                        field: "location.lat"
                    })
                );
            }

            for (lat, lon) in [
                (10.0, f64::NAN),
                (10.0, f64::INFINITY),
                (10.0, f64::NEG_INFINITY),
                (10.0, 181.0),
                (10.0, -181.0),
            ] {
                let mut req = valid_request();
                req.location = CreateLocation { lat, lon };
                assert_eq!(
                    req.validate(),
                    Err(NodeCreateValidationError::InvalidCoordinate {
                        field: "location.lon"
                    })
                );
            }
        }

        #[test]
        fn accepts_world_bound_edges() {
            for (lat, lon) in [(90.0, 180.0), (-90.0, -180.0), (0.0, 0.0)] {
                let mut req = valid_request();
                req.location = CreateLocation { lat, lon };
                assert!(req.validate().is_ok());
            }
        }

        #[test]
        fn rejects_blank_summary_when_present() {
            let mut req = valid_request();
            req.summary = Some("   ".to_string());
            assert_eq!(
                req.validate(),
                Err(NodeCreateValidationError::MissingOrEmptyField("summary"))
            );
        }

        #[test]
        fn rejects_summary_over_max_length() {
            let mut req = valid_request();
            req.summary = Some("a".repeat(NODE_SUMMARY_MAX_LEN + 1));
            assert_eq!(
                req.validate(),
                Err(NodeCreateValidationError::FieldTooLong {
                    field: "summary",
                    max: NODE_SUMMARY_MAX_LEN
                })
            );
        }

        #[test]
        fn rejects_info_over_max_length() {
            let mut req = valid_request();
            req.info = Some("a".repeat(NODE_INFO_MAX_LEN + 1));
            assert_eq!(
                req.validate(),
                Err(NodeCreateValidationError::FieldTooLong {
                    field: "info",
                    max: NODE_INFO_MAX_LEN
                })
            );
        }

        #[test]
        fn rejects_blank_tag() {
            let mut req = valid_request();
            req.tags = Some(vec!["ok".to_string(), "   ".to_string()]);
            assert_eq!(
                req.validate(),
                Err(NodeCreateValidationError::MissingOrEmptyField("tags[]"))
            );
        }

        #[test]
        fn rejects_tag_over_max_length() {
            let mut req = valid_request();
            req.tags = Some(vec!["a".repeat(NODE_TAG_MAX_LEN + 1)]);
            assert_eq!(
                req.validate(),
                Err(NodeCreateValidationError::FieldTooLong {
                    field: "tags[]",
                    max: NODE_TAG_MAX_LEN
                })
            );
        }

        #[test]
        fn rejects_too_many_tags() {
            let mut req = valid_request();
            req.tags = Some(
                (0..NODE_TAGS_MAX_COUNT + 1)
                    .map(|i| i.to_string())
                    .collect(),
            );
            assert_eq!(
                req.validate(),
                Err(NodeCreateValidationError::TooManyTags {
                    max: NODE_TAGS_MAX_COUNT
                })
            );
        }

        #[test]
        fn accepts_max_tag_count() {
            let mut req = valid_request();
            req.tags = Some((0..NODE_TAGS_MAX_COUNT).map(|i| i.to_string()).collect());
            assert!(req.validate().is_ok());
        }

        #[test]
        fn rejects_unknown_fields() {
            let json = r#"{"title":"A Node","kind":"Werkstatt","address":"Musterstraße 1","location":{"lat":53.5,"lon":10.0},"wat":true}"#;
            assert!(serde_json::from_str::<CreateNodeRequest>(json).is_err());
        }

        #[test]
        fn rejects_id_field_because_server_owns_it() {
            let json = r#"{"id":"00000000-0000-0000-0000-000000000001","title":"A Node","kind":"Werkstatt","address":"Musterstraße 1","location":{"lat":53.5,"lon":10.0}}"#;
            assert!(serde_json::from_str::<CreateNodeRequest>(json).is_err());
        }

        #[test]
        fn rejects_created_at_because_server_owns_timestamps() {
            let json = r#"{"title":"A Node","kind":"Werkstatt","address":"Musterstraße 1","location":{"lat":53.5,"lon":10.0},"created_at":"2026-01-01T00:00:00Z"}"#;
            assert!(serde_json::from_str::<CreateNodeRequest>(json).is_err());
        }

        #[test]
        fn rejects_unknown_location_fields() {
            let json = r#"{"title":"A Node","kind":"Werkstatt","address":"Musterstraße 1","location":{"lat":53.5,"lon":10.0,"alt":5.0}}"#;
            assert!(serde_json::from_str::<CreateNodeRequest>(json).is_err());
        }
    }
}

fn set_node_record_fields(record: &mut Value, node: &Node) -> std::io::Result<()> {
    let object = record.as_object_mut().ok_or_else(|| {
        std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "node record is not an object",
        )
    })?;
    object.insert("id".to_string(), json!(node.id));
    object.insert("kind".to_string(), json!(node.kind));
    object.insert("title".to_string(), json!(node.title));
    object.insert("created_at".to_string(), json!(node.created_at));
    object.insert("updated_at".to_string(), json!(node.updated_at));
    object.insert(
        "location".to_string(),
        json!({ "lat": node.location.lat, "lon": node.location.lon }),
    );
    for (key, value) in [
        ("summary", node.summary.as_ref().map(|value| json!(value))),
        ("info", node.info.as_ref().map(|value| json!(value))),
        ("address", node.address.as_ref().map(|value| json!(value))),
    ] {
        if let Some(value) = value {
            object.insert(key.to_string(), value);
        } else {
            object.remove(key);
        }
    }
    if node.tags.is_empty() {
        object.remove("tags");
    } else {
        object.insert("tags".to_string(), json!(node.tags));
    }
    object.remove("steckbrief");
    Ok(())
}

async fn replace_node_jsonl(node: &Node) -> std::io::Result<bool> {
    let path = nodes_path();
    let file = File::open(&path).await?;
    let mut lines = BufReader::new(file).lines();
    let mut tmp_path = path.clone();
    let filename = tmp_path.file_name().ok_or_else(|| {
        std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "nodes path has no filename",
        )
    })?;
    let mut tmp_filename = filename.to_os_string();
    tmp_filename.push(format!(".tmp.{}", Uuid::new_v4()));
    tmp_path.set_file_name(tmp_filename);

    let result = async {
        let tmp_file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&tmp_path)
            .await?;
        let mut writer = BufWriter::new(tmp_file);
        let mut replaced = false;
        while let Some(line) = lines.next_line().await? {
            let mut output = line.clone();
            if let Ok(mut value) = serde_json::from_str::<Value>(&line) {
                if value.get("id").and_then(Value::as_str) == Some(node.id.as_str()) {
                    set_node_record_fields(&mut value, node)?;
                    output = serde_json::to_string(&value).map_err(|error| {
                        std::io::Error::new(std::io::ErrorKind::InvalidData, error)
                    })?;
                    replaced = true;
                }
            }
            writer.write_all(output.as_bytes()).await?;
            writer.write_all(b"\n").await?;
        }
        writer.flush().await?;
        let file = writer.into_inner();
        file.sync_all().await?;
        Ok::<bool, std::io::Error>(replaced)
    }
    .await;

    match result {
        Ok(replaced) => {
            tokio::fs::rename(&tmp_path, &path).await?;
            Ok(replaced)
        }
        Err(error) => {
            let _ = tokio::fs::remove_file(&tmp_path).await;
            Err(error)
        }
    }
}

async fn delete_node_jsonl(id: &str) -> std::io::Result<bool> {
    let path = nodes_path();
    let file = File::open(&path).await?;
    let mut lines = BufReader::new(file).lines();
    let mut tmp_path = path.clone();
    let filename = tmp_path.file_name().ok_or_else(|| {
        std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "nodes path has no filename",
        )
    })?;
    let mut tmp_filename = filename.to_os_string();
    tmp_filename.push(format!(".tmp.{}", Uuid::new_v4()));
    tmp_path.set_file_name(tmp_filename);

    let result = async {
        let tmp_file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&tmp_path)
            .await?;
        let mut writer = BufWriter::new(tmp_file);
        let mut deleted = false;
        while let Some(line) = lines.next_line().await? {
            let matches = serde_json::from_str::<Value>(&line)
                .ok()
                .and_then(|value| value.get("id").and_then(Value::as_str).map(str::to_string))
                .as_deref()
                == Some(id);
            if matches {
                deleted = true;
                continue;
            }
            writer.write_all(line.as_bytes()).await?;
            writer.write_all(b"\n").await?;
        }
        writer.flush().await?;
        let file = writer.into_inner();
        file.sync_all().await?;
        Ok::<bool, std::io::Error>(deleted)
    }
    .await;

    match result {
        Ok(deleted) => {
            tokio::fs::rename(&tmp_path, &path).await?;
            Ok(deleted)
        }
        Err(error) => {
            let _ = tokio::fs::remove_file(&tmp_path).await;
            Err(error)
        }
    }
}

pub async fn replace_node(
    State(state): State<ApiState>,
    Path(id): Path<String>,
    Json(payload): Json<Value>,
) -> Result<Json<Node>, PatchNodeError> {
    reject_node_patch_unless_writable(&state)
        .map_err(|(status, body)| PatchNodeError::Message(status, body))?;
    let request: node_create::CreateNodeRequest =
        serde_json::from_value(payload).map_err(|error| {
            PatchNodeError::Message(
                StatusCode::BAD_REQUEST,
                format!("invalid node replacement request: {error}"),
            )
        })?;
    let validated = request.validate().map_err(|error| {
        PatchNodeError::Message(
            StatusCode::BAD_REQUEST,
            format!(
                "invalid node replacement request: {}",
                node_create_error_message(&error)
            ),
        )
    })?;
    if validated.operation_id.is_some() {
        return Err(PatchNodeError::Message(
            StatusCode::BAD_REQUEST,
            "operation_id is only valid when creating a node".to_string(),
        ));
    }

    let _persist_guard = state.nodes_persist.lock().await;
    let existing = state
        .nodes
        .read()
        .await
        .get(&id)
        .cloned()
        .ok_or(PatchNodeError::Status(StatusCode::NOT_FOUND))?;
    let node = Node {
        id: existing.id,
        kind: validated.kind,
        title: validated.title,
        created_at: existing.created_at,
        updated_at: chrono::Utc::now().to_rfc3339(),
        summary: validated.summary,
        info: validated.info,
        tags: validated.tags,
        address: Some(validated.address),
        location: Location {
            lat: validated.lat,
            lon: validated.lon,
        },
    };

    match state.config.domain_node_write_source {
        DomainNodeWriteSource::Jsonl => {
            if !replace_node_jsonl(&node).await.map_err(|error| {
                tracing::error!(%error, node_id = %id, "failed to replace node JSONL record");
                PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR)
            })? {
                return Err(PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR));
            }
        }
        DomainNodeWriteSource::Postgres => {
            let pool = state
                .db_pool
                .as_ref()
                .ok_or(PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;
            replace_node_in_postgres(pool, &node).await.map_err(|error| match error {
                NodeWriteError::NotFound => PatchNodeError::Status(StatusCode::NOT_FOUND),
                other => {
                    tracing::error!(%other, node_id = %id, "failed to replace node in PostgreSQL");
                    PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR)
                }
            })?;
        }
    }

    let mut nodes = state.nodes.write().await;
    nodes.insert(id.clone(), node.clone());
    state.metrics.set_nodes_cache_count(nodes.len() as i64);
    tracing::info!(event = "node.updated.collective", node_id = %id, "Node collectively updated");
    Ok(Json(node))
}

pub async fn delete_node(
    State(state): State<ApiState>,
    Path(id): Path<String>,
) -> Result<StatusCode, PatchNodeError> {
    reject_node_patch_unless_writable(&state)
        .map_err(|(status, body)| PatchNodeError::Message(status, body))?;
    let persistence_is_coherent = matches!(
        (
            state.config.domain_node_write_source,
            state.config.domain_edge_write_source,
        ),
        (DomainNodeWriteSource::Jsonl, DomainEdgeWriteSource::Jsonl,)
            | (
                DomainNodeWriteSource::Postgres,
                DomainEdgeWriteSource::Postgres,
            )
    );
    if !persistence_is_coherent {
        return Err(PatchNodeError::Message(
            StatusCode::CONFLICT,
            "node deletion requires matching node and edge write sources".to_string(),
        ));
    }
    let _persist_guard = state.nodes_persist.lock().await;
    if state.nodes.read().await.get(&id).is_none() {
        return Err(PatchNodeError::Status(StatusCode::NOT_FOUND));
    }

    let cached_edge_ids: Vec<String> = state
        .edges
        .read()
        .await
        .iter_in_order()
        .filter(|edge| {
            (edge.source_id == id && edge.source_type.as_deref() != Some("account"))
                || (edge.target_id == id && edge.target_type.as_deref() != Some("account"))
        })
        .map(|edge| edge.id.clone())
        .collect();

    let persisted_edge_ids = match state.config.domain_node_write_source {
        DomainNodeWriteSource::Jsonl => {
            // Keep the edge lock until the node file has also been replaced. Otherwise a
            // concurrent edge create could attach a new edge between cascade cleanup and
            // node deletion, leaving an orphan behind.
            let _edge_persist_guard = edge_create_persist_lock().lock().await;
            let removed = delete_edges_referencing_node_jsonl(&id).await.map_err(|error| {
                tracing::error!(%error, node_id = %id, "failed to remove node edges from JSONL");
                PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR)
            })?;
            if !delete_node_jsonl(&id).await.map_err(|error| {
                tracing::error!(%error, node_id = %id, "failed to delete node JSONL record");
                PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR)
            })? {
                return Err(PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR));
            }
            removed
        }
        DomainNodeWriteSource::Postgres => {
            let pool = state
                .db_pool
                .as_ref()
                .ok_or(PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;
            delete_node_with_edges_in_postgres(pool, &id).await.map_err(|error| match error {
                NodeWriteError::NotFound => PatchNodeError::Status(StatusCode::NOT_FOUND),
                other => {
                    tracing::error!(%other, node_id = %id, "failed to delete node in PostgreSQL");
                    PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR)
                }
            })?
        }
    };

    let mut edges = state.edges.write().await;
    for edge_id in cached_edge_ids.iter().chain(persisted_edge_ids.iter()) {
        edges.remove(edge_id);
    }
    drop(edges);
    let mut nodes = state.nodes.write().await;
    nodes.remove(&id);
    state.metrics.set_nodes_cache_count(nodes.len() as i64);
    tracing::info!(event = "node.deleted.collective", node_id = %id, removed_edges = persisted_edge_ids.len(), "Node collectively deleted");
    Ok(StatusCode::NO_CONTENT)
}

pub async fn patch_node(
    State(state): State<ApiState>,
    Path(id): Path<String>,
    Json(payload): Json<UpdateNode>,
) -> Result<Json<Node>, PatchNodeError> {
    reject_node_patch_unless_writable(&state)
        .map_err(|(status, body)| PatchNodeError::Message(status, body))?;

    if state.config.domain_node_write_source == DomainNodeWriteSource::Postgres {
        return patch_node_postgres(&state, &id, payload).await;
    }

    patch_node_jsonl(state, id, payload).await
}

async fn patch_node_postgres(
    state: &ApiState,
    id: &str,
    payload: UpdateNode,
) -> Result<Json<Node>, PatchNodeError> {
    let pool = state
        .db_pool
        .as_ref()
        .ok_or(PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;

    let patch = NodePatchInput {
        info: payload.info.clone(),
    };

    // Serialize DB patch + cache update in-process so a later committed patch cannot
    // be overwritten in the cache by an earlier request that resumes late after commit.
    // This is an in-process coherence guard, not a multi-instance cache invalidation mechanism.
    let _persist_guard = state.nodes_persist.lock().await;

    let node = patch_node_in_postgres(pool, id, patch)
        .await
        .map_err(|e| match e {
            NodeWriteError::NotFound => PatchNodeError::Status(StatusCode::NOT_FOUND),
            NodeWriteError::Mapping(err) => {
                tracing::error!(?err, node_id = %id, "node mapping failed after postgres patch");
                PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR)
            }
            NodeWriteError::Serialization(err) => {
                tracing::error!(?err, node_id = %id, "payload serialization failed during node patch");
                PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR)
            }
            NodeWriteError::Database(err) => {
                tracing::error!(?err, node_id = %id, "database error during node patch");
                PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR)
            }
        })?;

    let mut cache_guard = state.nodes.write().await;
    cache_guard.insert(id.to_string(), node.clone());
    state
        .metrics
        .set_nodes_cache_count(cache_guard.len() as i64);
    drop(cache_guard);

    tracing::info!(node_id = %id, write_source = "postgres", "Node patch finished");

    Ok(Json(node))
}

async fn patch_node_jsonl(
    state: ApiState,
    id: String,
    payload: UpdateNode,
) -> Result<Json<Node>, PatchNodeError> {
    // Serialize PATCH persistence (per-process): allow concurrent node reads during file I/O;
    // only the brief in-memory cache write-lock blocks readers to guarantee read-your-writes in this instance.
    let start_persist_wait = std::time::Instant::now();
    let _persist_guard = state.nodes_persist.lock().await;
    let persist_lock_wait_ms = start_persist_wait.elapsed().as_millis();

    let path = nodes_path();
    // Open source file for reading
    let file = File::open(&path)
        .await
        .map_err(|_| PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;
    let mut lines = BufReader::new(file).lines();

    // Use a unique temporary file + rename for atomic writes to prevent data corruption and race conditions
    let mut tmp_path = path.clone();
    if let Some(filename) = tmp_path.file_name() {
        let mut new_filename = filename.to_os_string();
        new_filename.push(format!(".tmp.{}", Uuid::new_v4()));
        tmp_path.set_file_name(new_filename);
    } else {
        return Err(PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR));
    }

    let start_persist = std::time::Instant::now();

    // Inner function to handle processing and writing logic so we can catch errors and cleanup
    let process_result = async {
        let tmp_file = OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(true)
            .open(&tmp_path)
            .await
            .map_err(|_| PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;

        let mut writer = BufWriter::new(tmp_file);
        let mut found_node: Option<Node> = None;
        let mut updated = false;

        while let Ok(Some(line)) = lines.next_line().await {
            // Optimization: check ID without parsing full Value
            let should_update = match serde_json::from_str::<IdOnly>(&line) {
                Ok(obj) => obj.id.as_deref() == Some(id.as_str()),
                Err(_) => return Err(PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR)),
            };

            if should_update {
                let mut v: Value =
                    serde_json::from_str(&line).map_err(|_| PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;

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

                // Map to Node and fail hard if mapping fails.
                // Ensures we never persist changes without a valid Node response.
                let node = map_json_to_node(&v).ok_or(PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;

                // Security/Consistency: Ensure the ID hasn't been changed via the update.
                if node.id != id {
                    tracing::error!(path_id = %id, payload_id = %node.id, "Node ID mismatch in PATCH");
                    return Err(PatchNodeError::Status(StatusCode::BAD_REQUEST));
                }
                found_node = Some(node);

                let s = serde_json::to_string(&v).map_err(|_| PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;
                writer
                    .write_all(s.as_bytes())
                    .await
                    .map_err(|_| PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;
                updated = true;
            } else {
                writer
                    .write_all(line.as_bytes())
                    .await
                    .map_err(|_| PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;
            }

            writer
                .write_all(b"\n")
                .await
                .map_err(|_| PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;
        }

        if !updated {
            return Err(PatchNodeError::Status(StatusCode::NOT_FOUND));
        }

        writer
            .flush()
            .await
            .map_err(|_| PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;

        // Ensure durability
        let file = writer.into_inner();
        file.sync_all()
            .await
            .map_err(|_| PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;

        Ok(found_node)
    }
    .await;

    let found_node = match process_result {
        Ok(n) => n,
        Err(e) => {
            // Cleanup temp file on failure
            let _ = tokio::fs::remove_file(&tmp_path).await;
            return Err(e);
        }
    };

    if let Err(_e) = tokio::fs::rename(&tmp_path, &path).await {
        // Cleanup temp file if rename fails
        let _ = tokio::fs::remove_file(&tmp_path).await;
        return Err(PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR));
    }

    let persist_ms = start_persist.elapsed().as_millis();

    // Update in-memory cache
    let start_mem_wait = std::time::Instant::now();
    let mut cache_guard = state.nodes.write().await;
    let mem_lock_wait_ms = start_mem_wait.elapsed().as_millis();
    let start_mem_hold = std::time::Instant::now();

    if let Some(ref updated_node) = found_node {
        cache_guard.insert(id.clone(), updated_node.clone());
    }

    // Update metrics
    state
        .metrics
        .set_nodes_cache_count(cache_guard.len() as i64);

    let mem_lock_hold_ms = start_mem_hold.elapsed().as_millis();
    // Explicitly drop lock before logging to avoid holding it during tracing
    drop(cache_guard);

    tracing::info!(
        persist_ms,
        persist_lock_wait_ms,
        mem_lock_wait_ms,
        mem_lock_hold_ms,
        node_id = %id,
        node_found = found_node.is_some(),
        "Node patch finished"
    );

    found_node
        .map(Json)
        .ok_or(PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR))
}

pub async fn list_nodes(
    State(state): State<ApiState>,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Json<ListResponse<Node>>, StatusCode> {
    let bbox = match params.get("bbox") {
        Some(raw_bbox) => Some(parse_bbox(raw_bbox).ok_or(StatusCode::BAD_REQUEST)?),
        None => None,
    };
    let limit: usize = parse_usize_param(&params, "limit", 100)?.min(MAX_PAGE_SIZE);
    let (cursor_mode, after_id) = parse_cursor_params(&params)?;
    validate_cursor_limit(cursor_mode, limit)?;

    let cache = state.nodes.read().await;

    if cursor_mode {
        // Cursor mode sorts by stable id ascending (see query::cursor_page),
        // independent of the file/insertion order used by the legacy path.
        let refs: Vec<&Node> = cache
            .iter_in_order()
            .filter(|node| match &bbox {
                Some(bb) => point_in_bbox(node.location.lon, node.location.lat, bb),
                None => true,
            })
            .collect();
        let page = cursor_page(
            refs,
            limit,
            after_id.as_deref(),
            |node: &Node| node.id.as_str(),
            |node: &Node| node.clone(),
        );
        Ok(Json(ListResponse::Cursor(page)))
    } else {
        let offset: usize = parse_usize_param(&params, "offset", 0)?;
        let out: Vec<Node> = cache
            .iter_in_order()
            .filter(|node| match &bbox {
                Some(bb) => point_in_bbox(node.location.lon, node.location.lat, bb),
                None => true,
            })
            .skip(offset)
            .take(limit)
            .cloned()
            .collect();
        Ok(Json(ListResponse::Legacy(out)))
    }
}

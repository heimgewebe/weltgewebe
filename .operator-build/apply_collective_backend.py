from pathlib import Path

root = Path.cwd()

# Keep public reads public while applying write middleware only to mutations.
routes = root / "apps/api/src/routes/mod.rs"
text = routes.read_text()
old = '''        .route(
            "/nodes/{id}",
            get(get_node)
                .patch(patch_node)
                .put(replace_node)
                .delete(delete_node)
                .route_layer(from_fn(require_write)),
        )
'''
new = '''        .route(
            "/nodes/{id}",
            get(get_node).merge(
                axum::routing::patch(patch_node)
                    .put(replace_node)
                    .delete(delete_node)
                    .route_layer(from_fn(require_write)),
            ),
        )
'''
assert text.count(old) == 1, "unexpected node route after initial edit"
text = text.replace(old, new)
old = '''        .route(
            "/edges/{id}",
            get(get_edge)
                .patch(patch_edge)
                .delete(delete_edge)
                .route_layer(from_fn(require_write)),
        )
'''
new = '''        .route(
            "/edges/{id}",
            get(get_edge).merge(
                axum::routing::patch(patch_edge)
                    .delete(delete_edge)
                    .route_layer(from_fn(require_write)),
            ),
        )
'''
assert text.count(old) == 1, "unexpected edge route after initial edit"
routes.write_text(text.replace(old, new))

# PostgreSQL mutation helpers.
db = root / "apps/api/src/domain_db.rs"
text = db.read_text()
marker = '''/// Apply a patch to one `domain_nodes` row inside a transaction.
'''
insert = '''fn serialize_node_payload(node: &Node) -> Result<String, serde_json::Error> {
    let mut payload_map = Map::new();
    if let Some(summary) = &node.summary {
        payload_map.insert("summary".to_string(), json!(summary));
    }
    if let Some(info) = &node.info {
        payload_map.insert("info".to_string(), json!(info));
    }
    if !node.tags.is_empty() {
        payload_map.insert("tags".to_string(), json!(node.tags));
    }
    if let Some(address) = &node.address {
        payload_map.insert("address".to_string(), json!(address));
    }
    serde_json::to_string(&Value::Object(payload_map))
}

#[derive(Debug, thiserror::Error)]
pub enum EdgeMutationError {
    #[error("edge not found")]
    NotFound,
    #[error("failed to persist edge mutation: {0}")]
    Database(#[source] sqlx::Error),
}

pub async fn update_edge_kind_in_postgres(
    pool: &PgPool,
    id: &str,
    edge_kind: &str,
) -> Result<(), EdgeMutationError> {
    let result = sqlx::query("UPDATE domain_edges SET edge_kind = $2 WHERE id = $1")
        .bind(id)
        .bind(edge_kind)
        .execute(pool)
        .await
        .map_err(EdgeMutationError::Database)?;
    if result.rows_affected() == 0 {
        return Err(EdgeMutationError::NotFound);
    }
    Ok(())
}

pub async fn delete_edge_in_postgres(
    pool: &PgPool,
    id: &str,
) -> Result<(), EdgeMutationError> {
    let result = sqlx::query("DELETE FROM domain_edges WHERE id = $1")
        .bind(id)
        .execute(pool)
        .await
        .map_err(EdgeMutationError::Database)?;
    if result.rows_affected() == 0 {
        return Err(EdgeMutationError::NotFound);
    }
    Ok(())
}

'''
assert text.count(marker) == 1, "node patch marker missing"
text = text.replace(marker, insert + marker)
marker = '''// ── node-create write path ──────────────────────────────────────────────────
'''
insert = '''pub async fn replace_node_in_postgres(
    pool: &PgPool,
    node: &Node,
) -> Result<(), NodeWriteError> {
    let payload = serialize_node_payload(node).map_err(NodeWriteError::Serialization)?;
    let updated_at = DateTime::parse_from_rfc3339(&node.updated_at)
        .map(|value| value.with_timezone(&Utc))
        .map_err(|error| NodeWriteError::Mapping(anyhow::Error::new(error)))?;
    let result = sqlx::query(
        "UPDATE domain_nodes \\
         SET kind = $2, title = $3, lat = $4, lon = $5, updated_at = $6, payload = $7::jsonb \\
         WHERE id = $1",
    )
    .bind(&node.id)
    .bind(&node.kind)
    .bind(&node.title)
    .bind(node.location.lat)
    .bind(node.location.lon)
    .bind(updated_at)
    .bind(payload)
    .execute(pool)
    .await
    .map_err(NodeWriteError::Database)?;
    if result.rows_affected() == 0 {
        return Err(NodeWriteError::NotFound);
    }
    Ok(())
}

pub async fn delete_node_with_edges_in_postgres(
    pool: &PgPool,
    id: &str,
) -> Result<Vec<String>, NodeWriteError> {
    let mut tx = pool.begin().await.map_err(NodeWriteError::Database)?;
    let exists: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM domain_nodes WHERE id = $1)")
        .bind(id)
        .fetch_one(&mut *tx)
        .await
        .map_err(NodeWriteError::Database)?;
    if !exists {
        tx.rollback().await.ok();
        return Err(NodeWriteError::NotFound);
    }

    let edge_ids: Vec<String> = sqlx::query_scalar(
        "SELECT id FROM domain_edges \\
         WHERE (source_id = $1 AND COALESCE(payload->>'source_type', 'node') = 'node') \\
            OR (target_id = $1 AND COALESCE(payload->>'target_type', 'node') = 'node')",
    )
    .bind(id)
    .fetch_all(&mut *tx)
    .await
    .map_err(NodeWriteError::Database)?;

    sqlx::query(
        "DELETE FROM domain_edges \\
         WHERE (source_id = $1 AND COALESCE(payload->>'source_type', 'node') = 'node') \\
            OR (target_id = $1 AND COALESCE(payload->>'target_type', 'node') = 'node')",
    )
    .bind(id)
    .execute(&mut *tx)
    .await
    .map_err(NodeWriteError::Database)?;
    sqlx::query("DELETE FROM domain_nodes WHERE id = $1")
        .bind(id)
        .execute(&mut *tx)
        .await
        .map_err(NodeWriteError::Database)?;
    tx.commit().await.map_err(NodeWriteError::Database)?;
    Ok(edge_ids)
}

'''
assert text.count(marker) == 1, "node-create marker missing"
text = text.replace(marker, insert + marker)
old = '''    let mut payload_map = Map::new();
    if let Some(summary) = &node.summary {
        payload_map.insert("summary".to_string(), json!(summary));
    }
    if let Some(info) = &node.info {
        payload_map.insert("info".to_string(), json!(info));
    }
    if !node.tags.is_empty() {
        payload_map.insert("tags".to_string(), json!(node.tags));
    }
    if let Some(address) = &node.address {
        payload_map.insert("address".to_string(), json!(address));
    }
    let payload = serde_json::to_string(&Value::Object(payload_map))
        .map_err(NodeCreateError::Serialization)?;
'''
new = '''    let payload = serialize_node_payload(node).map_err(NodeCreateError::Serialization)?;
'''
assert text.count(old) == 1, "node create payload block missing"
db.write_text(text.replace(old, new))

# Node full replacement and cascade deletion.
nodes = root / "apps/api/src/routes/nodes.rs"
text = nodes.read_text()
old = '''use super::{
    domain_write_guard::{
'''
new = '''use super::{
    edges::delete_edges_referencing_node_jsonl,
    domain_write_guard::{
'''
assert text.count(old) == 1, "nodes super import marker missing"
text = text.replace(old, new)
old = '''use crate::domain_db::{
    insert_domain_node, patch_node_in_postgres, CreateOperationKey, CreateWriteOutcome,
    NodeCreateError, NodePatchInput, NodeWriteError,
};
'''
new = '''use crate::domain_db::{
    delete_node_with_edges_in_postgres, insert_domain_node, patch_node_in_postgres,
    replace_node_in_postgres, CreateOperationKey, CreateWriteOutcome, NodeCreateError,
    NodePatchInput, NodeWriteError,
};
'''
assert text.count(old) == 1, "nodes domain_db import missing"
text = text.replace(old, new)
marker = '''pub async fn patch_node(
'''
insert = '''fn set_node_record_fields(record: &mut Value, node: &Node) -> std::io::Result<()> {
    let object = record.as_object_mut().ok_or_else(|| {
        std::io::Error::new(std::io::ErrorKind::InvalidData, "node record is not an object")
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
        std::io::Error::new(std::io::ErrorKind::InvalidInput, "nodes path has no filename")
    })?;
    let mut tmp_filename = filename.to_os_string();
    tmp_filename.push(format!(".tmp.{}", Uuid::new_v4()));
    tmp_path.set_file_name(tmp_filename);

    let result = async {
        let tmp_file = OpenOptions::new().write(true).create_new(true).open(&tmp_path).await?;
        let mut writer = BufWriter::new(tmp_file);
        let mut replaced = false;
        while let Some(line) = lines.next_line().await? {
            let mut output = line.clone();
            if let Ok(mut value) = serde_json::from_str::<Value>(&line) {
                if value.get("id").and_then(Value::as_str) == Some(node.id.as_str()) {
                    set_node_record_fields(&mut value, node)?;
                    output = serde_json::to_string(&value)
                        .map_err(|error| std::io::Error::new(std::io::ErrorKind::InvalidData, error))?;
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
    }.await;

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
        std::io::Error::new(std::io::ErrorKind::InvalidInput, "nodes path has no filename")
    })?;
    let mut tmp_filename = filename.to_os_string();
    tmp_filename.push(format!(".tmp.{}", Uuid::new_v4()));
    tmp_path.set_file_name(tmp_filename);

    let result = async {
        let tmp_file = OpenOptions::new().write(true).create_new(true).open(&tmp_path).await?;
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
    }.await;

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
    let request: node_create::CreateNodeRequest = serde_json::from_value(payload).map_err(|error| {
        PatchNodeError::Message(
            StatusCode::BAD_REQUEST,
            format!("invalid node replacement request: {error}"),
        )
    })?;
    let validated = request.validate().map_err(|error| {
        PatchNodeError::Message(
            StatusCode::BAD_REQUEST,
            format!("invalid node replacement request: {}", node_create_error_message(&error)),
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
        location: Location { lat: validated.lat, lon: validated.lon },
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
            let pool = state.db_pool.as_ref().ok_or(PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;
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
            let pool = state.db_pool.as_ref().ok_or(PatchNodeError::Status(StatusCode::INTERNAL_SERVER_ERROR))?;
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

'''
assert text.count(marker) == 1, "patch_node marker missing"
text = text.replace(marker, insert + marker)
nodes.write_text(text)

# Edge collective update/delete plus JSONL rewrite helper.
edges = root / "apps/api/src/routes/edges.rs"
text = edges.read_text()
old = '''use crate::domain_db::{
    insert_domain_edge, CreateOperationKey, CreateWriteOutcome, EdgeWriteError,
};
'''
new = '''use crate::domain_db::{
    delete_edge_in_postgres, insert_domain_edge, update_edge_kind_in_postgres,
    CreateOperationKey, CreateWriteOutcome, EdgeMutationError, EdgeWriteError,
};
'''
assert text.count(old) == 1, "edges domain_db import missing"
text = text.replace(old, new)
text = text.replace(
    '''        AsyncBufReadExt, AsyncReadExt, AsyncSeekExt, AsyncWriteExt, BufReader, SeekFrom,
''',
    '''        AsyncBufReadExt, AsyncReadExt, AsyncSeekExt, AsyncWriteExt, BufReader, BufWriter,
        SeekFrom,
''',
)
marker = '''/// Append a single edge record as a JSONL line. Durability via fsync.
'''
insert = '''#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UpdateEdgeRequest {
    edge_kind: String,
}

const COLLECTIVE_EDGE_KIND_VALUES: [&str; 4] = [
    "delegation",
    "membership",
    "ownership",
    "reference",
];

enum EdgeJsonlRewriteAction {
    Keep,
    Remove,
}

async fn rewrite_edges_jsonl<F>(mut transform: F) -> std::io::Result<Vec<Edge>>
where
    F: FnMut(&mut Value) -> std::io::Result<(EdgeJsonlRewriteAction, Option<Edge>)>,
{
    let path = edges_path();
    let file = match File::open(&path).await {
        Ok(file) => file,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(error) => return Err(error),
    };
    let mut lines = BufReader::new(file).lines();
    let mut tmp_path = path.clone();
    let filename = tmp_path.file_name().ok_or_else(|| {
        std::io::Error::new(std::io::ErrorKind::InvalidInput, "edges path has no filename")
    })?;
    let mut tmp_filename = filename.to_os_string();
    tmp_filename.push(format!(".tmp.{}", Uuid::new_v4()));
    tmp_path.set_file_name(tmp_filename);

    let result = async {
        let tmp_file = OpenOptions::new().write(true).create_new(true).open(&tmp_path).await?;
        let mut writer = BufWriter::new(tmp_file);
        let mut changed = Vec::new();
        while let Some(line) = lines.next_line().await? {
            let Ok(mut value) = serde_json::from_str::<Value>(&line) else {
                writer.write_all(line.as_bytes()).await?;
                writer.write_all(b"\n").await?;
                continue;
            };
            let (action, affected) = transform(&mut value)?;
            if let Some(edge) = affected {
                changed.push(edge);
            }
            if matches!(action, EdgeJsonlRewriteAction::Remove) {
                continue;
            }
            let output = serde_json::to_string(&value)
                .map_err(|error| std::io::Error::new(std::io::ErrorKind::InvalidData, error))?;
            writer.write_all(output.as_bytes()).await?;
            writer.write_all(b"\n").await?;
        }
        writer.flush().await?;
        let file = writer.into_inner();
        file.sync_all().await?;
        Ok::<Vec<Edge>, std::io::Error>(changed)
    }.await;

    match result {
        Ok(changed) => {
            tokio::fs::rename(&tmp_path, &path).await?;
            Ok(changed)
        }
        Err(error) => {
            let _ = tokio::fs::remove_file(&tmp_path).await;
            Err(error)
        }
    }
}

pub(crate) async fn delete_edges_referencing_node_jsonl(
    node_id: &str,
) -> std::io::Result<Vec<String>> {
    let _persist_guard = edge_create_persist_lock().lock().await;
    let removed = rewrite_edges_jsonl(|value| {
        let edge: Edge = match serde_json::from_value(value.clone()) {
            Ok(edge) => edge,
            Err(_) => return Ok((EdgeJsonlRewriteAction::Keep, None)),
        };
        let references_node =
            (edge.source_id == node_id && edge.source_type.as_deref() != Some("account"))
                || (edge.target_id == node_id && edge.target_type.as_deref() != Some("account"));
        if references_node {
            Ok((EdgeJsonlRewriteAction::Remove, Some(edge)))
        } else {
            Ok((EdgeJsonlRewriteAction::Keep, None))
        }
    }).await?;
    Ok(removed.into_iter().map(|edge| edge.id).collect())
}

pub async fn patch_edge(
    State(state): State<ApiState>,
    Path(id): Path<String>,
    Json(payload): Json<Value>,
) -> Result<Json<Edge>, (StatusCode, String)> {
    reject_edge_create_unless_writable(&state)?;
    let request: UpdateEdgeRequest = serde_json::from_value(payload).map_err(|error| {
        (StatusCode::BAD_REQUEST, format!("invalid edge update request: {error}"))
    })?;
    let edge_kind = request.edge_kind.trim();
    if !COLLECTIVE_EDGE_KIND_VALUES.contains(&edge_kind) {
        return Err((StatusCode::BAD_REQUEST, "invalid edge_kind".to_string()));
    }
    let mut edge = state
        .edges
        .read()
        .await
        .get(&id)
        .cloned()
        .ok_or_else(|| (StatusCode::NOT_FOUND, "edge not found".to_string()))?;
    edge.edge_kind = edge_kind.to_string();

    let _persist_guard = edge_create_persist_lock().lock().await;
    match state.config.domain_edge_write_source {
        DomainEdgeWriteSource::Jsonl => {
            let mut changed = rewrite_edges_jsonl(|value| {
                if value.get("id").and_then(Value::as_str) != Some(id.as_str()) {
                    return Ok((EdgeJsonlRewriteAction::Keep, None));
                }
                let object = value.as_object_mut().ok_or_else(|| {
                    std::io::Error::new(std::io::ErrorKind::InvalidData, "edge record is not an object")
                })?;
                object.insert("edge_kind".to_string(), json!(edge_kind));
                let updated: Edge = serde_json::from_value(value.clone())
                    .map_err(|error| std::io::Error::new(std::io::ErrorKind::InvalidData, error))?;
                Ok((EdgeJsonlRewriteAction::Keep, Some(updated)))
            }).await.map_err(|error| {
                tracing::error!(%error, edge_id = %id, "failed to update edge JSONL record");
                (StatusCode::INTERNAL_SERVER_ERROR, "failed to update edge".to_string())
            })?;
            edge = changed.pop().ok_or_else(|| {
                (StatusCode::INTERNAL_SERVER_ERROR, "edge persistence record missing".to_string())
            })?;
        }
        DomainEdgeWriteSource::Postgres => {
            let pool = state.db_pool.as_ref().ok_or_else(|| {
                (StatusCode::INTERNAL_SERVER_ERROR, "PostgreSQL pool unavailable for edge write".to_string())
            })?;
            update_edge_kind_in_postgres(pool, &id, edge_kind).await.map_err(|error| match error {
                EdgeMutationError::NotFound => (StatusCode::NOT_FOUND, "edge not found".to_string()),
                other => {
                    tracing::error!(%other, edge_id = %id, "failed to update edge in PostgreSQL");
                    (StatusCode::INTERNAL_SERVER_ERROR, "failed to update edge".to_string())
                }
            })?;
        }
    }
    state.edges.write().await.insert(id.clone(), edge.clone());
    tracing::info!(event = "edge.updated.collective", edge_id = %id, "Edge collectively updated");
    Ok(Json(edge))
}

pub async fn delete_edge(
    State(state): State<ApiState>,
    Path(id): Path<String>,
) -> Result<StatusCode, (StatusCode, String)> {
    reject_edge_create_unless_writable(&state)?;
    if state.edges.read().await.get(&id).is_none() {
        return Err((StatusCode::NOT_FOUND, "edge not found".to_string()));
    }
    let _persist_guard = edge_create_persist_lock().lock().await;
    match state.config.domain_edge_write_source {
        DomainEdgeWriteSource::Jsonl => {
            let removed = rewrite_edges_jsonl(|value| {
                if value.get("id").and_then(Value::as_str) != Some(id.as_str()) {
                    return Ok((EdgeJsonlRewriteAction::Keep, None));
                }
                let edge: Edge = serde_json::from_value(value.clone())
                    .map_err(|error| std::io::Error::new(std::io::ErrorKind::InvalidData, error))?;
                Ok((EdgeJsonlRewriteAction::Remove, Some(edge)))
            }).await.map_err(|error| {
                tracing::error!(%error, edge_id = %id, "failed to delete edge JSONL record");
                (StatusCode::INTERNAL_SERVER_ERROR, "failed to delete edge".to_string())
            })?;
            if removed.is_empty() {
                return Err((StatusCode::INTERNAL_SERVER_ERROR, "edge persistence record missing".to_string()));
            }
        }
        DomainEdgeWriteSource::Postgres => {
            let pool = state.db_pool.as_ref().ok_or_else(|| {
                (StatusCode::INTERNAL_SERVER_ERROR, "PostgreSQL pool unavailable for edge write".to_string())
            })?;
            delete_edge_in_postgres(pool, &id).await.map_err(|error| match error {
                EdgeMutationError::NotFound => (StatusCode::NOT_FOUND, "edge not found".to_string()),
                other => {
                    tracing::error!(%other, edge_id = %id, "failed to delete edge in PostgreSQL");
                    (StatusCode::INTERNAL_SERVER_ERROR, "failed to delete edge".to_string())
                }
            })?;
        }
    }
    state.edges.write().await.remove(&id);
    tracing::info!(event = "edge.deleted.collective", edge_id = %id, "Edge collectively deleted");
    Ok(StatusCode::NO_CONTENT)
}

'''
assert text.count(marker) == 1, "edge append marker missing"
text = text.replace(marker, insert + marker)
edges.write_text(text)

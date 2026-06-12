use super::domain_write_guard::reject_edge_create_unless_writable;
use super::query::{
    cursor_page, parse_cursor_params, parse_usize_param, validate_cursor_limit, ListResponse,
    MAX_PAGE_SIZE,
};
use crate::config::DomainEdgeWriteSource;
use crate::domain_db::{insert_domain_edge, EdgeWriteError};
use crate::state::{ApiState, OrderedCache};
use crate::utils::edges_path;
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    Json,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::OnceLock;
use tokio::sync::Mutex;
use tokio::{
    fs::{File, OpenOptions},
    io::{AsyncBufReadExt, AsyncReadExt, AsyncSeekExt, AsyncWriteExt, BufReader, SeekFrom},
};
use uuid::Uuid;

/// Process-local lock serializing edge-create persistence (duplicate check +
/// JSONL append + cache insert) so concurrent creates cannot interleave the
/// check and the write. Kept module-local instead of on `ApiState` so the
/// edge-create feature does not ripple through every manual `ApiState` literal
/// (notably the DB-proof harness states). The lock is per process, matching the
/// existing JSONL-API process model; cross-process file locking is out of scope.
static EDGE_CREATE_PERSIST: OnceLock<Mutex<()>> = OnceLock::new();

fn edge_create_persist_lock() -> &'static Mutex<()> {
    EDGE_CREATE_PERSIST.get_or_init(|| Mutex::new(()))
}

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

pub(crate) const DEFAULT_MAX_EDGES_CACHE: usize = 500_000;

pub(crate) fn max_edges_cache_limit() -> usize {
    match std::env::var("MAX_EDGES_CACHE") {
        Ok(val) => match val.parse::<usize>() {
            Ok(v) => v,
            Err(_) => {
                tracing::warn!(
                    value = %val,
                    "Invalid MAX_EDGES_CACHE, falling back to default 500,000"
                );
                DEFAULT_MAX_EDGES_CACHE
            }
        },
        Err(_) => DEFAULT_MAX_EDGES_CACHE,
    }
}

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

    let max_edges = max_edges_cache_limit();

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
) -> Result<Json<ListResponse<Edge>>, StatusCode> {
    let src = params.get("source_id");
    let dst = params.get("target_id");
    let limit: usize = parse_usize_param(&params, "limit", 250)?.min(MAX_PAGE_SIZE);
    let (cursor_mode, after_id) = parse_cursor_params(&params)?;
    validate_cursor_limit(cursor_mode, limit)?;

    let matches = |edge: &&Edge| {
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
    };

    let cache = state.edges.read().await;

    if cursor_mode {
        // Cursor mode sorts by stable id ascending (see query::cursor_page),
        // independent of the file/insertion order used by the legacy path.
        let refs: Vec<&Edge> = cache.iter_in_order().filter(matches).collect();
        let page = cursor_page(
            refs,
            limit,
            after_id.as_deref(),
            |edge: &Edge| edge.id.as_str(),
            |edge: &Edge| edge.clone(),
        );
        Ok(Json(ListResponse::Cursor(page)))
    } else {
        let offset: usize = parse_usize_param(&params, "offset", 0)?;
        let out: Vec<Edge> = cache
            .iter_in_order()
            .filter(matches)
            .skip(offset)
            .take(limit)
            .cloned()
            .collect();
        Ok(Json(ListResponse::Legacy(out)))
    }
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

/// Append a single edge record as a JSONL line. Durability via fsync.
/// Callers MUST hold the `edge_create_persist_lock` to serialize writes.
///
/// If the existing file does not end with a newline (e.g. a hand-written or
/// truncated fixture), a separator newline is written first so the previous
/// record and the new record are never glued into one unparseable line.
async fn append_edge_line(record: &Value) -> std::io::Result<()> {
    let path = edges_path();
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

    // Preserve the JSONL record boundary: only the last byte is read for the
    // check (no full-file scan, no rewrite). With O_APPEND the seek moves the
    // read position only; writes still always land at the end of the file.
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

/// Outcome of inspecting the persisted edges file before a create.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct EdgePersistenceStatus {
    /// The file already holds at least `max_edges_cache_limit()` lines, so an
    /// appended record would land on a line index [`load_edges`] never
    /// materializes after a restart (the loader truncates by *lines read*,
    /// not by parsed edges — blank or corrupt lines consume slots too).
    cache_limit_reached: bool,
    /// The id already exists somewhere in the persistence source, even when
    /// it is not in the in-memory cache (e.g. in a suffix the loader
    /// truncated away).
    duplicate_id: bool,
}

/// Scan the persisted edges file before an append, mirroring [`load_edges`]
/// semantics: every line counts toward the cache limit, unparseable lines are
/// skipped, and a final unterminated line is still read. The whole file is
/// scanned — also beyond the limit — so a duplicate id in the unmaterialized
/// suffix is detected. A missing file means an empty persistence source.
/// Callers MUST hold the `edge_create_persist_lock`.
async fn inspect_edge_persistence_for_create(id: &str) -> std::io::Result<EdgePersistenceStatus> {
    let path = edges_path();
    let max_edges = max_edges_cache_limit();
    let file = match File::open(&path).await {
        Ok(f) => f,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            // A missing file is only writable when the loader would materialize
            // at least one appended line after restart.
            return Ok(EdgePersistenceStatus {
                cache_limit_reached: max_edges == 0,
                duplicate_id: false,
            });
        }
        Err(e) => return Err(e),
    };

    let mut lines = BufReader::new(file).lines();
    let mut lines_read: usize = 0;

    while let Some(line) = lines.next_line().await? {
        lines_read += 1;
        let edge: Edge = match serde_json::from_str(&line) {
            Ok(v) => v,
            // The loader skips unparseable lines; mirror that instead of
            // introducing a harder failure mode here.
            Err(_) => continue,
        };
        if edge.id == id {
            // Duplicate is terminal: create_edge returns 409 before consulting
            // the limit, so scanning the remaining file would only extend the
            // exclusive persist lock.
            return Ok(EdgePersistenceStatus {
                cache_limit_reached: false,
                duplicate_id: true,
            });
        }
    }

    Ok(EdgePersistenceStatus {
        cache_limit_reached: lines_read >= max_edges,
        duplicate_id: false,
    })
}

/// Build the in-memory `Edge` and its canonical JSONL record from a validated
/// create request plus the server-owned `id` and `created_at`.
///
/// The returned `Edge` carries exactly the values that land in the cache and
/// the JSONL line. `note` is only written to the record when present (absent
/// means omitted, never `null`); `expires_at`, `payload`, and `metadata` are
/// never written.
fn build_edge_record(
    validated: edge_create::ValidatedCreateEdge,
    id: String,
    created_at: String,
) -> (Edge, Value) {
    let edge = Edge {
        id,
        source_id: validated.source_id,
        source_type: Some(validated.source_type),
        target_id: validated.target_id,
        target_type: Some(validated.target_type),
        edge_kind: validated.edge_kind,
        note: validated.note,
        created_at: Some(created_at),
    };

    let mut record = serde_json::Map::new();
    record.insert("id".into(), json!(edge.id));
    record.insert("source_id".into(), json!(edge.source_id));
    record.insert("source_type".into(), json!(edge.source_type));
    record.insert("target_id".into(), json!(edge.target_id));
    record.insert("target_type".into(), json!(edge.target_type));
    record.insert("edge_kind".into(), json!(edge.edge_kind));
    record.insert("created_at".into(), json!(edge.created_at));
    if let Some(note) = &edge.note {
        record.insert("note".into(), json!(note));
    }

    (edge, Value::Object(record))
}

/// Map an `EdgeCreateValidationError` onto a stable message for the 400 body.
fn edge_create_error_message(err: &edge_create::EdgeCreateValidationError) -> String {
    use edge_create::EdgeCreateValidationError as E;
    match err {
        E::MissingOrEmptyField(field) => format!("missing or empty field: {field}"),
        E::InvalidEnumValue { field, value } => {
            format!("invalid enum value for {field}: {value}")
        }
        E::InvalidUuid { field, value } => format!("invalid UUID for {field}: {value}"),
        E::NoteTooLong => "note exceeds the maximum length of 1000 characters".to_string(),
    }
}

/// Create an edge (OPT-ARC-001 Phase E-C).
///
/// Write path: write gate ([`reject_edge_create_unless_writable`]) -> contract
/// validation (PR-1 semantics) -> server-generated `id` / `created_at` ->
/// persistence via the configured edge-create write source -> cache insert ->
/// 201. The cache is only mutated after a successful durable persistence step,
/// so a failed write never leaves a phantom edge in memory.
///
/// JSONL (default): persistence safety checks (file-level duplicate id,
/// cache-limit materializability) followed by a durable JSONL append (fsync).
/// PostgreSQL (opt-in via `WELTGEWEBE_DOMAIN_EDGE_WRITE_SOURCE=postgres`,
/// requires the PostgreSQL read source): a plain INSERT into `domain_edges`;
/// a duplicate id surfaces as 409 via the unique violation. No dual-write:
/// JSONL mode never touches PostgreSQL, PostgreSQL mode never appends JSONL
/// and never falls back to JSONL.
pub async fn create_edge(
    State(state): State<ApiState>,
    Json(payload): Json<Value>,
) -> Result<(StatusCode, Json<Edge>), (StatusCode, String)> {
    reject_edge_create_unless_writable(&state)?;

    // Deserialize manually (instead of extracting Json<CreateEdgeRequest>) so
    // contract violations — unknown fields like `expires_at`, missing required
    // fields, explicit nulls — map to a deterministic 400 rather than an
    // extractor-shaped 422.
    let request: edge_create::CreateEdgeRequest = serde_json::from_value(payload).map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("invalid edge create request: {e}"),
        )
    })?;

    let validated = request.validate().map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!(
                "invalid edge create request: {}",
                edge_create_error_message(&e)
            ),
        )
    })?;

    // Server-owned values: generate `id` when the client omitted it and stamp
    // `created_at` (clients can never supply it — see CreateEdgeRequest).
    let id = validated
        .id
        .clone()
        .unwrap_or_else(|| Uuid::new_v4().to_string());
    let created_at = chrono::Utc::now().to_rfc3339();
    let (edge, record) = build_edge_record(validated, id, created_at);

    // --- Persist ---
    // Persist to the configured edge-create write source. Only after a
    // successful durable write is the cache mutated, and the two write sources
    // are mutually exclusive (no dual-write): JSONL mode never touches
    // PostgreSQL, PostgreSQL mode never appends JSONL.
    match state.config.domain_edge_write_source {
        DomainEdgeWriteSource::Jsonl => {
            // Serialize JSONL creates so check-then-write is atomic
            let _persist_guard = edge_create_persist_lock().lock().await;

            // Inspect the persistence source itself, not only the cache: when
            // `max_edges_cache_limit()` truncated the load, the cache holds only a
            // prefix of the file. A duplicate id hiding in the unmaterialized suffix
            // and a write that could never be materialized after a restart must both
            // be rejected here. Duplicate wins over the limit so the client gets the
            // more precise cause.
            let persistence = inspect_edge_persistence_for_create(&edge.id)
                .await
                .map_err(|e| {
                    tracing::error!(error = %e, "failed to inspect edges JSONL before create");
                    (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        "failed to persist edge".to_string(),
                    )
                })?;
            if persistence.duplicate_id {
                return Err((StatusCode::CONFLICT, "edge id already exists".to_string()));
            }
            if persistence.cache_limit_reached {
                return Err((StatusCode::CONFLICT, "edge cache limit reached".to_string()));
            }

            // The cache-level duplicate check stays: tests may seed the cache
            // directly, and it guards the exceptional case of cache/persistence
            // divergence.
            {
                let edges = state.edges.read().await;
                if edges.get(&edge.id).is_some() {
                    return Err((StatusCode::CONFLICT, "edge id already exists".to_string()));
                }
            }

            // Only after a successful durable append is the cache mutated. A failed
            // write must never leave a phantom edge in memory.
            if let Err(e) = append_edge_line(&record).await {
                tracing::error!(error = %e, "failed to append edge to JSONL");
                return Err((
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "failed to persist edge".to_string(),
                ));
            }

            {
                let mut edges = state.edges.write().await;
                edges.insert(edge.id.clone(), edge.clone());
            }
        }
        DomainEdgeWriteSource::Postgres => {
            // No JSONL inspection and no JSONL append in this mode: the plain
            // INSERT's primary key makes a duplicate id surface as 409, and a
            // restart reloads edges from domain_edges.
            //
            // The cache-level duplicate check stays for parity with the JSONL
            // arm: tests may seed the cache directly.
            {
                let edges = state.edges.read().await;
                if edges.get(&edge.id).is_some() {
                    return Err((StatusCode::CONFLICT, "edge id already exists".to_string()));
                }
            }

            // Startup validation guarantees a pool exists in this mode; treat a
            // missing pool as an internal error rather than silently degrading
            // to JSONL.
            let pool = state.db_pool.as_ref().ok_or_else(|| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "PostgreSQL pool unavailable for edge write".to_string(),
                )
            })?;
            match insert_domain_edge(pool, &edge).await {
                Ok(()) => {}
                Err(EdgeWriteError::DuplicateId) => {
                    return Err((StatusCode::CONFLICT, "edge id already exists".to_string()));
                }
                Err(EdgeWriteError::CacheLimitReached) => {
                    return Err((StatusCode::CONFLICT, "edge cache limit reached".to_string()));
                }
                Err(e) => {
                    tracing::error!(error = %e, "failed to insert edge into domain_edges");
                    return Err((
                        StatusCode::INTERNAL_SERVER_ERROR,
                        "failed to persist edge".to_string(),
                    ));
                }
            }

            {
                let mut edges = state.edges.write().await;
                edges.insert(edge.id.clone(), edge.clone());
            }
        }
    }

    tracing::info!(
        event = "edge.created",
        edge_id = %edge.id,
        write_source = ?state.config.domain_edge_write_source,
        "Edge created"
    );

    Ok((StatusCode::CREATED, Json(edge)))
}

/// Edge-create request contract — OPT-ARC-001 Phase E-C, PR-1 (Semantik-Lock).
///
/// This module locks the *accepted* shape and validation rules of a
/// `POST /edges` create request without taking on routing, persistence, or
/// status-code concerns. The [`create_edge`] handler (PR-2, JSONL edge create)
/// consumes `CreateEdgeRequest` / `CreateEdgeRequest::validate` and owns the
/// HTTP mapping.
///
/// Locked semantics (see
/// `docs/reports/domain-edge-create-semantics-preflight.md`):
/// - `created_at` is not accepted from clients — the server owns the timestamp.
/// - `expires_at` is not accepted — it must never be silently dropped, so it is
///   rejected via `deny_unknown_fields` rather than ignored.
/// - `payload` / `metadata` are not accepted (the edge contract forbids them).
/// - any other unknown field is rejected instead of silently ignored.
/// - `source_type` / `target_type` are required and enum-checked.
/// - `edge_kind` is required and enum-checked.
/// - `source_id` / `target_id` are required, non-blank, and UUID-formatted.
/// - `id` is optional but, when present, must be non-blank and UUID-formatted.
/// - `note` is optional but, when present, must be non-blank and ≤ 1000 chars.
///
/// `deny_unknown_fields` is applied **only** to `CreateEdgeRequest`, never to the
/// read-side `Edge` model, so existing JSONL/read semantics stay untouched.
mod edge_create {
    use serde::de::{self, Deserialize, Deserializer, Visitor};
    use std::fmt;
    use uuid::Uuid;

    /// Allowed `edge_kind` values, mirroring `contracts/domain/edge.schema.json`.
    const EDGE_KIND_VALUES: [&str; 4] = ["delegation", "membership", "ownership", "reference"];

    /// Allowed `source_type` / `target_type` values, mirroring the edge contract.
    const EDGE_PARTICIPANT_TYPE_VALUES: [&str; 3] = ["role", "node", "account"];

    /// Maximum `note` length in characters, mirroring the edge contract
    /// (`maxLength: 1000`). JSON Schema counts characters, not bytes.
    const EDGE_NOTE_MAX_LEN: usize = 1000;

    /// Deserialize an optional string field with hardened null-semantics: the
    /// field may be **absent** (`#[serde(default)]` yields `None`) but an
    /// explicit JSON `null` is **rejected** instead of being coerced to `None`.
    /// A present value must be a string; numbers, objects, and arrays fail.
    ///
    /// This keeps "optional" meaning "may be omitted" rather than "may be
    /// nulled", so a client cannot erase an edge field by sending `null` — no
    /// silent meaning-loss in JSON costume.
    fn deserialize_optional_non_null_string<'de, D>(
        deserializer: D,
    ) -> Result<Option<String>, D::Error>
    where
        D: Deserializer<'de>,
    {
        struct OptionalNonNullStringVisitor;

        impl<'de> Visitor<'de> for OptionalNonNullStringVisitor {
            type Value = Option<String>;

            fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
                formatter.write_str("a string or an absent field, not null")
            }

            fn visit_some<D>(self, deserializer: D) -> Result<Self::Value, D::Error>
            where
                D: Deserializer<'de>,
            {
                String::deserialize(deserializer).map(Some)
            }

            fn visit_none<E>(self) -> Result<Self::Value, E>
            where
                E: de::Error,
            {
                Err(E::custom("null is not allowed; omit the field instead"))
            }

            fn visit_unit<E>(self) -> Result<Self::Value, E>
            where
                E: de::Error,
            {
                Err(E::custom("null is not allowed; omit the field instead"))
            }
        }

        deserializer.deserialize_option(OptionalNonNullStringVisitor)
    }

    /// Accepted shape of a future `POST /edges` create request.
    ///
    /// `created_at`, `expires_at`, `payload`, and `metadata` are intentionally
    /// absent; together with `deny_unknown_fields` they are rejected rather than
    /// silently dropped. `source_type` and `target_type` are **required**,
    /// matching the domain contract. The remaining optional fields `id` and
    /// `note` may be omitted but reject an explicit `null`, so "optional" never
    /// quietly collapses into "nullable".
    ///
    /// `pub(super)` exposes the type to the parent `edges` module so the upcoming
    /// POST /edges handler can consume it without a later visibility rework.
    #[derive(Debug, serde::Deserialize)]
    #[serde(deny_unknown_fields)]
    pub(super) struct CreateEdgeRequest {
        #[serde(default, deserialize_with = "deserialize_optional_non_null_string")]
        id: Option<String>,
        source_id: String,
        target_id: String,
        edge_kind: String,
        source_type: String,
        target_type: String,
        #[serde(default, deserialize_with = "deserialize_optional_non_null_string")]
        note: Option<String>,
    }

    /// Validated form of a `CreateEdgeRequest`.
    ///
    /// Values are preserved verbatim — no lowercasing, no trimming into storage.
    /// Whitespace is only inspected to reject blank required/optional fields.
    /// Fields are `pub(super)` so the upcoming POST /edges handler in the parent
    /// `edges` module can read the validated values directly.
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub(super) struct ValidatedCreateEdge {
        pub(super) id: Option<String>,
        pub(super) source_id: String,
        pub(super) target_id: String,
        pub(super) edge_kind: String,
        pub(super) source_type: String,
        pub(super) target_type: String,
        pub(super) note: Option<String>,
    }

    /// Why a `CreateEdgeRequest` failed validation.
    ///
    /// Intentionally HTTP-agnostic: this PR fixes the create contract and its
    /// validation only. Status-code mapping belongs to the POST /edges PR.
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub(super) enum EdgeCreateValidationError {
        /// A required field was missing/blank, or an optional field that, when
        /// present, must be non-blank (`id`, `note`) was blank.
        MissingOrEmptyField(&'static str),
        /// An enum-constrained field held a value outside its allowed set.
        InvalidEnumValue { field: &'static str, value: String },
        /// An id-like field (`id`, `source_id`, `target_id`) was not a valid UUID.
        InvalidUuid { field: &'static str, value: String },
        /// `note` exceeded the contract maximum of 1000 characters.
        NoteTooLong,
    }

    /// Reject a field that is empty or whitespace-only.
    fn require_non_blank(
        field: &'static str,
        value: &str,
    ) -> Result<(), EdgeCreateValidationError> {
        if value.trim().is_empty() {
            return Err(EdgeCreateValidationError::MissingOrEmptyField(field));
        }
        Ok(())
    }

    /// Reject a value outside its allowed enum set. Matching is exact: wrong
    /// casing fails (no case-folding, no normalization).
    fn require_enum(
        field: &'static str,
        value: &str,
        allowed: &[&str],
    ) -> Result<(), EdgeCreateValidationError> {
        if allowed.contains(&value) {
            Ok(())
        } else {
            Err(EdgeCreateValidationError::InvalidEnumValue {
                field,
                value: value.to_string(),
            })
        }
    }

    /// Reject a value that is not a valid UUID (any form `uuid::Uuid` accepts).
    fn require_uuid(field: &'static str, value: &str) -> Result<(), EdgeCreateValidationError> {
        Uuid::parse_str(value)
            .map(|_| ())
            .map_err(|_| EdgeCreateValidationError::InvalidUuid {
                field,
                value: value.to_string(),
            })
    }

    impl CreateEdgeRequest {
        /// Validate into a `ValidatedCreateEdge` without mutating values.
        ///
        /// Pure: no persistence, no UUID generation, no timestamping. Order:
        /// (1) required fields non-blank, (2) `id`/`source_id`/`target_id` UUID
        /// format, (3) `edge_kind`/`source_type`/`target_type` exact enum
        /// members, (4) `note` non-blank and ≤ 1000 characters when present.
        /// `id` stays optional so the server can generate it; when present it
        /// must be a UUID.
        pub(super) fn validate(self) -> Result<ValidatedCreateEdge, EdgeCreateValidationError> {
            // (1) non-blank required fields.
            require_non_blank("source_id", &self.source_id)?;
            require_non_blank("target_id", &self.target_id)?;
            require_non_blank("edge_kind", &self.edge_kind)?;
            require_non_blank("source_type", &self.source_type)?;
            require_non_blank("target_type", &self.target_type)?;
            if let Some(id) = &self.id {
                require_non_blank("id", id)?;
            }

            // (2) UUID format for id-like fields.
            require_uuid("source_id", &self.source_id)?;
            require_uuid("target_id", &self.target_id)?;
            if let Some(id) = &self.id {
                require_uuid("id", id)?;
            }

            // (3) enum-constrained fields (exact match, no case-folding).
            require_enum("edge_kind", &self.edge_kind, &EDGE_KIND_VALUES)?;
            require_enum(
                "source_type",
                &self.source_type,
                &EDGE_PARTICIPANT_TYPE_VALUES,
            )?;
            require_enum(
                "target_type",
                &self.target_type,
                &EDGE_PARTICIPANT_TYPE_VALUES,
            )?;

            // (4) note: optional, non-blank and within length when present.
            if let Some(note) = &self.note {
                require_non_blank("note", note)?;
                if note.chars().count() > EDGE_NOTE_MAX_LEN {
                    return Err(EdgeCreateValidationError::NoteTooLong);
                }
            }

            Ok(ValidatedCreateEdge {
                id: self.id,
                source_id: self.source_id,
                target_id: self.target_id,
                edge_kind: self.edge_kind,
                source_type: self.source_type,
                target_type: self.target_type,
                note: self.note,
            })
        }
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        // Valid UUIDs for contract-near fixtures: `id`, `source_id`, and
        // `target_id` are UUID-formatted per the domain contract.
        const EDGE_ID: &str = "00000000-0000-0000-0000-000000000001";
        const SOURCE_ID: &str = "00000000-0000-0000-0000-000000000002";
        const TARGET_ID: &str = "00000000-0000-0000-0000-000000000003";

        fn valid_request() -> CreateEdgeRequest {
            CreateEdgeRequest {
                id: None,
                source_id: SOURCE_ID.to_string(),
                target_id: TARGET_ID.to_string(),
                edge_kind: "reference".to_string(),
                source_type: "node".to_string(),
                target_type: "account".to_string(),
                note: None,
            }
        }

        // ---- positive: accepted shapes ----

        #[test]
        fn edge_create_request_accepts_minimal_payload() {
            // "Minimal" now carries the required participant types.
            let json = format!(
                r#"{{"source_id":"{SOURCE_ID}","source_type":"node","target_id":"{TARGET_ID}","target_type":"account","edge_kind":"reference"}}"#
            );
            let req = serde_json::from_str::<CreateEdgeRequest>(&json)
                .expect("minimal request must deserialize");
            assert_eq!(
                req.validate(),
                Ok(ValidatedCreateEdge {
                    id: None,
                    source_id: SOURCE_ID.to_string(),
                    target_id: TARGET_ID.to_string(),
                    edge_kind: "reference".to_string(),
                    source_type: "node".to_string(),
                    target_type: "account".to_string(),
                    note: None,
                })
            );
        }

        #[test]
        fn edge_create_request_accepts_full_payload() {
            let json = format!(
                r#"{{"id":"{EDGE_ID}","source_id":"{SOURCE_ID}","target_id":"{TARGET_ID}","edge_kind":"ownership","source_type":"node","target_type":"account","note":"a note"}}"#
            );
            let req = serde_json::from_str::<CreateEdgeRequest>(&json)
                .expect("full request must deserialize");
            assert_eq!(
                req.validate(),
                Ok(ValidatedCreateEdge {
                    id: Some(EDGE_ID.to_string()),
                    source_id: SOURCE_ID.to_string(),
                    target_id: TARGET_ID.to_string(),
                    edge_kind: "ownership".to_string(),
                    source_type: "node".to_string(),
                    target_type: "account".to_string(),
                    note: Some("a note".to_string()),
                })
            );
        }

        #[test]
        fn edge_create_request_validates_edge_kind_enum() {
            for kind in EDGE_KIND_VALUES {
                let mut req = valid_request();
                req.edge_kind = kind.to_string();
                assert!(
                    req.validate().is_ok(),
                    "edge_kind `{kind}` must be accepted"
                );
            }

            let mut req = valid_request();
            req.edge_kind = "frobnicate".to_string();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::InvalidEnumValue {
                    field: "edge_kind",
                    value: "frobnicate".to_string(),
                })
            );
        }

        // ---- source_type / target_type: required + enum (contract parity) ----

        #[test]
        fn edge_create_request_validates_source_and_target_type_enum() {
            for ty in EDGE_PARTICIPANT_TYPE_VALUES {
                let mut req = valid_request();
                req.source_type = ty.to_string();
                req.target_type = ty.to_string();
                let validated = req.validate().expect("participant type must be accepted");
                assert_eq!(validated.source_type, ty);
                assert_eq!(validated.target_type, ty);
            }
        }

        #[test]
        fn edge_create_request_rejects_missing_source_type() {
            let json = format!(
                r#"{{"source_id":"{SOURCE_ID}","target_id":"{TARGET_ID}","target_type":"account","edge_kind":"reference"}}"#
            );
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(&json).is_err(),
                "source_type is required and must not be omitted"
            );
        }

        #[test]
        fn edge_create_request_rejects_missing_target_type() {
            let json = format!(
                r#"{{"source_id":"{SOURCE_ID}","source_type":"node","target_id":"{TARGET_ID}","edge_kind":"reference"}}"#
            );
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(&json).is_err(),
                "target_type is required and must not be omitted"
            );
        }

        #[test]
        fn edge_create_request_rejects_null_source_type() {
            let json = format!(
                r#"{{"source_id":"{SOURCE_ID}","source_type":null,"target_id":"{TARGET_ID}","target_type":"account","edge_kind":"reference"}}"#
            );
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(&json).is_err(),
                "source_type=null must be rejected"
            );
        }

        #[test]
        fn edge_create_request_rejects_null_target_type() {
            let json = format!(
                r#"{{"source_id":"{SOURCE_ID}","source_type":"node","target_id":"{TARGET_ID}","target_type":null,"edge_kind":"reference"}}"#
            );
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(&json).is_err(),
                "target_type=null must be rejected"
            );
        }

        #[test]
        fn edge_create_request_rejects_blank_source_type() {
            let mut req = valid_request();
            req.source_type = "  ".to_string();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::MissingOrEmptyField(
                    "source_type"
                ))
            );
        }

        #[test]
        fn edge_create_request_rejects_blank_target_type() {
            let mut req = valid_request();
            req.target_type = "   ".to_string();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::MissingOrEmptyField(
                    "target_type"
                ))
            );
        }

        #[test]
        fn edge_create_request_rejects_invalid_source_type() {
            let mut req = valid_request();
            req.source_type = "group".to_string();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::InvalidEnumValue {
                    field: "source_type",
                    value: "group".to_string(),
                })
            );
        }

        #[test]
        fn edge_create_request_rejects_invalid_target_type() {
            let mut req = valid_request();
            req.target_type = "group".to_string();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::InvalidEnumValue {
                    field: "target_type",
                    value: "group".to_string(),
                })
            );
        }

        // ---- id / source_id / target_id: UUID format ----

        #[test]
        fn edge_create_request_rejects_invalid_source_id_uuid() {
            let mut req = valid_request();
            req.source_id = "not-a-uuid".to_string();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::InvalidUuid {
                    field: "source_id",
                    value: "not-a-uuid".to_string(),
                })
            );
        }

        #[test]
        fn edge_create_request_rejects_invalid_target_id_uuid() {
            let mut req = valid_request();
            req.target_id = "not-a-uuid".to_string();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::InvalidUuid {
                    field: "target_id",
                    value: "not-a-uuid".to_string(),
                })
            );
        }

        #[test]
        fn edge_create_request_rejects_invalid_id_uuid_when_present() {
            let mut req = valid_request();
            req.id = Some("not-a-uuid".to_string());
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::InvalidUuid {
                    field: "id",
                    value: "not-a-uuid".to_string(),
                })
            );
        }

        #[test]
        fn edge_create_request_allows_absent_id_for_server_generation() {
            let req = valid_request();
            assert_eq!(req.id, None);
            let validated = req.validate().expect("absent id must be accepted");
            assert_eq!(validated.id, None);
        }

        #[test]
        fn edge_create_request_accepts_valid_uuid_id_when_present() {
            let mut req = valid_request();
            req.id = Some(EDGE_ID.to_string());
            let validated = req.validate().expect("valid uuid id must be accepted");
            assert_eq!(validated.id.as_deref(), Some(EDGE_ID));
        }

        // ---- negative: deny_unknown_fields / silent-drop protection ----

        #[test]
        fn edge_create_request_rejects_expires_at_to_prevent_silent_drop() {
            let json = format!(
                r#"{{"source_id":"{SOURCE_ID}","source_type":"node","target_id":"{TARGET_ID}","target_type":"account","edge_kind":"reference","expires_at":"2026-01-01T00:00:00Z"}}"#
            );
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(&json).is_err(),
                "expires_at must be rejected, never silently dropped"
            );
        }

        #[test]
        fn edge_create_request_rejects_created_at_because_server_owns_timestamp() {
            let json = format!(
                r#"{{"source_id":"{SOURCE_ID}","source_type":"node","target_id":"{TARGET_ID}","target_type":"account","edge_kind":"reference","created_at":"2026-01-01T00:00:00Z"}}"#
            );
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(&json).is_err(),
                "created_at must be rejected; the server owns the create timestamp"
            );
        }

        #[test]
        fn edge_create_request_rejects_payload_and_metadata() {
            let payload = format!(
                r#"{{"source_id":"{SOURCE_ID}","source_type":"node","target_id":"{TARGET_ID}","target_type":"account","edge_kind":"reference","payload":{{}}}}"#
            );
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(&payload).is_err(),
                "payload must be rejected"
            );
            let metadata = format!(
                r#"{{"source_id":"{SOURCE_ID}","source_type":"node","target_id":"{TARGET_ID}","target_type":"account","edge_kind":"reference","metadata":{{}}}}"#
            );
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(&metadata).is_err(),
                "metadata must be rejected"
            );
        }

        #[test]
        fn edge_create_request_rejects_unknown_fields() {
            let json = format!(
                r#"{{"source_id":"{SOURCE_ID}","source_type":"node","target_id":"{TARGET_ID}","target_type":"account","edge_kind":"reference","wat":true}}"#
            );
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(&json).is_err(),
                "unknown fields must be rejected, never silently ignored"
            );
        }

        // ---- negative: explicit null / non-string on optional fields ----
        //
        // `id` and `note` stay optional: absent is valid (proven by
        // edge_create_request_accepts_minimal_payload), but an explicit null or
        // a non-string value must fail rather than collapse to None.

        #[test]
        fn edge_create_request_rejects_null_id() {
            let json = format!(
                r#"{{"id":null,"source_id":"{SOURCE_ID}","source_type":"node","target_id":"{TARGET_ID}","target_type":"account","edge_kind":"reference"}}"#
            );
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(&json).is_err(),
                "id=null must be rejected; omit id instead"
            );
        }

        #[test]
        fn edge_create_request_rejects_null_note() {
            let json = format!(
                r#"{{"source_id":"{SOURCE_ID}","source_type":"node","target_id":"{TARGET_ID}","target_type":"account","edge_kind":"reference","note":null}}"#
            );
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(&json).is_err(),
                "note=null must be rejected; omit note instead"
            );
        }

        #[test]
        fn edge_create_request_rejects_non_string_optional_fields() {
            // Present optional fields must be strings; other JSON types fail.
            let numeric_id = format!(
                r#"{{"id":123,"source_id":"{SOURCE_ID}","source_type":"node","target_id":"{TARGET_ID}","target_type":"account","edge_kind":"reference"}}"#
            );
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(&numeric_id).is_err(),
                "numeric id must be rejected"
            );
            let object_note = format!(
                r#"{{"source_id":"{SOURCE_ID}","source_type":"node","target_id":"{TARGET_ID}","target_type":"account","edge_kind":"reference","note":{{}}}}"#
            );
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(&object_note).is_err(),
                "object note must be rejected"
            );
        }

        // ---- negative: required fields missing (serde level) ----

        #[test]
        fn edge_create_request_rejects_missing_source_id() {
            let json = format!(
                r#"{{"source_type":"node","target_id":"{TARGET_ID}","target_type":"account","edge_kind":"reference"}}"#
            );
            assert!(serde_json::from_str::<CreateEdgeRequest>(&json).is_err());
        }

        #[test]
        fn edge_create_request_rejects_missing_target_id() {
            let json = format!(
                r#"{{"source_id":"{SOURCE_ID}","source_type":"node","target_type":"account","edge_kind":"reference"}}"#
            );
            assert!(serde_json::from_str::<CreateEdgeRequest>(&json).is_err());
        }

        #[test]
        fn edge_create_request_rejects_missing_edge_kind() {
            let json = format!(
                r#"{{"source_id":"{SOURCE_ID}","source_type":"node","target_id":"{TARGET_ID}","target_type":"account"}}"#
            );
            assert!(serde_json::from_str::<CreateEdgeRequest>(&json).is_err());
        }

        // ---- negative: blank required / optional fields (validate level) ----

        #[test]
        fn edge_create_request_rejects_blank_source_id() {
            let mut req = valid_request();
            req.source_id = "   ".to_string();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::MissingOrEmptyField("source_id"))
            );
        }

        #[test]
        fn edge_create_request_rejects_blank_target_id() {
            let mut req = valid_request();
            req.target_id = String::new();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::MissingOrEmptyField("target_id"))
            );
        }

        #[test]
        fn edge_create_request_rejects_blank_edge_kind() {
            let mut req = valid_request();
            req.edge_kind = "  ".to_string();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::MissingOrEmptyField("edge_kind"))
            );
        }

        #[test]
        fn edge_create_request_rejects_blank_id_when_present() {
            let mut req = valid_request();
            req.id = Some("   ".to_string());
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::MissingOrEmptyField("id"))
            );
        }

        #[test]
        fn edge_create_request_rejects_blank_note_when_present() {
            let mut req = valid_request();
            req.note = Some("   ".to_string());
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::MissingOrEmptyField("note"))
            );
        }

        // ---- negative: wrong casing on enums (validate level) ----

        #[test]
        fn edge_create_request_rejects_uppercase_enum_values() {
            // Wrong casing must fail — no automatic lowercasing / normalization.
            let mut req = valid_request();
            req.edge_kind = "Reference".to_string();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::InvalidEnumValue {
                    field: "edge_kind",
                    value: "Reference".to_string(),
                })
            );

            let mut req = valid_request();
            req.source_type = "Node".to_string();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::InvalidEnumValue {
                    field: "source_type",
                    value: "Node".to_string(),
                })
            );

            let mut req = valid_request();
            req.target_type = "Account".to_string();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::InvalidEnumValue {
                    field: "target_type",
                    value: "Account".to_string(),
                })
            );
        }

        // ---- negative / boundary: note length ----

        #[test]
        fn edge_create_request_accepts_note_at_max_length() {
            let mut req = valid_request();
            req.note = Some("a".repeat(EDGE_NOTE_MAX_LEN));
            let validated = req
                .validate()
                .expect("note of exactly the max length must be accepted");
            assert_eq!(
                validated.note.map(|n| n.chars().count()),
                Some(EDGE_NOTE_MAX_LEN)
            );
        }

        #[test]
        fn edge_create_request_rejects_note_over_max_length() {
            let mut req = valid_request();
            req.note = Some("a".repeat(EDGE_NOTE_MAX_LEN + 1));
            assert_eq!(req.validate(), Err(EdgeCreateValidationError::NoteTooLong));
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{max_edges_cache_limit, DEFAULT_MAX_EDGES_CACHE};
    use crate::test_helpers::EnvGuard;
    use serial_test::serial;

    #[test]
    #[serial]
    fn max_edges_cache_invalid_falls_back_to_default() {
        let _env = EnvGuard::set("MAX_EDGES_CACHE", "not-a-number");

        assert_eq!(max_edges_cache_limit(), DEFAULT_MAX_EDGES_CACHE);
    }

    #[test]
    #[serial]
    fn max_edges_cache_absent_returns_default() {
        let _env = EnvGuard::unset("MAX_EDGES_CACHE");

        assert_eq!(max_edges_cache_limit(), DEFAULT_MAX_EDGES_CACHE);
    }
}

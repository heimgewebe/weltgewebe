//! PostgreSQL loaders and mutation helpers for domain data (OPT-ARC-001).
//!
//! JSONL remains the default source. PostgreSQL is used only when the matching
//! read/write source is explicitly selected; route and startup guards prohibit
//! mixed-source writes and silent fallback.

use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use futures_util::TryStreamExt;
use serde_json::{json, Map, Value};
use sqlx::PgPool;
use uuid::Uuid;

use crate::auth::accounts::AccountStore;
use crate::auth::role::Role;
use crate::routes::accounts::{
    map_json_to_public_account, AccountInternal, Location as AccountLocation,
};
use crate::routes::auth::MAX_EMAIL_LEN;
use crate::routes::edges::Edge;
use crate::routes::nodes::{Location, Node};
use crate::state::OrderedCache;

const DEFAULT_TIMESTAMP: &str = "1970-01-01T00:00:00Z";

/// One client-generated create operation, scoped to the authenticated account.
/// Resource ids and timestamps remain server-owned; this key only identifies a
/// retry of the same user action.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CreateOperationKey {
    pub actor_id: String,
    pub operation_id: String,
}

/// Durable create result. `Existing` means the operation key was already
/// committed; the route still verifies that the semantic request is identical.
#[derive(Debug, Clone, PartialEq)]
pub enum CreateWriteOutcome<T> {
    Created,
    Existing(T),
}

type NodeRow = (
    String,
    String,
    String,
    Option<f64>,
    Option<f64>,
    Option<DateTime<Utc>>,
    Option<DateTime<Utc>>,
    String,
);

type EdgeRow = (
    String,
    String,
    String,
    String,
    Option<DateTime<Utc>>,
    String,
);

type AccountRow = (
    String,
    String,
    String,
    Option<String>,
    String,
    i64,
    bool,
    Option<f64>,
    Option<f64>,
    String,
    Option<String>,
    Option<String>,
    String,
    String,
);

fn parse_payload(text: &str) -> Value {
    serde_json::from_str(text).unwrap_or_else(|_| Value::Object(Map::new()))
}

fn payload_string(payload: &Value, key: &str) -> Option<String> {
    payload
        .get(key)
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
}

fn payload_string_array(payload: &Value, key: &str) -> Vec<String> {
    payload
        .get(key)
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|x| x.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default()
}

fn node_timestamps(
    created: Option<DateTime<Utc>>,
    updated: Option<DateTime<Utc>>,
) -> (String, String) {
    let created_s = created.map(|t| t.to_rfc3339());
    let updated_s = updated.map(|t| t.to_rfc3339());
    let created_at = created_s
        .as_ref()
        .or(updated_s.as_ref())
        .cloned()
        .unwrap_or_else(|| DEFAULT_TIMESTAMP.to_string());
    let updated_at = updated_s
        .or(created_s)
        .unwrap_or_else(|| DEFAULT_TIMESTAMP.to_string());
    (created_at, updated_at)
}

pub async fn load_nodes_from_postgres(pool: &PgPool) -> Result<OrderedCache<Node>> {
    let rows: Vec<NodeRow> = sqlx::query_as(
        "SELECT id, kind, title, lat, lon, created_at, updated_at, payload::text \
         FROM domain_nodes ORDER BY id ASC",
    )
    .fetch_all(pool)
    .await
    .context("failed to load nodes from domain_nodes")?;

    let mut cache = OrderedCache::new();
    let mut skipped = 0usize;
    for (id, kind, title, lat, lon, created_at, updated_at, payload_text) in rows {
        let (lat, lon) = match (lat, lon) {
            (Some(lat), Some(lon)) => (lat, lon),
            _ => {
                tracing::warn!(node_id = %id, "skipping domain node with NULL location");
                skipped += 1;
                continue;
            }
        };
        let payload = parse_payload(&payload_text);
        let (created_at, updated_at) = node_timestamps(created_at, updated_at);
        let node = Node {
            id: id.clone(),
            kind,
            title,
            created_at,
            updated_at,
            summary: payload_string(&payload, "summary"),
            info: payload_string(&payload, "info"),
            tags: payload_string_array(&payload, "tags"),
            address: payload_string(&payload, "address"),
            location: Location { lat, lon },
        };
        cache.insert(id, node);
    }

    tracing::info!(count = cache.len(), skipped, "Loaded nodes from PostgreSQL");
    Ok(cache)
}

pub async fn load_edges_from_postgres(pool: &PgPool) -> Result<OrderedCache<Edge>> {
    let max_edges = crate::routes::edges::max_edges_cache_limit();
    let fetch_limit = max_edges.saturating_add(1).min(i64::MAX as usize) as i64;
    let mut rows = sqlx::query_as::<_, EdgeRow>(
        "SELECT id, source_id, target_id, edge_kind, created_at, payload::text \
         FROM domain_edges ORDER BY id ASC LIMIT $1",
    )
    .bind(fetch_limit)
    .fetch(pool);

    let mut cache = OrderedCache::new();
    let mut seen = 0usize;
    let mut truncated = false;
    while let Some((id, source_id, target_id, edge_kind, created_at, payload_text)) = rows
        .try_next()
        .await
        .context("failed to load edges from domain_edges")?
    {
        if seen >= max_edges {
            truncated = true;
            break;
        }

        let payload = parse_payload(&payload_text);
        let edge = Edge {
            id: id.clone(),
            source_id,
            source_type: payload_string(&payload, "source_type"),
            target_id,
            target_type: payload_string(&payload, "target_type"),
            edge_kind,
            note: payload_string(&payload, "note"),
            created_at: created_at.map(|t| t.to_rfc3339()),
        };
        cache.insert(id, edge);
        seen += 1;
    }
    if truncated {
        tracing::warn!(
            max_edges,
            "Edges cache limit reached, truncating PostgreSQL load"
        );
    }
    tracing::info!(
        count = cache.len(),
        truncated,
        "Loaded edges from PostgreSQL"
    );
    Ok(cache)
}

/// Read-only readiness counters for a future `domain_accounts.webauthn_user_id`
/// backfill (AUTH-PG-003).
///
/// This is deliberately an audit surface, not a migration primitive: it reads
/// `domain_accounts` and `passkey_credentials`, classifies unsafe states, and
/// performs no writes. A later backfill/NOT NULL decision must use these counts
/// as evidence instead of assuming that missing UUIDs can be regenerated safely.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct AuthUserIdBackfillAudit {
    pub accounts_total: i64,
    pub accounts_missing_auth_user_id: i64,
    pub credential_rows_total: i64,
    pub credential_account_ids_distinct: i64,
    pub credential_accounts_missing_auth_user_id: i64,
    pub credential_accounts_without_domain_account: i64,
    pub credential_accounts_with_multiple_auth_user_ids: i64,
    pub credential_accounts_with_account_credential_uuid_mismatch: i64,
}

impl AuthUserIdBackfillAudit {
    /// `true` when a later backfill would have any account rows to touch.
    pub fn has_backfill_scope(&self) -> bool {
        self.accounts_missing_auth_user_id > 0
    }

    /// `true` when current credential/account data is not safe for cutover or
    /// a mechanical NOT NULL migration without human review.
    pub fn has_cutover_blockers(&self) -> bool {
        self.credential_accounts_missing_auth_user_id > 0
            || self.credential_accounts_without_domain_account > 0
            || self.credential_accounts_with_multiple_auth_user_ids > 0
            || self.credential_accounts_with_account_credential_uuid_mismatch > 0
    }
}

async fn count_scalar(pool: &PgPool, sql: &str) -> Result<i64> {
    sqlx::query_scalar::<_, i64>(sql)
        .fetch_one(pool)
        .await
        .with_context(|| format!("failed to run AUTH-PG-003 audit query: {sql}"))
}

/// Audit `webauthn_user_id` backfill readiness without mutating the database.
///
/// The counters intentionally separate three cases that would otherwise be
/// easy to flatten incorrectly:
/// - accounts missing `webauthn_user_id` but carrying no credential yet
///   (backfill scope, not automatically a cutover blocker),
/// - credential-bearing accounts whose domain-account row has NULL
///   `webauthn_user_id` (identity repair required before cutover),
/// - credential rows that cannot be reconciled to exactly one account UUID
///   (orphan, multi-UUID, or mismatch blockers).
pub async fn audit_auth_user_id_backfill_readiness(
    pool: &PgPool,
) -> Result<AuthUserIdBackfillAudit> {
    let accounts_total = count_scalar(pool, "SELECT COUNT(*) FROM domain_accounts").await?;
    let accounts_missing_auth_user_id = count_scalar(
        pool,
        "SELECT COUNT(*) FROM domain_accounts WHERE webauthn_user_id IS NULL",
    )
    .await?;
    let credential_rows_total =
        count_scalar(pool, "SELECT COUNT(*) FROM passkey_credentials").await?;
    let credential_account_ids_distinct = count_scalar(
        pool,
        "SELECT COUNT(DISTINCT account_id) FROM passkey_credentials",
    )
    .await?;
    let credential_accounts_missing_auth_user_id = count_scalar(
        pool,
        "SELECT COUNT(*) FROM (\
             SELECT p.account_id \
             FROM passkey_credentials p \
             JOIN domain_accounts a ON a.id = p.account_id \
             WHERE a.webauthn_user_id IS NULL \
             GROUP BY p.account_id\
         ) credential_accounts_with_null_domain_uuid",
    )
    .await?;
    let credential_accounts_without_domain_account = count_scalar(
        pool,
        "SELECT COUNT(*) FROM (\
             SELECT p.account_id \
             FROM passkey_credentials p \
             LEFT JOIN domain_accounts a ON a.id = p.account_id \
             WHERE a.id IS NULL \
             GROUP BY p.account_id\
         ) orphan_credential_accounts",
    )
    .await?;
    let credential_accounts_with_multiple_auth_user_ids = count_scalar(
        pool,
        "SELECT COUNT(*) FROM (\
             SELECT account_id \
             FROM passkey_credentials \
             GROUP BY account_id \
             HAVING COUNT(DISTINCT webauthn_user_id) > 1\
         ) multi_webauthn_user_id_accounts",
    )
    .await?;
    let credential_accounts_with_account_credential_uuid_mismatch = count_scalar(
        pool,
        "SELECT COUNT(*) FROM (\
             SELECT p.account_id \
             FROM passkey_credentials p \
             JOIN domain_accounts a ON a.id = p.account_id \
             WHERE a.webauthn_user_id IS NOT NULL \
               AND p.webauthn_user_id <> a.webauthn_user_id \
             GROUP BY p.account_id\
         ) credential_account_uuid_mismatches",
    )
    .await?;

    Ok(AuthUserIdBackfillAudit {
        accounts_total,
        accounts_missing_auth_user_id,
        credential_rows_total,
        credential_account_ids_distinct,
        credential_accounts_missing_auth_user_id,
        credential_accounts_without_domain_account,
        credential_accounts_with_multiple_auth_user_ids,
        credential_accounts_with_account_credential_uuid_mismatch,
    })
}

/// Project one raw `domain_accounts` row into an `AccountInternal`, applying
/// the same legacy-field normalization (`ron`/`mode`/`visibility`) as the bulk
/// loader. Returns `None` (with a warning logged) when the row fails
/// projection — the caller decides what "no account" means in its context.
fn account_row_to_internal(row: AccountRow) -> Option<AccountInternal> {
    let (
        id,
        kind,
        title,
        legacy_mode,
        db_map_state,
        radius_m,
        disabled,
        location_lat,
        location_lon,
        role,
        email,
        webauthn_text,
        public_text,
        private_text,
    ) = row;

    let public_payload = parse_payload(&public_text);
    let private_payload = parse_payload(&private_text);
    let ron_flag = private_payload
        .get("ron_flag")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let visibility = private_payload.get("visibility").and_then(|v| v.as_str());
    let suppress_public_pos = private_payload
        .get("suppress_public_pos")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let legacy_not_on_map = kind == "ron"
        || ron_flag
        || legacy_mode.as_deref() == Some("ron")
        || visibility == Some("private")
        || suppress_public_pos;
    let effective_map_state = if legacy_not_on_map
        || db_map_state == "not_on_map"
        || location_lat.is_none()
        || location_lon.is_none()
    {
        "not_on_map"
    } else if db_map_state == "radius" || visibility == Some("approximate") || radius_m > 0 {
        "radius"
    } else {
        "exact"
    };
    let effective_radius_m = match effective_map_state {
        "radius" if radius_m == 0 => 250,
        "radius" => radius_m,
        _ => 0,
    };

    let mut record = Map::new();
    record.insert("id".to_string(), json!(id));
    record.insert("type".to_string(), json!("garnrolle"));
    record.insert("title".to_string(), json!(title));
    record.insert("map_state".to_string(), json!(effective_map_state));
    if let Some(summary) = public_payload.get("summary").and_then(|v| v.as_str()) {
        record.insert("summary".to_string(), json!(summary));
    }
    if let Some(tags) = public_payload.get("tags") {
        if tags.is_array() {
            record.insert("tags".to_string(), tags.clone());
        }
    }
    if let (Some(lat), Some(lon)) = (location_lat, location_lon) {
        record.insert("location".to_string(), json!({ "lat": lat, "lon": lon }));
    }
    record.insert(
        "radius_m".to_string(),
        json!(effective_radius_m.max(0) as u64),
    );
    record.insert("disabled".to_string(), json!(disabled));

    let value = Value::Object(record);
    let public = match map_json_to_public_account(&value) {
        Some(public) => public,
        None => {
            tracing::warn!(account_id = %id, "skipping domain account that failed projection");
            return None;
        }
    };
    let role = Role::from_str_lossy(&role);
    let webauthn_user_id = webauthn_text
        .as_deref()
        .and_then(|s| Uuid::parse_str(s).ok())
        .unwrap_or_else(Uuid::new_v4);
    Some(AccountInternal {
        public,
        role,
        email,
        webauthn_user_id,
    })
}

pub async fn load_accounts_from_postgres(pool: &PgPool) -> Result<AccountStore> {
    let rows: Vec<AccountRow> = sqlx::query_as(
        "SELECT id, kind, title, mode, map_state, radius_m, disabled, \
         location_lat, location_lon, role, email, \
         webauthn_user_id::text, public_payload::text, private_payload::text \
         FROM domain_accounts ORDER BY id ASC",
    )
    .fetch_all(pool)
    .await
    .context("failed to load accounts from domain_accounts")?;

    let mut store = AccountStore::new();
    let mut skipped = 0usize;
    let total = rows.len();
    for row in rows {
        match account_row_to_internal(row) {
            Some(account) => store.insert_unindexed(account),
            None => skipped += 1,
        }
    }
    debug_assert!(skipped <= total);
    store.rebuild_email_index();
    tracing::info!(
        count = store.len(),
        skipped,
        "Loaded accounts from PostgreSQL"
    );
    Ok(store)
}

/// Monotonic version advanced by the same triggers that append domain outbox
/// events. A process compares this value with its local projection generation
/// before serving PostgreSQL-backed domain reads.
pub async fn domain_projection_version(pool: &PgPool) -> Result<i64> {
    sqlx::query_scalar("SELECT version FROM domain_projection_state WHERE singleton = TRUE")
        .fetch_one(pool)
        .await
        .context("failed to read domain projection version")
}

/// Load all process-local domain projections while the committed database
/// generation is stable. Reads use independent pooled connections, but the
/// before/after version fence forces a retry whenever a committed domain
/// mutation overlaps the load. Therefore a returned projection cannot combine
/// rows from two committed generations.
pub async fn load_stable_domain_projection_from_postgres(
    pool: &PgPool,
) -> Result<(AccountStore, OrderedCache<Node>, OrderedCache<Edge>, i64)> {
    const MAX_ATTEMPTS: usize = 5;
    for attempt in 1..=MAX_ATTEMPTS {
        let before = domain_projection_version(pool).await?;
        let (accounts, nodes, edges) = tokio::try_join!(
            load_accounts_from_postgres(pool),
            load_nodes_from_postgres(pool),
            load_edges_from_postgres(pool),
        )?;
        let after = domain_projection_version(pool).await?;
        if before == after {
            return Ok((accounts, nodes, edges, after));
        }
        tracing::info!(
            attempt,
            before,
            after,
            "Domain projection changed during reload; retrying stable snapshot"
        );
    }
    anyhow::bail!("domain projection did not stabilize after {MAX_ATTEMPTS} reload attempts")
}

/// Look up exactly one account by its normalized, non-empty email
/// (`lower(btrim(email))`), mirroring the partial unique index
/// [`ACCOUNT_EMAIL_UNIQUE_CONSTRAINT`].
///
/// Used by the auth auto-provisioning race path: when a concurrent insert (a
/// different process, or a prior run) wins the unique-email race, this
/// resolves the account that actually persisted instead of fabricating a
/// second, divergent one.
pub async fn find_account_by_normalized_email(
    pool: &PgPool,
    email_norm: &str,
) -> Result<Option<AccountInternal>> {
    let row: Option<AccountRow> = sqlx::query_as(
        "SELECT id, kind, title, mode, map_state, radius_m, disabled, \
         location_lat, location_lon, role, email, \
         webauthn_user_id::text, public_payload::text, private_payload::text \
         FROM domain_accounts WHERE lower(btrim(email)) = $1",
    )
    .bind(email_norm)
    .fetch_optional(pool)
    .await
    .context("failed to look up account by normalized email")?;

    Ok(row.and_then(account_row_to_internal))
}

// ── OPT-ARC-001 Phase E-B: node-patch write path ────────────────────────────
//
// Narrow PostgreSQL write helper for `PATCH /nodes` only. Applies the current
// JSONL patch semantics (info set/null/no-op, steckbrief cleanup) using a
// SELECT FOR UPDATE + conditional UPDATE transaction. Timestamp semantics are
// intentionally JSONL-parity: supplied `info` patches bump `updated_at` even
// when the projected value is unchanged; `steckbrief` cleanup also bumps it. It
// does NOT touch in-memory caches and does NOT write JSONL — the caller owns
// cache updates.
//
// This helper owns only node patches; account, node-create and edge writes
// use their dedicated helpers below.

/// Subset of node payload fields modified by `PATCH /nodes`.
#[derive(Debug, Clone, PartialEq)]
pub struct NodePatchInput {
    /// `None` = no-op; `Some(Some(s))` = set; `Some(None)` = clear.
    pub info: Option<Option<String>>,
}

/// Error from the node-patch write path.
#[derive(Debug, thiserror::Error)]
pub enum NodeWriteError {
    #[error("node not found")]
    NotFound,
    #[error("invalid edge reference blocks node deletion: {0}")]
    InvalidEdgeReference(String),
    #[error("failed to map node row: {0}")]
    Mapping(#[source] anyhow::Error),
    #[error("failed to serialize node payload: {0}")]
    Serialization(#[source] serde_json::Error),
    #[error("failed to persist node to domain_nodes: {0}")]
    Database(#[source] sqlx::Error),
}

fn node_from_row(row: NodeRow) -> Result<Node, anyhow::Error> {
    let (id, kind, title, lat, lon, created_at, updated_at, payload_text) = row;
    let (lat, lon) = match (lat, lon) {
        (Some(lat), Some(lon)) => (lat, lon),
        _ => anyhow::bail!("domain node {} has NULL location", id),
    };
    let payload = parse_payload(&payload_text);
    let (created_at, updated_at) = node_timestamps(created_at, updated_at);
    Ok(Node {
        id,
        kind,
        title,
        created_at,
        updated_at,
        summary: payload_string(&payload, "summary"),
        info: payload_string(&payload, "info"),
        tags: payload_string_array(&payload, "tags"),
        address: payload_string(&payload, "address"),
        location: Location { lat, lon },
    })
}

fn edge_from_row(row: EdgeRow) -> Result<Edge, anyhow::Error> {
    let (id, source_id, target_id, edge_kind, created_at, payload_text) = row;
    let payload = parse_payload(&payload_text);
    Ok(Edge {
        id,
        source_id,
        source_type: payload_string(&payload, "source_type"),
        target_id,
        target_type: payload_string(&payload, "target_type"),
        edge_kind,
        note: payload_string(&payload, "note"),
        created_at: created_at.map(|t| t.to_rfc3339()),
    })
}

fn serialize_node_payload(node: &Node) -> Result<String, serde_json::Error> {
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

/// Apply a patch to one `domain_nodes` row inside a transaction.
///
/// Semantics:
/// - `info: None` is a no-op (no DB write, `updated_at` unchanged).
/// - `info: Some(Some(s))` sets `info` to `s`.
/// - `info: Some(None)` removes `info` from the payload (key absent after patch).
///   The public `Node` projection is identical to the JSONL handler — both yield
///   `node.info == None` — but the DB payload shape differs: the JSONL handler
///   stores `{"info": null}`, this path stores a payload without the `info` key.
/// - `steckbrief` is removed from the payload if present.
/// - `updated_at` follows the current JSONL patch semantics: supplied `info`
///   patches bump the timestamp even when the public projection is unchanged;
///   `steckbrief` cleanup also bumps it.
///
/// The final `Node` projection is built **before** `tx.commit()` so a mapping or
/// serialization failure cannot produce a DB mutation that returns 500 to the
/// caller.
pub async fn patch_node_in_postgres(
    pool: &PgPool,
    id: &str,
    patch: NodePatchInput,
) -> Result<Node, NodeWriteError> {
    let mut tx = pool.begin().await.map_err(NodeWriteError::Database)?;

    let row: Option<NodeRow> = sqlx::query_as(
        "SELECT id, kind, title, lat, lon, created_at, updated_at, payload::text \
         FROM domain_nodes WHERE id = $1 FOR UPDATE",
    )
    .bind(id)
    .fetch_optional(&mut *tx)
    .await
    .map_err(NodeWriteError::Database)?;

    let (row_id, kind, title, lat, lon, created_at, updated_at, payload_text) = match row {
        Some(r) => r,
        None => {
            tx.rollback().await.ok();
            return Err(NodeWriteError::NotFound);
        }
    };

    let mut payload: serde_json::Value = parse_payload(&payload_text);
    let mut has_changes = false;

    {
        // Reject non-object payloads before any mutation: a non-object payload is
        // data corruption in domain_nodes.payload.
        let obj = payload.as_object_mut().ok_or_else(|| {
            NodeWriteError::Mapping(anyhow::anyhow!("domain node {} has non-object payload", id))
        })?;

        match &patch.info {
            Some(Some(s)) => {
                obj.insert("info".to_string(), serde_json::Value::String(s.clone()));
                has_changes = true;
            }
            Some(None) => {
                obj.remove("info");
                has_changes = true;
            }
            None => {}
        }
        if obj.remove("steckbrief").is_some() {
            has_changes = true;
        }
    }

    // Serialize payload once after all mutations; propagate errors instead of
    // silently falling back to "{}".
    let final_payload_text =
        serde_json::to_string(&payload).map_err(NodeWriteError::Serialization)?;

    let new_updated_at = if has_changes {
        let now = chrono::Utc::now();
        sqlx::query(
            "UPDATE domain_nodes \
             SET payload = $2::jsonb, updated_at = $3 \
             WHERE id = $1",
        )
        .bind(id)
        .bind(&final_payload_text)
        .bind(now)
        .execute(&mut *tx)
        .await
        .map_err(NodeWriteError::Database)?;
        Some(now)
    } else {
        updated_at
    };

    // Build the public projection before commit so a mapping failure cannot persist
    // a DB mutation that returns 500 to the caller.
    let final_node = node_from_row((
        row_id,
        kind,
        title,
        lat,
        lon,
        created_at,
        new_updated_at,
        final_payload_text,
    ))
    .map_err(NodeWriteError::Mapping)?;

    tx.commit().await.map_err(NodeWriteError::Database)?;

    Ok(final_node)
}

pub async fn replace_node_in_postgres(pool: &PgPool, node: &Node) -> Result<(), NodeWriteError> {
    let payload = serialize_node_payload(node).map_err(NodeWriteError::Serialization)?;
    let updated_at = DateTime::parse_from_rfc3339(&node.updated_at)
        .map(|value| value.with_timezone(&Utc))
        .map_err(|error| NodeWriteError::Mapping(anyhow::Error::new(error)))?;
    let result = sqlx::query(
        "UPDATE domain_nodes \
         SET kind = $2, title = $3, lat = $4, lon = $5, updated_at = $6, payload = $7::jsonb \
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
    // Edge creation uses the same table lock. Holding it through the node and
    // projection deletes prevents an edge insert from interleaving with the
    // cascade in another process.
    sqlx::query("LOCK TABLE domain_edges IN EXCLUSIVE MODE")
        .execute(&mut *tx)
        .await
        .map_err(NodeWriteError::Database)?;
    let node_id: Option<String> =
        sqlx::query_scalar("SELECT id FROM domain_nodes WHERE id = $1 FOR UPDATE")
            .bind(id)
            .fetch_optional(&mut *tx)
            .await
            .map_err(NodeWriteError::Database)?;
    if node_id.is_none() {
        tx.rollback().await.ok();
        return Err(NodeWriteError::NotFound);
    }

    let account_collision_exists: bool =
        sqlx::query_scalar("SELECT EXISTS (SELECT 1 FROM domain_accounts WHERE id = $1)")
            .bind(id)
            .fetch_one(&mut *tx)
            .await
            .map_err(NodeWriteError::Database)?;
    let role_collision_exists: bool = sqlx::query_scalar(
        "SELECT EXISTS (\
             SELECT 1 FROM domain_edges \
             WHERE (source_id = $1 AND payload->>'source_type' = 'role') \
                OR (target_id = $1 AND payload->>'target_type' = 'role')\
         )",
    )
    .bind(id)
    .fetch_one(&mut *tx)
    .await
    .map_err(NodeWriteError::Database)?;
    let untyped_endpoint_is_ambiguous = account_collision_exists || role_collision_exists;

    let invalid_edge: Option<(String, Option<String>, Option<String>)> = sqlx::query_as(
        "SELECT id, \
                CASE WHEN source_id = $1 THEN payload->>'source_type' ELSE NULL END AS source_type, \
                CASE WHEN target_id = $1 THEN payload->>'target_type' ELSE NULL END AS target_type \
         FROM domain_edges \
         WHERE (source_id = $1 AND (\
                    jsonb_typeof(payload) <> 'object' \
                 OR (payload ? 'source_type' AND (\
                        jsonb_typeof(payload->'source_type') <> 'string' \
                        OR payload->>'source_type' NOT IN ('node', 'account', 'role')\
                    )) \
                 OR (NOT (payload ? 'source_type') AND $2)\
               )) \
            OR (target_id = $1 AND (\
                    jsonb_typeof(payload) <> 'object' \
                 OR (payload ? 'target_type' AND (\
                        jsonb_typeof(payload->'target_type') <> 'string' \
                        OR payload->>'target_type' NOT IN ('node', 'account', 'role')\
                    )) \
                 OR (NOT (payload ? 'target_type') AND $2)\
               )) \
         ORDER BY id \
         LIMIT 1",
    )
    .bind(id)
    .bind(untyped_endpoint_is_ambiguous)
    .fetch_optional(&mut *tx)
    .await
    .map_err(NodeWriteError::Database)?;
    if let Some((edge_id, source_type, target_type)) = invalid_edge {
        tx.rollback().await.ok();
        return Err(NodeWriteError::InvalidEdgeReference(format!(
            "edge {edge_id} has source_type={source_type:?} target_type={target_type:?} for endpoint id {id}"
        )));
    }

    let edge_ids: Vec<String> = sqlx::query_scalar(
        "DELETE FROM domain_edges \
         WHERE (source_id = $1 AND (\
                    payload->>'source_type' = 'node' \
                 OR (NOT (payload ? 'source_type') AND NOT $2)\
               )) \
            OR (target_id = $1 AND (\
                    payload->>'target_type' = 'node' \
                 OR (NOT (payload ? 'target_type') AND NOT $2)\
               )) \
         RETURNING id",
    )
    .bind(id)
    .bind(untyped_endpoint_is_ambiguous)
    .fetch_all(&mut *tx)
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

// ── node-create write path ──────────────────────────────────────────────────
//
// Narrow PostgreSQL write helper for `POST /nodes` only. Maps the validated
// `Node` the create route already builds (server-owned id/timestamps) into a
// `domain_nodes` row inside a transaction. Payload keys mirror
// `load_nodes_from_postgres` (summary, info, tags, address) — no new key
// names. It does NOT touch in-memory caches and does NOT write JSONL — the
// caller owns cache updates.

/// Error from the node-create write path.
#[derive(Debug, thiserror::Error)]
pub enum NodeCreateError {
    #[error("node id already exists")]
    DuplicateId,
    #[error("failed to map existing node row: {0}")]
    Mapping(#[source] anyhow::Error),
    #[error("failed to serialize node payload: {0}")]
    Serialization(#[source] serde_json::Error),
    #[error("invalid server-generated node timestamp: {0}")]
    InvalidTimestamp(#[source] chrono::ParseError),
    #[error("failed to persist node to domain_nodes: {0}")]
    Database(#[source] sqlx::Error),
}

/// Insert exactly one node row into `domain_nodes` (`POST /nodes`).
///
/// Runs inside a transaction and relies on the primary-key constraint for
/// race-safe duplicate detection. Node ids are server-generated UUIDv4s, so a
/// table-wide lock and a separate precheck would only serialize unrelated
/// writers without adding correctness.
///
/// This function performs no in-memory mutation and writes no JSONL.
pub async fn insert_domain_node(
    pool: &PgPool,
    node: &Node,
    operation: Option<&CreateOperationKey>,
) -> Result<CreateWriteOutcome<Node>, NodeCreateError> {
    let payload = serialize_node_payload(node).map_err(NodeCreateError::Serialization)?;

    // These values are generated by the server. A parse failure therefore
    // signals an internal contract violation and must fail before any write.
    let created_at = DateTime::parse_from_rfc3339(&node.created_at)
        .map(|dt| dt.with_timezone(&Utc))
        .map_err(NodeCreateError::InvalidTimestamp)?;
    let updated_at = DateTime::parse_from_rfc3339(&node.updated_at)
        .map(|dt| dt.with_timezone(&Utc))
        .map_err(NodeCreateError::InvalidTimestamp)?;

    let mut tx = pool.begin().await.map_err(NodeCreateError::Database)?;

    if let Some(operation) = operation {
        let lock_key = crate::advisory_lock::stable_advisory_lock_key(
            "weltgewebe:create-operation:v1",
            &[&operation.actor_id, &operation.operation_id],
        );
        sqlx::query("SELECT pg_advisory_xact_lock($1::bigint)")
            .bind(lock_key)
            .fetch_one(&mut *tx)
            .await
            .map_err(NodeCreateError::Database)?;

        let existing: Option<NodeRow> = sqlx::query_as(
            "SELECT id, kind, title, lat, lon, created_at, updated_at, payload::text \
             FROM domain_nodes \
             WHERE create_actor_id = $1 AND create_operation_id = $2",
        )
        .bind(&operation.actor_id)
        .bind(&operation.operation_id)
        .fetch_optional(&mut *tx)
        .await
        .map_err(NodeCreateError::Database)?;

        if let Some(row) = existing {
            let existing = node_from_row(row).map_err(NodeCreateError::Mapping)?;
            tx.commit().await.map_err(NodeCreateError::Database)?;
            return Ok(CreateWriteOutcome::Existing(existing));
        }
    }

    let result = sqlx::query(
        "INSERT INTO domain_nodes \
            (id, kind, title, lat, lon, created_at, updated_at, payload, \
             create_actor_id, create_operation_id) \
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10)",
    )
    .bind(&node.id)
    .bind(&node.kind)
    .bind(&node.title)
    .bind(node.location.lat)
    .bind(node.location.lon)
    .bind(created_at)
    .bind(updated_at)
    .bind(&payload)
    .bind(operation.map(|value| value.actor_id.as_str()))
    .bind(operation.map(|value| value.operation_id.as_str()))
    .execute(&mut *tx)
    .await;

    match result {
        Ok(_) => {
            tx.commit().await.map_err(NodeCreateError::Database)?;
            Ok(CreateWriteOutcome::Created)
        }
        Err(sqlx::Error::Database(db_err)) if db_err.is_unique_violation() => {
            tx.rollback().await.ok();
            if let Some(operation) = operation {
                let existing: Option<NodeRow> = sqlx::query_as(
                    "SELECT id, kind, title, lat, lon, created_at, updated_at, payload::text \
                     FROM domain_nodes \
                     WHERE create_actor_id = $1 AND create_operation_id = $2",
                )
                .bind(&operation.actor_id)
                .bind(&operation.operation_id)
                .fetch_optional(pool)
                .await
                .map_err(NodeCreateError::Database)?;
                if let Some(row) = existing {
                    return node_from_row(row)
                        .map(CreateWriteOutcome::Existing)
                        .map_err(NodeCreateError::Mapping);
                }
            }
            Err(NodeCreateError::DuplicateId)
        }
        Err(e) => {
            tx.rollback().await.ok();
            Err(NodeCreateError::Database(e))
        }
    }
}

// ── OPT-ARC-001 Phase E-A: account-create write path ────────────────────────
//
// Narrow PostgreSQL write helper for `POST /accounts` only. It maps the same
// validated, JSONL-shaped account record that `create_account` would otherwise
// append to JSONL, using the same semantic mapping as the Phase C backfill
// (`tests/db_domain_backfill.rs::import_accounts`) so that a row written here is
// indistinguishable from "JSONL create + Phase C backfill". It does NOT touch
// in-memory caches and does NOT write JSONL — the caller owns cache updates.
//
// This helper owns account insertion only; node and edge writes use their
// dedicated helpers.

fn json_f64(v: &Value) -> Option<f64> {
    v.as_f64()
        .or_else(|| v.as_str().and_then(|s| s.parse().ok()))
}

fn parse_ts(v: &Value) -> Option<DateTime<Utc>> {
    v.as_str().and_then(|s| s.parse().ok())
}

/// Serialise the listed keys of `source` into a compact JSON object string,
/// skipping absent or null keys (mirrors the Phase C backfill payload helper).
fn payload_from_keys(keys: &[&str], source: &Value) -> String {
    let mut m = Map::new();
    for &k in keys {
        if let Some(val) = source.get(k) {
            if !val.is_null() {
                m.insert(k.to_string(), val.clone());
            }
        }
    }
    serde_json::to_string(&Value::Object(m)).unwrap_or_else(|_| "{}".to_string())
}

/// A single row destined for `domain_accounts`, built from a validated,
/// JSONL-shaped account record. UUID and JSON columns are carried as text so
/// they can be bound with explicit `::uuid` / `::jsonb` casts (the sqlx build
/// has no `uuid` feature), exactly as the Phase C backfill binds them.
#[derive(Debug, Clone, PartialEq)]
pub struct NewDomainAccountRow {
    pub id: String,
    pub kind: String,
    pub title: String,
    pub legacy_mode: Option<String>,
    pub map_state: String,
    pub radius_m: i64,
    pub disabled: bool,
    pub location_lat: Option<f64>,
    pub location_lon: Option<f64>,
    pub role: String,
    pub email: Option<String>,
    /// UUID as text (validated), bound with `$n::uuid`; `None` stores NULL.
    pub webauthn_user_id: Option<String>,
    pub created_at: Option<DateTime<Utc>>,
    pub updated_at: Option<DateTime<Utc>>,
    pub public_payload: String,
    pub private_payload: String,
}

impl NewDomainAccountRow {
    /// Map a validated, JSONL-shaped account record to a `domain_accounts` row.
    ///
    /// This mirrors the Phase C backfill mapping exactly so the Phase D loader
    /// reconstructs the same public projection. In particular:
    /// - `kind` ← `type` (default `garnrolle`)
    /// - `kind` is canonicalised to `garnrolle`
    /// - `map_state` is `not_on_map`, `exact`, or `radius`; legacy `ron` fields
    ///   only force the privacy-safe `not_on_map` state
    /// - the deprecated database `mode` column receives NULL for new writes
    /// - `radius_m` is bumped to 250 when `visibility == "approximate"` and 0
    ///   (idempotent with the loader, which only adjusts when the stored radius
    ///   is still 0)
    /// - `private_payload` preserves only `visibility` and
    ///   `suppress_public_pos` where needed for compatibility. Phase E-A
    ///   `POST /accounts` does not accept `suppress_public_pos` in the request
    ///   payload; privacy on create uses `visibility=private` (or loader defaults).
    /// - `created_at` / `updated_at` are taken from the record if present, else
    ///   NULL. The current create path never sets them, so account-create rows
    ///   store NULL — identical to JSONL-create followed by Phase C backfill.
    ///   These columns are not part of the public projection and are not read by
    ///   the loader, so the choice is non-observable via the API.
    pub fn from_jsonl_record(v: &Value) -> Result<Self> {
        let id = v
            .get("id")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string())
            .context("account record is missing a non-empty id")?;

        let legacy_kind = v
            .get("type")
            .and_then(|v| v.as_str())
            .unwrap_or("garnrolle");
        let kind = "garnrolle".to_string();
        let title = v
            .get("title")
            .and_then(|v| v.as_str())
            .unwrap_or("Untitled")
            .to_string();

        let ron_flag = v.get("ron_flag").and_then(|v| v.as_bool()).unwrap_or(false);
        let visibility = v.get("visibility").and_then(|v| v.as_str());
        let explicit_mode = v.get("mode").and_then(|v| v.as_str());
        let disabled = v.get("disabled").and_then(|v| v.as_bool()).unwrap_or(false);

        let location_lat = v
            .get("location")
            .and_then(|l| l.get("lat"))
            .and_then(json_f64);
        let location_lon = v
            .get("location")
            .and_then(|l| l.get("lon"))
            .and_then(json_f64);

        let role = v
            .get("role")
            .and_then(|v| v.as_str())
            .unwrap_or("gast")
            .to_string();

        // Normalize like the API create path: trim, then treat an after-trim
        // empty value as "no email" (None). This keeps the persisted value
        // consistent with the normalized unique index `lower(btrim(email))` and
        // the `domain_accounts_email_not_empty_after_trim` check constraint.
        let email = v
            .get("email")
            .and_then(|v| v.as_str())
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string());

        // Only persist a UUID we can actually parse; otherwise store NULL.
        let webauthn_user_id = v
            .get("webauthn_user_id")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .filter(|s| Uuid::parse_str(s).is_ok())
            .map(|s| s.to_string());

        let created_at = v.get("created_at").and_then(parse_ts);
        let updated_at = v.get("updated_at").and_then(parse_ts);

        let legacy_not_on_map = legacy_kind == "ron"
            || ron_flag
            || explicit_mode == Some("ron")
            || visibility == Some("private")
            || v.get("suppress_public_pos")
                .and_then(|value| value.as_bool())
                .unwrap_or(false);
        let mut radius_m: i64 = v.get("radius_m").and_then(|v| v.as_u64()).unwrap_or(0) as i64;
        let explicit_map_state = v.get("map_state").and_then(|v| v.as_str());
        if let Some(state) = explicit_map_state {
            if !matches!(state, "not_on_map" | "exact" | "radius") {
                anyhow::bail!("invalid account map_state: {state}");
            }
        }
        let map_state = if legacy_not_on_map
            || explicit_map_state == Some("not_on_map")
            || location_lat.is_none()
            || location_lon.is_none()
        {
            radius_m = 0;
            "not_on_map".to_string()
        } else if explicit_map_state == Some("radius")
            || visibility == Some("approximate")
            || radius_m > 0
        {
            if radius_m == 0 {
                radius_m = 250;
            }
            "radius".to_string()
        } else {
            radius_m = 0;
            "exact".to_string()
        };

        let public_payload = payload_from_keys(&["summary", "tags"], v);

        let mut priv_map = Map::new();
        if let Some(address) = v
            .get("address")
            .and_then(|value| value.as_str())
            .map(str::trim)
            .filter(|value| !value.is_empty())
        {
            priv_map.insert("address".to_string(), Value::String(address.to_string()));
        }
        if let Some(vis) = visibility {
            priv_map.insert("visibility".to_string(), Value::String(vis.to_string()));
            if vis == "private" {
                priv_map.insert("suppress_public_pos".to_string(), Value::Bool(true));
            }
        }
        let private_payload = if priv_map.is_empty() {
            "{}".to_string()
        } else {
            serde_json::to_string(&Value::Object(priv_map))
                .context("failed to serialise account private_payload")?
        };

        Ok(Self {
            id,
            kind,
            title,
            legacy_mode: None,
            map_state,
            radius_m,
            disabled,
            location_lat,
            location_lon,
            role,
            email,
            webauthn_user_id,
            created_at,
            updated_at,
            public_payload,
            private_payload,
        })
    }
}

/// Name of the partial unique index that enforces normalized account-email
/// uniqueness (`lower(btrim(email))` where the trimmed email is non-empty).
/// Kept in sync with the migration
/// `20260613000001_domain_accounts_email_normalized_unique`.
pub const ACCOUNT_EMAIL_UNIQUE_CONSTRAINT: &str = "domain_accounts_email_normalized_unique";

/// Name of the `domain_accounts` primary-key constraint (PostgreSQL default
/// `<table>_pkey`). Kept in sync with the table definition in
/// `20260531000003_create_domain_accounts`.
pub const ACCOUNT_ID_PRIMARY_KEY_CONSTRAINT: &str = "domain_accounts_pkey";

/// Error from the account-create write path.
#[derive(Debug, thiserror::Error)]
pub enum AccountWriteError {
    /// The account `id` (primary key) already exists in `domain_accounts`.
    #[error("account id already exists")]
    DuplicateId,
    /// Another account already persists the same normalized, non-empty email
    /// (`lower(btrim(email))`), rejected by the partial unique index
    /// [`ACCOUNT_EMAIL_UNIQUE_CONSTRAINT`].
    #[error("account email already exists")]
    DuplicateEmail,
    /// The JSONL-shaped record could not be mapped to a row.
    #[error("failed to map account record: {0}")]
    Mapping(#[source] anyhow::Error),
    /// Any other database failure.
    #[error("failed to persist account to domain_accounts: {0}")]
    Database(#[source] sqlx::Error),
}

/// Insert exactly one account row into `domain_accounts` (Phase E-A).
///
/// A plain `INSERT` (no `ON CONFLICT`) is used on purpose: account creation must
/// never silently overwrite an existing account. The database unique constraints
/// are the race-safety boundary; a violation is classified by constraint name so
/// the route can return a precise `409 CONFLICT` cause: a primary-key collision
/// surfaces as [`AccountWriteError::DuplicateId`], and a normalized-email
/// collision (the partial unique index [`ACCOUNT_EMAIL_UNIQUE_CONSTRAINT`]) as
/// [`AccountWriteError::DuplicateEmail`]. This function performs no in-memory
/// mutation and writes no JSONL.
pub async fn insert_account_from_jsonl_record(
    pool: &PgPool,
    record: &Value,
) -> Result<(), AccountWriteError> {
    let row = NewDomainAccountRow::from_jsonl_record(record).map_err(AccountWriteError::Mapping)?;

    let result = sqlx::query(
        "INSERT INTO domain_accounts \
            (id, kind, title, mode, map_state, radius_m, disabled, \
             location_lat, location_lon, \
             role, email, webauthn_user_id, \
             created_at, updated_at, \
             public_payload, private_payload) \
         VALUES \
            ($1, $2, $3, $4, $5, $6, $7, \
             $8, $9, \
             $10, $11, $12::uuid, \
             $13, $14, \
             $15::jsonb, $16::jsonb)",
    )
    .bind(&row.id)
    .bind(&row.kind)
    .bind(&row.title)
    .bind(row.legacy_mode.as_deref())
    .bind(&row.map_state)
    .bind(row.radius_m)
    .bind(row.disabled)
    .bind(row.location_lat)
    .bind(row.location_lon)
    .bind(&row.role)
    .bind(row.email.as_deref())
    .bind(row.webauthn_user_id.as_deref())
    .bind(row.created_at)
    .bind(row.updated_at)
    .bind(&row.public_payload)
    .bind(&row.private_payload)
    .execute(pool)
    .await;

    match result {
        Ok(_) => Ok(()),
        Err(sqlx::Error::Database(db_err)) if db_err.is_unique_violation() => {
            // Classify ONLY the two constraints this code owns; both map to a
            // precise 409 cause with distinct error bodies. Any other unique
            // violation (e.g. a future constraint) stays a generic database
            // error instead of being mislabelled as a duplicate id. Each
            // `constraint()` borrow ends at the comparison, so `db_err` can be
            // moved back into the generic error in the final branch.
            if db_err.constraint() == Some(ACCOUNT_EMAIL_UNIQUE_CONSTRAINT) {
                Err(AccountWriteError::DuplicateEmail)
            } else if db_err.constraint() == Some(ACCOUNT_ID_PRIMARY_KEY_CONSTRAINT) {
                Err(AccountWriteError::DuplicateId)
            } else {
                Err(AccountWriteError::Database(sqlx::Error::Database(db_err)))
            }
        }
        Err(e) => Err(AccountWriteError::Database(e)),
    }
}

/// Name of the check constraint that rejects after-trim empty persisted emails.

#[derive(Debug, Clone, PartialEq)]
pub struct AccountProfileUpdate {
    pub title: String,
    pub summary: Option<String>,
    pub tags: Vec<String>,
    pub address: Option<String>,
    pub map_state: String,
    pub radius_m: i64,
    pub location: Option<AccountLocation>,
}

#[derive(Debug, Clone)]
pub struct StoredAccountProfile {
    pub account: AccountInternal,
    pub address: Option<String>,
    pub location: Option<AccountLocation>,
}

#[derive(Debug, thiserror::Error)]
pub enum AccountProfileUpdateError {
    #[error("account not found")]
    NotFound,
    #[error("a map location is required for this visibility")]
    MissingLocation,
    #[error("failed to serialise account profile: {0}")]
    Serialization(#[source] serde_json::Error),
    #[error("failed to map updated account")]
    Mapping,
    #[error("failed to update account profile in domain_accounts: {0}")]
    Database(#[source] sqlx::Error),
}

pub async fn load_account_profile_from_postgres(
    pool: &PgPool,
    account_id: &str,
) -> Result<Option<(Option<String>, Option<AccountLocation>)>, sqlx::Error> {
    let row: Option<(Option<String>, Option<f64>, Option<f64>)> = sqlx::query_as(
        "SELECT private_payload->>'address', location_lat, location_lon \
         FROM domain_accounts WHERE id = $1",
    )
    .bind(account_id)
    .fetch_optional(pool)
    .await?;

    Ok(row.map(|(address, lat, lon)| {
        let location = match (lat, lon) {
            (Some(lat), Some(lon)) => Some(AccountLocation { lat, lon }),
            _ => None,
        };
        (address, location)
    }))
}

pub async fn update_account_profile_in_postgres(
    pool: &PgPool,
    account_id: &str,
    update: &AccountProfileUpdate,
) -> Result<StoredAccountProfile, AccountProfileUpdateError> {
    let mut tx = pool
        .begin()
        .await
        .map_err(AccountProfileUpdateError::Database)?;
    let existing: Option<(Option<f64>, Option<f64>)> = sqlx::query_as(
        "SELECT location_lat, location_lon FROM domain_accounts WHERE id = $1 FOR UPDATE",
    )
    .bind(account_id)
    .fetch_optional(&mut *tx)
    .await
    .map_err(AccountProfileUpdateError::Database)?;
    let Some((existing_lat, existing_lon)) = existing else {
        return Err(AccountProfileUpdateError::NotFound);
    };

    let effective_location = update
        .location
        .clone()
        .or(match (existing_lat, existing_lon) {
            (Some(lat), Some(lon)) => Some(AccountLocation { lat, lon }),
            _ => None,
        });
    if update.map_state != "not_on_map" && effective_location.is_none() {
        return Err(AccountProfileUpdateError::MissingLocation);
    }

    let mut public_map = Map::new();
    if let Some(summary) = &update.summary {
        public_map.insert("summary".to_string(), Value::String(summary.clone()));
    }
    if !update.tags.is_empty() {
        public_map.insert("tags".to_string(), json!(update.tags));
    }
    let public_payload = serde_json::to_string(&Value::Object(public_map))
        .map_err(AccountProfileUpdateError::Serialization)?;

    let mut private_map = Map::new();
    if let Some(address) = &update.address {
        private_map.insert("address".to_string(), Value::String(address.clone()));
    }
    let private_payload = serde_json::to_string(&Value::Object(private_map))
        .map_err(AccountProfileUpdateError::Serialization)?;

    let (new_lat, new_lon) = match &update.location {
        Some(location) => (Some(location.lat), Some(location.lon)),
        None => (None, None),
    };

    let row: AccountRow = sqlx::query_as(
        "UPDATE domain_accounts SET \
           title = $2, \
           map_state = $3, \
           radius_m = $4, \
           location_lat = COALESCE($5, location_lat), \
           location_lon = COALESCE($6, location_lon), \
           public_payload = (public_payload - 'summary' - 'tags') || $7::jsonb, \
           private_payload = (private_payload - 'address' - 'visibility' - 'suppress_public_pos' - 'ron_flag') || $8::jsonb, \
           updated_at = now() \
         WHERE id = $1 \
         RETURNING id, kind, title, mode, map_state, radius_m, disabled, \
           location_lat, location_lon, role, email, webauthn_user_id::text, \
           public_payload::text, private_payload::text",
    )
    .bind(account_id)
    .bind(&update.title)
    .bind(&update.map_state)
    .bind(update.radius_m)
    .bind(new_lat)
    .bind(new_lon)
    .bind(&public_payload)
    .bind(&private_payload)
    .fetch_one(&mut *tx)
    .await
    .map_err(AccountProfileUpdateError::Database)?;

    tx.commit()
        .await
        .map_err(AccountProfileUpdateError::Database)?;
    let account = account_row_to_internal(row).ok_or(AccountProfileUpdateError::Mapping)?;
    Ok(StoredAccountProfile {
        account,
        address: update.address.clone(),
        location: effective_location,
    })
}

pub const ACCOUNT_EMAIL_NOT_EMPTY_CONSTRAINT: &str = "domain_accounts_email_not_empty_after_trim";

/// Error from the account email update write path.
#[derive(Debug, thiserror::Error)]
pub enum AccountEmailUpdateError {
    /// The account id does not exist in `domain_accounts`.
    #[error("account not found")]
    NotFound,
    /// Another account already persists the same normalized, non-empty email.
    #[error("account email already exists")]
    DuplicateEmail,
    /// The supplied email cannot be persisted under the DB email constraints.
    #[error("invalid account email")]
    InvalidEmail,
    /// Any other database failure.
    #[error("failed to update account email in domain_accounts: {0}")]
    Database(#[source] sqlx::Error),
}

/// Update one account email in `domain_accounts` (AUTH-PG-001).
///
/// This helper performs no in-memory mutation and writes no JSONL. Callers must
/// update the `AccountStore` only after this function returns `Ok(())`, so the
/// PostgreSQL path remains DB-before-cache and restart-stable.
pub async fn update_account_email_in_postgres(
    pool: &PgPool,
    account_id: &str,
    new_email: &str,
) -> Result<DateTime<Utc>, AccountEmailUpdateError> {
    let new_email = new_email.trim().to_ascii_lowercase();
    if new_email.is_empty() || new_email.len() > MAX_EMAIL_LEN {
        return Err(AccountEmailUpdateError::InvalidEmail);
    }

    let result = sqlx::query_scalar::<_, DateTime<Utc>>(
        "UPDATE domain_accounts \
         SET email = $2, updated_at = now() \
         WHERE id = $1 \
         RETURNING updated_at",
    )
    .bind(account_id)
    .bind(&new_email)
    .fetch_optional(pool)
    .await;

    match result {
        Ok(Some(updated_at)) => Ok(updated_at),
        Ok(None) => Err(AccountEmailUpdateError::NotFound),
        Err(sqlx::Error::Database(db_err)) => {
            if db_err.constraint() == Some(ACCOUNT_EMAIL_UNIQUE_CONSTRAINT) {
                Err(AccountEmailUpdateError::DuplicateEmail)
            } else if db_err.constraint() == Some(ACCOUNT_EMAIL_NOT_EMPTY_CONSTRAINT) {
                Err(AccountEmailUpdateError::InvalidEmail)
            } else {
                Err(AccountEmailUpdateError::Database(sqlx::Error::Database(
                    db_err,
                )))
            }
        }
        Err(e) => Err(AccountEmailUpdateError::Database(e)),
    }
}

// ── OPT-ARC-001 Phase E-C: edge-create write path ───────────────────────────
//
// Narrow PostgreSQL helper for internal derived-Faden projection. It maps the same
// validated `Edge` value that `create_edge` puts into the cache and the
// response (built via the canonical `build_edge_record` semantics), so the
// PostgreSQL branch accepts exactly the same create semantics as JSONL. The
// payload keys mirror `load_edges_from_postgres` (source_type, target_type,
// note) — no new key names. It does NOT touch in-memory caches and does NOT
// write JSONL — the caller owns cache updates.
//
// This helper owns edge insertion only; account and node writes use their
// dedicated helpers.

/// A single row destined for `domain_edges`, built from the validated `Edge`
/// the create route already uses for cache and response. `payload` is carried
/// as text and bound with an explicit `::jsonb` cast, exactly as the account
/// write path binds its payloads.
#[derive(Debug, Clone, PartialEq)]
pub struct NewDomainEdgeRow {
    pub id: String,
    pub source_id: String,
    pub target_id: String,
    pub edge_kind: String,
    /// Server-owned create timestamp. Required for new creates: the column is
    /// nullable for legacy/import contexts, but a create must never drop it.
    pub created_at: DateTime<Utc>,
    pub payload: String,
}

impl NewDomainEdgeRow {
    /// Map a validated `Edge` (cache/response value of `create_edge`) to a
    /// `domain_edges` row.
    ///
    /// - `created_at` must be present and RFC3339-parseable; otherwise mapping
    ///   fails and the route returns 500 without any DB or cache mutation.
    /// - `payload` carries `source_type` / `target_type` (when present) and
    ///   `note` only when `Some` — absent means omitted, never `null` —
    ///   matching what `load_edges_from_postgres` reads back.
    /// - `expires_at`, `payload`, `metadata` create fields do not exist here:
    ///   `CreateEdgeRequest` rejects them via `deny_unknown_fields`.
    pub fn from_edge(edge: &crate::routes::edges::Edge) -> Result<Self> {
        let created_at_text = edge
            .created_at
            .as_deref()
            .context("edge record is missing created_at")?;
        let created_at = DateTime::parse_from_rfc3339(created_at_text)
            .with_context(|| format!("edge created_at is not RFC3339: {created_at_text}"))?
            .with_timezone(&Utc);

        let mut payload_map = Map::new();
        if let Some(source_type) = &edge.source_type {
            payload_map.insert(
                "source_type".to_string(),
                Value::String(source_type.clone()),
            );
        }
        if let Some(target_type) = &edge.target_type {
            payload_map.insert(
                "target_type".to_string(),
                Value::String(target_type.clone()),
            );
        }
        if let Some(note) = &edge.note {
            payload_map.insert("note".to_string(), Value::String(note.clone()));
        }
        let payload = serde_json::to_string(&Value::Object(payload_map))
            .context("failed to serialise edge payload")?;

        Ok(Self {
            id: edge.id.clone(),
            source_id: edge.source_id.clone(),
            target_id: edge.target_id.clone(),
            edge_kind: edge.edge_kind.clone(),
            created_at,
            payload,
        })
    }
}

/// Error from the edge-create write path.
#[derive(Debug, thiserror::Error)]
pub enum EdgeWriteError {
    /// The edge `id` (primary key) already exists in `domain_edges`.
    #[error("edge id already exists")]
    DuplicateId,
    /// The edge cache limit has been reached, preventing insert.
    #[error("edge cache limit reached")]
    CacheLimitReached,
    /// The validated edge could not be mapped to a row.
    #[error("failed to map edge record: {0}")]
    Mapping(#[source] anyhow::Error),
    /// Any other database failure.
    #[error("failed to persist edge to domain_edges: {0}")]
    Database(#[source] sqlx::Error),
}

/// Insert exactly one edge row into `domain_edges` (Phase E-C).
///
/// The PostgreSQL create path is serialized in a transaction:
/// table-level lock, duplicate precheck, cache-limit count check, then final
/// INSERT. Duplicate ids are checked before the cache-limit condition so the
/// client receives the more precise 409 cause. A unique violation can still
/// surface as a defensive fallback.
///
/// This function performs no in-memory mutation and writes no JSONL.
pub async fn insert_domain_edge(
    pool: &PgPool,
    edge: &crate::routes::edges::Edge,
    operation: Option<&CreateOperationKey>,
) -> Result<CreateWriteOutcome<Edge>, EdgeWriteError> {
    let row = NewDomainEdgeRow::from_edge(edge).map_err(EdgeWriteError::Mapping)?;

    let mut tx = pool.begin().await.map_err(EdgeWriteError::Database)?;

    // The existing edge path already serializes creates for cache-limit and
    // duplicate-id semantics. The operation lookup belongs inside the same
    // transaction so a replay cannot race the first insert.
    sqlx::query("LOCK TABLE domain_edges IN EXCLUSIVE MODE")
        .execute(&mut *tx)
        .await
        .map_err(EdgeWriteError::Database)?;

    if let Some(operation) = operation {
        let existing: Option<EdgeRow> = sqlx::query_as(
            "SELECT id, source_id, target_id, edge_kind, created_at, payload::text \
             FROM domain_edges \
             WHERE create_actor_id = $1 AND create_operation_id = $2",
        )
        .bind(&operation.actor_id)
        .bind(&operation.operation_id)
        .fetch_optional(&mut *tx)
        .await
        .map_err(EdgeWriteError::Database)?;
        if let Some(row) = existing {
            let existing = edge_from_row(row).map_err(EdgeWriteError::Mapping)?;
            tx.commit().await.map_err(EdgeWriteError::Database)?;
            return Ok(CreateWriteOutcome::Existing(existing));
        }
    }

    let (exists,): (bool,) =
        sqlx::query_as("SELECT EXISTS (SELECT 1 FROM domain_edges WHERE id = $1)")
            .bind(&row.id)
            .fetch_one(&mut *tx)
            .await
            .map_err(EdgeWriteError::Database)?;

    if exists {
        tx.rollback().await.ok();
        return Err(EdgeWriteError::DuplicateId);
    }

    let max_edges = crate::routes::edges::max_edges_cache_limit();
    let max_edges_i64 = i64::try_from(max_edges).unwrap_or(i64::MAX);

    let (limit_reached,): (bool,) = sqlx::query_as("SELECT COUNT(*) >= $1 FROM domain_edges")
        .bind(max_edges_i64)
        .fetch_one(&mut *tx)
        .await
        .map_err(EdgeWriteError::Database)?;

    if limit_reached {
        tx.rollback().await.ok();
        return Err(EdgeWriteError::CacheLimitReached);
    }

    let result = sqlx::query(
        "INSERT INTO domain_edges \
            (id, source_id, target_id, edge_kind, created_at, payload, \
             create_actor_id, create_operation_id) \
         VALUES \
            ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)",
    )
    .bind(&row.id)
    .bind(&row.source_id)
    .bind(&row.target_id)
    .bind(&row.edge_kind)
    .bind(row.created_at)
    .bind(&row.payload)
    .bind(operation.map(|value| value.actor_id.as_str()))
    .bind(operation.map(|value| value.operation_id.as_str()))
    .execute(&mut *tx)
    .await;

    match result {
        Ok(_) => {
            tx.commit().await.map_err(EdgeWriteError::Database)?;
            Ok(CreateWriteOutcome::Created)
        }
        Err(sqlx::Error::Database(db_err)) if db_err.is_unique_violation() => {
            tx.rollback().await.ok();
            if let Some(operation) = operation {
                let existing: Option<EdgeRow> = sqlx::query_as(
                    "SELECT id, source_id, target_id, edge_kind, created_at, payload::text \
                     FROM domain_edges \
                     WHERE create_actor_id = $1 AND create_operation_id = $2",
                )
                .bind(&operation.actor_id)
                .bind(&operation.operation_id)
                .fetch_optional(pool)
                .await
                .map_err(EdgeWriteError::Database)?;
                if let Some(row) = existing {
                    return edge_from_row(row)
                        .map(CreateWriteOutcome::Existing)
                        .map_err(EdgeWriteError::Mapping);
                }
            }
            Err(EdgeWriteError::DuplicateId)
        }
        Err(e) => {
            tx.rollback().await.ok();
            Err(EdgeWriteError::Database(e))
        }
    }
}

#[cfg(test)]
mod edge_write_path_tests {
    use super::*;
    use crate::routes::edges::Edge;

    fn create_edge_value() -> Edge {
        Edge {
            id: "00000000-0000-0000-0000-0000000000e1".to_string(),
            source_id: "00000000-0000-0000-0000-0000000000a1".to_string(),
            source_type: Some("node".to_string()),
            target_id: "00000000-0000-0000-0000-0000000000b1".to_string(),
            target_type: Some("account".to_string()),
            edge_kind: "reference".to_string(),
            note: None,
            created_at: Some("2026-06-12T10:00:00+00:00".to_string()),
        }
    }

    #[test]
    fn maps_create_edge_with_loader_compatible_payload_keys() {
        let mut edge = create_edge_value();
        edge.note = Some("a note".to_string());
        let row = NewDomainEdgeRow::from_edge(&edge).expect("map");
        assert_eq!(row.id, edge.id);
        assert_eq!(row.source_id, edge.source_id);
        assert_eq!(row.target_id, edge.target_id);
        assert_eq!(row.edge_kind, "reference");
        assert_eq!(row.created_at.to_rfc3339(), "2026-06-12T10:00:00+00:00");
        // Payload keys must match what load_edges_from_postgres reads back.
        let payload: Value = serde_json::from_str(&row.payload).expect("payload json");
        assert_eq!(
            payload.get("source_type").and_then(|v| v.as_str()),
            Some("node")
        );
        assert_eq!(
            payload.get("target_type").and_then(|v| v.as_str()),
            Some("account")
        );
        assert_eq!(payload.get("note").and_then(|v| v.as_str()), Some("a note"));
    }

    #[test]
    fn omits_note_key_when_note_is_absent() {
        let row = NewDomainEdgeRow::from_edge(&create_edge_value()).expect("map");
        let payload: Value = serde_json::from_str(&row.payload).expect("payload json");
        assert!(
            payload.get("note").is_none(),
            "absent note must be omitted, never null"
        );
    }

    #[test]
    fn rejects_missing_created_at() {
        let mut edge = create_edge_value();
        edge.created_at = None;
        let err = NewDomainEdgeRow::from_edge(&edge).unwrap_err();
        assert!(err.to_string().contains("missing created_at"));
    }

    #[test]
    fn rejects_unparseable_created_at() {
        let mut edge = create_edge_value();
        edge.created_at = Some("yesterday".to_string());
        let err = NewDomainEdgeRow::from_edge(&edge).unwrap_err();
        assert!(err.to_string().contains("not RFC3339"));
    }
}

#[cfg(test)]
mod write_path_tests {
    use super::*;
    use serde_json::json;

    // The tests below exercise the row-mapper/backfill-parity surface for
    // JSONL-shaped records. Not every legacy/privacy field covered here is
    // currently route-reachable through `POST /accounts`.

    /// The create route builds exactly this record shape before persistence.
    fn create_record() -> Value {
        json!({
            "id": "writepath-unit-1",
            "type": "garnrolle",
            "map_state": "radius",
            "title": "Unit",
            "summary": "A summary",
            "tags": ["x", "y"],
            "role": "weber",
            "location": { "lat": 53.5, "lon": 10.0 },
            "radius_m": 250,
            "email": "unit@example.test"
        })
    }

    #[test]
    fn maps_create_record_like_backfill() {
        let row = NewDomainAccountRow::from_jsonl_record(&create_record()).expect("map");
        assert_eq!(row.id, "writepath-unit-1");
        assert_eq!(row.kind, "garnrolle");
        assert_eq!(row.title, "Unit");
        assert_eq!(row.legacy_mode, None);
        assert_eq!(row.map_state, "radius");
        assert_eq!(row.radius_m, 250);
        assert!(!row.disabled);
        assert_eq!(row.location_lat, Some(53.5));
        assert_eq!(row.location_lon, Some(10.0));
        assert_eq!(row.role, "weber");
        assert_eq!(row.email.as_deref(), Some("unit@example.test"));
        // create records carry no webauthn_user_id / timestamps
        assert_eq!(row.webauthn_user_id, None);
        assert_eq!(row.created_at, None);
        assert_eq!(row.updated_at, None);
        // public_payload carries summary + tags
        let public: Value = serde_json::from_str(&row.public_payload).expect("public json");
        assert_eq!(
            public.get("summary").and_then(|v| v.as_str()),
            Some("A summary")
        );
        assert!(public.get("tags").and_then(|v| v.as_array()).is_some());
        // New writes do not persist the legacy identity mode.
        let private: Value = serde_json::from_str(&row.private_payload).expect("private json");
        assert!(private.get("mode").is_none());
        assert!(private.get("visibility").is_none());
        assert!(private.get("ron_flag").is_none());
    }

    #[test]
    fn private_visibility_sets_suppress_public_pos() {
        let record = json!({
            "id": "writepath-unit-private",
            "type": "garnrolle",
            "title": "Private",
            "location": { "lat": 53.5, "lon": 10.0 },
            "visibility": "private"
        });
        let row = NewDomainAccountRow::from_jsonl_record(&record).expect("map");
        let private: Value = serde_json::from_str(&row.private_payload).expect("private json");
        assert_eq!(
            private.get("visibility").and_then(|v| v.as_str()),
            Some("private")
        );
        assert_eq!(
            private.get("suppress_public_pos").and_then(|v| v.as_bool()),
            Some(true)
        );
    }

    #[test]
    fn invalid_explicit_map_state_is_rejected() {
        let record = json!({
            "id": "writepath-unit-invalid-state",
            "type": "garnrolle",
            "title": "Invalid state",
            "map_state": "public-ish",
            "location": { "lat": 53.5, "lon": 10.0 }
        });
        let error = NewDomainAccountRow::from_jsonl_record(&record)
            .expect_err("unknown map_state must not be repaired implicitly");
        assert!(error.to_string().contains("invalid account map_state"));
    }

    #[test]
    fn explicit_not_on_map_keeps_internal_location_private() {
        let record = json!({
            "id": "writepath-unit-hidden-location",
            "type": "garnrolle",
            "title": "Hidden location",
            "map_state": "not_on_map",
            "location": { "lat": 53.5, "lon": 10.0 },
            "radius_m": 500
        });
        let row = NewDomainAccountRow::from_jsonl_record(&record).expect("map");
        assert_eq!(row.map_state, "not_on_map");
        assert_eq!(row.radius_m, 0);
        assert_eq!(row.location_lat, Some(53.5));
        assert_eq!(row.location_lon, Some(10.0));
        assert_eq!(row.legacy_mode, None);
    }

    #[test]
    fn approximate_zero_radius_becomes_250() {
        let record = json!({
            "id": "writepath-unit-approx",
            "type": "garnrolle",
            "title": "Approx",
            "location": { "lat": 53.5, "lon": 10.0 },
            "visibility": "approximate",
            "radius_m": 0
        });
        let row = NewDomainAccountRow::from_jsonl_record(&record).expect("map");
        assert_eq!(row.radius_m, 250);
    }

    #[test]
    fn payload_from_keys_preserves_selected_non_null_fields() {
        let source = serde_json::json!({
            "summary": "hello",
            "tags": ["a", "b"],
            "private_note": "secret",
            "empty": null
        });

        let payload = payload_from_keys(&["summary", "tags", "empty", "missing"], &source);
        let parsed: serde_json::Value = serde_json::from_str(&payload).unwrap();

        assert_eq!(
            parsed,
            serde_json::json!({
                "summary": "hello",
                "tags": ["a", "b"]
            })
        );
    }

    #[test]
    fn payload_from_keys_returns_empty_object_for_missing_or_null_fields() {
        let source = serde_json::json!({
            "summary": null,
            "private_note": "secret"
        });

        let payload = payload_from_keys(&["summary", "tags"], &source);

        assert_eq!(payload, "{}");
    }

    #[test]
    fn ron_flag_normalizes_to_not_on_map() {
        let record = json!({
            "id": "writepath-unit-ron",
            "type": "garnrolle",
            "title": "Ron",
            "ron_flag": true
        });
        let row = NewDomainAccountRow::from_jsonl_record(&record).expect("map");
        assert_eq!(row.legacy_mode, None);
        assert_eq!(row.map_state, "not_on_map");
        let private: Value = serde_json::from_str(&row.private_payload).expect("private json");
        assert!(private.get("ron_flag").is_none());
    }

    #[test]
    fn email_is_trimmed_and_after_trim_empty_becomes_none() {
        let with_email = |email: Value| json!({ "id": "wp-email", "type": "garnrolle", "title": "E", "email": email });
        let no_email = json!({ "id": "wp-email", "type": "garnrolle", "title": "E" });

        let map = |v: &Value| {
            NewDomainAccountRow::from_jsonl_record(v)
                .expect("map")
                .email
        };

        assert_eq!(map(&no_email), None, "missing email => None");
        assert_eq!(map(&with_email(Value::Null)), None, "null email => None");
        assert_eq!(map(&with_email(json!(""))), None, "empty email => None");
        assert_eq!(
            map(&with_email(json!("   "))),
            None,
            "after-trim-empty email => None"
        );
        assert_eq!(
            map(&with_email(json!(" alpha@example.invalid "))).as_deref(),
            Some("alpha@example.invalid"),
            "surrounding whitespace is trimmed"
        );
    }
}

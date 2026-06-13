//! Read-only PostgreSQL loaders for domain data (OPT-ARC-001 Phase D).
//!
//! JSONL remains the default read source and write truth. These loaders are
//! only used when `DomainReadSource::Postgres` is explicitly selected.

use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use futures_util::TryStreamExt;
use serde_json::{json, Map, Value};
use sqlx::PgPool;
use uuid::Uuid;

use crate::auth::accounts::AccountStore;
use crate::auth::role::Role;
use crate::routes::accounts::{map_json_to_public_account, AccountInternal};
use crate::routes::edges::Edge;
use crate::routes::nodes::{Location, Node};
use crate::state::OrderedCache;

const DEFAULT_TIMESTAMP: &str = "1970-01-01T00:00:00Z";

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

pub async fn load_accounts_from_postgres(pool: &PgPool) -> Result<AccountStore> {
    let rows: Vec<AccountRow> = sqlx::query_as(
        "SELECT id, kind, title, mode, radius_m, disabled, \
         location_lat, location_lon, role, email, \
         webauthn_user_id::text, public_payload::text, private_payload::text \
         FROM domain_accounts ORDER BY id ASC",
    )
    .fetch_all(pool)
    .await
    .context("failed to load accounts from domain_accounts")?;

    let mut store = AccountStore::new();
    let mut skipped = 0usize;
    for (
        id,
        kind,
        title,
        db_mode,
        radius_m,
        disabled,
        location_lat,
        location_lon,
        role,
        email,
        webauthn_text,
        public_text,
        private_text,
    ) in rows
    {
        let public_payload = parse_payload(&public_text);
        let private_payload = parse_payload(&private_text);
        let ron_flag = private_payload
            .get("ron_flag")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let visibility = private_payload.get("visibility").and_then(|v| v.as_str());
        let effective_mode = if kind == "ron" || ron_flag {
            "ron".to_string()
        } else {
            db_mode
        };
        let effective_radius_m = if visibility == Some("approximate") && radius_m == 0 {
            250
        } else {
            radius_m
        };

        let mut record = Map::new();
        record.insert("id".to_string(), json!(id));
        record.insert("type".to_string(), json!(kind));
        record.insert("title".to_string(), json!(title));
        record.insert("mode".to_string(), json!(effective_mode));
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
        if let Some(vis) = visibility {
            record.insert("visibility".to_string(), json!(vis));
        }
        if ron_flag {
            record.insert("ron_flag".to_string(), json!(true));
        }

        let value = Value::Object(record);
        let mut public = match map_json_to_public_account(&value) {
            Some(public) => public,
            None => {
                tracing::warn!(account_id = %id, "skipping domain account that failed projection");
                skipped += 1;
                continue;
            }
        };
        let suppress_public_pos = private_payload
            .get("suppress_public_pos")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        if suppress_public_pos {
            public.public_pos = None;
        }
        let role = Role::from_str_lossy(&role);
        let webauthn_user_id = webauthn_text
            .as_deref()
            .and_then(|s| Uuid::parse_str(s).ok())
            .unwrap_or_else(Uuid::new_v4);
        store.insert_unindexed(AccountInternal {
            public,
            role,
            email,
            webauthn_user_id,
        });
    }
    store.rebuild_email_index();
    tracing::info!(
        count = store.len(),
        skipped,
        "Loaded accounts from PostgreSQL"
    );
    Ok(store)
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
// Out of scope (unchanged): account writes, edge writes, step-up email
// persistence, WebAuthn user-id writeback.

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
        location: Location { lat, lon },
    })
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

// ── OPT-ARC-001 Phase E-A: account-create write path ────────────────────────
//
// Narrow PostgreSQL write helper for `POST /accounts` only. It maps the same
// validated, JSONL-shaped account record that `create_account` would otherwise
// append to JSONL, using the same semantic mapping as the Phase C backfill
// (`tests/db_domain_backfill.rs::import_accounts`) so that a row written here is
// indistinguishable from "JSONL create + Phase C backfill". It does NOT touch
// in-memory caches and does NOT write JSONL — the caller owns cache updates.
//
// Out of scope (unchanged): node writes, edge writes, step-up email persistence,
// WebAuthn user-id writeback persistence.

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
    pub mode: String,
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
    /// - `mode` ← explicit `mode`, else `ron` when `type == "ron"` or `ron_flag`,
    ///   else `verortet` when visibility or coordinates are present, else `ron`
    /// - `radius_m` is bumped to 250 when `visibility == "approximate"` and 0
    ///   (idempotent with the loader, which only adjusts when the stored radius
    ///   is still 0)
    /// - `private_payload` preserves `visibility`, `suppress_public_pos` (for
    ///   private visibility), `ron_flag`, and the explicit `mode`. Phase E-A
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

        let email = v
            .get("email")
            .and_then(|v| v.as_str())
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

        let mode = if let Some(m) = explicit_mode {
            m.to_string()
        } else if kind == "ron" || ron_flag {
            "ron".to_string()
        } else if visibility.is_some() || (location_lat.is_some() && location_lon.is_some()) {
            "verortet".to_string()
        } else {
            "ron".to_string()
        };

        let mut radius_m: i64 = v.get("radius_m").and_then(|v| v.as_u64()).unwrap_or(0) as i64;
        if visibility == Some("approximate") && radius_m == 0 {
            radius_m = 250;
        }

        let public_payload = payload_from_keys(&["summary", "tags"], v);

        let mut priv_map = Map::new();
        if let Some(vis) = visibility {
            priv_map.insert("visibility".to_string(), Value::String(vis.to_string()));
            if vis == "private" {
                priv_map.insert("suppress_public_pos".to_string(), Value::Bool(true));
            }
        }
        if ron_flag {
            priv_map.insert("ron_flag".to_string(), Value::Bool(true));
        }
        if let Some(em) = explicit_mode {
            priv_map.insert("mode".to_string(), Value::String(em.to_string()));
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
            mode,
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
            (id, kind, title, mode, radius_m, disabled, \
             location_lat, location_lon, \
             role, email, webauthn_user_id, \
             created_at, updated_at, \
             public_payload, private_payload) \
         VALUES \
            ($1, $2, $3, $4, $5, $6, \
             $7, $8, \
             $9, $10, $11::uuid, \
             $12, $13, \
             $14::jsonb, $15::jsonb)",
    )
    .bind(&row.id)
    .bind(&row.kind)
    .bind(&row.title)
    .bind(&row.mode)
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
            // Classify the violated unique constraint by name so the route can
            // return a precise 409 cause. A normalized-email collision and a
            // primary-key (account id) collision both map to 409, but carry
            // distinct error bodies.
            if db_err.constraint() == Some(ACCOUNT_EMAIL_UNIQUE_CONSTRAINT) {
                Err(AccountWriteError::DuplicateEmail)
            } else {
                Err(AccountWriteError::DuplicateId)
            }
        }
        Err(e) => Err(AccountWriteError::Database(e)),
    }
}

// ── OPT-ARC-001 Phase E-C: edge-create write path ───────────────────────────
//
// Narrow PostgreSQL write helper for `POST /edges` only. It maps the same
// validated `Edge` value that `create_edge` puts into the cache and the
// response (built via the canonical `build_edge_record` semantics), so the
// PostgreSQL branch accepts exactly the same create semantics as JSONL. The
// payload keys mirror `load_edges_from_postgres` (source_type, target_type,
// note) — no new key names. It does NOT touch in-memory caches and does NOT
// write JSONL — the caller owns cache updates.
//
// Out of scope (unchanged): account writes, node writes, step-up email
// persistence, WebAuthn user-id writeback persistence.

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
) -> Result<(), EdgeWriteError> {
    let row = NewDomainEdgeRow::from_edge(edge).map_err(EdgeWriteError::Mapping)?;

    let mut tx = pool.begin().await.map_err(EdgeWriteError::Database)?;

    sqlx::query("LOCK TABLE domain_edges IN EXCLUSIVE MODE")
        .execute(&mut *tx)
        .await
        .map_err(EdgeWriteError::Database)?;

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
            (id, source_id, target_id, edge_kind, created_at, payload) \
         VALUES \
            ($1, $2, $3, $4, $5, $6::jsonb)",
    )
    .bind(&row.id)
    .bind(&row.source_id)
    .bind(&row.target_id)
    .bind(&row.edge_kind)
    .bind(row.created_at)
    .bind(&row.payload)
    .execute(&mut *tx)
    .await;

    match result {
        Ok(_) => {
            tx.commit().await.map_err(EdgeWriteError::Database)?;
            Ok(())
        }
        Err(sqlx::Error::Database(db_err)) if db_err.is_unique_violation() => {
            tx.rollback().await.ok();
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
            "mode": "verortet",
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
        assert_eq!(row.mode, "verortet");
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
        // private_payload preserves the explicit mode (mirrors backfill)
        let private: Value = serde_json::from_str(&row.private_payload).expect("private json");
        assert_eq!(
            private.get("mode").and_then(|v| v.as_str()),
            Some("verortet")
        );
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
    fn ron_flag_forces_ron_mode() {
        let record = json!({
            "id": "writepath-unit-ron",
            "type": "garnrolle",
            "title": "Ron",
            "ron_flag": true
        });
        let row = NewDomainAccountRow::from_jsonl_record(&record).expect("map");
        assert_eq!(row.mode, "ron");
        let private: Value = serde_json::from_str(&row.private_payload).expect("private json");
        assert_eq!(
            private.get("ron_flag").and_then(|v| v.as_bool()),
            Some(true)
        );
    }
}

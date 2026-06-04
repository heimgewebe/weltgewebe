//! Read-only PostgreSQL loaders for domain data (OPT-ARC-001 Phase D).
//!
//! These functions read nodes, edges, and accounts from the Phase B domain
//! tables (`domain_nodes`, `domain_edges`, `domain_accounts`) into the same
//! in-memory types used by the JSONL runtime path: [`OrderedCache`],
//! [`OrderedCache`], and [`AccountStore`].
//!
//! They are strictly read-only:
//!
//! - no writes, no upserts, no migrations, no JSONL backfill;
//! - the startup switch is implemented behind [`crate::config::DomainReadSource`];
//!   JSONL remains the default; Postgres is opt-in;
//! - write path remains JSONL until Phase E.
//!
//! A loader is only ever invoked when an operator explicitly opts in via the
//! [`crate::config::DomainReadSource`] gate.
//!
//! ## Ordering contract
//!
//! Every loader orders rows by `id ASC` (primary-key order). This matches the
//! stable, id-ascending order already used by the cursor-pagination endpoints.
//! It deliberately does **not** reproduce the legacy JSONL file/insertion order
//! used by the offset path; legacy-offset parity with JSONL is out of scope.
//!
//! ## JSONB handling
//!
//! The sqlx build for this crate does not enable the `json` feature, so JSONB
//! columns are read as TEXT (via `::text`) and parsed with `serde_json` in Rust.
//! Booleans inside JSONB are read from the parsed value, never cast directly
//! with `::bool` in SQL.
//!
//! ## Account privacy parity
//!
//! The public projection of an account is computed by the **same** function as
//! the JSONL runtime path ([`map_json_to_public_account`]): the loader
//! reconstructs a JSONL-shaped record from the row and feeds it through that
//! function. This guarantees identical mode/jitter/visibility handling. The one
//! rule that function does not model — an explicit `suppress_public_pos=true`
//! without `visibility=private` — is applied as an explicit override afterwards.

use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use serde_json::{json, Map, Value};
use sqlx::PgPool;
use uuid::Uuid;

use crate::auth::accounts::AccountStore;
use crate::auth::role::Role;
use crate::routes::accounts::{map_json_to_public_account, AccountInternal};
use crate::routes::edges::Edge;
use crate::routes::nodes::{Location, Node};
use crate::state::OrderedCache;

/// Matches the JSONL `Node` fallback timestamp (see `From<NodeDto> for Node`).
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
            (Some(la), Some(lo)) => (la, lo),
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

    tracing::info!(
        count = cache.len(),
        skipped,
        "Loaded nodes from PostgreSQL (domain_nodes)"
    );
    Ok(cache)
}

pub async fn load_edges_from_postgres(pool: &PgPool) -> Result<OrderedCache<Edge>> {
    let max_edges = crate::routes::edges::max_edges_cache_limit();
    let fetch_limit = max_edges.saturating_add(1).min(i64::MAX as usize) as i64;

    let rows: Vec<EdgeRow> = sqlx::query_as(
        "SELECT id, source_id, target_id, edge_kind, created_at, payload::text \
         FROM domain_edges ORDER BY id ASC LIMIT $1",
    )
    .bind(fetch_limit)
    .fetch_all(pool)
    .await
    .context("failed to load edges from domain_edges")?;

    let truncated = rows.len() > max_edges;
    let mut cache = OrderedCache::new();
    for (id, source_id, target_id, edge_kind, created_at, payload_text) in
        rows.into_iter().take(max_edges)
    {
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
    }

    if truncated {
        tracing::warn!(
            max_edges,
            "Edges cache limit reached, truncating PostgreSQL domain_edges load"
        );
    }

    tracing::info!(
        count = cache.len(),
        truncated,
        "Loaded edges from PostgreSQL (domain_edges)"
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
                tracing::warn!(
                    account_id = %id,
                    "skipping domain account that failed public projection"
                );
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
        "Loaded accounts from PostgreSQL (domain_accounts)"
    );
    Ok(store)
}

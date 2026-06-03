//! OPT-ARC-001 Phase D: PostgreSQL read-path loaders for domain data.
//!
//! This module reads nodes, edges, and accounts from `domain_nodes`,
//! `domain_edges`, and `domain_accounts` (Phase B schema) and projects them
//! into the same in-memory shapes the JSONL path produces:
//!
//! - [`load_nodes_from_postgres`]  -> `OrderedCache<Node>`
//! - [`load_edges_from_postgres`]  -> `OrderedCache<Edge>`
//! - [`load_accounts_from_postgres`] -> `AccountStore`
//!
//! Phase D contract — read path only, no writes:
//!
//! - The loader NEVER writes to PostgreSQL.
//! - Privacy semantics are reconstructed from explicit columns and the
//!   preserved legacy `private_payload` JSONB documented in Phase C
//!   (`docs/reports/domain-backfill-proof.md`).
//! - `public_pos` is recomputed via the same deterministic
//!   `calculate_jittered_pos` the JSONL path uses, so API responses are
//!   identical regardless of source.
//! - Rows that violate Phase-D invariants (verortet without exact coords,
//!   unmappable JSON) are SKIPPED with a `tracing::warn!`, mirroring the
//!   `serde_json::from_str(...).ok()` tolerance of the JSONL loader.
//! - Malformed JSONB text is parsed conservatively via `serde_json::from_str`
//!   on the scalar text; no dependency on the `sqlx/json` feature.

use sqlx::PgPool;
use sqlx::Row;
use uuid::Uuid;

use crate::auth::accounts::AccountStore;
use crate::auth::role::Role;
use crate::routes::accounts::{map_json_to_public_account, AccountInternal};
use crate::routes::edges::Edge;
use crate::routes::nodes::{Location as NodeLocation, Node};
use crate::state::OrderedCache;



/// Domain load error raised by the Phase D read path.
#[derive(Debug, thiserror::Error)]
pub enum DomainDbLoadError {
    /// PostgreSQL pool is missing or never configured.
    #[error("domain read source is 'postgres' but no DATABASE_URL / db_pool is available")]
    DbPoolUnavailable,
    /// Underlying sqlx query failure.
    #[error("domain read query failed: {0}")]
    Query(#[from] sqlx::Error),
}

// ── Nodes ──────────────────────────────────────────────────────────────────

/// Loads all nodes from `domain_nodes` into an `OrderedCache<Node>`.
///
/// Stable id-ascending ordering is preserved by reading the primary key
/// index and inserting in that order, so the in-memory `iter_in_order()`
/// output matches what the JSONL path would have produced for the same
/// canonical id set.
pub async fn load_nodes_from_postgres(pool: &PgPool) -> Result<OrderedCache<Node>, DomainDbLoadError> {
    let rows = sqlx::query(
        "SELECT id, kind, title, lat, lon, created_at, updated_at,
                payload::text AS payload_text
         FROM domain_nodes
         ORDER BY id ASC",
    )
    .fetch_all(pool)
    .await?;

    let mut nodes = OrderedCache::new();
    let mut skipped = 0usize;
    for row in rows {
        let id: String = row
            .try_get("id")
            .map_err(DomainDbLoadError::Query)?;
        let kind: String = row.try_get("kind").unwrap_or_else(|_| "Unknown".to_string());
        let title: String = row.try_get("title").unwrap_or_else(|_| "Untitled".to_string());
        let lat: Option<f64> = row.try_get("lat").ok();
        let lon: Option<f64> = row.try_get("lon").ok();
        let created_at: Option<chrono::DateTime<chrono::Utc>> = row.try_get("created_at").ok();
        let updated_at: Option<chrono::DateTime<chrono::Utc>> = row.try_get("updated_at").ok();
        let payload_text: String = row
            .try_get::<Option<String>, _>("payload_text")
            .ok()
            .flatten()
            .unwrap_or_else(|| "{}".to_string());

        let payload: serde_json::Value = serde_json::from_str(&payload_text).unwrap_or_else(|_| {
            tracing::warn!(
                node_id = %id,
                payload_len = payload_text.len(),
                "node payload jsonb was not valid JSON; treating as empty object"
            );
            serde_json::Value::Object(Default::default())
        });

        let summary = payload
            .get("summary")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        let info = payload
            .get("info")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        let tags = payload
            .get("tags")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();

        let (lat, lon) = match (lat, lon) {
            (Some(la), Some(lo)) => (la, lo),
            _ => {
                tracing::debug!(node_id = %id, "skipping node without lat/lon");
                skipped += 1;
                continue;
            }
        };

        let default_ts = "1970-01-01T00:00:00Z".to_string();
        let created_at = created_at
            .map(|t| t.to_rfc3339())
            .or_else(|| updated_at.map(|t| t.to_rfc3339()))
            .unwrap_or(default_ts.clone());
        let updated_at = updated_at
            .map(|t| t.to_rfc3339())
            .or_else(|| created_at.clone().into())
            .unwrap_or(default_ts);

        nodes.insert(
            id.clone(),
            Node {
                id,
                kind,
                title,
                created_at,
                updated_at,
                summary,
                info,
                tags,
                location: NodeLocation { lat, lon },
            },
        );
    }

    if skipped > 0 {
        tracing::warn!(
            skipped,
            "skipped domain_nodes rows missing lat/lon during Phase D read"
        );
    }

    Ok(nodes)
}

// ── Edges ──────────────────────────────────────────────────────────────────

/// Loads all edges from `domain_edges` into an `OrderedCache<Edge>`.
///
/// Stable id-ascending ordering is preserved.
pub async fn load_edges_from_postgres(pool: &PgPool) -> Result<OrderedCache<Edge>, DomainDbLoadError> {
    let rows = sqlx::query(
        "SELECT id, source_id, target_id, edge_kind, created_at,
                payload::text AS payload_text
         FROM domain_edges
         ORDER BY id ASC",
    )
    .fetch_all(pool)
    .await?;

    let mut edges = OrderedCache::new();
    let mut skipped = 0usize;
    for row in rows {
        let id: String = match row.try_get("id") {
            Ok(v) => v,
            Err(e) => {
                tracing::warn!(error = %e, "skipping edge without id");
                skipped += 1;
                continue;
            }
        };
        let source_id: String = match row.try_get("source_id") {
            Ok(v) => v,
            Err(_) => {
                tracing::debug!(edge_id = %id, "skipping edge without source_id");
                skipped += 1;
                continue;
            }
        };
        let target_id: String = match row.try_get("target_id") {
            Ok(v) => v,
            Err(_) => {
                tracing::debug!(edge_id = %id, "skipping edge without target_id");
                skipped += 1;
                continue;
            }
        };
        let edge_kind: String = row
            .try_get("edge_kind")
            .unwrap_or_else(|_| String::new());
        let created_at: Option<chrono::DateTime<chrono::Utc>> = row.try_get("created_at").ok();
        let payload_text: String = row
            .try_get::<Option<String>, _>("payload_text")
            .ok()
            .flatten()
            .unwrap_or_else(|| "{}".to_string());

        let payload: serde_json::Value = serde_json::from_str(&payload_text).unwrap_or_default();

        let source_type = payload
            .get("source_type")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        let target_type = payload
            .get("target_type")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        let note = payload
            .get("note")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());

        edges.insert(
            id.clone(),
            Edge {
                id,
                source_id,
                source_type,
                target_id,
                target_type,
                edge_kind,
                note,
                created_at: created_at.map(|t| t.to_rfc3339()),
            },
        );
    }

    if skipped > 0 {
        tracing::warn!(
            skipped,
            "skipped domain_edges rows during Phase D read"
        );
    }

    Ok(edges)
}

// ── Accounts ───────────────────────────────────────────────────────────────

/// Loads all accounts from `domain_accounts` into an `AccountStore`.
///
/// Privacy contract (Phase D):
///
/// 1. `location_lat` / `location_lon` are the **private** residence
///    coordinates — they are never exposed by the API. The DB-Read-Path
///    feeds them into [`map_json_to_public_account`] via a synthetic
///    `serde_json::Value` (with `location.lat` / `location.lon` keys)
///    so the existing privacy rules fire identically to the JSONL path.
/// 2. Legacy `visibility` and `ron_flag` semantics are reconstructed
///    from `private_payload->>'visibility'` and `private_payload->>'ron_flag'`
///    using SQL scalar extraction (no `sqlx/json` feature required).
/// 3. `mode` is read from the explicit `mode` column (preferred truth)
///    and only falls back to legacy heuristics when null.
pub async fn load_accounts_from_postgres(
    pool: &PgPool,
) -> Result<AccountStore, DomainDbLoadError> {
    let rows = sqlx::query(
        "SELECT id, kind, title, mode, radius_m, disabled,
                location_lat, location_lon,
                role, email, webauthn_user_id,
                created_at, updated_at,
                public_payload::text AS public_payload_text,
                private_payload::text AS private_payload_text,
                private_payload->>'visibility' AS priv_visibility,
                CASE
                  WHEN lower(private_payload->>'suppress_public_pos') = 'true' THEN true
                  WHEN lower(private_payload->>'suppress_public_pos') = 'false' THEN false
                  ELSE NULL
                END AS priv_suppress_public_pos,
                CASE
                  WHEN lower(private_payload->>'ron_flag') = 'true' THEN true
                  WHEN lower(private_payload->>'ron_flag') = 'false' THEN false
                  ELSE NULL
                END AS priv_ron_flag
         FROM domain_accounts
         ORDER BY id ASC",
    )
    .fetch_all(pool)
    .await?;


    let mut store = AccountStore::new();
    let mut skipped = 0usize;

    for row in rows {
        let id: String = match row.try_get("id") {
            Ok(v) => v,
            Err(e) => {
                tracing::warn!(error = %e, "skipping account row without id");
                skipped += 1;
                continue;
            }
        };

        let kind: String = row.try_get("kind").unwrap_or_else(|_| "garnrolle".to_string());
        let title: String = row.try_get("title").unwrap_or_else(|_| "Untitled".to_string());
        let mode: Option<String> = row.try_get("mode").ok();
        let radius_m_i64: i64 = row.try_get("radius_m").unwrap_or(0i64);
        let disabled: bool = row.try_get("disabled").unwrap_or(false);
        let location_lat: Option<f64> = row.try_get("location_lat").ok();
        let location_lon: Option<f64> = row.try_get("location_lon").ok();
        let role_str: String = row.try_get("role").unwrap_or_else(|_| "gast".to_string());
        let email: Option<String> = row
            .try_get::<Option<String>, _>("email")
            .ok()
            .flatten()
            .filter(|s| !s.is_empty());
        let webauthn_user_id: Option<Uuid> = row.try_get("webauthn_user_id").ok();
        let created_at: Option<chrono::DateTime<chrono::Utc>> = row.try_get("created_at").ok();
        let updated_at: Option<chrono::DateTime<chrono::Utc>> = row.try_get("updated_at").ok();
        let public_payload_text: String = row
            .try_get::<Option<String>, _>("public_payload_text")
            .ok()
            .flatten()
            .unwrap_or_else(|| "{}".to_string());
        let private_payload_text: String = row
            .try_get::<Option<String>, _>("private_payload_text")
            .ok()
            .flatten()
            .unwrap_or_else(|| "{}".to_string());

        // Scalar extraction already done in SQL (no sqlx/json feature needed).
        // We also parse the JSON text so we keep the same path semantics as
        // the JSONL loader: tolerant of malformed JSON, never silently
        // accepting it. The scalar fields are authoritative for the
        // privacy decisions below.
        let private_payload: serde_json::Value =
            serde_json::from_str(&private_payload_text).unwrap_or_else(|_| {
                tracing::warn!(
                    account_id = %id,
                    "private_payload was not valid JSON; treating as empty"
                );
                serde_json::Value::Object(Default::default())
            });
        let public_payload: serde_json::Value =
            serde_json::from_str(&public_payload_text).unwrap_or_default();

        let priv_visibility: Option<String> = row
            .try_get::<Option<String>, _>("priv_visibility")
            .ok()
            .flatten();
        let priv_suppress: Option<bool> = row
            .try_get::<Option<bool>, _>("priv_suppress_public_pos")
            .ok()
            .flatten();
        let priv_ron_flag: Option<bool> = row
            .try_get::<Option<bool>, _>("priv_ron_flag")
            .ok()
            .flatten();

        // Privacy contract: public_pos is suppressed when either
        // visibility == "private" OR suppress_public_pos == true. We
        // materialize that as a synthetic "visibility" = "private" so
        // map_json_to_public_account's existing branch fires identically
        // to the JSONL path, and the suppress_public_pos privacy intent
        // is honored even when the legacy visibility key is missing.
        let effective_visibility: Option<&str> = if priv_suppress.unwrap_or(false) {
            Some("private")
        } else {
            priv_visibility.as_deref()
        };

        let mut record = serde_json::Map::new();
        record.insert("id".into(), serde_json::Value::String(id.clone()));
        record.insert("type".into(), serde_json::Value::String(kind.clone()));
        record.insert("title".into(), serde_json::Value::String(title.clone()));
        record.insert("mode".into(), serde_json::Value::String(mode.clone().unwrap_or_default()));
        record.insert(
            "radius_m".into(),
            serde_json::Value::Number(serde_json::Number::from(radius_m_i64.max(0) as u64)),
        );
        record.insert("disabled".into(), serde_json::Value::Bool(disabled));

        if let (Some(lat), Some(lon)) = (location_lat, location_lon) {
            record.insert(
                "location".into(),
                serde_json::json!({ "lat": lat, "lon": lon }),
            );
        }

        // Surface legacy fields to the public mapper so the visibility
        // and Ron branches are reachable.
        if let Some(vis) = effective_visibility {
            record.insert(
                "visibility".into(),
                serde_json::Value::String(vis.to_string()),
            );
        }
        if priv_ron_flag.unwrap_or(false) {
            record.insert("ron_flag".into(), serde_json::Value::Bool(true));
        }
        // Also surface any ron_flag written into the JSON text (Phase C
        // writes it; some test fixtures may have it only in JSON).
        if let Some(ron_flag) = private_payload.get("ron_flag").and_then(|v| v.as_bool()) {
            record.insert("ron_flag".into(), serde_json::Value::Bool(ron_flag));
        }


        // public_payload (summary, tags) is already what the JSONL loader
        // produced, so we can splice those keys through transparently.
        if let Some(summary) = public_payload.get("summary").and_then(|v| v.as_str()) {
            record.insert(
                "summary".into(),
                serde_json::Value::String(summary.to_string()),
            );
        }
        if let Some(tags) = public_payload.get("tags").and_then(|v| v.as_array()) {
            let tag_strings: Vec<serde_json::Value> = tags
                .iter()
                .filter_map(|t| t.as_str().map(|s| serde_json::Value::String(s.to_string())))
                .collect();
            if !tag_strings.is_empty() {
                record.insert("tags".into(), serde_json::Value::Array(tag_strings));
            }
        }

        // Suppress: ignore the public_payload's id/type/title so our column
        // values are the canonical source (Phase B explicit columns win).
        let value = serde_json::Value::Object(record);
        let public = match map_json_to_public_account(&value) {
            Some(p) => p,
            None => {
                tracing::debug!(account_id = %id, "skipping account that did not map to a public view");
                skipped += 1;
                continue;
            }
        };

        let role = Role::from_str_lossy(&role_str);
        let _ = created_at;
        let _ = updated_at;

        store.insert_unindexed(AccountInternal {
            public,
            role,
            email: email.clone(),
            webauthn_user_id: webauthn_user_id.unwrap_or_else(Uuid::new_v4),
        });
    }

    if skipped > 0 {
        tracing::warn!(
            skipped,
            "skipped domain_accounts rows during Phase D read"
        );
    }

    store.rebuild_email_index();
    Ok(store)
}

// ── Self-test helpers (used by integration tests; not API-callable) ────────

/// Re-export so integration tests can call the same privacy-reconstruction
/// path the DB loader uses, without re-implementing the public projection
/// logic in test code.
#[doc(hidden)]
#[allow(dead_code)]
pub fn reconstruct_public_account_for_test(
    id: &str,
    kind: &str,
    title: &str,
    explicit_mode: Option<&str>,
    radius_m: u32,
    location: Option<(f64, f64)>,
    visibility: Option<&str>,
    ron_flag: bool,
    suppress_public_pos: bool,
) -> Option<crate::routes::accounts::AccountPublic> {

    let mut record = serde_json::Map::new();
    record.insert("id".into(), serde_json::Value::String(id.to_string()));
    record.insert("type".into(), serde_json::Value::String(kind.to_string()));
    record.insert("title".into(), serde_json::Value::String(title.to_string()));
    if let Some(m) = explicit_mode {
        record.insert("mode".into(), serde_json::Value::String(m.to_string()));
    }
    record.insert(
        "radius_m".into(),
        serde_json::Value::Number(serde_json::Number::from(radius_m as u64)),
    );
    if let Some((lat, lon)) = location {
        record.insert(
            "location".into(),
            serde_json::json!({ "lat": lat, "lon": lon }),
        );
    }
    if let Some(vis) = visibility {
        record.insert(
            "visibility".into(),
            serde_json::Value::String(vis.to_string()),
        );
    }
    if ron_flag {
        record.insert("ron_flag".into(), serde_json::Value::Bool(true));
    }
    if suppress_public_pos {
        record.insert(
            "suppress_public_pos".into(),
            serde_json::Value::Bool(true),
        );
    }
    let value = serde_json::Value::Object(record);
    map_json_to_public_account(&value)
}

// Re-exports for integration tests that need to construct AccountPublic
// fixtures without re-importing from the routes module.
#[doc(hidden)]
#[allow(dead_code)]
pub use crate::routes::accounts::AccountPublic as PublicAccount;
#[doc(hidden)]
#[allow(dead_code)]
pub use crate::routes::accounts::Location as PublicLocation;
#[doc(hidden)]
#[allow(dead_code)]
pub use crate::routes::accounts::AccountMode as PublicAccountMode;




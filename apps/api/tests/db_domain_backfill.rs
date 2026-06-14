//! Integration proof: Phase C JSONL→PostgreSQL domain backfill (OPT-ARC-001).
//!
//! Proves that JSONL fixture data can be imported deterministically and idempotently
//! into domain_nodes, domain_edges, and domain_accounts tables.
//!
//! Phase scope: import proof only. No runtime read/write paths are switched.
//! JSONL remains the active data source until Phase D/E.
//!
//! Run with:
//!   DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
//!     cargo test --locked -p weltgewebe-api --test db_domain_backfill \
//!     -- --include-ignored --test-threads=1
//!
//! Notes:
//! - Tests are ignored by default to keep offline paths green.
//! - DATABASE_URL must point to direct PostgreSQL (not PgBouncer at :6432).
//! - Use --test-threads=1 to avoid row-level conflicts between parallel tests.

use sqlx::postgres::{PgConnectOptions, PgPoolOptions};
use std::{path::PathBuf, str::FromStr};

fn direct_database_url() -> String {
    let url = std::env::var("DATABASE_URL").expect(
        "DATABASE_URL must be set to run db_domain_backfill tests; \
         point it to direct PostgreSQL (port 5432)",
    );
    assert!(
        !url.contains(":6432"),
        "DATABASE_URL must target direct PostgreSQL, not PgBouncer (port 6432)"
    );
    url
}

async fn connect_pool() -> sqlx::PgPool {
    let connect_opts = PgConnectOptions::from_str(&direct_database_url())
        .expect("DATABASE_URL must be a valid postgres connection string");
    PgPoolOptions::new()
        .max_connections(2)
        .connect_with(connect_opts)
        .await
        .expect("failed to connect to direct PostgreSQL")
}

async fn run_migrations(pool: &sqlx::PgPool) {
    let migrations_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("migrations");
    let migrator = sqlx::migrate::Migrator::new(migrations_dir)
        .await
        .expect("failed to load migrations");
    migrator.run(pool).await.expect("failed to run migrations");
}

/// Backfill counters returned by each import function.
///
/// records_inserted + records_updated = records_read - malformed_json_lines - skipped_records
#[derive(Debug, Default)]
struct BackfillReport {
    records_read: usize,
    records_inserted: usize,
    records_updated: usize,
    malformed_json_lines: usize,
    skipped_records: usize,
    /// Emails that appeared more than once across accounts already in the table.
    /// Populated only by import_accounts.
    duplicate_emails: Vec<String>,
}

// ── Mapping helpers ───────────────────────────────────────────────────────────

fn f64_from_value(v: &serde_json::Value) -> Option<f64> {
    v.as_f64()
        .or_else(|| v.as_str().and_then(|s| s.parse().ok()))
}

fn parse_ts(v: &serde_json::Value) -> Option<chrono::DateTime<chrono::Utc>> {
    v.as_str().and_then(|s| s.parse().ok())
}

fn payload_str(keys: &[&str], source: &serde_json::Value) -> String {
    let mut m = serde_json::Map::new();
    for &k in keys {
        if let Some(val) = source.get(k) {
            if !val.is_null() {
                m.insert(k.to_string(), val.clone());
            }
        }
    }
    serde_json::to_string(&serde_json::Value::Object(m)).unwrap_or_else(|_| "{}".to_string())
}

// ── Import functions ──────────────────────────────────────────────────────────

/// Import JSONL content into domain_nodes.
///
/// Idempotency contract: ON CONFLICT (id) DO UPDATE SET — second run converges
/// to source truth, no duplicate rows.
async fn import_nodes(pool: &sqlx::PgPool, content: &str) -> BackfillReport {
    let mut report = BackfillReport::default();

    for line in content.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        report.records_read += 1;

        let v: serde_json::Value = match serde_json::from_str(line) {
            Ok(v) => v,
            Err(_) => {
                report.malformed_json_lines += 1;
                continue;
            }
        };

        let id = match v
            .get("id")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s.to_string(),
            None => {
                report.skipped_records += 1;
                continue;
            }
        };

        let kind = v
            .get("kind")
            .and_then(|v| v.as_str())
            .unwrap_or("Unknown")
            .to_string();
        let title = v
            .get("title")
            .and_then(|v| v.as_str())
            .unwrap_or("Untitled")
            .to_string();
        let lat = v
            .get("location")
            .and_then(|l| l.get("lat"))
            .and_then(f64_from_value);
        let lon = v
            .get("location")
            .and_then(|l| l.get("lon"))
            .and_then(f64_from_value);
        let created_at = v.get("created_at").map(parse_ts).unwrap_or(None);
        let updated_at = v.get("updated_at").map(parse_ts).unwrap_or(None);
        let payload = payload_str(&["summary", "info", "tags"], &v);

        let (already_exists,): (bool,) =
            sqlx::query_as("SELECT EXISTS(SELECT 1 FROM domain_nodes WHERE id = $1)")
                .bind(&id)
                .fetch_one(pool)
                .await
                .unwrap_or_else(|e| panic!("existence check failed for node {id}: {e}"));

        sqlx::query(
            "INSERT INTO domain_nodes
                 (id, kind, title, lat, lon, created_at, updated_at, payload)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
             ON CONFLICT (id) DO UPDATE SET
                 kind       = EXCLUDED.kind,
                 title      = EXCLUDED.title,
                 lat        = EXCLUDED.lat,
                 lon        = EXCLUDED.lon,
                 created_at = EXCLUDED.created_at,
                 updated_at = EXCLUDED.updated_at,
                 payload    = EXCLUDED.payload",
        )
        .bind(&id)
        .bind(&kind)
        .bind(&title)
        .bind(lat)
        .bind(lon)
        .bind(created_at)
        .bind(updated_at)
        .bind(&payload)
        .execute(pool)
        .await
        .unwrap_or_else(|e| panic!("failed to upsert node {id}: {e}"));

        if already_exists {
            report.records_updated += 1;
        } else {
            report.records_inserted += 1;
        }
    }

    report
}

/// Import JSONL content into domain_edges.
///
/// edge_kind is read from "edge_kind", falling back to "kind" or "edgeKind"
/// to match the Edge struct's serde aliases.
async fn import_edges(pool: &sqlx::PgPool, content: &str) -> BackfillReport {
    let mut report = BackfillReport::default();

    for line in content.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        report.records_read += 1;

        let v: serde_json::Value = match serde_json::from_str(line) {
            Ok(v) => v,
            Err(_) => {
                report.malformed_json_lines += 1;
                continue;
            }
        };

        let id = match v
            .get("id")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s.to_string(),
            None => {
                report.skipped_records += 1;
                continue;
            }
        };

        let source_id = match v.get("source_id").and_then(|v| v.as_str()) {
            Some(s) => s.to_string(),
            None => {
                report.skipped_records += 1;
                continue;
            }
        };

        let target_id = match v.get("target_id").and_then(|v| v.as_str()) {
            Some(s) => s.to_string(),
            None => {
                report.skipped_records += 1;
                continue;
            }
        };

        let edge_kind = v
            .get("edge_kind")
            .or_else(|| v.get("kind"))
            .or_else(|| v.get("edgeKind"))
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();

        let created_at = v.get("created_at").map(parse_ts).unwrap_or(None);
        let payload = payload_str(&["source_type", "target_type", "note"], &v);

        let (already_exists,): (bool,) =
            sqlx::query_as("SELECT EXISTS(SELECT 1 FROM domain_edges WHERE id = $1)")
                .bind(&id)
                .fetch_one(pool)
                .await
                .unwrap_or_else(|e| panic!("existence check failed for edge {id}: {e}"));

        sqlx::query(
            "INSERT INTO domain_edges
                 (id, source_id, target_id, edge_kind, created_at, payload)
             VALUES ($1, $2, $3, $4, $5, $6::jsonb)
             ON CONFLICT (id) DO UPDATE SET
                 source_id  = EXCLUDED.source_id,
                 target_id  = EXCLUDED.target_id,
                 edge_kind  = EXCLUDED.edge_kind,
                 created_at = EXCLUDED.created_at,
                 payload    = EXCLUDED.payload",
        )
        .bind(&id)
        .bind(&source_id)
        .bind(&target_id)
        .bind(&edge_kind)
        .bind(created_at)
        .bind(&payload)
        .execute(pool)
        .await
        .unwrap_or_else(|e| panic!("failed to upsert edge {id}: {e}"));

        if already_exists {
            report.records_updated += 1;
        } else {
            report.records_inserted += 1;
        }
    }

    report
}

/// Import JSONL content into domain_accounts.
///
/// JSONL uses "type" for kind (matching AccountPublic serialisation).
/// location lat/lon are the private residence coordinates, stored in
/// location_lat/location_lon — not the jittered public_pos.
/// Duplicate emails are audited and reported but not blocked (Phase B policy).
async fn import_accounts(pool: &sqlx::PgPool, content: &str) -> BackfillReport {
    let mut report = BackfillReport::default();

    for line in content.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        report.records_read += 1;

        let v: serde_json::Value = match serde_json::from_str(line) {
            Ok(v) => v,
            Err(_) => {
                report.malformed_json_lines += 1;
                continue;
            }
        };

        let id = match v
            .get("id")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s.to_string(),
            None => {
                report.skipped_records += 1;
                continue;
            }
        };

        // JSONL serialises AccountPublic.kind as "type" (serde rename)
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

        let disabled: bool = v.get("disabled").and_then(|v| v.as_bool()).unwrap_or(false);

        let location_lat = v
            .get("location")
            .and_then(|l| l.get("lat"))
            .and_then(f64_from_value);
        let location_lon = v
            .get("location")
            .and_then(|l| l.get("lon"))
            .and_then(f64_from_value);

        let role = v
            .get("role")
            .and_then(|v| v.as_str())
            .unwrap_or("gast")
            .to_string();

        // Normalize like from_jsonl_record / the API create path: trim, then
        // treat an after-trim-empty value as "no email" (None), matching the
        // unique index and the not-empty-after-trim check constraint.
        let email: Option<String> = v
            .get("email")
            .and_then(|v| v.as_str())
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string());

        // Validate webauthn_user_id as UUID before sending to PostgreSQL
        let webauthn_user_id: Option<String> = v
            .get("webauthn_user_id")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .filter(|s| uuid::Uuid::parse_str(s).is_ok())
            .map(|s| s.to_string());

        let created_at = v.get("created_at").map(parse_ts).unwrap_or(None);
        let updated_at = v.get("updated_at").map(parse_ts).unwrap_or(None);

        // Legacy mapping for mode
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

        let public_payload = payload_str(&["summary", "tags"], &v);

        // Construct private_payload preserving legacy fields
        let mut priv_map = serde_json::Map::new();
        if let Some(vis) = visibility {
            priv_map.insert(
                "visibility".to_string(),
                serde_json::Value::String(vis.to_string()),
            );
            if vis == "private" {
                priv_map.insert(
                    "suppress_public_pos".to_string(),
                    serde_json::Value::Bool(true),
                );
            }
        }
        if ron_flag {
            priv_map.insert("ron_flag".to_string(), serde_json::Value::Bool(ron_flag));
        }
        if let Some(em) = explicit_mode {
            priv_map.insert(
                "mode".to_string(),
                serde_json::Value::String(em.to_string()),
            );
        }

        let private_payload = if priv_map.is_empty() {
            "{}".to_string()
        } else {
            serde_json::to_string(&serde_json::Value::Object(priv_map)).unwrap()
        };

        // Audit duplicate emails using the SAME normalization as the unique
        // index (lower(btrim(email))) and skip the duplicate BEFORE inserting,
        // so the normal path avoids an intentional unique violation before
        // insert. The email was already trimmed/empty-normalized above, so
        // after-trim-empty values are None here and never unique-relevant.
        if let Some(ref em) = email {
            let (dup_count,): (i64,) = sqlx::query_as(
                "SELECT COUNT(*) FROM domain_accounts
                 WHERE email IS NOT NULL
                   AND btrim(email) <> ''
                   AND btrim($1) <> ''
                   AND lower(btrim(email)) = lower(btrim($1))
                   AND id != $2",
            )
            .bind(em.as_str())
            .bind(&id)
            .fetch_one(pool)
            .await
            .unwrap_or((0,));
            if dup_count > 0 {
                report.duplicate_emails.push(em.clone());
                report.skipped_records += 1;
                continue;
            }
        }

        let (already_exists,): (bool,) =
            sqlx::query_as("SELECT EXISTS(SELECT 1 FROM domain_accounts WHERE id = $1)")
                .bind(&id)
                .fetch_one(pool)
                .await
                .unwrap_or_else(|e| panic!("existence check failed for account {id}: {e}"));

        let upsert_result = sqlx::query(
            "INSERT INTO domain_accounts
                 (id, kind, title, mode, radius_m, disabled,
                  location_lat, location_lon,
                  role, email, webauthn_user_id,
                  created_at, updated_at,
                  public_payload, private_payload)
             VALUES
                 ($1, $2, $3, $4, $5, $6,
                  $7, $8,
                  $9, $10, $11::uuid,
                  $12, $13,
                  $14::jsonb, $15::jsonb)
             ON CONFLICT (id) DO UPDATE SET
                 kind             = EXCLUDED.kind,
                 title            = EXCLUDED.title,
                 mode             = EXCLUDED.mode,
                 radius_m         = EXCLUDED.radius_m,
                 disabled         = EXCLUDED.disabled,
                 location_lat     = EXCLUDED.location_lat,
                 location_lon     = EXCLUDED.location_lon,
                 role             = EXCLUDED.role,
                 email            = EXCLUDED.email,
                 webauthn_user_id = EXCLUDED.webauthn_user_id,
                 created_at       = EXCLUDED.created_at,
                 updated_at       = EXCLUDED.updated_at,
                 public_payload   = EXCLUDED.public_payload,
                 private_payload  = EXCLUDED.private_payload",
        )
        .bind(&id)
        .bind(&kind)
        .bind(&title)
        .bind(&mode)
        .bind(radius_m)
        .bind(disabled)
        .bind(location_lat)
        .bind(location_lon)
        .bind(&role)
        .bind(email.as_deref())
        .bind(webauthn_user_id.as_deref())
        .bind(created_at)
        .bind(updated_at)
        .bind(&public_payload)
        .bind(&private_payload)
        .execute(pool)
        .await;

        match upsert_result {
            Ok(_) => {
                if already_exists {
                    report.records_updated += 1;
                } else {
                    report.records_inserted += 1;
                }
            }
            // Defensive last resort only: the lower(btrim(email)) audit above is
            // the normal skip path, so this arm is reached only under a race or
            // drift (a concurrent writer between audit and insert). Audit and
            // skip rather than abort the backfill; only this exact constraint is
            // handled — any other database error still aborts the import.
            Err(sqlx::Error::Database(db_err))
                if db_err.constraint()
                    == Some(weltgewebe_api::domain_db::ACCOUNT_EMAIL_UNIQUE_CONSTRAINT) =>
            {
                if let Some(ref em) = email {
                    report.duplicate_emails.push(em.clone());
                }
                report.skipped_records += 1;
            }
            Err(e) => panic!("failed to upsert account {id}: {e}"),
        }
    }

    report
}

// ── Fixtures ──────────────────────────────────────────────────────────────────

const NODE_FIXTURE: &str = r#"
{"id":"backfill-proof-node-alpha","kind":"Ort","title":"Alpha Node","created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-02T00:00:00Z","location":{"lat":53.5,"lon":10.0},"summary":"Alpha summary","tags":["tag-a"]}
{"id":"backfill-proof-node-beta","kind":"Person","title":"Beta Node","created_at":"2026-02-01T00:00:00Z","updated_at":"2026-02-02T00:00:00Z","location":{"lat":48.1,"lon":11.6},"info":"Beta info"}
{"id":"backfill-proof-node-gamma","kind":"Unknown","title":"Gamma Node","location":{"lat":52.5,"lon":13.4}}
"#;

const EDGE_FIXTURE: &str = r#"
{"id":"backfill-proof-edge-alpha","source_id":"backfill-proof-node-alpha","target_id":"backfill-proof-node-beta","edge_kind":"knows","created_at":"2026-01-15T00:00:00Z","note":"Test note"}
{"id":"backfill-proof-edge-beta","source_id":"backfill-proof-node-beta","target_id":"backfill-proof-node-gamma","edge_kind":"related"}
"#;

const ACCOUNT_FIXTURE: &str = r#"
{"id":"backfill-proof-account-alpha","type":"garnrolle","title":"Alpha Account","mode":"verortet","radius_m":100,"location":{"lat":53.5,"lon":10.0},"role":"weber","email":"alpha@proof.example","summary":"Alpha summary"}
{"id":"backfill-proof-account-beta","type":"ron","title":"Beta Account","mode":"ron","radius_m":0,"role":"gast"}
"#;

const MALFORMED_NODE_FIXTURE: &str = r#"
{"id":"backfill-proof-node-valid-1","kind":"Test","title":"Valid One","location":{"lat":50.0,"lon":9.0}}
not valid json at all {{{
{"id":"backfill-proof-node-valid-2","kind":"Test","title":"Valid Two","location":{"lat":51.0,"lon":9.0}}
"#;

const DUPLICATE_ID_NODE_FIXTURE: &str = r#"
{"id":"backfill-proof-node-dup","kind":"First","title":"First Version","location":{"lat":50.0,"lon":9.0}}
{"id":"backfill-proof-node-dup","kind":"Second","title":"Second Version","location":{"lat":51.0,"lon":10.0}}
"#;

const DUPLICATE_EMAIL_ACCOUNT_FIXTURE: &str = r#"
{"id":"backfill-proof-account-dup-email-a","type":"garnrolle","title":"Dup Email A","mode":"verortet","radius_m":0,"location":{"lat":53.0,"lon":10.0},"role":"gast","email":"dup@proof.example"}
{"id":"backfill-proof-account-dup-email-b","type":"garnrolle","title":"Dup Email B","mode":"verortet","radius_m":0,"location":{"lat":53.0,"lon":10.0},"role":"gast","email":"  DUP@proof.example  "}
"#;

const LEGACY_ACCOUNT_FIXTURE: &str = r#"
{"id":"legacy-private","location":{"lat":50.0,"lon":10.0},"visibility":"private"}
{"id":"legacy-missing-type","location":{"lat":51.0,"lon":11.0}}
{"id":"legacy-missing-mode-ron-flag","ron_flag":true}
{"id":"legacy-approximate","location":{"lat":52.0,"lon":12.0},"visibility":"approximate","radius_m":0}
"#;

// ── Tests ─────────────────────────────────────────────────────────────────────

/// Proves that 3 node fixtures import with correct field mapping,
/// and a second identical import produces no duplicate rows (idempotency).
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn domain_backfill_nodes_deterministic_and_idempotent() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    sqlx::query("DELETE FROM domain_nodes WHERE id LIKE 'backfill-proof-node-%'")
        .execute(&pool)
        .await
        .expect("pre-test cleanup of domain_nodes failed");

    // First import
    let r1 = import_nodes(&pool, NODE_FIXTURE).await;
    assert_eq!(r1.records_read, 3, "must read 3 node fixture records");
    assert_eq!(
        r1.records_inserted, 3,
        "first import: all 3 must be new inserts"
    );
    assert_eq!(r1.records_updated, 0, "first import: no updates expected");
    assert_eq!(r1.malformed_json_lines, 0);
    assert_eq!(r1.skipped_records, 0);

    // Field mapping verification
    let (kind, title): (String, String) =
        sqlx::query_as("SELECT kind, title FROM domain_nodes WHERE id = $1")
            .bind("backfill-proof-node-alpha")
            .fetch_one(&pool)
            .await
            .expect("node alpha must exist after import");
    assert_eq!(kind, "Ort");
    assert_eq!(title, "Alpha Node");

    let (lat, lon): (Option<f64>, Option<f64>) =
        sqlx::query_as("SELECT lat, lon FROM domain_nodes WHERE id = $1")
            .bind("backfill-proof-node-alpha")
            .fetch_one(&pool)
            .await
            .expect("node alpha coordinates must be readable");
    assert!((lat.unwrap() - 53.5).abs() < 1e-6, "lat must map correctly");
    assert!((lon.unwrap() - 10.0).abs() < 1e-6, "lon must map correctly");

    // Node without optional timestamps: gamma has no created_at/updated_at
    let (gamma_created_at,): (Option<chrono::DateTime<chrono::Utc>>,) =
        sqlx::query_as("SELECT created_at FROM domain_nodes WHERE id = $1")
            .bind("backfill-proof-node-gamma")
            .fetch_one(&pool)
            .await
            .expect("node gamma must exist");
    assert!(
        gamma_created_at.is_none(),
        "node without timestamps must have NULL created_at"
    );

    // Second import (idempotency)
    let r2 = import_nodes(&pool, NODE_FIXTURE).await;
    assert_eq!(r2.records_read, 3, "second import: must read 3 records");
    assert_eq!(
        r2.records_inserted, 0,
        "second import: no new rows expected"
    );
    assert_eq!(
        r2.records_updated, 3,
        "second import: all 3 must be updates"
    );

    // Row count unchanged after re-import
    let (count,): (i64,) =
        sqlx::query_as("SELECT COUNT(*) FROM domain_nodes WHERE id LIKE 'backfill-proof-node-%'")
            .fetch_one(&pool)
            .await
            .expect("count query failed");
    assert_eq!(
        count, 3,
        "idempotent re-import must not create duplicate rows"
    );

    sqlx::query("DELETE FROM domain_nodes WHERE id LIKE 'backfill-proof-node-%'")
        .execute(&pool)
        .await
        .expect("post-test cleanup failed");

    pool.close().await;
}

/// Proves that 2 edge fixtures import with correct field mapping (including
/// edge_kind and optional note in payload), and re-import is idempotent.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn domain_backfill_edges_deterministic_and_idempotent() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    sqlx::query("DELETE FROM domain_edges WHERE id LIKE 'backfill-proof-edge-%'")
        .execute(&pool)
        .await
        .expect("pre-test cleanup of domain_edges failed");

    // First import
    let r1 = import_edges(&pool, EDGE_FIXTURE).await;
    assert_eq!(r1.records_read, 2);
    assert_eq!(r1.records_inserted, 2);
    assert_eq!(r1.records_updated, 0);
    assert_eq!(r1.malformed_json_lines, 0);
    assert_eq!(r1.skipped_records, 0);

    // Field mapping: edge_kind, source_id, target_id
    let (source_id, target_id, edge_kind): (String, String, String) =
        sqlx::query_as("SELECT source_id, target_id, edge_kind FROM domain_edges WHERE id = $1")
            .bind("backfill-proof-edge-alpha")
            .fetch_one(&pool)
            .await
            .expect("edge alpha must exist after import");
    assert_eq!(source_id, "backfill-proof-node-alpha");
    assert_eq!(target_id, "backfill-proof-node-beta");
    assert_eq!(edge_kind, "knows");

    // note goes into payload jsonb; extract via SQL to avoid sqlx json feature
    let (note,): (Option<String>,) =
        sqlx::query_as("SELECT payload->>'note' FROM domain_edges WHERE id = $1")
            .bind("backfill-proof-edge-alpha")
            .fetch_one(&pool)
            .await
            .expect("edge alpha payload note must be readable");
    assert_eq!(
        note.as_deref(),
        Some("Test note"),
        "note must be preserved in payload jsonb"
    );

    // Second import (idempotency)
    let r2 = import_edges(&pool, EDGE_FIXTURE).await;
    assert_eq!(r2.records_read, 2);
    assert_eq!(r2.records_inserted, 0);
    assert_eq!(r2.records_updated, 2);

    let (count,): (i64,) =
        sqlx::query_as("SELECT COUNT(*) FROM domain_edges WHERE id LIKE 'backfill-proof-edge-%'")
            .fetch_one(&pool)
            .await
            .expect("count query failed");
    assert_eq!(
        count, 2,
        "idempotent re-import must not create duplicate rows"
    );

    sqlx::query("DELETE FROM domain_edges WHERE id LIKE 'backfill-proof-edge-%'")
        .execute(&pool)
        .await
        .expect("post-test cleanup failed");

    pool.close().await;
}

/// Proves that 2 account fixtures (one verortet, one ron) import with correct
/// field mapping, and re-import is idempotent.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn domain_backfill_accounts_deterministic_and_idempotent() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    sqlx::query("DELETE FROM domain_accounts WHERE id LIKE 'backfill-proof-account-%'")
        .execute(&pool)
        .await
        .expect("pre-test cleanup of domain_accounts failed");

    // First import
    let r1 = import_accounts(&pool, ACCOUNT_FIXTURE).await;
    assert_eq!(r1.records_read, 2);
    assert_eq!(r1.records_inserted, 2);
    assert_eq!(r1.records_updated, 0);
    assert_eq!(r1.malformed_json_lines, 0);
    assert_eq!(r1.skipped_records, 0);
    assert!(
        r1.duplicate_emails.is_empty(),
        "no duplicate emails in clean fixture"
    );

    // Field mapping: kind, mode, role, email, location_lat/lon (verortet account)
    let (kind, mode, role, email, loc_lat, loc_lon): (
        String,
        String,
        String,
        Option<String>,
        Option<f64>,
        Option<f64>,
    ) = sqlx::query_as(
        "SELECT kind, mode, role, email, location_lat, location_lon
         FROM domain_accounts WHERE id = $1",
    )
    .bind("backfill-proof-account-alpha")
    .fetch_one(&pool)
    .await
    .expect("account alpha must exist after import");

    assert_eq!(kind, "garnrolle");
    assert_eq!(mode, "verortet");
    assert_eq!(role, "weber");
    assert_eq!(email.as_deref(), Some("alpha@proof.example"));
    assert!(
        (loc_lat.unwrap() - 53.5).abs() < 1e-6,
        "location_lat must map correctly"
    );
    assert!(
        (loc_lon.unwrap() - 10.0).abs() < 1e-6,
        "location_lon must map correctly"
    );

    // ron account: no location
    let (beta_lat, beta_lon): (Option<f64>, Option<f64>) =
        sqlx::query_as("SELECT location_lat, location_lon FROM domain_accounts WHERE id = $1")
            .bind("backfill-proof-account-beta")
            .fetch_one(&pool)
            .await
            .expect("account beta must exist");
    assert!(
        beta_lat.is_none(),
        "ron account must have NULL location_lat"
    );
    assert!(
        beta_lon.is_none(),
        "ron account must have NULL location_lon"
    );

    // radius_m type: stored as BIGINT, bound as i64
    let (radius_m,): (i64,) = sqlx::query_as("SELECT radius_m FROM domain_accounts WHERE id = $1")
        .bind("backfill-proof-account-alpha")
        .fetch_one(&pool)
        .await
        .expect("radius_m must be readable");
    assert_eq!(radius_m, 100);

    // Second import (idempotency)
    let r2 = import_accounts(&pool, ACCOUNT_FIXTURE).await;
    assert_eq!(r2.records_read, 2);
    assert_eq!(r2.records_inserted, 0);
    assert_eq!(r2.records_updated, 2);

    let (count,): (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM domain_accounts WHERE id LIKE 'backfill-proof-account-%'",
    )
    .fetch_one(&pool)
    .await
    .expect("count query failed");
    assert_eq!(
        count, 2,
        "idempotent re-import must not create duplicate rows"
    );

    sqlx::query("DELETE FROM domain_accounts WHERE id LIKE 'backfill-proof-account-%'")
        .execute(&pool)
        .await
        .expect("post-test cleanup failed");

    pool.close().await;
}

/// Proves that malformed JSONL lines are counted and quarantined, while valid
/// lines are imported successfully. No silent continuation.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn domain_backfill_malformed_lines_quarantined() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    sqlx::query(
        "DELETE FROM domain_nodes WHERE id IN \
         ('backfill-proof-node-valid-1', 'backfill-proof-node-valid-2')",
    )
    .execute(&pool)
    .await
    .expect("pre-test cleanup failed");

    let r = import_nodes(&pool, MALFORMED_NODE_FIXTURE).await;

    // 3 non-empty lines total: 2 valid JSON, 1 malformed
    assert_eq!(r.records_read, 3, "must count all non-empty lines");
    assert_eq!(
        r.malformed_json_lines, 1,
        "exactly one malformed line must be quarantined"
    );
    assert_eq!(r.records_inserted, 2, "two valid records must be imported");
    assert_eq!(r.skipped_records, 0);

    let (count,): (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM domain_nodes WHERE id IN \
         ('backfill-proof-node-valid-1', 'backfill-proof-node-valid-2')",
    )
    .fetch_one(&pool)
    .await
    .expect("count query failed");
    assert_eq!(count, 2, "only valid records must be present in DB");

    sqlx::query(
        "DELETE FROM domain_nodes WHERE id IN \
         ('backfill-proof-node-valid-1', 'backfill-proof-node-valid-2')",
    )
    .execute(&pool)
    .await
    .expect("post-test cleanup failed");

    pool.close().await;
}

/// Proves that duplicate IDs within a single import are handled deterministically.
/// The second occurrence overwrites the first (ON CONFLICT DO UPDATE).
/// The final row count is 1, not 2.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn domain_backfill_duplicate_id_converges() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    sqlx::query("DELETE FROM domain_nodes WHERE id = 'backfill-proof-node-dup'")
        .execute(&pool)
        .await
        .expect("pre-test cleanup failed");

    let r = import_nodes(&pool, DUPLICATE_ID_NODE_FIXTURE).await;

    // 2 lines read, 1 insert, 1 update (second line conflicts and updates)
    assert_eq!(r.records_read, 2);
    assert_eq!(r.records_inserted, 1, "first occurrence must be an insert");
    assert_eq!(
        r.records_updated, 1,
        "second occurrence must be an update (ON CONFLICT)"
    );

    // Final state: exactly 1 row
    let (count,): (i64,) =
        sqlx::query_as("SELECT COUNT(*) FROM domain_nodes WHERE id = 'backfill-proof-node-dup'")
            .fetch_one(&pool)
            .await
            .expect("count query failed");
    assert_eq!(count, 1, "duplicate ID must not create a second row");

    // Last-write-wins: the second record's kind is "Second"
    let (kind, title): (String, String) =
        sqlx::query_as("SELECT kind, title FROM domain_nodes WHERE id = $1")
            .bind("backfill-proof-node-dup")
            .fetch_one(&pool)
            .await
            .expect("dup node must be readable");
    assert_eq!(
        kind, "Second",
        "last-write-wins: second record's kind must prevail"
    );
    assert_eq!(title, "Second Version");

    sqlx::query("DELETE FROM domain_nodes WHERE id = 'backfill-proof-node-dup'")
        .execute(&pool)
        .await
        .expect("post-test cleanup failed");

    pool.close().await;
}

/// Proves that a whitespace- and case-variant duplicate account email (the
/// second fixture row is `"  DUP@proof.example  "`) is audited AND skipped using
/// the SAME `lower(btrim(email))` normalization as the
/// `domain_accounts_email_normalized_unique` index (TODO 2A): the first account
/// is imported, the duplicate is audited and skipped (not imported).
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn domain_backfill_duplicate_account_emails_audited() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    sqlx::query(
        "DELETE FROM domain_accounts WHERE id IN \
         ('backfill-proof-account-dup-email-a', 'backfill-proof-account-dup-email-b')",
    )
    .execute(&pool)
    .await
    .expect("pre-test cleanup failed");

    let r = import_accounts(&pool, DUPLICATE_EMAIL_ACCOUNT_FIXTURE).await;

    // TODO 2A: the lower(btrim(email)) audit detects the whitespace/case-variant
    // duplicate and skips it BEFORE insert; the first row is imported.
    assert_eq!(r.records_read, 2);
    assert_eq!(r.records_inserted, 1, "only the first account is imported");
    assert_eq!(r.records_updated, 0);
    assert_eq!(
        r.skipped_records, 1,
        "the duplicate-email account must be skipped"
    );

    // The duplicate is audited as the trimmed value and normalizes to the same key.
    assert_eq!(
        r.duplicate_emails.len(),
        1,
        "one duplicate email must be audited (the second account)"
    );
    assert_eq!(
        r.duplicate_emails[0], "DUP@proof.example",
        "the audited duplicate is the trimmed (not raw) email value"
    );
    assert_eq!(
        r.duplicate_emails[0].to_ascii_lowercase(),
        "dup@proof.example"
    );

    // Only the first row is present in the DB (the duplicate was rejected).
    let (count,): (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM domain_accounts WHERE id IN \
         ('backfill-proof-account-dup-email-a', 'backfill-proof-account-dup-email-b')",
    )
    .fetch_one(&pool)
    .await
    .expect("count query failed");
    assert_eq!(
        count, 1,
        "the normalized unique index rejects the duplicate-email account"
    );

    sqlx::query(
        "DELETE FROM domain_accounts WHERE id IN \
         ('backfill-proof-account-dup-email-a', 'backfill-proof-account-dup-email-b')",
    )
    .execute(&pool)
    .await
    .expect("post-test cleanup failed");

    pool.close().await;
}

/// Proves that legacy accounts import correctly preserving semantics.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn domain_backfill_legacy_account_semantics() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    sqlx::query("DELETE FROM domain_accounts WHERE id LIKE 'legacy-%'")
        .execute(&pool)
        .await
        .expect("pre-test cleanup failed");

    let r = import_accounts(&pool, LEGACY_ACCOUNT_FIXTURE).await;
    assert_eq!(r.records_read, 4);
    assert_eq!(r.records_inserted, 4);

    // legacy-private: visibility: "private" + location.
    // Compile-safety: use SQL scalar extraction (private_payload->>'key')
    // to read JSONB as TEXT, avoiding the sqlx/json feature dependency.
    let (kind, mode, visibility, suppress_public_pos): (
        String,
        String,
        Option<String>,
        Option<String>,
    ) = sqlx::query_as(
        "SELECT
             kind,
             mode,
             private_payload->>'visibility',
             private_payload->>'suppress_public_pos'
         FROM domain_accounts
         WHERE id = $1",
    )
    .bind("legacy-private")
    .fetch_one(&pool)
    .await
    .expect("legacy-private must exist");
    assert_eq!(kind, "garnrolle", "missing type defaults to garnrolle");
    assert_eq!(mode, "verortet", "location presence infers verortet");
    assert_eq!(
        visibility.as_deref(),
        Some("private"),
        "private_payload.visibility must be preserved"
    );
    assert_eq!(
        suppress_public_pos.as_deref(),
        Some("true"),
        "private visibility must set suppress_public_pos=true"
    );

    // legacy-missing-type: missing type + location
    let (kind, mode): (String, String) =
        sqlx::query_as("SELECT kind, mode FROM domain_accounts WHERE id = 'legacy-missing-type'")
            .fetch_one(&pool)
            .await
            .expect("legacy-missing-type must exist");
    assert_eq!(kind, "garnrolle");
    assert_eq!(mode, "verortet");

    // legacy-missing-mode-ron-flag: missing mode + ron_flag: true
    let (mode,): (String,) = sqlx::query_as(
        "SELECT mode FROM domain_accounts WHERE id = 'legacy-missing-mode-ron-flag'",
    )
    .fetch_one(&pool)
    .await
    .expect("legacy-missing-mode-ron-flag must exist");
    assert_eq!(mode, "ron");

    // legacy-approximate: visibility: "approximate" + zero radius
    let (radius_m,): (i64,) =
        sqlx::query_as("SELECT radius_m FROM domain_accounts WHERE id = 'legacy-approximate'")
            .fetch_one(&pool)
            .await
            .expect("legacy-approximate must exist");
    assert_eq!(radius_m, 250);

    sqlx::query("DELETE FROM domain_accounts WHERE id LIKE 'legacy-%'")
        .execute(&pool)
        .await
        .expect("post-test cleanup failed");

    pool.close().await;
}

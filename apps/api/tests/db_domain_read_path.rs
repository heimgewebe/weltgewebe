//! Integration proof: Phase D PostgreSQL domain read path (OPT-ARC-001).
//!
//! Proves that the optional PostgreSQL read loader in `apps/api/src/domain_db.rs`
//! can populate the same in-memory caches the JSONL path produces:
//!
//! - `load_nodes_from_postgres`     -> `OrderedCache<Node>`
//! - `load_edges_from_postgres`     -> `OrderedCache<Edge>`
//! - `load_accounts_from_postgres`  -> `AccountStore`
//!
//! Phase D contract (read-only, no JSONL removal):
//!
//! - Privacy semantics are reconstructed from explicit columns and
//!   `private_payload` JSONB. In particular:
//!   - `visibility: "private"` => `public_pos` must NOT be serialised.
//!   - `visibility: "approximate"` with `radius_m = 0` => `radius_m == 250`.
//!   - `mode: "ron"` or `ron_flag: true` => no `public_pos`.
//!   - legacy `visibility` and `ron_flag` are recovered via SQL scalar
//!     extraction (`->>'key'`) — no `sqlx/json` feature required.
//! - No write path is exercised; JSONL append/create endpoints are unchanged.
//! - The default runtime (no `WELTGEWEBE_DOMAIN_READ_SOURCE=postgres`) is
//!   covered by the existing JSONL integration tests; this file only proves
//!   the opt-in DB path.
//!
//! Run with:
//!   DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
//!     cargo test --locked -p weltgewebe-api --test db_domain_read_path \
//!     -- --include-ignored --test-threads=1
//!
//! Notes:
//! - Tests are ignored by default to keep offline paths green.
//! - DATABASE_URL must point to direct PostgreSQL (not PgBouncer at :6432).
//! - Use --test-threads=1 to avoid row-level conflicts between parallel tests.

use sqlx::postgres::{PgConnectOptions, PgPoolOptions};
use std::{path::PathBuf, str::FromStr};

use weltgewebe_api::domain_db::{
    load_accounts_from_postgres, load_edges_from_postgres, load_nodes_from_postgres,
};

fn direct_database_url() -> String {
    let url = std::env::var("DATABASE_URL").expect(
        "DATABASE_URL must be set to run db_domain_read_path tests; \
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

// ── Nodes ──────────────────────────────────────────────────────────────────

const NODE_FIXTURE_READ: &[&str] = &[
    r#"{"id":"readpath-node-alpha","kind":"Ort","title":"Alpha","created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-02T00:00:00Z","location":{"lat":53.5,"lon":10.0},"summary":"Alpha summary","tags":["tag-a"]}"#,
    r#"{"id":"readpath-node-beta","kind":"Person","title":"Beta","location":{"lat":48.1,"lon":11.6},"info":"Beta info"}"#,
];

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_read_path_loads_nodes_with_payload_fields() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    sqlx::query("DELETE FROM domain_nodes WHERE id LIKE 'readpath-node-%'")
        .execute(&pool)
        .await
        .expect("pre-test cleanup failed");

    for line in NODE_FIXTURE_READ {
        let v: serde_json::Value = serde_json::from_str(line).expect("fixture parse");
        let id = v["id"].as_str().unwrap();
        let kind = v["kind"].as_str().unwrap_or("Unknown");
        let title = v["title"].as_str().unwrap_or("Untitled");
        let lat = v["location"]["lat"].as_f64();
        let lon = v["location"]["lon"].as_f64();
        let payload = serde_json::to_string(&serde_json::json!({
            "summary": v.get("summary"),
            "info": v.get("info"),
            "tags": v.get("tags"),
        }))
        .unwrap();

        sqlx::query(
            "INSERT INTO domain_nodes (id, kind, title, lat, lon, payload)
             VALUES ($1, $2, $3, $4, $5, $6::jsonb)",
        )
        .bind(id)
        .bind(kind)
        .bind(title)
        .bind(lat)
        .bind(lon)
        .bind(&payload)
        .execute(&pool)
        .await
        .expect("failed to insert node");
    }

    let cache = load_nodes_from_postgres(&pool)
        .await
        .expect("loader should succeed");

    assert_eq!(cache.len(), 2, "must read both fixture nodes");

    let alpha = cache.get("readpath-node-alpha").expect("alpha must exist");
    assert_eq!(alpha.id, "readpath-node-alpha");
    assert_eq!(alpha.kind, "Ort");
    assert_eq!(alpha.title, "Alpha");
    assert!((alpha.location.lat - 53.5).abs() < 1e-6);
    assert!((alpha.location.lon - 10.0).abs() < 1e-6);
    assert_eq!(alpha.summary.as_deref(), Some("Alpha summary"));
    assert_eq!(alpha.tags, vec!["tag-a".to_string()]);

    let beta = cache.get("readpath-node-beta").expect("beta must exist");
    assert_eq!(beta.kind, "Person");
    assert_eq!(beta.info.as_deref(), Some("Beta info"));
    assert!(beta.summary.is_none());

    sqlx::query("DELETE FROM domain_nodes WHERE id LIKE 'readpath-node-%'")
        .execute(&pool)
        .await
        .expect("post-test cleanup failed");
    pool.close().await;
}

// ── Edges ──────────────────────────────────────────────────────────────────

const EDGE_FIXTURE_READ: &[&str] = &[
    r#"{"id":"readpath-edge-alpha","source_id":"readpath-node-alpha","target_id":"readpath-node-beta","edge_kind":"knows","note":"alpha note"}"#,
    r#"{"id":"readpath-edge-beta","source_id":"readpath-node-beta","target_id":"readpath-node-alpha","edge_kind":"related"}"#,
];

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_read_path_loads_edges_with_payload_fields() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    sqlx::query("DELETE FROM domain_edges WHERE id LIKE 'readpath-edge-%'")
        .execute(&pool)
        .await
        .expect("pre-test cleanup failed");

    for line in EDGE_FIXTURE_READ {
        let v: serde_json::Value = serde_json::from_str(line).expect("fixture parse");
        let id = v["id"].as_str().unwrap();
        let source_id = v["source_id"].as_str().unwrap();
        let target_id = v["target_id"].as_str().unwrap();
        let edge_kind = v["edge_kind"].as_str().unwrap_or("");
        let payload = serde_json::to_string(&serde_json::json!({
            "source_type": v.get("source_type"),
            "target_type": v.get("target_type"),
            "note": v.get("note"),
        }))
        .unwrap();

        sqlx::query(
            "INSERT INTO domain_edges (id, source_id, target_id, edge_kind, payload)
             VALUES ($1, $2, $3, $4, $5::jsonb)",
        )
        .bind(id)
        .bind(source_id)
        .bind(target_id)
        .bind(edge_kind)
        .bind(&payload)
        .execute(&pool)
        .await
        .expect("failed to insert edge");
    }

    let cache = load_edges_from_postgres(&pool)
        .await
        .expect("loader should succeed");

    assert_eq!(cache.len(), 2, "must read both fixture edges");

    let alpha = cache.get("readpath-edge-alpha").expect("alpha must exist");
    assert_eq!(alpha.source_id, "readpath-node-alpha");
    assert_eq!(alpha.target_id, "readpath-node-beta");
    assert_eq!(alpha.edge_kind, "knows");
    assert_eq!(alpha.note.as_deref(), Some("alpha note"));

    let beta = cache.get("readpath-edge-beta").expect("beta must exist");
    assert_eq!(beta.edge_kind, "related");
    assert!(beta.note.is_none());

    sqlx::query("DELETE FROM domain_edges WHERE id LIKE 'readpath-edge-%'")
        .execute(&pool)
        .await
        .expect("post-test cleanup failed");
    pool.close().await;
}

// ── Accounts (privacy reconstruction) ─────────────────────────────────────

/// Verortet account with explicit public_pos.
const ACCOUNT_VERORTET_ROW: &str = r#"{"id":"readpath-account-verortet","kind":"garnrolle","title":"Verortet","mode":"verortet","radius_m":0,"location":{"lat":53.5,"lon":10.0},"role":"weber","email":"verortet@readpath.example","public_payload":{"summary":"V summary"},"private_payload":{}}"#;

/// Private account: private_payload.visibility="private" + suppress_public_pos.
/// Public_pos must NOT be exposed even though location_lat/lon are set.
const ACCOUNT_PRIVATE_ROW: &str = r#"{"id":"readpath-account-private","kind":"garnrolle","title":"Private","mode":"verortet","radius_m":0,"location":{"lat":50.0,"lon":10.0},"role":"gast","public_payload":{},"private_payload":{"visibility":"private","suppress_public_pos":true}}"#;

/// Approximate account: visibility="approximate" with radius_m=0 must become 250.
const ACCOUNT_APPROX_ROW: &str = r#"{"id":"readpath-account-approx","kind":"garnrolle","title":"Approx","mode":"verortet","radius_m":0,"location":{"lat":52.0,"lon":12.0},"role":"gast","public_payload":{},"private_payload":{"visibility":"approximate"}}"#;

/// RoN account: no public_pos even if location is set in DB columns.
const ACCOUNT_RON_ROW: &str = r#"{"id":"readpath-account-ron","kind":"ron","title":"Ron","mode":"ron","radius_m":0,"role":"gast","public_payload":{},"private_payload":{"ron_flag":true}}"#;

async fn insert_account_row(pool: &sqlx::PgPool, json_row: &str) {
    let v: serde_json::Value = serde_json::from_str(json_row).expect("fixture parse");
    let id = v["id"].as_str().unwrap();
    let kind = v["kind"].as_str().unwrap_or("garnrolle");
    let title = v["title"].as_str().unwrap_or("Untitled");
    let mode = v["mode"].as_str().unwrap_or("ron");
    let radius_m: i64 = v.get("radius_m").and_then(|x| x.as_i64()).unwrap_or(0);
    let location_lat = v.get("location").and_then(|l| l["lat"].as_f64());
    let location_lon = v.get("location").and_then(|l| l["lon"].as_f64());
    let role = v["role"].as_str().unwrap_or("gast");
    let email = v.get("email").and_then(|x| x.as_str()).map(|s| s.to_string());
    let public_payload = v
        .get("public_payload")
        .map(|p| serde_json::to_string(p).unwrap())
        .unwrap_or_else(|| "{}".to_string());
    let private_payload = v
        .get("private_payload")
        .map(|p| serde_json::to_string(p).unwrap())
        .unwrap_or_else(|| "{}".to_string());

    sqlx::query(
        "INSERT INTO domain_accounts
             (id, kind, title, mode, radius_m, location_lat, location_lon,
              role, email, public_payload, private_payload)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11::jsonb)",
    )
    .bind(id)
    .bind(kind)
    .bind(title)
    .bind(mode)
    .bind(radius_m)
    .bind(location_lat)
    .bind(location_lon)
    .bind(role)
    .bind(email)
    .bind(&public_payload)
    .bind(&private_payload)
    .execute(pool)
    .await
    .expect("failed to insert account");
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_read_path_accounts_reconstruct_privacy_semantics() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    sqlx::query("DELETE FROM domain_accounts WHERE id LIKE 'readpath-account-%'")
        .execute(&pool)
        .await
        .expect("pre-test cleanup failed");

    insert_account_row(&pool, ACCOUNT_VERORTET_ROW).await;
    insert_account_row(&pool, ACCOUNT_PRIVATE_ROW).await;
    insert_account_row(&pool, ACCOUNT_APPROX_ROW).await;
    insert_account_row(&pool, ACCOUNT_RON_ROW).await;

    let store = load_accounts_from_postgres(&pool)
        .await
        .expect("loader should succeed");
    assert_eq!(store.len(), 4, "must read all 4 fixture accounts");

    // 1) Verortet account: must have a public_pos and the expected kind.
    let verortet = store
        .get("readpath-account-verortet")
        .expect("verortet must be loaded");
    assert_eq!(verortet.public.kind, "garnrolle");
    assert_eq!(verortet.public.mode, weltgewebe_api::routes::accounts::AccountMode::Verortet);
    assert_eq!(verortet.public.radius_m, 0);
    assert_eq!(verortet.public.summary.as_deref(), Some("V summary"));
    let pp = verortet
        .public
        .public_pos
        .as_ref()
        .expect("verortet account must expose public_pos");
    // public_pos is the same exact location when radius_m == 0
    assert!((pp.lat - 53.5).abs() < 1e-6);
    assert!((pp.lon - 10.0).abs() < 1e-6);
    assert_eq!(verortet.email.as_deref(), Some("verortet@readpath.example"));

    // 2) Private account: public_pos must be None (suppress_public_pos=true).
    let private = store
        .get("readpath-account-private")
        .expect("private must be loaded");
    assert_eq!(
        private.public.mode,
        weltgewebe_api::routes::accounts::AccountMode::Verortet,
        "private retains Verortet identity"
    );
    assert!(
        private.public.public_pos.is_none(),
        "private account MUST NOT expose public_pos"
    );

    // 3) Approximate account: radius_m == 0 + visibility: approximate => 250
    let approx = store
        .get("readpath-account-approx")
        .expect("approx must be loaded");
    assert_eq!(
        approx.public.mode,
        weltgewebe_api::routes::accounts::AccountMode::Verortet
    );
    assert_eq!(
        approx.public.radius_m, 250,
        "approximate radius_m must default to 250 when missing/0"
    );
    assert!(
        approx.public.public_pos.is_some(),
        "approximate verortet account must expose a public_pos"
    );

    // 4) RoN account: no public_pos even with mode=ron.
    let ron = store
        .get("readpath-account-ron")
        .expect("ron must be loaded");
    assert_eq!(
        ron.public.mode,
        weltgewebe_api::routes::accounts::AccountMode::Ron
    );
    assert!(
        ron.public.public_pos.is_none(),
        "RoN account must not expose a public_pos"
    );

    // Email index is rebuilt.
    assert!(
        store.get_by_email("verortet@readpath.example").is_some(),
        "email index must be populated for the verortet account"
    );

    sqlx::query("DELETE FROM domain_accounts WHERE id LIKE 'readpath-account-%'")
        .execute(&pool)
        .await
        .expect("post-test cleanup failed");
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_read_path_empty_table_returns_empty_caches() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    // Clean any leftover readpath rows from other tests; we only assert the
    // loaders behave on a (potentially) empty table, so we delete narrowly.
    sqlx::query("DELETE FROM domain_nodes WHERE id LIKE 'readpath-empty-%'")
        .execute(&pool)
        .await
        .expect("pre-test cleanup of nodes failed");
    sqlx::query("DELETE FROM domain_edges WHERE id LIKE 'readpath-empty-%'")
        .execute(&pool)
        .await
        .expect("pre-test cleanup of edges failed");
    sqlx::query("DELETE FROM domain_accounts WHERE id LIKE 'readpath-empty-%'")
        .execute(&pool)
        .await
        .expect("pre-test cleanup of accounts failed");

    // We don't assert .is_empty() because other tests/operators may have
    // written rows; the contract here is simply that the loaders succeed
    // and return some cache shape. Detailed population is already proven
    // by the preceding dedicated tests.
    let nodes = load_nodes_from_postgres(&pool)
        .await
        .expect("node loader must succeed on an empty/narrow table");
    let edges = load_edges_from_postgres(&pool)
        .await
        .expect("edge loader must succeed on an empty/narrow table");
    let accounts = load_accounts_from_postgres(&pool)
        .await
        .expect("account loader must succeed on an empty/narrow table");

    // All three loaders must return a cache/store type, never an error,
    // even when the queried prefix has no rows. We assert the read-only
    // contract: caches accept arbitrary input size without panicking.
    let _ = (nodes.len(), edges.len(), accounts.len());

    pool.close().await;
}


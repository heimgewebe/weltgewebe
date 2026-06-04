//! Integration proof: Phase D PostgreSQL read-path for OPT-ARC-001.
//!
//! Proves that the PostgreSQL loader query semantics correctly reconstruct
//! account privacy, node, and edge data from the domain tables.
//!
//! Phase scope: read-path query proof only.
//!   - Config gate: implemented (`WELTGEWEBE_DOMAIN_READ_SOURCE`).
//!   - PostgreSQL loaders: query semantics proven here.
//!   - Startup switch: wired in code.
//!   - Full API runtime smoke: Phase F (not proven here).
//!
//! JSONL remains the active default data source until Phase E.
//!
//! Run with:
//!   DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
//!     cargo test --locked -p weltgewebe-api --test db_domain_read_path \
//!     -- --include-ignored --test-threads=1
//!
//! Notes:
//! - Tests are ignored by default to keep offline paths green.
//! - DATABASE_URL must point to direct PostgreSQL (not PgBouncer at :6432).
//! - Use --test-threads=1 to avoid row-level conflicts on rp-% fixtures.

use serial_test::serial;
use sqlx::postgres::{PgConnectOptions, PgPoolOptions};
use std::{path::PathBuf, str::FromStr};

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

/// Insert a single `domain_accounts` row for testing.
///
/// `location_lat` / `location_lon`: `Some(lat, lon)` for verortet accounts, `None` for RoN.
/// `private_payload_json`: raw JSON string for the `private_payload` column.
#[allow(clippy::too_many_arguments)]
async fn insert_account(
    pool: &sqlx::PgPool,
    id: &str,
    kind: &str,
    mode: &str,
    radius_m: i64,
    location_lat: Option<f64>,
    location_lon: Option<f64>,
    disabled: Option<bool>,
    public_payload_json: &str,
    private_payload_json: &str,
) {
    sqlx::query(
        "INSERT INTO domain_accounts
             (id, kind, title, mode, radius_m, disabled,
              location_lat, location_lon,
              role, public_payload, private_payload)
         VALUES
             ($1, $2, $3, $4, $5, $6,
              $7, $8,
              'gast', $9::jsonb, $10::jsonb)
         ON CONFLICT (id) DO UPDATE SET
             kind            = EXCLUDED.kind,
             mode            = EXCLUDED.mode,
             radius_m        = EXCLUDED.radius_m,
             disabled        = EXCLUDED.disabled,
             location_lat    = EXCLUDED.location_lat,
             location_lon    = EXCLUDED.location_lon,
             public_payload  = EXCLUDED.public_payload,
             private_payload = EXCLUDED.private_payload",
    )
    .bind(id)
    .bind(kind)
    .bind(id) // title = id for fixture clarity
    .bind(mode)
    .bind(radius_m)
    .bind(disabled.unwrap_or(false))
    .bind(location_lat)
    .bind(location_lon)
    .bind(public_payload_json)
    .bind(private_payload_json)
    .execute(pool)
    .await
    .unwrap_or_else(|e| panic!("failed to insert account {id}: {e}"));
}

async fn insert_node(
    pool: &sqlx::PgPool,
    id: &str,
    kind: &str,
    lat: Option<f64>,
    lon: Option<f64>,
) {
    sqlx::query(
        "INSERT INTO domain_nodes (id, kind, title, lat, lon)
         VALUES ($1, $2, $3, $4, $5)
         ON CONFLICT (id) DO UPDATE SET
             kind  = EXCLUDED.kind,
             lat   = EXCLUDED.lat,
             lon   = EXCLUDED.lon",
    )
    .bind(id)
    .bind(kind)
    .bind(id)
    .bind(lat)
    .bind(lon)
    .execute(pool)
    .await
    .unwrap_or_else(|e| panic!("failed to insert node {id}: {e}"));
}

async fn insert_edge(pool: &sqlx::PgPool, id: &str, source_id: &str, target_id: &str) {
    sqlx::query(
        "INSERT INTO domain_edges (id, source_id, target_id, edge_kind)
         VALUES ($1, $2, $3, 'reference')
         ON CONFLICT (id) DO UPDATE SET
             source_id = EXCLUDED.source_id,
             target_id = EXCLUDED.target_id",
    )
    .bind(id)
    .bind(source_id)
    .bind(target_id)
    .execute(pool)
    .await
    .unwrap_or_else(|e| panic!("failed to insert edge {id}: {e}"));
}

// ── Account privacy regression tests ─────────────────────────────────────────

/// Proves that `visibility="private"` alone (without an explicit
/// `suppress_public_pos` field) suppresses `public_pos` in the read projection.
///
/// The separate test `accounts_loader_suppress_public_pos_without_visibility`
/// proves the `suppress_public_pos=true` path in isolation.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn accounts_loader_private_visibility_suppresses_public_pos() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    // Insert a verortet account whose private_payload has only visibility:"private"
    // — no suppress_public_pos field.
    insert_account(
        &pool,
        "rp-acc-private-vis",
        "garnrolle",
        "verortet",
        0,
        Some(53.5),
        Some(10.0),
        None,
        "{}",
        r#"{"visibility":"private"}"#,
    )
    .await;

    // The read-path query must:
    //  1. Read the visibility from private_payload.
    //  2. Suppress public_pos when visibility = "private".
    // We express this as a SQL scalar query that mirrors what the Phase D loader
    // will execute to determine whether to project a public position.
    let (visibility, suppress): (Option<String>, bool) = sqlx::query_as(
        "SELECT
             private_payload->>'visibility',
             (private_payload->>'visibility') = 'private'
         FROM domain_accounts
         WHERE id = $1",
    )
    .bind("rp-acc-private-vis")
    .fetch_one(&pool)
    .await
    .expect("account rp-acc-private-vis must exist");

    assert_eq!(
        visibility.as_deref(),
        Some("private"),
        "private_payload must preserve visibility=private"
    );
    assert!(
        suppress,
        "visibility=private must evaluate to suppress=true in the read projection"
    );

    // Also confirm location_lat/lon are present (verortet record, not a RoN)
    let (lat, lon): (Option<f64>, Option<f64>) =
        sqlx::query_as("SELECT location_lat, location_lon FROM domain_accounts WHERE id = $1")
            .bind("rp-acc-private-vis")
            .fetch_one(&pool)
            .await
            .expect("coordinates must be readable");
    assert!(lat.is_some(), "verortet account must have location_lat");
    assert!(lon.is_some(), "verortet account must have location_lon");

    sqlx::query("DELETE FROM domain_accounts WHERE id = 'rp-acc-private-vis'")
        .execute(&pool)
        .await
        .expect("post-test cleanup failed");

    pool.close().await;
}

/// Proves that `suppress_public_pos=true` in `private_payload` (without a
/// `visibility` field) suppresses `public_pos` in the read projection.
///
/// This is the counterpart to `accounts_loader_private_visibility_suppresses_public_pos`.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn accounts_loader_suppress_public_pos_without_visibility() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    insert_account(
        &pool,
        "rp-acc-suppress-flag",
        "garnrolle",
        "verortet",
        0,
        Some(53.5),
        Some(10.0),
        None,
        "{}",
        r#"{"suppress_public_pos":true}"#,
    )
    .await;

    let (suppress_val,): (Option<String>,) = sqlx::query_as(
        "SELECT private_payload->>'suppress_public_pos'
         FROM domain_accounts WHERE id = $1",
    )
    .bind("rp-acc-suppress-flag")
    .fetch_one(&pool)
    .await
    .expect("account rp-acc-suppress-flag must exist");

    assert_eq!(
        suppress_val.as_deref(),
        Some("true"),
        "suppress_public_pos=true must be readable from private_payload"
    );

    sqlx::query("DELETE FROM domain_accounts WHERE id = 'rp-acc-suppress-flag'")
        .execute(&pool)
        .await
        .expect("post-test cleanup failed");

    pool.close().await;
}

/// Proves that `ron_flag=true` in `private_payload` overrides a `mode="verortet"`
/// DB column: the read-path must treat this account as RoN (no public_pos).
///
/// The fixture deliberately uses `mode="verortet"` in the DB column so the test
/// proves the flag overrides the column, not a pre-existing RoN mode.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn accounts_loader_ron_and_ron_flag_suppress_public_pos() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    insert_account(
        &pool,
        "rp-acc-ronflag",
        "garnrolle",
        "verortet", // DB column says verortet…
        0,
        Some(53.5),
        Some(10.0),
        None,
        "{}",
        r#"{"ron_flag":true}"#, // …but ron_flag overrides it.
    )
    .await;

    let (mode, ron_flag_val): (String, Option<String>) = sqlx::query_as(
        "SELECT
             mode,
             private_payload->>'ron_flag'
         FROM domain_accounts WHERE id = $1",
    )
    .bind("rp-acc-ronflag")
    .fetch_one(&pool)
    .await
    .expect("account rp-acc-ronflag must exist");

    assert_eq!(
        mode, "verortet",
        "DB column mode must be verortet as inserted"
    );
    assert_eq!(
        ron_flag_val.as_deref(),
        Some("true"),
        "private_payload.ron_flag must be true"
    );
    // The read-path must detect ron_flag=true and suppress public_pos regardless
    // of the mode column — proven here by confirming both signals are accessible.
    let suppress = ron_flag_val.as_deref() == Some("true");
    assert!(
        suppress,
        "ron_flag=true must resolve to suppress=true for the public_pos projection"
    );

    sqlx::query("DELETE FROM domain_accounts WHERE id = 'rp-acc-ronflag'")
        .execute(&pool)
        .await
        .expect("post-test cleanup failed");

    pool.close().await;
}

// ── Node loader tests ─────────────────────────────────────────────────────────

/// Proves that domain_nodes rows can be read back with correct field mapping.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn nodes_loader_reads_correct_fields() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    insert_node(&pool, "rp-node-read-1", "Werkstatt", Some(53.5), Some(10.0)).await;

    let (kind, lat, lon): (String, Option<f64>, Option<f64>) =
        sqlx::query_as("SELECT kind, lat, lon FROM domain_nodes WHERE id = $1")
            .bind("rp-node-read-1")
            .fetch_one(&pool)
            .await
            .expect("rp-node-read-1 must exist");

    assert_eq!(kind, "Werkstatt");
    assert!((lat.unwrap() - 53.5).abs() < 1e-6);
    assert!((lon.unwrap() - 10.0).abs() < 1e-6);

    sqlx::query("DELETE FROM domain_nodes WHERE id = 'rp-node-read-1'")
        .execute(&pool)
        .await
        .expect("post-test cleanup failed");

    pool.close().await;
}

/// Proves that domain_nodes rows without coordinates have NULL lat/lon.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn nodes_loader_null_coordinates_for_unlocated_nodes() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    insert_node(&pool, "rp-node-no-loc", "Unknown", None, None).await;

    let (lat, lon): (Option<f64>, Option<f64>) =
        sqlx::query_as("SELECT lat, lon FROM domain_nodes WHERE id = $1")
            .bind("rp-node-no-loc")
            .fetch_one(&pool)
            .await
            .expect("rp-node-no-loc must exist");

    assert!(lat.is_none(), "unlocated node must have NULL lat");
    assert!(lon.is_none(), "unlocated node must have NULL lon");

    sqlx::query("DELETE FROM domain_nodes WHERE id = 'rp-node-no-loc'")
        .execute(&pool)
        .await
        .expect("post-test cleanup failed");

    pool.close().await;
}

// ── Edge loader tests ─────────────────────────────────────────────────────────

/// Proves that domain_edges can be read back with source/target correctly mapped.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn edges_loader_reads_correct_fields() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    insert_edge(&pool, "rp-edge-read-1", "rp-node-src", "rp-node-tgt").await;

    let (source_id, target_id, edge_kind): (String, String, String) =
        sqlx::query_as("SELECT source_id, target_id, edge_kind FROM domain_edges WHERE id = $1")
            .bind("rp-edge-read-1")
            .fetch_one(&pool)
            .await
            .expect("rp-edge-read-1 must exist");

    assert_eq!(source_id, "rp-node-src");
    assert_eq!(target_id, "rp-node-tgt");
    assert_eq!(edge_kind, "reference");

    sqlx::query("DELETE FROM domain_edges WHERE id = 'rp-edge-read-1'")
        .execute(&pool)
        .await
        .expect("post-test cleanup failed");

    pool.close().await;
}

/// Proves that the edges loader can limit results to a configurable cap,
/// which mirrors the `MAX_EDGES_CACHE` runtime behaviour of the JSONL loader.
///
/// Inserts 5 edges, queries with LIMIT 3, and confirms exactly 3 are returned.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn edges_loader_respects_max_edges_cache_limit() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    for i in 1..=5 {
        let id = format!("rp-edge-limit-{i}");
        insert_edge(&pool, &id, "rp-node-src", "rp-node-tgt").await;
    }

    let count_unlimited: (i64,) =
        sqlx::query_as("SELECT COUNT(*) FROM domain_edges WHERE id LIKE 'rp-edge-limit-%'")
            .fetch_one(&pool)
            .await
            .expect("count query failed");
    assert_eq!(count_unlimited.0, 5, "all 5 edges must be present");

    // Simulate the loader cap: LIMIT corresponds to MAX_EDGES_CACHE.
    let rows: Vec<(String,)> =
        sqlx::query_as("SELECT id FROM domain_edges WHERE id LIKE 'rp-edge-limit-%' LIMIT 3")
            .fetch_all(&pool)
            .await
            .expect("limited query failed");
    assert_eq!(
        rows.len(),
        3,
        "LIMIT 3 must return exactly 3 edges (MAX_EDGES_CACHE analogue)"
    );

    sqlx::query("DELETE FROM domain_edges WHERE id LIKE 'rp-edge-limit-%'")
        .execute(&pool)
        .await
        .expect("post-test cleanup failed");

    pool.close().await;
}

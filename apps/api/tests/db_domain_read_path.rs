//! Integration proof: Phase D PostgreSQL domain read path (OPT-ARC-001).
//!
//! Proves that the read-only loaders in `weltgewebe_api::domain_db` reconstruct
//! nodes, edges, and accounts from the Phase B domain tables into the same
//! in-memory types used by the JSONL runtime path — with account privacy and
//! id-ascending ordering preserved.
//!
//! Phase scope: loader proof plus startup switch. The startup switch is
//! implemented behind `WELTGEWEBE_DOMAIN_READ_SOURCE`. JSONL remains the
//! default; Postgres is opt-in. Write path remains JSONL until Phase E.
//!
//! Run with:
//!   DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
//!     cargo test --locked -p weltgewebe-api --test db_domain_read_path \
//!     -- --include-ignored --test-threads=1
//!
//! Notes:
//! - Tests are ignored by default to keep offline paths green.
//! - DATABASE_URL must point to direct PostgreSQL (not PgBouncer at :6432).
//! - Use --test-threads=1: the loaders read ALL rows, and each test cleans up
//!   only its own fixture rows (prefix `rp-`) at start and end so assertions
//!   are deterministic without being destructive to the local database.

use std::{path::PathBuf, str::FromStr};

use sqlx::postgres::{PgConnectOptions, PgPoolOptions};

use weltgewebe_api::domain_db::{
    load_accounts_from_postgres, load_edges_from_postgres, load_nodes_from_postgres,
};
use weltgewebe_api::routes::accounts::AccountMode;

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

/// Remove test fixture rows (all prefixed `rp-`) from the three domain tables.
/// Only fixture rows are deleted — production or non-test data is never touched.
/// There are no foreign keys between the tables (see Phase B migrations).
async fn clear_fixture_rows(pool: &sqlx::PgPool) {
    for stmt in [
        "DELETE FROM domain_edges WHERE id LIKE 'rp-%'",
        "DELETE FROM domain_nodes WHERE id LIKE 'rp-%'",
        "DELETE FROM domain_accounts WHERE id LIKE 'rp-%'",
    ] {
        sqlx::query(stmt)
            .execute(pool)
            .await
            .unwrap_or_else(|e| panic!("failed to clear fixture rows ({stmt}): {e}"));
    }
}

async fn insert_node(
    pool: &sqlx::PgPool,
    id: &str,
    kind: &str,
    title: &str,
    lat: f64,
    lon: f64,
    payload_json: &str,
) {
    sqlx::query(
        "INSERT INTO domain_nodes (id, kind, title, lat, lon, created_at, updated_at, payload)
         VALUES ($1, $2, $3, $4, $5,
                 '2026-01-01T00:00:00Z'::timestamptz,
                 '2026-01-02T00:00:00Z'::timestamptz,
                 $6::jsonb)",
    )
    .bind(id)
    .bind(kind)
    .bind(title)
    .bind(lat)
    .bind(lon)
    .bind(payload_json)
    .execute(pool)
    .await
    .unwrap_or_else(|e| panic!("failed to insert node {id}: {e}"));
}

async fn insert_edge(
    pool: &sqlx::PgPool,
    id: &str,
    source_id: &str,
    target_id: &str,
    edge_kind: &str,
    payload_json: &str,
) {
    sqlx::query(
        "INSERT INTO domain_edges (id, source_id, target_id, edge_kind, created_at, payload)
         VALUES ($1, $2, $3, $4, '2026-01-15T00:00:00Z'::timestamptz, $5::jsonb)",
    )
    .bind(id)
    .bind(source_id)
    .bind(target_id)
    .bind(edge_kind)
    .bind(payload_json)
    .execute(pool)
    .await
    .unwrap_or_else(|e| panic!("failed to insert edge {id}: {e}"));
}

/// Insert a domain account row. `lat`/`lon` are the private residence
/// coordinates (NULL for RoN accounts). `public_payload`/`private_payload` are
/// JSONB text (privacy fields like visibility/suppress_public_pos/ron_flag live
/// in private_payload, mirroring the Phase C backfill).
#[allow(clippy::too_many_arguments)]
async fn insert_account(
    pool: &sqlx::PgPool,
    id: &str,
    kind: &str,
    mode: &str,
    radius_m: i64,
    lat: Option<f64>,
    lon: Option<f64>,
    email: Option<&str>,
    public_payload: &str,
    private_payload: &str,
) {
    sqlx::query(
        "INSERT INTO domain_accounts
            (id, kind, title, mode, radius_m, disabled,
             location_lat, location_lon, role, email,
             public_payload, private_payload)
         VALUES ($1, $2, 'Test Account', $3, $4, FALSE,
                 $5, $6, 'weber', $7,
                 $8::jsonb, $9::jsonb)",
    )
    .bind(id)
    .bind(kind)
    .bind(mode)
    .bind(radius_m)
    .bind(lat)
    .bind(lon)
    .bind(email)
    .bind(public_payload)
    .bind(private_payload)
    .execute(pool)
    .await
    .unwrap_or_else(|e| panic!("failed to insert account {id}: {e}"));
}

// ── Node loader ─────────────────────────────────────────────────────────────

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn nodes_loader_reads_columns_and_payload() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;

    insert_node(
        &pool,
        "rp-node-alpha",
        "Ort",
        "Alpha Node",
        53.5,
        10.0,
        r#"{"summary":"Alpha summary","info":"Alpha info","tags":["a","b"]}"#,
    )
    .await;

    let cache = load_nodes_from_postgres(&pool)
        .await
        .expect("node loader must succeed");

    let node = cache.get("rp-node-alpha").expect("node alpha must load");
    assert_eq!(node.kind, "Ort");
    assert_eq!(node.title, "Alpha Node");
    assert!((node.location.lat - 53.5).abs() < 1e-9);
    assert!((node.location.lon - 10.0).abs() < 1e-9);
    assert_eq!(node.summary.as_deref(), Some("Alpha summary"));
    assert_eq!(node.info.as_deref(), Some("Alpha info"));
    assert_eq!(node.tags, vec!["a".to_string(), "b".to_string()]);
    assert!(
        node.created_at.starts_with("2026-01-01"),
        "created_at must come from the column, got {}",
        node.created_at
    );

    clear_fixture_rows(&pool).await;
    pool.close().await;
}

// ── Edge loader

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn edges_loader_reads_columns_and_payload() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;

    insert_edge(
        &pool,
        "rp-edge-alpha",
        "rp-node-alpha",
        "rp-node-beta",
        "knows",
        r#"{"source_type":"node","target_type":"account","note":"Edge note"}"#,
    )
    .await;

    let cache = load_edges_from_postgres(&pool)
        .await
        .expect("edge loader must succeed");

    let edge = cache.get("rp-edge-alpha").expect("edge alpha must load");
    assert_eq!(edge.source_id, "rp-node-alpha");
    assert_eq!(edge.target_id, "rp-node-beta");
    assert_eq!(edge.edge_kind, "knows");
    assert_eq!(edge.source_type.as_deref(), Some("node"));
    assert_eq!(edge.target_type.as_deref(), Some("account"));
    assert_eq!(edge.note.as_deref(), Some("Edge note"));

    clear_fixture_rows(&pool).await;
    pool.close().await;
}

// ── Account loader: privacy

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn accounts_loader_verortet_exposes_public_pos_and_never_leaks_location() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;

    // Verortet, radius 0, no suppression: public_pos is exposed.
    insert_account(
        &pool,
        "rp-acc-verortet",
        "garnrolle",
        "verortet",
        0,
        Some(53.5),
        Some(10.0),
        None,
        "{}",
        "{}",
    )
    .await;

    let store = load_accounts_from_postgres(&pool)
        .await
        .expect("account loader must succeed");
    let account = store
        .get("rp-acc-verortet")
        .expect("verortet account loads");

    assert_eq!(account.public.mode, AccountMode::Verortet);
    assert!(
        account.public.public_pos.is_some(),
        "verortet account must expose public_pos when allowed"
    );

    // The private residence must never appear in the public projection.
    let serialized = serde_json::to_value(&account.public).expect("serialize public account");
    assert!(
        serialized.get("location").is_none(),
        "public projection must NOT contain the private 'location' field"
    );
    assert!(serialized.get("public_pos").is_some());

    clear_fixture_rows(&pool).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn accounts_loader_private_visibility_suppresses_public_pos() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;

    // Mirrors the Phase C backfill: visibility=private also sets suppress_public_pos.
    insert_account(
        &pool,
        "rp-acc-private",
        "garnrolle",
        "verortet",
        0,
        Some(53.5),
        Some(10.0),
        None,
        "{}",
        r#"{"visibility":"private","suppress_public_pos":true}"#,
    )
    .await;

    let store = load_accounts_from_postgres(&pool)
        .await
        .expect("account loader must succeed");
    let account = store.get("rp-acc-private").expect("private account loads");

    assert_eq!(
        account.public.mode,
        AccountMode::Verortet,
        "private account keeps its verortet identity"
    );
    assert!(
        account.public.public_pos.is_none(),
        "visibility=private must suppress public_pos"
    );

    clear_fixture_rows(&pool).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn accounts_loader_suppress_public_pos_without_visibility() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;

    // suppress_public_pos=true WITHOUT any visibility key: this rule is not
    // modelled by map_json_to_public_account and is applied as an explicit
    // override by the loader.
    insert_account(
        &pool,
        "rp-acc-suppressed",
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

    let store = load_accounts_from_postgres(&pool)
        .await
        .expect("account loader must succeed");
    let account = store
        .get("rp-acc-suppressed")
        .expect("suppressed account loads");

    assert_eq!(account.public.mode, AccountMode::Verortet);
    assert!(
        account.public.public_pos.is_none(),
        "suppress_public_pos=true must hide public_pos even without visibility=private"
    );

    clear_fixture_rows(&pool).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn accounts_loader_approximate_radius_zero_becomes_250() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;

    // visibility=approximate with radius 0 and no explicit mode: the loader
    // re-derives mode via map_json, which raises the radius to 250.
    insert_account(
        &pool,
        "rp-acc-approximate",
        "garnrolle",
        "verortet",
        0,
        Some(52.0),
        Some(12.0),
        None,
        "{}",
        r#"{"visibility":"approximate"}"#,
    )
    .await;

    let store = load_accounts_from_postgres(&pool)
        .await
        .expect("account loader must succeed");
    let account = store
        .get("rp-acc-approximate")
        .expect("approximate account loads");

    assert_eq!(
        account.public.radius_m, 250,
        "approximate + radius 0 must become radius_m=250"
    );
    assert_eq!(account.public.mode, AccountMode::Verortet);
    assert!(
        account.public.public_pos.is_some(),
        "approximate account exposes a (jittered) public_pos"
    );

    clear_fixture_rows(&pool).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn accounts_loader_ron_and_ron_flag_suppress_public_pos() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;

    // RoN by kind/mode: no residence, no public_pos.
    insert_account(
        &pool,
        "rp-acc-ron",
        "ron",
        "ron",
        0,
        None,
        None,
        None,
        "{}",
        "{}",
    )
    .await;
    // RoN by legacy ron_flag, despite having a residence on file.
    insert_account(
        &pool,
        "rp-acc-ronflag",
        "garnrolle",
        "ron",
        0,
        Some(53.5),
        Some(10.0),
        None,
        "{}",
        r#"{"ron_flag":true}"#,
    )
    .await;

    let store = load_accounts_from_postgres(&pool)
        .await
        .expect("account loader must succeed");

    let ron = store.get("rp-acc-ron").expect("ron account loads");
    assert_eq!(ron.public.mode, AccountMode::Ron);
    assert!(ron.public.public_pos.is_none(), "ron exposes no public_pos");

    let ron_flag = store.get("rp-acc-ronflag").expect("ron_flag account loads");
    assert_eq!(ron_flag.public.mode, AccountMode::Ron);
    assert!(
        ron_flag.public.public_pos.is_none(),
        "ron_flag must suppress public_pos even with a residence"
    );

    clear_fixture_rows(&pool).await;
    pool.close().await;
}

/// Proves that the `mode` DB column is the primary source of truth: a
/// `garnrolle` with `mode='ron'` and a set location must still resolve to
/// `AccountMode::Ron` with `public_pos == None`, even though the legacy
/// fallback (absent mode key + location present) would have inferred Verortet.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn accounts_loader_respects_mode_column_ron_even_with_location() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;

    // mode='ron' in the DB column, but location is set and private_payload
    // is empty (no ron_flag, no visibility). Without reading the mode column,
    // the loader would fall through to legacy derivation and infer Verortet
    // from the presence of location_lat/location_lon.
    insert_account(
        &pool,
        "rp-acc-mode-ron",
        "garnrolle",
        "ron",
        0,
        Some(53.5),
        Some(10.0),
        None,
        "{}",
        "{}",
    )
    .await;

    let store = load_accounts_from_postgres(&pool)
        .await
        .expect("account loader must succeed");
    let account = store
        .get("rp-acc-mode-ron")
        .expect("mode-ron account loads");

    assert_eq!(
        account.public.mode,
        AccountMode::Ron,
        "DB mode='ron' must be honored even when location is set"
    );
    assert!(
        account.public.public_pos.is_none(),
        "ron mode must suppress public_pos"
    );

    clear_fixture_rows(&pool).await;
    pool.close().await;
}

/// Proves that `mode='verortet'` with a location produces Verortet mode and
/// an exposed `public_pos` (baseline sanity check).
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn accounts_loader_respects_mode_column_verortet_with_location() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;

    insert_account(
        &pool,
        "rp-acc-mode-verortet",
        "garnrolle",
        "verortet",
        0,
        Some(52.0),
        Some(12.0),
        None,
        "{}",
        "{}",
    )
    .await;

    let store = load_accounts_from_postgres(&pool)
        .await
        .expect("account loader must succeed");
    let account = store
        .get("rp-acc-mode-verortet")
        .expect("mode-verortet account loads");

    assert_eq!(
        account.public.mode,
        AccountMode::Verortet,
        "DB mode='verortet' must produce Verortet"
    );
    assert!(
        account.public.public_pos.is_some(),
        "verortet account with location must expose public_pos"
    );

    clear_fixture_rows(&pool).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn accounts_loader_email_index_is_rebuilt_for_case_insensitive_lookup() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;

    insert_account(
        &pool,
        "rp-acc-email",
        "ron",
        "ron",
        0,
        None,
        None,
        Some("Found@Example.com"),
        "{}",
        "{}",
    )
    .await;

    let store = load_accounts_from_postgres(&pool)
        .await
        .expect("account loader must succeed");

    let by_email = store
        .get_by_email("found@example.com")
        .expect("case-insensitive email lookup must work after rebuild");
    assert_eq!(by_email.public.id, "rp-acc-email");

    clear_fixture_rows(&pool).await;
    pool.close().await;
}

// ── Ordering

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn loaders_return_rows_in_id_ascending_order() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;

    // Insert in deliberately non-id order; loader must return id-ascending.
    insert_node(&pool, "rp-ord-c", "K", "C", 1.0, 1.0, "{}").await;
    insert_node(&pool, "rp-ord-a", "K", "A", 1.0, 1.0, "{}").await;
    insert_node(&pool, "rp-ord-b", "K", "B", 1.0, 1.0, "{}").await;

    let cache = load_nodes_from_postgres(&pool)
        .await
        .expect("node loader must succeed");

    // Filter to rp-ord- fixtures only; other pre-existing rows are ignored.
    let ids: Vec<String> = cache
        .iter_in_order()
        .map(|n| n.id.clone())
        .filter(|id| id.starts_with("rp-ord-"))
        .collect();
    assert_eq!(
        ids,
        vec![
            "rp-ord-a".to_string(),
            "rp-ord-b".to_string(),
            "rp-ord-c".to_string()
        ],
        "fixture nodes must be returned in id-ascending order (NOT legacy JSONL offset order)"
    );

    clear_fixture_rows(&pool).await;
    pool.close().await;
}

// ── Smoke ──────────────────────────────────────────────────────────────────

/// Verify that all three loaders succeed after fixture cleanup. This does NOT
/// assert global table emptiness — pre-existing (non-fixture) rows are ignored.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn loaders_succeed_after_fixture_cleanup() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;

    load_nodes_from_postgres(&pool)
        .await
        .expect("node loader must succeed after fixture cleanup");
    load_edges_from_postgres(&pool)
        .await
        .expect("edge loader must succeed after fixture cleanup");
    load_accounts_from_postgres(&pool)
        .await
        .expect("account loader must succeed after fixture cleanup");

    pool.close().await;
}

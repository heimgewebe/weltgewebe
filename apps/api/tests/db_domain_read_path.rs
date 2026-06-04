//! Integration proof: Phase D PostgreSQL domain read path (OPT-ARC-001).
//!
//! Proves that the read-only loaders in `weltgewebe_api::domain_db` reconstruct
//! nodes, edges, and accounts from the Phase B domain tables into the same
//! in-memory types used by the JSONL runtime path — with account privacy and
//! id-ascending ordering preserved.
//!
//! Run with:
//!
//! ```bash
//! DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
//!   cargo test --locked -p weltgewebe-api --test db_domain_read_path \
//!   -- --include-ignored --test-threads=1
//! ```

use std::{path::PathBuf, str::FromStr};

use serial_test::serial;
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

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
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
    let cache = load_nodes_from_postgres(&pool).await.expect("node loader");
    let node = cache.get("rp-node-alpha").expect("node alpha must load");
    assert_eq!(node.kind, "Ort");
    assert_eq!(node.title, "Alpha Node");
    assert!((node.location.lat - 53.5).abs() < 1e-9);
    assert!((node.location.lon - 10.0).abs() < 1e-9);
    assert_eq!(node.summary.as_deref(), Some("Alpha summary"));
    assert_eq!(node.info.as_deref(), Some("Alpha info"));
    assert_eq!(node.tags, vec!["a".to_string(), "b".to_string()]);
    assert!(node.created_at.starts_with("2026-01-01"));
    clear_fixture_rows(&pool).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
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
    let cache = load_edges_from_postgres(&pool).await.expect("edge loader");
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

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn accounts_loader_verortet_exposes_public_pos_and_never_leaks_location() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;
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
        .expect("account loader");
    let account = store
        .get("rp-acc-verortet")
        .expect("verortet account loads");
    assert_eq!(account.public.mode, AccountMode::Verortet);
    assert!(account.public.public_pos.is_some());
    let serialized = serde_json::to_value(&account.public).expect("serialize public account");
    assert!(serialized.get("location").is_none());
    assert!(serialized.get("public_pos").is_some());
    clear_fixture_rows(&pool).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn accounts_loader_private_visibility_suppresses_public_pos() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;
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
        r#"{"visibility":"private"}"#,
    )
    .await;
    let store = load_accounts_from_postgres(&pool)
        .await
        .expect("account loader");
    let account = store.get("rp-acc-private").expect("private account loads");
    assert_eq!(account.public.mode, AccountMode::Verortet);
    assert!(account.public.public_pos.is_none());
    clear_fixture_rows(&pool).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn accounts_loader_suppress_public_pos_without_visibility() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;
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
        .expect("account loader");
    let account = store
        .get("rp-acc-suppressed")
        .expect("suppressed account loads");
    assert_eq!(account.public.mode, AccountMode::Verortet);
    assert!(account.public.public_pos.is_none());
    clear_fixture_rows(&pool).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn accounts_loader_approximate_radius_zero_becomes_250() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;
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
        .expect("account loader");
    let account = store
        .get("rp-acc-approximate")
        .expect("approximate account loads");
    assert_eq!(account.public.radius_m, 250);
    assert_eq!(account.public.mode, AccountMode::Verortet);
    assert!(account.public.public_pos.is_some());
    clear_fixture_rows(&pool).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn accounts_loader_ron_and_ron_flag_suppress_public_pos() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;
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
    insert_account(
        &pool,
        "rp-acc-ronflag",
        "garnrolle",
        "verortet",
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
        .expect("account loader");
    let ron = store.get("rp-acc-ron").expect("ron account loads");
    assert_eq!(ron.public.mode, AccountMode::Ron);
    assert!(ron.public.public_pos.is_none());
    let ron_flag = store.get("rp-acc-ronflag").expect("ron_flag account loads");
    assert_eq!(ron_flag.public.mode, AccountMode::Ron);
    assert!(ron_flag.public.public_pos.is_none());
    clear_fixture_rows(&pool).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn accounts_loader_respects_mode_column_ron_even_with_location() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;
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
        .expect("account loader");
    let account = store
        .get("rp-acc-mode-ron")
        .expect("mode-ron account loads");
    assert_eq!(account.public.mode, AccountMode::Ron);
    assert!(account.public.public_pos.is_none());
    clear_fixture_rows(&pool).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
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
        .expect("account loader");
    let account = store
        .get("rp-acc-mode-verortet")
        .expect("mode-verortet account loads");
    assert_eq!(account.public.mode, AccountMode::Verortet);
    assert!(account.public.public_pos.is_some());
    clear_fixture_rows(&pool).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
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
        .expect("account loader");
    let by_email = store
        .get_by_email("found@example.com")
        .expect("case-insensitive email lookup");
    assert_eq!(by_email.public.id, "rp-acc-email");
    clear_fixture_rows(&pool).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn loaders_return_rows_in_id_ascending_order() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;
    insert_node(&pool, "rp-ord-c", "K", "C", 1.0, 1.0, "{}").await;
    insert_node(&pool, "rp-ord-a", "K", "A", 1.0, 1.0, "{}").await;
    insert_node(&pool, "rp-ord-b", "K", "B", 1.0, 1.0, "{}").await;
    let cache = load_nodes_from_postgres(&pool).await.expect("node loader");
    let ids: Vec<String> = cache
        .iter_in_order()
        .map(|n| n.id.clone())
        .filter(|id| id.starts_with("rp-ord-"))
        .collect();
    assert_eq!(ids, vec!["rp-ord-a", "rp-ord-b", "rp-ord-c"]);
    clear_fixture_rows(&pool).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn loaders_succeed_after_fixture_cleanup() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;
    load_nodes_from_postgres(&pool).await.expect("node loader");
    load_edges_from_postgres(&pool).await.expect("edge loader");
    load_accounts_from_postgres(&pool)
        .await
        .expect("account loader");
    pool.close().await;
}

struct EnvGuard {
    key: String,
    old_value: Option<String>,
}

impl EnvGuard {
    fn set(key: &str, value: &str) -> Self {
        let old_value = std::env::var(key).ok();
        std::env::set_var(key, value);
        Self {
            key: key.to_string(),
            old_value,
        }
    }
}

impl Drop for EnvGuard {
    fn drop(&mut self) {
        match &self.old_value {
            Some(v) => std::env::set_var(&self.key, v),
            None => std::env::remove_var(&self.key),
        }
    }
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn edges_loader_respects_max_edges_cache_limit() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clear_fixture_rows(&pool).await;
    let _guard = EnvGuard::set("MAX_EDGES_CACHE", "2");
    insert_edge(
        &pool,
        "rp-edge-cache-a",
        "rp-node-x",
        "rp-node-y",
        "knows",
        "{}",
    )
    .await;
    insert_edge(
        &pool,
        "rp-edge-cache-b",
        "rp-node-x",
        "rp-node-y",
        "knows",
        "{}",
    )
    .await;
    insert_edge(
        &pool,
        "rp-edge-cache-c",
        "rp-node-x",
        "rp-node-y",
        "knows",
        "{}",
    )
    .await;
    let cache = load_edges_from_postgres(&pool).await.expect("edge loader");
    assert!(
        cache.len() <= 2,
        "loader must materialise at most 2 rows, got {}",
        cache.len()
    );
    clear_fixture_rows(&pool).await;
    pool.close().await;
}

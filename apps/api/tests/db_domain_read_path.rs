use std::path::PathBuf;

use serial_test::serial;
use sqlx::{Executor, PgPool};
use weltgewebe_api::domain_db::{
    load_accounts_from_postgres, load_edges_from_postgres, load_nodes_from_postgres,
};
use weltgewebe_api::routes::accounts::AccountMode;
use weltgewebe_api::test_helpers::EnvGuard;

async fn direct_pool() -> PgPool {
    let url = std::env::var("DATABASE_URL")
        .expect("DATABASE_URL must point at a direct PostgreSQL database");
    PgPool::connect(&url).await.expect("connect to PostgreSQL")
}

async fn run_migrations(pool: &PgPool) {
    let migrations_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("migrations");
    let migrator = sqlx::migrate::Migrator::new(migrations_dir)
        .await
        .expect("failed to load migrations");
    migrator.run(pool).await.expect("failed to run migrations");
}

async fn clean(pool: &PgPool) {
    pool.execute("DELETE FROM domain_edges WHERE id LIKE 'rp-%'")
        .await
        .expect("clean domain_edges");
    pool.execute("DELETE FROM domain_nodes WHERE id LIKE 'rp-%'")
        .await
        .expect("clean domain_nodes");
    pool.execute("DELETE FROM domain_accounts WHERE id LIKE 'rp-%'")
        .await
        .expect("clean domain_accounts");
}

async fn prepare_pool() -> PgPool {
    let pool = direct_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;
    pool
}

#[tokio::test]
#[ignore]
#[serial]
async fn nodes_loader_reconstructs_public_shape() {
    let pool = prepare_pool().await;
    sqlx::query(
        "INSERT INTO domain_nodes (id, kind, title, lat, lon, payload) \
         VALUES ('rp-node-a', 'place', 'Read Path Node', 53.55, 9.99, \
         '{\"summary\":\"Summary\",\"info\":\"Info\",\"tags\":[\"a\",\"b\"]}'::jsonb)",
    )
    .execute(&pool)
    .await
    .expect("insert node");

    let cache = load_nodes_from_postgres(&pool).await.expect("load nodes");
    let node = cache.get("rp-node-a").expect("node present");

    assert_eq!(node.title, "Read Path Node");
    assert_eq!(node.summary.as_deref(), Some("Summary"));
    assert_eq!(node.tags, vec!["a".to_string(), "b".to_string()]);
    clean(&pool).await;
}

#[tokio::test]
#[ignore]
#[serial]
async fn edges_loader_respects_max_edges_cache_limit() {
    let pool = prepare_pool().await;
    let _limit = EnvGuard::set("MAX_EDGES_CACHE", "1");
    for id in ["rp-edge-a", "rp-edge-b"] {
        sqlx::query(
            "INSERT INTO domain_edges (id, source_id, target_id, edge_kind, payload) \
             VALUES ($1, 'rp-node-a', 'rp-node-b', 'relates', '{}'::jsonb)",
        )
        .bind(id)
        .execute(&pool)
        .await
        .expect("insert edge");
    }

    let cache = load_edges_from_postgres(&pool).await.expect("load edges");

    assert!(
        cache.len() <= 1,
        "with MAX_EDGES_CACHE=1, loader must materialise at most one edge"
    );
    clean(&pool).await;
}

#[tokio::test]
#[ignore]
#[serial]
async fn accounts_loader_rebuilds_email_index_and_privacy_projection() {
    let pool = prepare_pool().await;
    sqlx::query(
        "INSERT INTO domain_accounts \
         (id, kind, title, mode, radius_m, disabled, location_lat, location_lon, role, email, public_payload, private_payload) \
         VALUES \
         ('rp-account-a', 'garnrolle', 'Visible', 'verortet', 0, false, 53.55, 9.99, 'gast', 'ReadPath@Example.test', '{\"summary\":\"Public\"}'::jsonb, '{}'::jsonb), \
         ('rp-account-b', 'garnrolle', 'Suppressed', 'verortet', 0, false, 53.56, 9.98, 'gast', NULL, '{}'::jsonb, '{\"suppress_public_pos\":true}'::jsonb)",
    )
    .execute(&pool)
    .await
    .expect("insert accounts");

    let store = load_accounts_from_postgres(&pool)
        .await
        .expect("load accounts");
    let visible = store
        .get_by_email("readpath@example.test")
        .expect("case-insensitive email lookup");
    let suppressed = store.get("rp-account-b").expect("suppressed account");

    assert_eq!(visible.public.summary.as_deref(), Some("Public"));
    assert!(visible.public.public_pos.is_some());
    assert!(suppressed.public.public_pos.is_none());
    clean(&pool).await;
}

#[tokio::test]
#[ignore]
#[serial]
async fn accounts_loader_respects_mode_column_ron_even_with_location() {
    let pool = prepare_pool().await;
    sqlx::query(
        "INSERT INTO domain_accounts \
         (id, kind, title, mode, radius_m, disabled, location_lat, location_lon, role, public_payload, private_payload) \
         VALUES \
         ('rp-account-ron-location', 'garnrolle', 'RoN With Location', 'ron', 0, false, 53.55, 9.99, 'gast', '{}'::jsonb, '{}'::jsonb)",
    )
    .execute(&pool)
    .await
    .expect("insert ron account");

    let store = load_accounts_from_postgres(&pool)
        .await
        .expect("load accounts");
    let account = store
        .get("rp-account-ron-location")
        .expect("ron account present");

    assert_eq!(account.public.mode, AccountMode::Ron);
    assert!(account.public.public_pos.is_none());
    clean(&pool).await;
}

#[tokio::test]
#[ignore]
#[serial]
async fn accounts_loader_approximate_radius_zero_becomes_250() {
    let pool = prepare_pool().await;
    sqlx::query(
        "INSERT INTO domain_accounts \
         (id, kind, title, mode, radius_m, disabled, location_lat, location_lon, role, public_payload, private_payload) \
         VALUES \
         ('rp-account-approximate', 'garnrolle', 'Approximate', 'verortet', 0, false, 53.55, 9.99, 'gast', '{}'::jsonb, '{\"visibility\":\"approximate\"}'::jsonb)",
    )
    .execute(&pool)
    .await
    .expect("insert approximate account");

    let store = load_accounts_from_postgres(&pool)
        .await
        .expect("load accounts");
    let account = store
        .get("rp-account-approximate")
        .expect("approximate account present");

    assert_eq!(account.public.mode, AccountMode::Verortet);
    assert_eq!(account.public.radius_m, 250);
    assert!(account.public.public_pos.is_some());
    clean(&pool).await;
}

#[tokio::test]
#[ignore]
#[serial]
async fn accounts_loader_private_visibility_suppresses_public_pos() {
    let pool = prepare_pool().await;
    sqlx::query(
        "INSERT INTO domain_accounts \
         (id, kind, title, mode, radius_m, disabled, location_lat, location_lon, role, public_payload, private_payload) \
         VALUES \
         ('rp-account-private', 'garnrolle', 'Private', 'verortet', 0, false, 53.55, 9.99, 'gast', '{}'::jsonb, '{\"visibility\":\"private\"}'::jsonb)",
    )
    .execute(&pool)
    .await
    .expect("insert private account");

    let store = load_accounts_from_postgres(&pool)
        .await
        .expect("load accounts");
    let account = store
        .get("rp-account-private")
        .expect("private account present");

    assert_eq!(account.public.mode, AccountMode::Verortet);
    assert!(account.public.public_pos.is_none());
    clean(&pool).await;
}

#[tokio::test]
#[ignore]
#[serial]
async fn accounts_loader_ron_flag_forces_ron_even_with_location() {
    let pool = prepare_pool().await;
    sqlx::query(
        "INSERT INTO domain_accounts \
         (id, kind, title, mode, radius_m, disabled, location_lat, location_lon, role, public_payload, private_payload) \
         VALUES \
         ('rp-account-ron-flag', 'garnrolle', 'RoN Flag', 'verortet', 0, false, 53.55, 9.99, 'gast', '{}'::jsonb, '{\"ron_flag\":true}'::jsonb)",
    )
    .execute(&pool)
    .await
    .expect("insert ron-flag account");

    let store = load_accounts_from_postgres(&pool)
        .await
        .expect("load accounts");
    let account = store
        .get("rp-account-ron-flag")
        .expect("ron-flag account present");

    assert_eq!(account.public.mode, AccountMode::Ron);
    assert!(account.public.public_pos.is_none());
    clean(&pool).await;
}

#[tokio::test]
#[ignore]
#[serial]
async fn empty_tables_with_only_fixtures_deleted_do_not_fail() {
    let pool = prepare_pool().await;

    let _nodes = load_nodes_from_postgres(&pool).await.expect("load nodes");
    let _edges = load_edges_from_postgres(&pool).await.expect("load edges");
    let _accounts = load_accounts_from_postgres(&pool)
        .await
        .expect("load accounts");
}

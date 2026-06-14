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

// Each DB proof test starts from a clean rp-* fixture namespace.
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

#[tokio::test]
#[ignore]
#[serial]
async fn jsonl_postgres_legacy_list_order_gap_diagnostic() {
    let pool = prepare_pool().await;
    let temp_dir = tempfile::tempdir().expect("create temp dir");
    let _env = EnvGuard::set("GEWEBE_IN_DIR", temp_dir.path().to_str().unwrap());

    // 1. Prepare non-ID-sorted JSONL fixtures (c, a, b order)
    let nodes_jsonl = "\
{\"id\":\"rp-list-node-c\",\"kind\":\"place\",\"title\":\"C\",\"location\":{\"lat\":0.0,\"lon\":0.0},\"payload\":{}}
{\"id\":\"rp-list-node-a\",\"kind\":\"place\",\"title\":\"A\",\"location\":{\"lat\":0.0,\"lon\":0.0},\"payload\":{}}
{\"id\":\"rp-list-node-b\",\"kind\":\"place\",\"title\":\"B\",\"location\":{\"lat\":0.0,\"lon\":0.0},\"payload\":{}}
";
    tokio::fs::write(temp_dir.path().join("demo.nodes.jsonl"), nodes_jsonl)
        .await
        .unwrap();

    let edges_jsonl = "\
{\"id\":\"rp-list-edge-c\",\"source_id\":\"rp-list-node-c\",\"target_id\":\"rp-list-node-a\",\"edge_kind\":\"relates\",\"payload\":{}}
{\"id\":\"rp-list-edge-a\",\"source_id\":\"rp-list-node-a\",\"target_id\":\"rp-list-node-b\",\"edge_kind\":\"relates\",\"payload\":{}}
{\"id\":\"rp-list-edge-b\",\"source_id\":\"rp-list-node-b\",\"target_id\":\"rp-list-node-c\",\"edge_kind\":\"relates\",\"payload\":{}}
";
    tokio::fs::write(temp_dir.path().join("demo.edges.jsonl"), edges_jsonl)
        .await
        .unwrap();

    let accounts_jsonl = "\
{\"id\":\"rp-list-account-c\",\"type\":\"garnrolle\",\"title\":\"C\",\"mode\":\"ron\",\"role\":\"gast\",\"email\":\"rp-list-account-c@example.invalid\"}
{\"id\":\"rp-list-account-a\",\"type\":\"garnrolle\",\"title\":\"A\",\"mode\":\"ron\",\"role\":\"gast\",\"email\":\"rp-list-account-a@example.invalid\"}
{\"id\":\"rp-list-account-b\",\"type\":\"garnrolle\",\"title\":\"B\",\"mode\":\"ron\",\"role\":\"gast\",\"email\":\"rp-list-account-b@example.invalid\"}
";
    tokio::fs::write(temp_dir.path().join("demo.accounts.jsonl"), accounts_jsonl)
        .await
        .unwrap();

    // 2. Prepare PostgreSQL fixtures (inserted in c, a, b order)
    sqlx::query(
        "INSERT INTO domain_nodes (id, kind, title, lat, lon, payload) \
         VALUES \
         ('rp-list-node-c', 'place', 'C', 0.0, 0.0, '{}'::jsonb), \
         ('rp-list-node-a', 'place', 'A', 0.0, 0.0, '{}'::jsonb), \
         ('rp-list-node-b', 'place', 'B', 0.0, 0.0, '{}'::jsonb)",
    )
    .execute(&pool)
    .await
    .expect("insert nodes");

    sqlx::query(
        "INSERT INTO domain_edges (id, source_id, target_id, edge_kind, payload) \
         VALUES \
         ('rp-list-edge-c', 'rp-list-node-c', 'rp-list-node-a', 'relates', '{}'::jsonb), \
         ('rp-list-edge-a', 'rp-list-node-a', 'rp-list-node-b', 'relates', '{}'::jsonb), \
         ('rp-list-edge-b', 'rp-list-node-b', 'rp-list-node-c', 'relates', '{}'::jsonb)",
    )
    .execute(&pool)
    .await
    .expect("insert edges");

    sqlx::query(
        "INSERT INTO domain_accounts \
         (id, kind, title, mode, role, email, public_payload, private_payload) \
         VALUES \
         ('rp-list-account-c', 'garnrolle', 'C', 'ron', 'gast', 'rp-list-account-c@example.invalid', '{}'::jsonb, '{}'::jsonb), \
         ('rp-list-account-a', 'garnrolle', 'A', 'ron', 'gast', 'rp-list-account-a@example.invalid', '{}'::jsonb, '{}'::jsonb), \
         ('rp-list-account-b', 'garnrolle', 'B', 'ron', 'gast', 'rp-list-account-b@example.invalid', '{}'::jsonb, '{}'::jsonb)"
    )
    .execute(&pool)
    .await
    .expect("insert accounts");

    // 3. Execute Loaders
    let jsonl_nodes = weltgewebe_api::routes::nodes::load_nodes().await;
    let pg_nodes = load_nodes_from_postgres(&pool).await.unwrap();

    let jsonl_edges = weltgewebe_api::routes::edges::load_edges().await;
    let pg_edges = load_edges_from_postgres(&pool).await.unwrap();

    let jsonl_accounts = weltgewebe_api::routes::accounts::load_all_accounts().await;
    let pg_accounts = load_accounts_from_postgres(&pool).await.unwrap();

    // 4. Assert Diagnostic Outcomes
    // Nodes: Legacy JSONL loader retains file order. PG loader uses ORDER BY id ASC.
    // The PostgreSQL proof database may contain unrelated local rows. Scope the
    // comparison to this diagnostic's rp-list-* fixtures so the assertion proves
    // list-order semantics, not database cleanliness.
    let jsonl_node_ids: Vec<&str> = jsonl_nodes
        .iter_in_order()
        .map(|n| n.id.as_str())
        .filter(|id| id.starts_with("rp-list-node-"))
        .collect();
    let postgres_node_ids: Vec<&str> = pg_nodes
        .iter_in_order()
        .map(|n| n.id.as_str())
        .filter(|id| id.starts_with("rp-list-node-"))
        .collect();

    // Intentional gap assertion:
    // This diagnostic records the current legacy-order mismatch between JSONL
    // file/cache order and PostgreSQL id order. When TODO 3 is resolved by
    // implementing blueprint-required legacy order preservation or by explicitly
    // revising the blueprint first, this diagnostic must be updated or replaced
    // by the final parity proof.

    assert_ne!(jsonl_node_ids, postgres_node_ids);
    assert_eq!(
        jsonl_node_ids,
        vec!["rp-list-node-c", "rp-list-node-a", "rp-list-node-b"]
    );
    assert_eq!(
        postgres_node_ids,
        vec!["rp-list-node-a", "rp-list-node-b", "rp-list-node-c"]
    );

    // Edges: Legacy JSONL loader retains file order. PG loader uses ORDER BY id ASC.
    let jsonl_edge_ids: Vec<&str> = jsonl_edges
        .iter_in_order()
        .map(|e| e.id.as_str())
        .filter(|id| id.starts_with("rp-list-edge-"))
        .collect();
    let postgres_edge_ids: Vec<&str> = pg_edges
        .iter_in_order()
        .map(|e| e.id.as_str())
        .filter(|id| id.starts_with("rp-list-edge-"))
        .collect();

    // Intentional gap assertion:
    // This diagnostic records the current legacy-order mismatch between JSONL
    // file/cache order and PostgreSQL id order. When TODO 3 is resolved by
    // implementing blueprint-required legacy order preservation or by explicitly
    // revising the blueprint first, this diagnostic must be updated or replaced
    // by the final parity proof.

    assert_ne!(jsonl_edge_ids, postgres_edge_ids);
    assert_eq!(
        jsonl_edge_ids,
        vec!["rp-list-edge-c", "rp-list-edge-a", "rp-list-edge-b"]
    );
    assert_eq!(
        postgres_edge_ids,
        vec!["rp-list-edge-a", "rp-list-edge-b", "rp-list-edge-c"]
    );

    // Accounts: AccountStore uses BTreeMap, so both loaders yield ID-ascending order.
    let jsonl_account_ids: Vec<&str> = jsonl_accounts
        .iter()
        .map(|(id, _)| id.as_str())
        .filter(|id| id.starts_with("rp-list-account-"))
        .collect();
    let postgres_account_ids: Vec<&str> = pg_accounts
        .iter()
        .map(|(id, _)| id.as_str())
        .filter(|id| id.starts_with("rp-list-account-"))
        .collect();

    assert_eq!(jsonl_account_ids, postgres_account_ids);
    assert_eq!(
        jsonl_account_ids,
        vec![
            "rp-list-account-a",
            "rp-list-account-b",
            "rp-list-account-c"
        ]
    );

    // Keep the shared proof database tidy after the successful diagnostic run.
    clean(&pool).await;
}

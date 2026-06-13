//! Integration proof: domain schema migrations (nodes, edges, accounts).
//!
//! Verifies that Phase B migrations for OPT-ARC-001 create domain tables and
//! indexes correctly, and that basic structural inserts and constraints hold.
//! In particular, the accounts schema intentionally keeps email non-unique in
//! Phase B to remain compatible with current JSONL/runtime tolerance until
//! Phase C duplicate-audit/quarantine policy is implemented.
//! Does NOT verify down-migration / DROP behaviour — that requires a
//! disposable database and is deferred to a dedicated revert-proof gate.
//! No runtime cutover is tested here — JSONL remains the active data source
//! until Phase D/E.
//!
//! Run with:
//!   DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
//!     cargo test --locked -p weltgewebe-api --test db_domain_schema_migrations -- --include-ignored
//!
//! Notes:
//! - Tests are ignored by default to keep offline paths green.
//! - DATABASE_URL must point to direct PostgreSQL (not PgBouncer at :6432).

use std::{path::PathBuf, str::FromStr};

use sqlx::postgres::{PgConnectOptions, PgPoolOptions};

fn direct_database_url() -> String {
    let url = std::env::var("DATABASE_URL").expect(
        "DATABASE_URL must be set to run db_domain_schema_migrations tests; \
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
    let migrations_dir: PathBuf = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("migrations");

    let migrator = sqlx::migrate::Migrator::new(migrations_dir)
        .await
        .expect("failed to load migrations");

    migrator.run(pool).await.expect("failed to run migrations");
}

async fn table_exists(pool: &sqlx::PgPool, table_name: &str) -> bool {
    let row: (bool,) = sqlx::query_as(
        "SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = $1
        )",
    )
    .bind(table_name)
    .fetch_one(pool)
    .await
    .expect("failed to query information_schema.tables");

    row.0
}

async fn index_exists(pool: &sqlx::PgPool, index_name: &str) -> bool {
    let row: (bool,) = sqlx::query_as(
        "SELECT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public'
            AND indexname = $1
        )",
    )
    .bind(index_name)
    .fetch_one(pool)
    .await
    .expect("failed to query pg_indexes");

    row.0
}

/// Verifies that running all migrations creates the domain tables and
/// expected indexes for nodes, edges, and accounts.
///
/// This is a schema-presence proof: it does not insert or query domain data.
/// No runtime read/write paths are tested here.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn domain_schema_tables_exist_after_migration() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    // --- domain_nodes ---
    assert!(
        table_exists(&pool, "domain_nodes").await,
        "domain_nodes table must exist after migration"
    );
    assert!(
        index_exists(&pool, "domain_nodes_kind").await,
        "domain_nodes_kind index must exist"
    );
    assert!(
        index_exists(&pool, "domain_nodes_lat_lon").await,
        "domain_nodes_lat_lon index must exist"
    );

    // --- domain_edges ---
    assert!(
        table_exists(&pool, "domain_edges").await,
        "domain_edges table must exist after migration"
    );
    assert!(
        index_exists(&pool, "domain_edges_source_id").await,
        "domain_edges_source_id index must exist"
    );
    assert!(
        index_exists(&pool, "domain_edges_target_id").await,
        "domain_edges_target_id index must exist"
    );
    assert!(
        index_exists(&pool, "domain_edges_source_target").await,
        "domain_edges_source_target index must exist"
    );

    // --- domain_accounts ---
    assert!(
        table_exists(&pool, "domain_accounts").await,
        "domain_accounts table must exist after migration"
    );
    assert!(
        index_exists(&pool, "domain_accounts_email_lookup").await,
        "domain_accounts_email_lookup index must exist"
    );

    pool.close().await;
}

/// Verifies that a row can be inserted into and read back from domain_nodes,
/// domain_edges, and domain_accounts using the schema defined in Phase B.
///
/// This is a structural smoke test only. It does not test any runtime API
/// logic, JSONL backfill, or cursor pagination behaviour.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn domain_schema_basic_insert_and_read() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    // Pre-test cleanup to avoid stale rows from a previously interrupted run.
    sqlx::query("DELETE FROM domain_nodes WHERE id = 'test-node-schema-probe'")
        .execute(&pool)
        .await
        .expect("pre-test cleanup of domain_nodes failed");

    // --- domain_nodes: insert and read back ---
    sqlx::query(
        "INSERT INTO domain_nodes (id, kind, title, lat, lon, payload)
         VALUES ('test-node-schema-probe', 'TestKind', 'Test Node', 53.55, 10.00, '{\"info\":\"probe\"}'::jsonb)",
    )
    .execute(&pool)
    .await
    .expect("failed to insert test row into domain_nodes");

    let (kind, title): (String, String) =
        sqlx::query_as("SELECT kind, title FROM domain_nodes WHERE id = $1")
            .bind("test-node-schema-probe")
            .fetch_one(&pool)
            .await
            .expect("failed to read back test row from domain_nodes");

    assert_eq!(kind, "TestKind");
    assert_eq!(title, "Test Node");

    sqlx::query("DELETE FROM domain_nodes WHERE id = 'test-node-schema-probe'")
        .execute(&pool)
        .await
        .expect("failed to clean up domain_nodes probe row");

    // --- domain_edges: insert and read back ---
    // Pre-test cleanup
    sqlx::query("DELETE FROM domain_edges WHERE id = 'test-edge-schema-probe'")
        .execute(&pool)
        .await
        .expect("pre-test cleanup of domain_edges failed");

    sqlx::query(
        "INSERT INTO domain_edges (id, source_id, target_id, edge_kind, payload)
         VALUES ('test-edge-schema-probe', 'src-001', 'tgt-001', 'TestKind', '{}'::jsonb)",
    )
    .execute(&pool)
    .await
    .expect("failed to insert test row into domain_edges");

    let (source_id, target_id): (String, String) =
        sqlx::query_as("SELECT source_id, target_id FROM domain_edges WHERE id = $1")
            .bind("test-edge-schema-probe")
            .fetch_one(&pool)
            .await
            .expect("failed to read back test row from domain_edges");

    assert_eq!(source_id, "src-001");
    assert_eq!(target_id, "tgt-001");

    sqlx::query("DELETE FROM domain_edges WHERE id = 'test-edge-schema-probe'")
        .execute(&pool)
        .await
        .expect("failed to clean up domain_edges probe row");

    // --- domain_accounts: insert and read back ---
    // Pre-test cleanup
    sqlx::query("DELETE FROM domain_accounts WHERE id = 'test-account-schema-probe'")
        .execute(&pool)
        .await
        .expect("pre-test cleanup of domain_accounts failed");

    sqlx::query(
        "INSERT INTO domain_accounts (id, kind, title, mode, radius_m, role, public_payload, private_payload)
            VALUES ('test-account-schema-probe', 'garnrolle', 'Test Account', 'ron', 0, 'gast', '{}'::jsonb, '{}'::jsonb)",
    )
    .execute(&pool)
    .await
    .expect("failed to insert test row into domain_accounts");

    let (kind, mode): (String, String) =
        sqlx::query_as("SELECT kind, mode FROM domain_accounts WHERE id = $1")
            .bind("test-account-schema-probe")
            .fetch_one(&pool)
            .await
            .expect("failed to read back test row from domain_accounts");

    assert_eq!(kind, "garnrolle");
    assert_eq!(mode, "ron");

    sqlx::query("DELETE FROM domain_accounts WHERE id = 'test-account-schema-probe'")
        .execute(&pool)
        .await
        .expect("failed to clean up domain_accounts probe row");

    pool.close().await;
}

/// Verifies that normalized non-empty account emails are unique
/// (case-insensitive) via the `domain_accounts_email_normalized_unique` partial
/// index, while NULL emails remain allowed and the case-insensitive lookup index
/// stays in place. TODO 2A supersedes the former Phase-B duplicate-email
/// tolerance for this narrow invariant only.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn domain_accounts_normalized_email_uniqueness_is_enforced() {
    let pool = connect_pool().await;
    run_migrations(&pool).await;

    // Clean up any prior probe rows
    sqlx::query(
        "DELETE FROM domain_accounts WHERE id IN (
            'test-email-dup-a', 'test-email-dup-b', 'test-email-null-a', 'test-email-null-b'
        )",
    )
    .execute(&pool)
    .await
    .expect("failed to clean up probe rows");

    // Insert first account with email
    sqlx::query(
        "INSERT INTO domain_accounts (id, kind, title, mode, radius_m, role, email, public_payload, private_payload)
         VALUES ('test-email-dup-a', 'ron', 'dup-a', 'ron', 0, 'gast', 'alpha@example.invalid', '{}', '{}')",
    )
    .execute(&pool)
    .await
    .expect("first insert with email must succeed");

    // Second account with the same normalized email (different case) must now be
    // rejected by the normalized unique index (TODO 2A).
    let dup_result = sqlx::query(
        "INSERT INTO domain_accounts (id, kind, title, mode, radius_m, role, email, public_payload, private_payload)
         VALUES ('test-email-dup-b', 'ron', 'dup-b', 'ron', 0, 'gast', 'ALPHA@example.invalid', '{}', '{}')",
    )
    .execute(&pool)
    .await;
    assert!(
        dup_result.is_err(),
        "duplicate normalized email must be rejected by domain_accounts_email_normalized_unique"
    );

    // Two accounts without email (NULL) must both succeed
    sqlx::query(
        "INSERT INTO domain_accounts (id, kind, title, mode, radius_m, role, public_payload, private_payload)
         VALUES ('test-email-null-a', 'ron', 'null-a', 'ron', 0, 'gast', '{}', '{}')",
    )
    .execute(&pool)
    .await
    .expect("first NULL-email insert must succeed");

    sqlx::query(
        "INSERT INTO domain_accounts (id, kind, title, mode, radius_m, role, public_payload, private_payload)
         VALUES ('test-email-null-b', 'ron', 'null-b', 'ron', 0, 'gast', '{}', '{}')",
    )
    .execute(&pool)
    .await
    .expect("second NULL-email insert must succeed");

    // Radius supports full u32 range via BIGINT + CHECK constraint.
    sqlx::query("DELETE FROM domain_accounts WHERE id = 'test-radius-u32-max'")
        .execute(&pool)
        .await
        .expect("pre-test cleanup of test-radius-u32-max failed");

    sqlx::query(
        "INSERT INTO domain_accounts (id, kind, title, mode, radius_m, role, public_payload, private_payload)
         VALUES ('test-radius-u32-max', 'ron', 'radius-max', 'ron', 4294967295, 'gast', '{}', '{}')",
    )
    .execute(&pool)
    .await
    .expect("u32::MAX radius_m must be accepted");

    let overflow_result = sqlx::query(
        "INSERT INTO domain_accounts (id, kind, title, mode, radius_m, role, public_payload, private_payload)
         VALUES ('test-radius-overflow', 'ron', 'radius-overflow', 'ron', 4294967296, 'gast', '{}', '{}')",
    )
    .execute(&pool)
    .await;

    assert!(
        overflow_result.is_err(),
        "radius_m above u32::MAX must violate check constraint"
    );

    // Clean up
    sqlx::query(
        "DELETE FROM domain_accounts WHERE id IN (
            'test-email-dup-a', 'test-email-dup-b', 'test-email-null-a', 'test-email-null-b',
            'test-radius-u32-max', 'test-radius-overflow'
        )",
    )
    .execute(&pool)
    .await
    .expect("failed to clean up probe rows");

    pool.close().await;
}

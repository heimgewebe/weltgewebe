//! Integration proof: SQLx → direct PostgreSQL → sessions CRUD (production path).
//!
//! This test is `#[ignore]` and requires a direct PostgreSQL connection.
//! Run with:
//!   PG_DIRECT_URL=postgres://welt:gewebe@localhost:5432/weltgewebe_proof \
//!     cargo test -p weltgewebe-api -- sqlx_postgres_direct --include-ignored
//!
//! Alternatively, DATABASE_URL is accepted as a fallback if PG_DIRECT_URL is not set:
//!   DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe_proof \
//!     cargo test -p weltgewebe-api -- sqlx_postgres_direct --include-ignored
//!
//! The test FAILS (panics) if neither PG_DIRECT_URL nor DATABASE_URL is set.
//! There is no silent skip -- absence of the required environment variable is a
//! configuration error for this proof harness.
//!
//! The URL MUST point directly to PostgreSQL, NOT to PgBouncer (port 6432).
//! The test asserts this explicitly: if the URL contains port 6432 the test panics.
//!
//! A Rust/Cargo test environment is required; a runtime host that only has the built
//! API binary is not enough to execute this proof harness.
//!
//! What this test proves when run successfully:
//! - `sqlx::PgPool` connects directly to PostgreSQL via DATABASE_URL / PG_DIRECT_URL.
//! - No `statement_cache_capacity(0)` override needed -- standard SQLx prepared
//!   statements work against a direct Postgres connection.
//! - INSERT / SELECT / UPDATE last_active / UPDATE verification / DELETE / COUNT on a
//!   sessions-column-compatible proof table succeed via SQLx.
//! - The PgBouncer path is explicitly NOT used (URL guard enforced).
//!
//! What is NOT proven here:
//! - `sqlx::migrate!` or `sqlx-cli` migration execution (separate proof step).
//! - Production `SessionStore` wiring (no `DbSessionStore` in this PR).
//! - PgBouncer compatibility (see `sqlx_pgbouncer_session_crud.rs` for that path).

use sqlx::postgres::{PgConnectOptions, PgPoolOptions};
use sqlx::Row;
use std::str::FromStr;
use uuid::Uuid;

/// Validates that `name` matches the expected proof-table pattern
/// `sqlx_pg_direct_proof_` followed by exactly 32 lowercase hex characters.
///
/// Panics if the pattern does not match — this is an internal guard to prevent
/// accidental misuse of [`create_proof_table`] / [`drop_proof_table`] with
/// arbitrary table names.
fn assert_proof_table_name(name: &str) {
    let prefix = "sqlx_pg_direct_proof_";
    assert!(
        name.starts_with(prefix)
            && name.len() == prefix.len() + 32
            && name[prefix.len()..].chars().all(|c| c.is_ascii_hexdigit()),
        "proof table name does not match expected pattern \
         'sqlx_pg_direct_proof_<32hex>': {name}"
    );
}

/// Asserts that `url` does not contain port 6432 (PgBouncer's default port in the
/// dev stack). Panics with a clear message if the check fails.
///
/// This guard ensures the test is actually exercising the direct-PostgreSQL proof
/// path and has not accidentally been pointed at PgBouncer.
fn assert_not_pgbouncer_url(url: &str) {
    assert!(
        !url.contains(":6432"),
        "PG_DIRECT_URL / DATABASE_URL must point to direct PostgreSQL, not PgBouncer \
         (port 6432 detected in URL). Use port 5432 or the correct direct-Postgres port."
    );
}

/// Creates a sessions-column-compatible proof table with a unique, prefixed name.
///
/// Uses a `sqlx_pg_direct_proof_` prefix followed by a UUID (hex, no dashes) to avoid
/// any collision with or mutation of the real `sessions` table from
/// `apps/api/migrations/20260428000000_create_sessions.up.sql`.
///
/// Column structure mirrors the migration's table definition (indices are intentionally
/// omitted — this is a CRUD-path fixture, not a migration proof).
///
/// The caller is responsible for dropping the table via [`drop_proof_table`] once done.
async fn create_proof_table(pool: &sqlx::PgPool, table_name: &str) {
    assert_proof_table_name(table_name);
    sqlx::query(&format!(
        "CREATE TABLE {} (\
            id          TEXT        PRIMARY KEY,\
            account_id  TEXT        NOT NULL,\
            device_id   TEXT        NOT NULL,\
            created_at  TIMESTAMPTZ NOT NULL,\
            last_active TIMESTAMPTZ NOT NULL,\
            expires_at  TIMESTAMPTZ NOT NULL\
        )",
        table_name
    ))
    .execute(pool)
    .await
    .expect("failed to create proof table");
}

/// Drops the sessions-column-compatible proof table created by [`create_proof_table`].
async fn drop_proof_table(pool: &sqlx::PgPool, table_name: &str) {
    assert_proof_table_name(table_name);
    sqlx::query(&format!("DROP TABLE IF EXISTS {}", table_name))
        .execute(pool)
        .await
        .expect("failed to drop proof table");
}

/// Runs the full CRUD proof sequence against the isolated sessions-column-compatible
/// proof table `table_name`.
///
/// Returns `Ok(())` when all SQLx operations succeed and all row-count checks pass.
/// Returns `Err(...)` on any SQLx error so the caller can always clean up the table.
///
/// Note: `assert!` / `assert_eq!` panics within this function will bypass cleanup; the
/// UUID-named table is left behind in that (unlikely) case, but causes no collision.
async fn run_crud_proof(
    pool: &sqlx::PgPool,
    table_name: &str,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let id = Uuid::new_v4().to_string();
    let account_id = format!("proof-account-{}", Uuid::new_v4());
    let device_id = format!("proof-device-{}", Uuid::new_v4());

    // --- INSERT (timestamps SQL-side; no chrono feature required) ---
    let insert_result = sqlx::query(&format!(
        "INSERT INTO {} \
             (id, account_id, device_id, created_at, last_active, expires_at) \
         VALUES \
             ($1, $2, $3, NOW(), NOW(), NOW() + INTERVAL '24 hours')",
        table_name
    ))
    .bind(&id)
    .bind(&account_id)
    .bind(&device_id)
    .execute(pool)
    .await?;

    assert_eq!(
        insert_result.rows_affected(),
        1,
        "INSERT must affect exactly one row"
    );

    // --- SELECT — string field round-trip ---
    let row = sqlx::query(&format!(
        "SELECT id, account_id, device_id FROM {} WHERE id = $1",
        table_name
    ))
    .bind(&id)
    .fetch_one(pool)
    .await?;

    assert_eq!(row.get::<String, _>("id"), id, "id must round-trip");
    assert_eq!(
        row.get::<String, _>("account_id"),
        account_id,
        "account_id must round-trip"
    );
    assert_eq!(
        row.get::<String, _>("device_id"),
        device_id,
        "device_id must round-trip"
    );

    // --- UPDATE last_active (mirrors SessionStore::touch; SQL-side timestamp) ---
    let update_result = sqlx::query(&format!(
        "UPDATE {} SET last_active = NOW() + INTERVAL '10 minutes' WHERE id = $1",
        table_name
    ))
    .bind(&id)
    .execute(pool)
    .await?;

    assert_eq!(
        update_result.rows_affected(),
        1,
        "UPDATE must affect exactly one row"
    );

    // --- Verify UPDATE: last_active must now be ahead of NOW() ---
    let is_future: bool = sqlx::query_scalar(&format!(
        "SELECT last_active > NOW() FROM {} WHERE id = $1",
        table_name
    ))
    .bind(&id)
    .fetch_one(pool)
    .await?;

    assert!(
        is_future,
        "last_active must be in the future after touch-UPDATE"
    );

    // --- DELETE ---
    let delete_result = sqlx::query(&format!("DELETE FROM {} WHERE id = $1", table_name))
        .bind(&id)
        .execute(pool)
        .await?;

    assert_eq!(
        delete_result.rows_affected(),
        1,
        "DELETE must remove exactly one row"
    );

    // --- COUNT after DELETE — confirm gone ---
    let count: i64 = sqlx::query_scalar(&format!(
        "SELECT COUNT(*) FROM {} WHERE id = $1",
        table_name
    ))
    .bind(&id)
    .fetch_one(pool)
    .await?;

    assert_eq!(count, 0, "session must be absent after DELETE");

    Ok(())
}

/// Proof: SQLx CRUD against a sessions-column-compatible proof table via direct
/// PostgreSQL connection (production path per ADR-0007).
///
/// Covers: direct connection (no PgBouncer), INSERT, SELECT (string round-trip),
/// UPDATE (last_active), post-UPDATE boolean verification, DELETE, post-DELETE COUNT.
///
/// No `statement_cache_capacity(0)` override -- standard SQLx prepared-statement
/// behaviour is exercised, which is the expected behaviour for direct Postgres.
#[tokio::test]
#[ignore = "requires PG_DIRECT_URL or DATABASE_URL pointing to direct PostgreSQL (not PgBouncer)"]
async fn sqlx_postgres_direct_session_crud() {
    // PG_DIRECT_URL takes precedence; DATABASE_URL is the fallback.
    // Neither being set is a hard failure -- not a silent skip.
    let direct_url = std::env::var("PG_DIRECT_URL")
        .or_else(|_| std::env::var("DATABASE_URL"))
        .expect(
            "PG_DIRECT_URL or DATABASE_URL must be set to run this proof test \
             -- point it at direct PostgreSQL (port 5432), e.g. \
             postgres://welt:gewebe@localhost:5432/weltgewebe_proof",
        );

    // Guard: reject any URL that targets PgBouncer port 6432.
    assert_not_pgbouncer_url(&direct_url);

    let connect_opts = PgConnectOptions::from_str(&direct_url)
        .expect("PG_DIRECT_URL / DATABASE_URL must be a valid postgres connection string");

    // No statement_cache_capacity(0): direct Postgres supports prepared statements
    // natively. Standard SQLx behaviour is the production path.
    let pool = PgPoolOptions::new()
        .max_connections(2)
        .connect_with(connect_opts)
        .await
        .expect(
            "failed to connect to direct PostgreSQL -- is Postgres running and \
             is the URL pointing to port 5432 (not PgBouncer at 6432)?",
        );

    // Isolated table: never touches the real `sessions` table.
    let table_name = format!(
        "sqlx_pg_direct_proof_{}",
        Uuid::new_v4().to_string().replace('-', "")
    );
    assert_proof_table_name(&table_name); // guard before any SQL use
    create_proof_table(&pool, &table_name).await;

    // Run CRUD via Result-returning fn so drop_proof_table always executes.
    let crud_result = run_crud_proof(&pool, &table_name).await;

    // Always clean up -- even when CRUD failed.
    drop_proof_table(&pool, &table_name).await;
    pool.close().await;

    // Propagate any CRUD failure after cleanup.
    crud_result.expect("CRUD proof failed -- see sqlx error above");
}

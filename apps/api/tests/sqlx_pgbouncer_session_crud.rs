//! Integration proof: SQLx → PgBouncer (transaction mode) → PostgreSQL → sessions CRUD.
//!
//! This test is `#[ignore]` and requires an external stack.
//! Run with:
//!   PGBOUNCER_URL=postgres://welt:gewebe@localhost:6432/weltgewebe \
//!     cargo test -p weltgewebe-api -- sqlx_pgbouncer --include-ignored
//!
//! PGBOUNCER_URL must point to PgBouncer, not directly to Postgres.
//! PgBouncer must be configured with POOL_MODE=transaction.
//! The proof is only valid when run against that stack — see proof report.
//!
//! What this test is intended to prove when it completes successfully against PgBouncer:
//! - sqlx::PgPool connects through PgBouncer in transaction pool mode.
//! - PgConnectOptions::statement_cache_capacity(0) neutralises the prepared-statement
//!   incompatibility with PgBouncer transaction mode.
//! - INSERT / SELECT / UPDATE / DELETE on a sessions-column-compatible proof table
//!   succeed via SQLx.
//!
//! What is NOT proven here:
//! - sqlx::migrate! or sqlx-cli migration execution (separate proof step).
//! - Production SessionStore wiring (no DbSessionStore in this PR).

use sqlx::postgres::{PgConnectOptions, PgPoolOptions};
use sqlx::Row;
use std::str::FromStr;
use uuid::Uuid;

/// Validates that `name` matches the expected proof-table pattern
/// `sqlx_pgbouncer_proof_` followed by exactly 32 lowercase hex characters.
///
/// Panics if the pattern does not match — this is an internal guard to prevent
/// accidental misuse of [`create_proof_table`] / [`drop_proof_table`] with
/// arbitrary table names.
fn assert_proof_table_name(name: &str) {
    let prefix = "sqlx_pgbouncer_proof_";
    assert!(
        name.starts_with(prefix)
            && name.len() == prefix.len() + 32
            && name[prefix.len()..].chars().all(|c| c.is_ascii_hexdigit()),
        "proof table name does not match expected pattern \
         'sqlx_pgbouncer_proof_<32hex>': {name}"
    );
}

/// Creates a sessions-column-compatible proof table with a unique, prefixed name.
///
/// Uses a `sqlx_pgbouncer_proof_` prefix followed by a UUID (hex, no dashes) to avoid
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
/// Returns `Err(…)` on any SQLx error so the caller can always clean up the table.
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

/// Proof: SQLx CRUD against a sessions-column-compatible proof table through PgBouncer
/// transaction mode.
///
/// Covers: connection, INSERT, SELECT (string round-trip), UPDATE (last_active),
/// post-UPDATE boolean verification, DELETE, post-DELETE COUNT.
///
/// A sessions-column-compatible proof table (`sqlx_pgbouncer_proof_<uuid>`) is created
/// for each run so the real `sessions` table is never touched. CRUD runs via
/// [`run_crud_proof`], which returns a `Result` so the table is always dropped before
/// the test outcome is finalised — even when SQLx returns an error.
///
/// Timestamps are generated SQL-side (NOW(), INTERVAL) to avoid binding
/// `chrono::DateTime` values, which would require the sqlx `"chrono"` feature and the
/// transitive dependency set it pulls in (sqlx-mysql, sqlx-sqlite, rsa, etc.).
///
/// `statement_cache_capacity(0)` is set explicitly: it prevents SQLx from caching
/// prepared-statement handles across pool connections, which is the root cause of
/// "prepared statement does not exist" errors under PgBouncer transaction mode.
#[tokio::test]
#[ignore = "requires PGBOUNCER_URL pointing to PgBouncer in transaction mode"]
async fn sqlx_pgbouncer_session_crud_through_transaction_mode() {
    let pgbouncer_url = std::env::var("PGBOUNCER_URL").expect(
        "PGBOUNCER_URL must be set to run this proof test \
         — point it at PgBouncer in transaction mode, e.g. \
         postgres://welt:gewebe@localhost:6432/weltgewebe",
    );

    let connect_opts = PgConnectOptions::from_str(&pgbouncer_url)
        .expect("PGBOUNCER_URL must be a valid postgres connection string")
        .statement_cache_capacity(0);

    let pool = PgPoolOptions::new()
        .max_connections(2)
        .connect_with(connect_opts)
        .await
        .expect("failed to connect via PGBOUNCER_URL — is the stack running?");

    // Isolated table: never touches the real `sessions` table.
    let table_name = format!(
        "sqlx_pgbouncer_proof_{}",
        Uuid::new_v4().to_string().replace('-', "")
    );
    assert_proof_table_name(&table_name); // guard before any SQL use
    create_proof_table(&pool, &table_name).await;

    // Run CRUD via Result-returning fn so drop_proof_table always executes.
    let crud_result = run_crud_proof(&pool, &table_name).await;

    // Always clean up — even when CRUD failed.
    drop_proof_table(&pool, &table_name).await;
    pool.close().await;

    // Propagate any CRUD failure after cleanup.
    crud_result.expect("CRUD proof failed — see sqlx error above");
}

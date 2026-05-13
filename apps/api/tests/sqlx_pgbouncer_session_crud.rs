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
//! What is proven:
//! - sqlx::PgPool connects through PgBouncer in transaction pool mode.
//! - PgConnectOptions::statement_cache_capacity(0) neutralises the prepared-statement
//!   incompatibility with PgBouncer transaction mode.
//! - INSERT / SELECT / UPDATE / DELETE on the sessions table succeed via SQLx.
//!
//! What is NOT proven here:
//! - sqlx::migrate! or sqlx-cli migration execution (separate proof step).
//! - Production SessionStore wiring (no DbSessionStore in this PR).

use sqlx::postgres::{PgConnectOptions, PgPoolOptions};
use sqlx::Row;
use std::str::FromStr;
use uuid::Uuid;

/// Idempotent test-fixture setup.
///
/// Creates the sessions table using the schema from
/// `apps/api/migrations/20260428000000_create_sessions.up.sql` — with `IF NOT EXISTS`
/// so the function is safe to call against a DB that already has the table.
///
/// This is a **test fixture**, not a sqlx migration proof. It exists so the proof test
/// can run against a fresh DB without requiring sqlx-cli or a prior `just db-migrate`.
/// The inline schema must be kept in sync with the migration file manually.
async fn ensure_sessions_table(pool: &sqlx::PgPool) {
    sqlx::query(
        "CREATE TABLE IF NOT EXISTS sessions (\
            id          TEXT        PRIMARY KEY,\
            account_id  TEXT        NOT NULL,\
            device_id   TEXT        NOT NULL,\
            created_at  TIMESTAMPTZ NOT NULL,\
            last_active TIMESTAMPTZ NOT NULL,\
            expires_at  TIMESTAMPTZ NOT NULL\
        )",
    )
    .execute(pool)
    .await
    .expect("failed to ensure sessions table exists");
}

/// Proof: SQLx CRUD against the sessions table through PgBouncer transaction mode.
///
/// Covers: connection, INSERT, SELECT (string round-trip), UPDATE (last_active),
/// post-UPDATE boolean verification, DELETE, post-DELETE COUNT.
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
    let pgbouncer_url = match std::env::var("PGBOUNCER_URL") {
        Ok(url) => url,
        Err(_) => {
            eprintln!("PGBOUNCER_URL not set — skipping SQLx/PgBouncer proof test");
            return;
        }
    };

    let connect_opts = PgConnectOptions::from_str(&pgbouncer_url)
        .expect("PGBOUNCER_URL must be a valid postgres connection string")
        .statement_cache_capacity(0);

    let pool = PgPoolOptions::new()
        .max_connections(2)
        .connect_with(connect_opts)
        .await
        .expect("failed to connect via PGBOUNCER_URL — is the stack running?");

    ensure_sessions_table(&pool).await;

    let id = Uuid::new_v4().to_string();
    let account_id = format!("proof-account-{}", Uuid::new_v4());
    let device_id = format!("proof-device-{}", Uuid::new_v4());

    // --- INSERT (timestamps SQL-side; no chrono feature required) ---
    let insert_result = sqlx::query(
        "INSERT INTO sessions \
             (id, account_id, device_id, created_at, last_active, expires_at) \
         VALUES \
             ($1, $2, $3, NOW(), NOW(), NOW() + INTERVAL '24 hours')",
    )
    .bind(&id)
    .bind(&account_id)
    .bind(&device_id)
    .execute(&pool)
    .await
    .expect("INSERT into sessions failed");

    assert_eq!(
        insert_result.rows_affected(),
        1,
        "INSERT must affect exactly one row"
    );

    // --- SELECT — string field round-trip ---
    let row = sqlx::query("SELECT id, account_id, device_id FROM sessions WHERE id = $1")
        .bind(&id)
        .fetch_one(&pool)
        .await
        .expect("SELECT from sessions failed");

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
    let update_result = sqlx::query(
        "UPDATE sessions SET last_active = NOW() + INTERVAL '10 minutes' WHERE id = $1",
    )
    .bind(&id)
    .execute(&pool)
    .await
    .expect("UPDATE on sessions failed");

    assert_eq!(
        update_result.rows_affected(),
        1,
        "UPDATE must affect exactly one row"
    );

    // --- Verify UPDATE: last_active must now be ahead of NOW() ---
    let is_future: bool =
        sqlx::query_scalar("SELECT last_active > NOW() FROM sessions WHERE id = $1")
            .bind(&id)
            .fetch_one(&pool)
            .await
            .expect("SELECT after UPDATE failed");

    assert!(
        is_future,
        "last_active must be in the future after touch-UPDATE"
    );

    // --- DELETE ---
    let delete_result = sqlx::query("DELETE FROM sessions WHERE id = $1")
        .bind(&id)
        .execute(&pool)
        .await
        .expect("DELETE from sessions failed");

    assert_eq!(
        delete_result.rows_affected(),
        1,
        "DELETE must remove exactly one row"
    );

    // --- COUNT after DELETE — confirm gone ---
    let count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM sessions WHERE id = $1")
        .bind(&id)
        .fetch_one(&pool)
        .await
        .expect("COUNT after DELETE failed");

    assert_eq!(count, 0, "session must be absent after DELETE");

    pool.close().await;
}

//! Integration test: DbSessionStore persistence path with PostgreSQL backend.
//!
//! This test validates that `DbSessionStore` correctly implements the `SessionOps` trait
//! when backed by PostgreSQL. It covers:
//! - Store recreation (session persists across `DbSessionStore` instances)
//! - Expiry filtering (expired sessions are excluded from results)
//! - list_by_account (returns only non-expired sessions for target account)
//! - delete_by_device (removes all sessions for account+device pair)
//! - delete_all_by_account (removes all sessions for target account)
//! - touch (updates last_active; 5-minute debounce respected)
//!
//! Run with:
//!   DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
//!     cargo test -p weltgewebe-api -- db_session_store_persistence --include-ignored
//!
//! The test is `#[ignore]` and requires DATABASE_URL to be set pointing directly
//! to PostgreSQL (not PgBouncer). If DATABASE_URL is unset, the test panics.

use sqlx::postgres::PgPoolOptions;
use std::str::FromStr;
use uuid::Uuid;

use weltgewebe_api::auth::session::SessionOps;
use weltgewebe_api::auth::session_db::DbSessionStore;

/// Helper: creates a temporary sessions table for testing (for potential future use).
#[allow(dead_code)]
async fn setup_test_sessions_table(pool: &sqlx::PgPool) -> String {
    let uuid_part = Uuid::new_v4().to_string().replace('-', "");
    let short_id = &uuid_part[0..8];
    let table_name = format!("test_sessions_{}", short_id);

    sqlx::query(&format!(
        "CREATE TABLE {} (
            id          TEXT        PRIMARY KEY,
            account_id  TEXT        NOT NULL,
            device_id   TEXT        NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL,
            last_active TIMESTAMPTZ NOT NULL,
            expires_at  TIMESTAMPTZ NOT NULL
        )",
        table_name
    ))
    .execute(pool)
    .await
    .expect("failed to create test sessions table");

    table_name
}

/// Helper: drops test table (for potential future use).
#[allow(dead_code)]
async fn teardown_test_sessions_table(pool: &sqlx::PgPool, table_name: &str) {
    sqlx::query(&format!("DROP TABLE IF EXISTS {}", table_name))
        .execute(pool)
        .await
        .expect("failed to drop test sessions table");
}

/// Proof: DbSessionStore can be recreated with a new pool instance
/// and sessions persisted in the previous instance are retrieved.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_session_store_persistence() {
    let database_url = std::env::var("DATABASE_URL").expect(
        "DATABASE_URL must be set to run this proof test -- \
         point it at direct PostgreSQL (port 5432), e.g. \
         postgres://welt:gewebe@localhost:5432/weltgewebe",
    );

    assert!(
        !database_url.contains(":6432"),
        "DATABASE_URL must point to direct PostgreSQL (port 5432), not PgBouncer (port 6432)"
    );

    let connect_opts = sqlx::postgres::PgConnectOptions::from_str(&database_url)
        .expect("DATABASE_URL must be a valid postgres connection string");

    // Pool 1: Insert session
    let pool1 = PgPoolOptions::new()
        .max_connections(2)
        .connect_with(connect_opts.clone())
        .await
        .expect("failed to connect to PostgreSQL");

    let account_id = format!("test-account-{}", Uuid::new_v4());
    let device_id = format!("test-device-{}", Uuid::new_v4());

    let store1 = DbSessionStore::new(pool1.clone());
    let session = store1
        .create(account_id.clone(), Some(device_id.clone()))
        .await
        .expect("failed to create session");

    let session_id = session.id.clone();
    println!("Created session: {}", session_id);

    // Pool 2: Verify session persists
    let connect_opts2 = sqlx::postgres::PgConnectOptions::from_str(&database_url)
        .expect("DATABASE_URL must be a valid postgres connection string");

    let pool2 = PgPoolOptions::new()
        .max_connections(2)
        .connect_with(connect_opts2)
        .await
        .expect("failed to connect to PostgreSQL (pool 2)");

    let store2 = DbSessionStore::new(pool2.clone());
    let retrieved = store2
        .get(&session_id)
        .await
        .expect("failed to retrieve session")
        .expect("session must exist after recreation");

    assert_eq!(
        retrieved.id, session_id,
        "recreated store must retrieve persisted session"
    );
    assert_eq!(retrieved.account_id, account_id, "account_id must match");
    assert_eq!(retrieved.device_id, device_id, "device_id must match");

    // Cleanup
    store2
        .delete(&session_id)
        .await
        .expect("failed to delete session");

    pool1.close().await;
    pool2.close().await;

    println!("✓ Store persistence proof passed");
}

/// Proof: DbSessionStore correctly filters expired sessions in list_by_account.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_session_store_expiry_filter() {
    let database_url = std::env::var("DATABASE_URL").expect("DATABASE_URL must be set");

    assert!(
        !database_url.contains(":6432"),
        "DATABASE_URL must point to direct PostgreSQL (port 5432)"
    );

    let connect_opts = sqlx::postgres::PgConnectOptions::from_str(&database_url)
        .expect("DATABASE_URL must be a valid postgres connection string");

    let pool = PgPoolOptions::new()
        .max_connections(2)
        .connect_with(connect_opts)
        .await
        .expect("failed to connect to PostgreSQL");

    let account_id = format!("test-account-{}", Uuid::new_v4());
    let store = DbSessionStore::new(pool.clone());

    // Create session (default 24h expiry → not expired)
    let session1 = store
        .create(account_id.clone(), None)
        .await
        .expect("failed to create session 1");

    // Create expired session by inserting directly
    let expired_id = Uuid::new_v4().to_string();
    let now = chrono::Utc::now();
    let past = now - chrono::Duration::hours(1);

    sqlx::query(
        "INSERT INTO sessions (id, account_id, device_id, created_at, last_active, expires_at)
         VALUES ($1, $2, $3, $4, $5, $6)",
    )
    .bind(&expired_id)
    .bind(&account_id)
    .bind("test-device")
    .bind(past)
    .bind(past)
    .bind(past)
    .execute(&pool)
    .await
    .expect("failed to insert expired session");

    // list_by_account must NOT return expired session
    let sessions = store
        .list_by_account(&account_id)
        .await
        .expect("failed to list sessions");

    assert_eq!(
        sessions.len(),
        1,
        "list_by_account must exclude expired sessions (expected 1, got {})",
        sessions.len()
    );
    assert_eq!(
        sessions[0].id, session1.id,
        "only non-expired session should be returned"
    );

    // Cleanup
    store
        .delete(&session1.id)
        .await
        .expect("failed to delete session 1");
    store
        .delete(&expired_id)
        .await
        .expect("failed to delete expired session");

    pool.close().await;

    println!("✓ Expiry filter proof passed");
}

/// Proof: delete_by_device removes all sessions for the target account+device pair.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_session_store_delete_by_device() {
    let database_url = std::env::var("DATABASE_URL").expect("DATABASE_URL must be set");

    let connect_opts = sqlx::postgres::PgConnectOptions::from_str(&database_url)
        .expect("DATABASE_URL must be a valid postgres connection string");

    let pool = PgPoolOptions::new()
        .max_connections(2)
        .connect_with(connect_opts)
        .await
        .expect("failed to connect to PostgreSQL");

    let account_id = format!("test-account-{}", Uuid::new_v4());
    let device1 = format!("device-{}", Uuid::new_v4());
    let device2 = format!("device-{}", Uuid::new_v4());

    let store = DbSessionStore::new(pool.clone());

    // Create 2 sessions for account+device1
    let session1a = store
        .create(account_id.clone(), Some(device1.clone()))
        .await
        .expect("failed to create session 1a");

    let session1b = store
        .create(account_id.clone(), Some(device1.clone()))
        .await
        .expect("failed to create session 1b");

    // Create 1 session for account+device2
    let session2 = store
        .create(account_id.clone(), Some(device2.clone()))
        .await
        .expect("failed to create session 2");

    // Delete all sessions for account+device1
    store
        .delete_by_device(&account_id, &device1)
        .await
        .expect("failed to delete_by_device");

    // Verify: device1 sessions are gone
    let s1a_after = store
        .get(&session1a.id)
        .await
        .expect("failed to get session 1a");
    let s1b_after = store
        .get(&session1b.id)
        .await
        .expect("failed to get session 1b");

    assert!(s1a_after.is_none(), "session 1a must be deleted");
    assert!(s1b_after.is_none(), "session 1b must be deleted");

    // Verify: device2 session still exists
    let s2_after = store
        .get(&session2.id)
        .await
        .expect("failed to get session 2")
        .expect("session 2 must still exist");

    assert_eq!(
        s2_after.id, session2.id,
        "session 2 (different device) must not be affected"
    );

    // Cleanup
    store
        .delete(&session2.id)
        .await
        .expect("failed to delete session 2");

    pool.close().await;

    println!("✓ delete_by_device proof passed");
}

/// Proof: delete_all_by_account removes all sessions for the target account.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_session_store_delete_all_by_account() {
    let database_url = std::env::var("DATABASE_URL").expect("DATABASE_URL must be set");

    let connect_opts = sqlx::postgres::PgConnectOptions::from_str(&database_url)
        .expect("DATABASE_URL must be a valid postgres connection string");

    let pool = PgPoolOptions::new()
        .max_connections(2)
        .connect_with(connect_opts)
        .await
        .expect("failed to connect to PostgreSQL");

    let account1 = format!("test-account-{}", Uuid::new_v4());
    let account2 = format!("test-account-{}", Uuid::new_v4());

    let store = DbSessionStore::new(pool.clone());

    // Create 3 sessions for account1
    let s1_1 = store
        .create(account1.clone(), None)
        .await
        .expect("failed to create session");
    let s1_2 = store
        .create(account1.clone(), None)
        .await
        .expect("failed to create session");
    let s1_3 = store
        .create(account1.clone(), None)
        .await
        .expect("failed to create session");

    // Create 1 session for account2
    let s2_1 = store
        .create(account2.clone(), None)
        .await
        .expect("failed to create session");

    // Delete all sessions for account1
    store
        .delete_all_by_account(&account1)
        .await
        .expect("failed to delete_all_by_account");

    // Verify: all account1 sessions are gone
    assert!(
        store.get(&s1_1.id).await.expect("failed to get").is_none(),
        "session 1.1 must be deleted"
    );
    assert!(
        store.get(&s1_2.id).await.expect("failed to get").is_none(),
        "session 1.2 must be deleted"
    );
    assert!(
        store.get(&s1_3.id).await.expect("failed to get").is_none(),
        "session 1.3 must be deleted"
    );

    // Verify: account2 session still exists
    let s2_check = store
        .get(&s2_1.id)
        .await
        .expect("failed to get")
        .expect("session 2.1 must still exist");

    assert_eq!(
        s2_check.id, s2_1.id,
        "account2 session must not be affected"
    );

    // Cleanup
    store
        .delete(&s2_1.id)
        .await
        .expect("failed to delete session 2.1");

    pool.close().await;

    println!("✓ delete_all_by_account proof passed");
}

/// Proof: touch updates last_active with 5-minute debounce.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_session_store_touch() {
    let database_url = std::env::var("DATABASE_URL").expect("DATABASE_URL must be set");

    let connect_opts = sqlx::postgres::PgConnectOptions::from_str(&database_url)
        .expect("DATABASE_URL must be a valid postgres connection string");

    let pool = PgPoolOptions::new()
        .max_connections(2)
        .connect_with(connect_opts)
        .await
        .expect("failed to connect to PostgreSQL");

    let account_id = format!("test-account-{}", Uuid::new_v4());
    let store = DbSessionStore::new(pool.clone());

    // Create session
    let session = store
        .create(account_id.clone(), None)
        .await
        .expect("failed to create session");

    let original_last_active = session.last_active;

    // Touch immediately (within 5 minutes) → should NOT update
    store.touch(&session.id).await.expect("failed to touch");

    let after_immediate = store
        .get(&session.id)
        .await
        .expect("failed to get")
        .expect("session must exist");

    assert_eq!(
        after_immediate.last_active, original_last_active,
        "touch within 5 minutes should not update last_active"
    );

    // Manually set last_active to 10 minutes ago
    let ten_min_ago = chrono::Utc::now() - chrono::Duration::minutes(10);
    sqlx::query("UPDATE sessions SET last_active = $1 WHERE id = $2")
        .bind(ten_min_ago)
        .bind(&session.id)
        .execute(&pool)
        .await
        .expect("failed to update last_active for test");

    // Touch again (now 10 min old → debounce triggered) → should update
    store.touch(&session.id).await.expect("failed to touch");

    let after_debounce = store
        .get(&session.id)
        .await
        .expect("failed to get")
        .expect("session must exist");

    assert!(
        after_debounce.last_active > ten_min_ago,
        "touch after 5+ minute gap should update last_active"
    );

    // Cleanup
    store
        .delete(&session.id)
        .await
        .expect("failed to delete session");

    pool.close().await;

    println!("✓ touch debounce proof passed");
}

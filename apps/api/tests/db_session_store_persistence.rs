//! Integration proof: DbSessionStore with direct PostgreSQL persistence.
//!
//! Run with:
//!   DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
//!     cargo test --locked -p weltgewebe-api --test db_session_store_persistence -- --include-ignored
//!
//! Notes:
//! - Tests are ignored by default to keep offline paths green.
//! - DATABASE_URL must point to direct PostgreSQL (not PgBouncer at :6432).

use std::{path::PathBuf, str::FromStr};

use sqlx::postgres::{PgConnectOptions, PgPoolOptions};
use uuid::Uuid;

use weltgewebe_api::auth::session::SessionOps;
use weltgewebe_api::auth::session_db::DbSessionStore;

fn direct_database_url() -> String {
    let url = std::env::var("DATABASE_URL").expect(
        "DATABASE_URL must be set to run db_session_store_persistence tests; \
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

    let pool = PgPoolOptions::new()
        .max_connections(2)
        .connect_with(connect_opts)
        .await
        .expect("failed to connect to direct PostgreSQL");

    ensure_migrations(&pool).await;

    pool
}

fn unique_account_id(test_name: &str) -> String {
    format!("db-session-store-{test_name}-{}", Uuid::new_v4())
}

async fn cleanup_account(pool: &sqlx::PgPool, account_id: &str) {
    sqlx::query("DELETE FROM sessions WHERE account_id = $1")
        .bind(account_id)
        .execute(pool)
        .await
        .expect("failed to cleanup account sessions");
}

async fn ensure_migrations(pool: &sqlx::PgPool) {
    let migrations_dir: PathBuf = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("migrations");

    let migrator = sqlx::migrate::Migrator::new(migrations_dir)
        .await
        .expect("failed to load migrations");

    migrator.run(pool).await.expect("failed to run migrations");
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_session_store_persistence() {
    let pool1 = connect_pool().await;
    let pool2 = connect_pool().await;
    let account_id = unique_account_id("persistence");
    let device_id = format!("device-{}", Uuid::new_v4());

    cleanup_account(&pool1, &account_id).await;

    let store1 = DbSessionStore::new(pool1.clone());
    let created = store1
        .create(account_id.clone(), Some(device_id.clone()))
        .await
        .expect("create failed");

    let store2 = DbSessionStore::new(pool2.clone());
    let retrieved = store2
        .get(&created.id)
        .await
        .expect("get failed")
        .expect("session should persist across store recreation");

    assert_eq!(retrieved.id, created.id);
    assert_eq!(retrieved.account_id, account_id);
    assert_eq!(retrieved.device_id, device_id);

    cleanup_account(&pool2, &account_id).await;
    pool1.close().await;
    pool2.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_session_store_expiry_filter() {
    let pool = connect_pool().await;
    let account_id = unique_account_id("expiry");
    let store = DbSessionStore::new(pool.clone());

    cleanup_account(&pool, &account_id).await;

    let live = store
        .create(account_id.clone(), None)
        .await
        .expect("create live session failed");

    let expired_id = Uuid::new_v4().to_string();
    sqlx::query(
        "INSERT INTO sessions (id, account_id, device_id, created_at, last_active, expires_at)
         VALUES ($1, $2, $3, NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 hours', NOW() - INTERVAL '1 hours')",
    )
    .bind(&expired_id)
    .bind(&account_id)
    .bind(format!("expired-device-{}", Uuid::new_v4()))
    .execute(&pool)
    .await
    .expect("insert expired session failed");

    let sessions = store
        .list_by_account(&account_id)
        .await
        .expect("list_by_account failed");

    assert_eq!(sessions.len(), 1, "expired sessions must be excluded");
    assert_eq!(sessions[0].id, live.id);

    cleanup_account(&pool, &account_id).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_session_store_list_by_account() {
    let pool = connect_pool().await;
    let target_account = unique_account_id("list-target");
    let other_account = unique_account_id("list-other");
    let store = DbSessionStore::new(pool.clone());

    cleanup_account(&pool, &target_account).await;
    cleanup_account(&pool, &other_account).await;

    let target_a = store
        .create(target_account.clone(), None)
        .await
        .expect("create target session a failed");
    let target_b = store
        .create(target_account.clone(), None)
        .await
        .expect("create target session b failed");
    let _other = store
        .create(other_account.clone(), None)
        .await
        .expect("create other account session failed");

    let mut ids: Vec<String> = store
        .list_by_account(&target_account)
        .await
        .expect("list_by_account failed")
        .into_iter()
        .map(|s| s.id)
        .collect();
    ids.sort();

    let mut expected = vec![target_a.id, target_b.id];
    expected.sort();

    assert_eq!(ids, expected, "must return only target account sessions");

    cleanup_account(&pool, &target_account).await;
    cleanup_account(&pool, &other_account).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_session_store_delete_by_device() {
    let pool = connect_pool().await;
    let account_id = unique_account_id("delete-device");
    let device_a = format!("device-a-{}", Uuid::new_v4());
    let device_b = format!("device-b-{}", Uuid::new_v4());
    let store = DbSessionStore::new(pool.clone());

    cleanup_account(&pool, &account_id).await;

    let a1 = store
        .create(account_id.clone(), Some(device_a.clone()))
        .await
        .expect("create a1 failed");
    let a2 = store
        .create(account_id.clone(), Some(device_a.clone()))
        .await
        .expect("create a2 failed");
    let b1 = store
        .create(account_id.clone(), Some(device_b.clone()))
        .await
        .expect("create b1 failed");

    store
        .delete_by_device(&account_id, &device_a)
        .await
        .expect("delete_by_device failed");

    assert!(store.get(&a1.id).await.expect("get a1 failed").is_none());
    assert!(store.get(&a2.id).await.expect("get a2 failed").is_none());
    assert!(store.get(&b1.id).await.expect("get b1 failed").is_some());

    cleanup_account(&pool, &account_id).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_session_store_delete_all_by_account() {
    let pool = connect_pool().await;
    let target_account = unique_account_id("delete-all-target");
    let other_account = unique_account_id("delete-all-other");
    let store = DbSessionStore::new(pool.clone());

    cleanup_account(&pool, &target_account).await;
    cleanup_account(&pool, &other_account).await;

    let t1 = store
        .create(target_account.clone(), None)
        .await
        .expect("create t1 failed");
    let t2 = store
        .create(target_account.clone(), None)
        .await
        .expect("create t2 failed");
    let o1 = store
        .create(other_account.clone(), None)
        .await
        .expect("create o1 failed");

    store
        .delete_all_by_account(&target_account)
        .await
        .expect("delete_all_by_account failed");

    assert!(store.get(&t1.id).await.expect("get t1 failed").is_none());
    assert!(store.get(&t2.id).await.expect("get t2 failed").is_none());
    assert!(store.get(&o1.id).await.expect("get o1 failed").is_some());

    cleanup_account(&pool, &target_account).await;
    cleanup_account(&pool, &other_account).await;
    pool.close().await;
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_session_store_touch() {
    let pool = connect_pool().await;
    let account_id = unique_account_id("touch");
    let store = DbSessionStore::new(pool.clone());

    cleanup_account(&pool, &account_id).await;

    let created = store
        .create(account_id.clone(), None)
        .await
        .expect("create failed");

    let baseline_from_db = store
        .get(&created.id)
        .await
        .expect("get baseline failed")
        .expect("created session missing");

    store.touch(&created.id).await.expect("touch failed");

    let after_immediate = store
        .get(&created.id)
        .await
        .expect("get immediate failed")
        .expect("session missing after immediate touch");

    assert_eq!(
        after_immediate.last_active, baseline_from_db.last_active,
        "touch within debounce window must not change last_active"
    );

    sqlx::query("UPDATE sessions SET last_active = NOW() - INTERVAL '10 minutes' WHERE id = $1")
        .bind(&created.id)
        .execute(&pool)
        .await
        .expect("backdate last_active failed");

    store.touch(&created.id).await.expect("second touch failed");

    let after_debounce = store
        .get(&created.id)
        .await
        .expect("get after debounce failed")
        .expect("session missing after debounce touch");

    assert!(
        after_debounce.last_active > baseline_from_db.last_active,
        "touch after debounce window must advance last_active"
    );

    cleanup_account(&pool, &account_id).await;
    pool.close().await;
}

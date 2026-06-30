//! Integration proof: AUTH-PG-002 DbPasskeyStore with direct PostgreSQL.
//!
//! Proves that a registered WebAuthn credential persisted by one store instance
//! is recoverable by a freshly constructed store instance (i.e. it survives a
//! store/app re-initialisation — the restart-stability invariant), that
//! duplicate credential IDs are rejected by the database, that lookups and
//! removals stay account-scoped, and that `update_credential` persists the
//! advanced signature counter.
//!
//! Scope: store layer only. The routes are NOT switched to this store; this
//! proves the persistence primitive, not a runtime cutover.
//!
//! Run with:
//!   DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
//!     cargo test --locked -p weltgewebe-api \
//!     --test db_passkey_store_persistence -- --include-ignored --test-threads=1
//!
//! Notes:
//! - Tests are ignored by default to keep offline paths green.
//! - DATABASE_URL must point to direct PostgreSQL (not PgBouncer at :6432).
//! - Fixtures use a recognizable account-id namespace and are cleaned up.

use std::{path::PathBuf, str::FromStr};

use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use base64::Engine;
use serde_json::json;
use sqlx::postgres::{PgConnectOptions, PgPoolOptions};
use uuid::Uuid;
use webauthn_rs::prelude::*;

use weltgewebe_api::auth::passkeys_db::{credential_id_key, DbPasskeyStore, DbPasskeyStoreError};

fn direct_database_url() -> String {
    let url = std::env::var("DATABASE_URL").expect(
        "DATABASE_URL must be set to run db_passkey_store_persistence tests; \
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

async fn ensure_migrations(pool: &sqlx::PgPool) {
    let migrations_dir: PathBuf = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("migrations");
    let migrator = sqlx::migrate::Migrator::new(migrations_dir)
        .await
        .expect("failed to load migrations");
    migrator.run(pool).await.expect("failed to run migrations");
}

fn unique_account_id(test_name: &str) -> String {
    format!("db-passkey-store-{test_name}-{}", Uuid::new_v4())
}

async fn cleanup_account(pool: &sqlx::PgPool, account_id: &str) {
    sqlx::query("DELETE FROM passkey_credentials WHERE account_id = $1")
        .bind(account_id)
        .execute(pool)
        .await
        .expect("failed to cleanup account passkeys");
}

/// Builds a deterministic, valid `Passkey` from a seed without a browser or
/// authenticator. The credential id is `[seed; 32]`; the rest is a minimal
/// ES256 record. This is the same fixture shape used by the passkeys unit
/// tests.
fn test_passkey(credential_seed: u8) -> Passkey {
    let credential_id = vec![credential_seed; 32];
    let credential_id_b64 = URL_SAFE_NO_PAD.encode(&credential_id);
    serde_json::from_value(json!({
        "cred": {
            "cred_id": credential_id_b64,
            "cred": {
                "type_": "ES256",
                "key": {
                    "EC_EC2": {
                        "curve": "SECP256R1",
                        "x": vec![1_u8; 32],
                        "y": vec![2_u8; 32]
                    }
                }
            },
            "counter": 0,
            "transports": null,
            "user_verified": false,
            "backup_eligible": false,
            "backup_state": false,
            "registration_policy": "preferred",
            "extensions": {
                "cred_protect": "NotRequested",
                "hmac_create_secret": "NotRequested"
            },
            "attestation": {
                "data": "None",
                "metadata": "None"
            },
            "attestation_format": "None"
        }
    }))
    .expect("passkey fixture must deserialize")
}

/// Builds a genuine `AuthenticationResult` (via serde) advancing the counter,
/// targeting the given credential id — no browser needed.
fn test_authentication_result(credential_id: &CredentialID, counter: u32) -> AuthenticationResult {
    let cred_id_value = serde_json::to_value(credential_id).expect("credential id serializes");
    serde_json::from_value(json!({
        "cred_id": cred_id_value,
        "needs_update": true,
        "user_verified": true,
        "backup_state": false,
        "backup_eligible": false,
        "counter": counter,
        "extensions": {}
    }))
    .expect("authentication result fixture must deserialize")
}

/// The core restart-stability proof: a credential inserted via `store1` is
/// found again via a freshly constructed `store2` (separate pool), i.e. it
/// survives store/app re-initialisation.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_passkey_store_persists_across_reinit() {
    let pool1 = connect_pool().await;
    let pool2 = connect_pool().await;
    let account_id = unique_account_id("persistence");
    let webauthn_user_id = Uuid::new_v4();
    let passkey = test_passkey(11);
    let cred_id = passkey.cred_id().clone();

    cleanup_account(&pool1, &account_id).await;

    let store1 = DbPasskeyStore::new(pool1.clone());
    store1
        .insert(&account_id, webauthn_user_id, &passkey)
        .await
        .expect("insert should succeed");

    // Fresh store over a fresh pool — simulates a process restart.
    let store2 = DbPasskeyStore::new(pool2.clone());

    let listed = store2
        .list_for_account(&account_id)
        .await
        .expect("list should succeed");
    assert_eq!(listed.len(), 1, "credential must persist across reinit");
    assert_eq!(listed[0].cred_id(), &cred_id);

    let found = store2
        .find_by_credential_id(&cred_id)
        .await
        .expect("find should succeed")
        .expect("credential must be found after reinit");
    assert_eq!(found.account_id, account_id);
    assert_eq!(found.passkey.cred_id(), &cred_id);

    let ids = store2
        .credential_ids_for_account(&account_id)
        .await
        .expect("credential_ids should succeed");
    assert_eq!(ids, vec![cred_id.clone()]);

    cleanup_account(&pool2, &account_id).await;
    pool1.close().await;
    pool2.close().await;
}

/// Duplicate credential ids are rejected by the database (the PRIMARY KEY is
/// the final source of truth), even across accounts.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_passkey_store_rejects_duplicate_credential_id() {
    let pool = connect_pool().await;
    let account_a = unique_account_id("dup-a");
    let account_b = unique_account_id("dup-b");
    let passkey = test_passkey(22);

    cleanup_account(&pool, &account_a).await;
    cleanup_account(&pool, &account_b).await;

    let store = DbPasskeyStore::new(pool.clone());
    store
        .insert(&account_a, Uuid::new_v4(), &passkey)
        .await
        .expect("first insert should succeed");

    let duplicate = store.insert(&account_b, Uuid::new_v4(), &passkey).await;
    assert!(
        matches!(duplicate, Err(DbPasskeyStoreError::DuplicateCredentialId)),
        "duplicate credential id must be rejected, got {duplicate:?}"
    );

    cleanup_account(&pool, &account_a).await;
    cleanup_account(&pool, &account_b).await;
    pool.close().await;
}

/// `find_by_credential_id` resolves the correct owner and never cross-account
/// authorises; `remove_for_account` is owner-bound.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_passkey_store_find_and_remove_are_account_scoped() {
    let pool = connect_pool().await;
    let account_a = unique_account_id("scope-a");
    let account_b = unique_account_id("scope-b");
    let a_key = test_passkey(33);
    let b_key = test_passkey(44);
    let a_cred = a_key.cred_id().clone();
    let b_cred = b_key.cred_id().clone();

    cleanup_account(&pool, &account_a).await;
    cleanup_account(&pool, &account_b).await;

    let store = DbPasskeyStore::new(pool.clone());
    store
        .insert(&account_a, Uuid::new_v4(), &a_key)
        .await
        .expect("insert account a");
    store
        .insert(&account_b, Uuid::new_v4(), &b_key)
        .await
        .expect("insert account b");

    let found = store
        .find_by_credential_id(&a_cred)
        .await
        .expect("find should succeed")
        .expect("a credential must be found");
    assert_eq!(found.account_id, account_a);

    // Wrong account cannot remove another account's credential.
    assert!(
        !store
            .remove_for_account(&account_b, &a_cred)
            .await
            .expect("remove should succeed"),
        "other account must not remove a credential it does not own"
    );
    assert!(
        store
            .find_by_credential_id(&a_cred)
            .await
            .expect("find should succeed")
            .is_some(),
        "credential must still exist after a wrong-account remove"
    );

    // Owner removes its own credential.
    assert!(
        store
            .remove_for_account(&account_a, &a_cred)
            .await
            .expect("remove should succeed"),
        "owner must remove its own credential"
    );
    assert!(
        store
            .find_by_credential_id(&a_cred)
            .await
            .expect("find should succeed")
            .is_none(),
        "removed credential must no longer be found"
    );
    assert!(
        store
            .find_by_credential_id(&b_cred)
            .await
            .expect("find should succeed")
            .is_some(),
        "other account credential must remain"
    );

    cleanup_account(&pool, &account_a).await;
    cleanup_account(&pool, &account_b).await;
    pool.close().await;
}

/// `update_credential` persists the advanced signature counter (replay/counter
/// semantics survive restart) and stays owner-bound.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_passkey_store_update_credential_persists_counter() {
    let pool1 = connect_pool().await;
    let pool2 = connect_pool().await;
    let account_id = unique_account_id("update");
    let other_account = unique_account_id("update-other");
    let passkey = test_passkey(55);
    let cred_id = passkey.cred_id().clone();

    cleanup_account(&pool1, &account_id).await;
    cleanup_account(&pool1, &other_account).await;

    let store = DbPasskeyStore::new(pool1.clone());
    store
        .insert(&account_id, Uuid::new_v4(), &passkey)
        .await
        .expect("insert should succeed");

    let auth_result = test_authentication_result(&cred_id, 7);

    // Cross-account update must fail-close and mutate nothing.
    let cross = store.update_credential(&other_account, &auth_result).await;
    assert!(
        matches!(cross, Err(DbPasskeyStoreError::NotFound)),
        "cross-account update must be rejected, got {cross:?}"
    );

    // Owner update advances the counter 0 -> 7.
    assert!(
        store
            .update_credential(&account_id, &auth_result)
            .await
            .expect("update should succeed"),
        "advancing the signature counter must report a change"
    );

    // Re-applying the same result is a no-op.
    assert!(
        !store
            .update_credential(&account_id, &auth_result)
            .await
            .expect("second update should succeed"),
        "re-applying an identical result must report no change"
    );

    // The advanced counter must be durable: a fresh store sees counter == 7,
    // so a replayed assertion with the old counter would be rejected later.
    let store2 = DbPasskeyStore::new(pool2.clone());
    let reloaded = store2
        .find_by_credential_id(&cred_id)
        .await
        .expect("find should succeed")
        .expect("credential must persist");
    let reloaded_value = serde_json::to_value(&reloaded.passkey).expect("passkey serializes");
    let counter = reloaded_value
        .get("cred")
        .and_then(|c| c.get("counter"))
        .and_then(|c| c.as_u64())
        .expect("counter present in stored credential");
    assert_eq!(counter, 7, "advanced counter must be persisted");

    cleanup_account(&pool2, &account_id).await;
    pool1.close().await;
    pool2.close().await;
}

/// Sanity check that the deterministic credential-id key used as the primary
/// key is reversible — kept here too so a DB-side regression surfaces in the
/// same proof job.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_passkey_store_credential_id_key_is_primary_key() {
    let pool = connect_pool().await;
    let account_id = unique_account_id("pk");
    let passkey = test_passkey(66);
    let cred_id = passkey.cred_id().clone();

    cleanup_account(&pool, &account_id).await;

    let store = DbPasskeyStore::new(pool.clone());
    store
        .insert(&account_id, Uuid::new_v4(), &passkey)
        .await
        .expect("insert should succeed");

    let key = credential_id_key(&cred_id);
    let stored_account: Option<String> =
        sqlx::query_scalar("SELECT account_id FROM passkey_credentials WHERE credential_id = $1")
            .bind(&key)
            .fetch_optional(&pool)
            .await
            .expect("query should succeed");
    assert_eq!(stored_account.as_deref(), Some(account_id.as_str()));

    cleanup_account(&pool, &account_id).await;
    pool.close().await;
}

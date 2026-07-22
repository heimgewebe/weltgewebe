//! Integration proof: AUTH-PG-002 passkey credential account FK-readiness audit.
//!
//! This is deliberately audit-only. It does not add a foreign key and does not
//! change runtime behavior. It proves that a future FK cutover has a deterministic
//! orphan detector for `passkey_credentials.account_id -> domain_accounts.id`.
//!
//! Run with:
//!   DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
//!     cargo test --locked -p weltgewebe-api \
//!     --test db_passkey_fk_readiness -- --include-ignored --test-threads=1

mod support;

use std::{path::PathBuf, str::FromStr};

use sqlx::postgres::{PgConnectOptions, PgPoolOptions};
use uuid::Uuid;

fn direct_database_url() -> String {
    let url = std::env::var("DATABASE_URL").expect(
        "DATABASE_URL must be set to run db_passkey_fk_readiness tests; \
         point it to direct PostgreSQL (port 5432)",
    );
    assert!(
        !url.contains(":6432"),
        "DATABASE_URL must target direct PostgreSQL, not PgBouncer (port 6432)"
    );
    support::postgres_proof::validated_direct_disposable_url(url)
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

fn fixture_prefix() -> &'static str {
    "db-passkey-fk-readiness-"
}

fn fixture_account_id(label: &str) -> String {
    format!("{}{label}-{}", fixture_prefix(), Uuid::new_v4())
}

fn fixture_credential_id(seed: &str) -> String {
    format!("{}{}", seed, Uuid::new_v4().simple())
}

async fn cleanup_fixtures(pool: &sqlx::PgPool) {
    let like = format!("{}%", fixture_prefix());
    sqlx::query("DELETE FROM passkey_credentials WHERE account_id LIKE $1")
        .bind(&like)
        .execute(pool)
        .await
        .expect("failed to cleanup passkey credential fixtures");
    sqlx::query("DELETE FROM domain_accounts WHERE id LIKE $1")
        .bind(&like)
        .execute(pool)
        .await
        .expect("failed to cleanup domain account fixtures");
}

async fn audit_orphan_passkey_accounts(pool: &sqlx::PgPool) -> Vec<(String, i64)> {
    let like = format!("{}%", fixture_prefix());
    sqlx::query_as(
        "SELECT pc.account_id, COUNT(*)::bigint AS credential_count \
         FROM passkey_credentials pc \
         LEFT JOIN domain_accounts da ON da.id = pc.account_id \
         WHERE da.id IS NULL AND pc.account_id LIKE $1 \
         GROUP BY pc.account_id \
         ORDER BY pc.account_id",
    )
    .bind(like)
    .fetch_all(pool)
    .await
    .expect("passkey FK-readiness audit query should run")
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn passkey_account_fk_readiness_audit_detects_orphans() {
    let pool = connect_pool().await;
    cleanup_fixtures(&pool).await;

    let valid_account_id = fixture_account_id("valid");
    let orphan_account_id = fixture_account_id("orphan");
    let valid_webauthn_user_id = Uuid::new_v4();
    let orphan_webauthn_user_id = Uuid::new_v4();

    sqlx::query(
        "INSERT INTO domain_accounts \
            (id, kind, title, mode, map_state, radius_m, disabled, role, email, webauthn_user_id, public_payload, private_payload) \
         VALUES \
            ($1, 'garnrolle', 'FK Readiness Account', NULL, 'not_on_map', 0, false, 'weber', $2, $3::uuid, '{}'::jsonb, '{}'::jsonb)",
    )
    .bind(&valid_account_id)
    .bind(format!("{valid_account_id}@example.invalid"))
    .bind(valid_webauthn_user_id.to_string())
    .execute(&pool)
    .await
    .expect("failed to seed referenced domain account");

    sqlx::query(
        "INSERT INTO passkey_credentials \
            (credential_id, account_id, webauthn_user_id, credential) \
         VALUES \
            ($1, $2, $3::uuid, '{}'::jsonb), \
            ($4, $5, $6::uuid, '{}'::jsonb)",
    )
    .bind(fixture_credential_id("91"))
    .bind(&valid_account_id)
    .bind(valid_webauthn_user_id.to_string())
    .bind(fixture_credential_id("92"))
    .bind(&orphan_account_id)
    .bind(orphan_webauthn_user_id.to_string())
    .execute(&pool)
    .await
    .expect("failed to seed passkey credential fixtures");

    let orphans = audit_orphan_passkey_accounts(&pool).await;
    assert_eq!(
        orphans,
        vec![(orphan_account_id.clone(), 1)],
        "audit must report only credentials whose account_id has no domain_accounts row"
    );

    cleanup_fixtures(&pool).await;
    let remaining = audit_orphan_passkey_accounts(&pool).await;
    assert!(
        remaining.is_empty(),
        "fixture cleanup must leave no audit rows"
    );

    pool.close().await;
}

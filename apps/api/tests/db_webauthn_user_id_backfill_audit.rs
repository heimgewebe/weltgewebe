//! AUTH-PG-003 read-only DB proof.
//! No backfill, no NOT NULL, no WebAuthn crypto: row/UUID coherence only.

use std::{path::PathBuf, str::FromStr};

use sqlx::postgres::{PgConnectOptions, PgPoolOptions};
use uuid::Uuid;
use weltgewebe_api::domain_db::{audit_auth_user_id_backfill_readiness, AuthUserIdBackfillAudit};

fn direct_database_url() -> String {
    let url = std::env::var("DATABASE_URL").expect(
        "DATABASE_URL must be set for this direct PostgreSQL proof; \
         point it to a disposable direct PostgreSQL database (port 5432)",
    );
    assert!(
        !url.contains(":6432"),
        "DATABASE_URL must target direct PostgreSQL, not PgBouncer (port 6432)"
    );
    url
}

fn require_fixture_mutation_opt_in() {
    let enabled = std::env::var("AUTH_PG_003_FIXTURE_MUTATION").unwrap_or_default();
    assert_eq!(
        enabled, "1",
        "AUTH_PG_003_FIXTURE_MUTATION=1 must be set; this ignored proof runs migrations and inserts/deletes auth-pg-003-audit-proof* fixtures, so use a disposable direct PostgreSQL database"
    );
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

const PREFIX: &str = "auth-pg-003-audit-proof";
const STABLE: &str = "auth-pg-003-audit-proof-stable";
const NULL_NO_CREDENTIAL: &str = "auth-pg-003-audit-proof-null-no-credential";
const NULL_WITH_CREDENTIAL: &str = "auth-pg-003-audit-proof-null-with-credential";
const MISMATCH: &str = "auth-pg-003-audit-proof-mismatch";
const MULTI_UUID: &str = "auth-pg-003-audit-proof-multi-uuid";
const ORPHAN: &str = "auth-pg-003-audit-proof-orphan";

fn delta(
    before: AuthUserIdBackfillAudit,
    after: AuthUserIdBackfillAudit,
) -> AuthUserIdBackfillAudit {
    AuthUserIdBackfillAudit {
        accounts_total: after.accounts_total - before.accounts_total,
        accounts_missing_auth_user_id: after.accounts_missing_auth_user_id
            - before.accounts_missing_auth_user_id,
        credential_rows_total: after.credential_rows_total - before.credential_rows_total,
        credential_account_ids_distinct: after.credential_account_ids_distinct
            - before.credential_account_ids_distinct,
        credential_accounts_missing_auth_user_id: after.credential_accounts_missing_auth_user_id
            - before.credential_accounts_missing_auth_user_id,
        credential_accounts_without_domain_account: after
            .credential_accounts_without_domain_account
            - before.credential_accounts_without_domain_account,
        credential_accounts_with_multiple_auth_user_ids: after
            .credential_accounts_with_multiple_auth_user_ids
            - before.credential_accounts_with_multiple_auth_user_ids,
        credential_accounts_with_account_credential_uuid_mismatch: after
            .credential_accounts_with_account_credential_uuid_mismatch
            - before.credential_accounts_with_account_credential_uuid_mismatch,
    }
}

async fn cleanup(pool: &sqlx::PgPool) {
    sqlx::query("DELETE FROM passkey_credentials WHERE account_id LIKE $1")
        .bind(format!("{PREFIX}%"))
        .execute(pool)
        .await
        .expect("cleanup passkey_credentials");
    sqlx::query("DELETE FROM domain_accounts WHERE id LIKE $1")
        .bind(format!("{PREFIX}%"))
        .execute(pool)
        .await
        .expect("cleanup domain_accounts");
}

async fn insert_account(pool: &sqlx::PgPool, id: &str, user_id: Option<Uuid>) {
    sqlx::query(
        "INSERT INTO domain_accounts \
            (id, kind, title, mode, radius_m, role, webauthn_user_id, public_payload, private_payload) \
         VALUES ($1, 'garnrolle', $2, 'ron', 0, 'gast', $3::uuid, '{}'::jsonb, '{}'::jsonb)",
    )
    .bind(id)
    .bind(id)
    .bind(user_id.map(|value| value.to_string()))
    .execute(pool)
    .await
    .expect("insert domain account fixture");
}

async fn insert_credential(pool: &sqlx::PgPool, id: &str, account_id: &str, user_id: Uuid) {
    sqlx::query(
        "INSERT INTO passkey_credentials (credential_id, account_id, webauthn_user_id, credential) \
         VALUES ($1, $2, $3::uuid, '{}'::jsonb)",
    )
    .bind(id)
    .bind(account_id)
    .bind(user_id.to_string())
    .execute(pool)
    .await
    .expect("insert credential fixture");
}

#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn db_webauthn_user_id_backfill_audit_classifies_fixture_delta() {
    require_fixture_mutation_opt_in();
    let pool = connect_pool().await;
    cleanup(&pool).await;
    let before = audit_auth_user_id_backfill_readiness(&pool)
        .await
        .expect("baseline audit");

    let stable_uuid = Uuid::new_v4();
    let null_with_credential_uuid = Uuid::new_v4();
    let mismatch_account_uuid = Uuid::new_v4();
    let mismatch_credential_uuid = Uuid::new_v4();
    let multi_account_uuid = Uuid::new_v4();
    let multi_credential_uuid_a = Uuid::new_v4();
    let multi_credential_uuid_b = Uuid::new_v4();
    let orphan_uuid = Uuid::new_v4();

    insert_account(&pool, STABLE, Some(stable_uuid)).await;
    insert_credential(&pool, &format!("{STABLE}-credential"), STABLE, stable_uuid).await;
    insert_account(&pool, NULL_NO_CREDENTIAL, None).await;
    insert_account(&pool, NULL_WITH_CREDENTIAL, None).await;
    insert_credential(
        &pool,
        &format!("{NULL_WITH_CREDENTIAL}-credential"),
        NULL_WITH_CREDENTIAL,
        null_with_credential_uuid,
    )
    .await;
    insert_account(&pool, MISMATCH, Some(mismatch_account_uuid)).await;
    insert_credential(
        &pool,
        &format!("{MISMATCH}-credential"),
        MISMATCH,
        mismatch_credential_uuid,
    )
    .await;
    insert_account(&pool, MULTI_UUID, Some(multi_account_uuid)).await;
    insert_credential(
        &pool,
        &format!("{MULTI_UUID}-credential-a"),
        MULTI_UUID,
        multi_credential_uuid_a,
    )
    .await;
    insert_credential(
        &pool,
        &format!("{MULTI_UUID}-credential-b"),
        MULTI_UUID,
        multi_credential_uuid_b,
    )
    .await;
    insert_credential(&pool, &format!("{ORPHAN}-credential"), ORPHAN, orphan_uuid).await;

    let after = audit_auth_user_id_backfill_readiness(&pool)
        .await
        .expect("audit after fixtures");
    let d = delta(before, after);

    assert_eq!(d.accounts_total, 5);
    assert_eq!(d.accounts_missing_auth_user_id, 2);
    assert_eq!(d.credential_rows_total, 6);
    assert_eq!(d.credential_account_ids_distinct, 5);
    assert_eq!(d.credential_accounts_missing_auth_user_id, 1);
    assert_eq!(d.credential_accounts_without_domain_account, 1);
    assert_eq!(d.credential_accounts_with_multiple_auth_user_ids, 1);
    assert_eq!(
        d.credential_accounts_with_account_credential_uuid_mismatch,
        2
    );
    assert!(d.has_backfill_scope());
    assert!(d.has_cutover_blockers());

    cleanup(&pool).await;
}

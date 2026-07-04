//! Integration proof: AUTH-PG-002 `passkey_credentials` schema preflight.
//!
//! Home-server-free CI counterpart of the runtime schema audit
//! (`docs/reports/auth-pg-002-runtime-schema-readiness-heimserver-2026-07-01.md`):
//! that audit found a runtime whose `_sqlx_migrations` did NOT contain
//! `20260630000001_create_passkey_credentials`. This preflight pins, against a
//! fresh PostgreSQL, exactly the invariants a controlled runtime migration step
//! must reproduce later:
//!
//! 1. the passkey migration is part of the compile-time embedded production
//!    migrator (`sqlx::migrate!("./migrations")` — the same artifact `lib.rs`
//!    runs at startup), not merely a file on disk;
//! 2. running that embedded migrator registers the migration in
//!    `_sqlx_migrations` with `success = true`;
//! 3. the resulting table has the contracted columns, types and nullability;
//! 4. the PRIMARY KEY is exactly `credential_id`, the non-unique account
//!    lookup index exists, and — deliberately — NO foreign key exists yet
//!    (the FK belongs to a later, explicitly gated cutover slice; a silently
//!    added FK must fail this preflight and go through that slice);
//! 5. the database itself enforces NOT NULL on `account_id` /
//!    `webauthn_user_id` / `credential` and uniqueness of `credential_id`.
//!
//! Run with:
//!   DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
//!     cargo test --locked -p weltgewebe-api \
//!     --test db_passkey_schema_preflight -- --include-ignored --test-threads=1
//!
//! Notes:
//! - DB-backed tests are ignored by default to keep offline paths green; the
//!   embedded-migrator containment check runs in the offline path too.
//! - DATABASE_URL must point to direct PostgreSQL (not PgBouncer at :6432).
//! - NOT proven here: the home-server runtime schema state, the controlled
//!   runtime application of this migration, and any production cutover.

use std::str::FromStr;

use sqlx::migrate::MigrationType;
use sqlx::postgres::{PgConnectOptions, PgPoolOptions};
use sqlx::Row;
use uuid::Uuid;

/// The exact compile-time embedded migrator production runs at startup
/// (`lib.rs`: `sqlx::migrate!("./migrations").run(pool)`). Deliberately NOT a
/// runtime directory scan: if the passkey migration ever fell out of the
/// embedded set, a directory-based `Migrator::new(..)` would still find the
/// file on disk and hide the regression.
static EMBEDDED_MIGRATOR: sqlx::migrate::Migrator = sqlx::migrate!("./migrations");

const PASSKEY_MIGRATION_VERSION: i64 = 20260630000001;

fn direct_database_url() -> String {
    let url = std::env::var("DATABASE_URL").expect(
        "DATABASE_URL must be set to run db_passkey_schema_preflight tests; \
         point it to direct PostgreSQL (port 5432)",
    );
    assert!(
        !url.contains(":6432"),
        "DATABASE_URL must target direct PostgreSQL, not PgBouncer (port 6432)"
    );
    url
}

/// Connects and applies the embedded production migrator (idempotent).
async fn preflight_pool() -> sqlx::PgPool {
    let connect_opts = PgConnectOptions::from_str(&direct_database_url())
        .expect("DATABASE_URL must be a valid postgres connection string");
    let pool = PgPoolOptions::new()
        .max_connections(2)
        .connect_with(connect_opts)
        .await
        .expect("failed to connect to direct PostgreSQL");
    EMBEDDED_MIGRATOR
        .run(&pool)
        .await
        .expect("embedded production migrator must apply cleanly");
    pool
}

/// Offline containment proof (deliberately NOT ignored): the passkey migration
/// is embedded in the production migrator as a reversible up/down pair. This is
/// the direct answer to "wird sie von `sqlx::migrate!(\"./migrations\")`
/// erfasst?" and needs no database.
#[test]
fn passkey_migration_is_embedded_in_production_migrator() {
    let passkey_migrations: Vec<_> = EMBEDDED_MIGRATOR
        .iter()
        .filter(|m| m.version == PASSKEY_MIGRATION_VERSION)
        .collect();
    assert!(
        !passkey_migrations.is_empty(),
        "migration {PASSKEY_MIGRATION_VERSION} (create_passkey_credentials) must be \
         part of the embedded production migrator"
    );
    for migration in &passkey_migrations {
        assert_eq!(
            migration.description.as_ref(),
            "create passkey credentials",
            "embedded migration {PASSKEY_MIGRATION_VERSION} must keep its description"
        );
    }
    let has_up = passkey_migrations
        .iter()
        .any(|m| matches!(m.migration_type, MigrationType::ReversibleUp));
    let has_down = passkey_migrations
        .iter()
        .any(|m| matches!(m.migration_type, MigrationType::ReversibleDown));
    assert!(
        has_up && has_down,
        "passkey migration must be embedded as a reversible up/down pair \
         (up: {has_up}, down: {has_down})"
    );
}

/// Running the embedded migrator on a fresh database registers the passkey
/// migration in `_sqlx_migrations` with `success = true` — the exact check the
/// heimserver runtime audit performs read-only.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn passkey_schema_preflight_migration_is_registered() {
    let pool = preflight_pool().await;

    let row = sqlx::query("SELECT success, description FROM _sqlx_migrations WHERE version = $1")
        .bind(PASSKEY_MIGRATION_VERSION)
        .fetch_optional(&pool)
        .await
        .expect("querying _sqlx_migrations must succeed")
        .expect("passkey migration must be registered in _sqlx_migrations");

    let success: bool = row.try_get("success").expect("success column");
    let description: String = row.try_get("description").expect("description column");
    assert!(
        success,
        "passkey migration must be registered as successful"
    );
    assert_eq!(description, "create passkey credentials");

    pool.close().await;
}

/// The migrated table carries exactly the contracted columns with the
/// contracted types and nullability, and the timestamp columns keep their
/// `now()` defaults.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn passkey_schema_preflight_table_shape_matches_contract() {
    let pool = preflight_pool().await;

    let rows = sqlx::query(
        "SELECT column_name, data_type, is_nullable, column_default \
         FROM information_schema.columns \
         WHERE table_schema = 'public' AND table_name = 'passkey_credentials' \
         ORDER BY column_name",
    )
    .fetch_all(&pool)
    .await
    .expect("information_schema query must succeed");

    let actual: Vec<(String, String, String)> = rows
        .iter()
        .map(|row| {
            (
                row.try_get::<String, _>("column_name")
                    .expect("column_name"),
                row.try_get::<String, _>("data_type").expect("data_type"),
                row.try_get::<String, _>("is_nullable")
                    .expect("is_nullable"),
            )
        })
        .collect();
    let expected: Vec<(String, String, String)> = [
        ("account_id", "text", "NO"),
        ("created_at", "timestamp with time zone", "NO"),
        ("credential", "jsonb", "NO"),
        ("credential_id", "text", "NO"),
        ("last_used_at", "timestamp with time zone", "YES"),
        ("updated_at", "timestamp with time zone", "NO"),
        ("webauthn_user_id", "uuid", "NO"),
    ]
    .iter()
    .map(|(name, ty, nullable)| (name.to_string(), ty.to_string(), nullable.to_string()))
    .collect();
    assert_eq!(
        actual, expected,
        "passkey_credentials columns/types/nullability must match the migration contract"
    );

    for column in ["created_at", "updated_at"] {
        let default: Option<String> = rows
            .iter()
            .find(|row| {
                row.try_get::<String, _>("column_name")
                    .expect("column_name")
                    == column
            })
            .expect("timestamp column must exist")
            .try_get("column_default")
            .expect("column_default");
        assert_eq!(
            default.as_deref(),
            Some("now()"),
            "{column} must default to now()"
        );
    }

    pool.close().await;
}

/// PRIMARY KEY is exactly `credential_id`, the account lookup index exists and
/// is non-unique, and no foreign key exists yet. The FK absence is asserted
/// deliberately: the migration defers the FK to the explicitly gated cutover
/// slice (see the migration header and the AUTH-PG-002 cutover plan) — adding
/// it silently must fail this preflight so it goes through that slice.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn passkey_schema_preflight_constraints_and_indexes() {
    let pool = preflight_pool().await;

    let pk_columns: Vec<String> = sqlx::query_scalar(
        "SELECT a.attname \
         FROM pg_index i \
         JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) \
         WHERE i.indrelid = 'passkey_credentials'::regclass AND i.indisprimary \
         ORDER BY a.attname",
    )
    .fetch_all(&pool)
    .await
    .expect("primary key introspection must succeed");
    assert_eq!(
        pk_columns,
        vec!["credential_id".to_string()],
        "PRIMARY KEY must be exactly credential_id"
    );

    let account_index: Option<(bool, bool)> = sqlx::query(
        "SELECT i.indisunique, i.indisprimary \
         FROM pg_index i \
         JOIN pg_class c ON c.oid = i.indexrelid \
         WHERE i.indrelid = 'passkey_credentials'::regclass \
           AND c.relname = 'passkey_credentials_account_id'",
    )
    .fetch_optional(&pool)
    .await
    .expect("index introspection must succeed")
    .map(|row| {
        (
            row.try_get("indisunique").expect("indisunique"),
            row.try_get("indisprimary").expect("indisprimary"),
        )
    });
    assert_eq!(
        account_index,
        Some((false, false)),
        "passkey_credentials_account_id must exist as a non-unique secondary index"
    );

    let fk_count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*)::bigint FROM pg_constraint \
         WHERE conrelid = 'passkey_credentials'::regclass AND contype = 'f'",
    )
    .fetch_one(&pool)
    .await
    .expect("constraint introspection must succeed");
    assert_eq!(
        fk_count, 0,
        "no foreign key may exist yet: the account FK is deferred to the gated \
         cutover slice and must not appear silently"
    );

    pool.close().await;
}

/// The database itself enforces the row contract: NULL `account_id`,
/// `webauthn_user_id` or `credential` are rejected with a not-null violation
/// (SQLSTATE 23502) and a duplicate `credential_id` with a unique violation
/// (SQLSTATE 23505) — independent of any store-layer mapping.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
async fn passkey_schema_preflight_rejects_null_and_duplicate_rows() {
    let pool = preflight_pool().await;
    let fixture = format!("db-passkey-schema-preflight-{}", Uuid::new_v4().simple());
    let account_id = format!("{fixture}-account");

    sqlx::query("DELETE FROM passkey_credentials WHERE account_id = $1")
        .bind(&account_id)
        .execute(&pool)
        .await
        .expect("fixture cleanup must succeed");

    fn assert_not_null_violation(
        column: &str,
        result: Result<sqlx::postgres::PgQueryResult, sqlx::Error>,
    ) {
        let error = match result {
            Ok(_) => panic!("NULL {column} insert must be rejected"),
            Err(error) => error,
        };
        let code = error
            .as_database_error()
            .and_then(|db| db.code())
            .map(|code| code.to_string());
        assert_eq!(
            code.as_deref(),
            Some("23502"),
            "NULL {column} must raise a not-null violation, got {error:?}"
        );
    }

    assert_not_null_violation(
        "account_id",
        sqlx::query(
            "INSERT INTO passkey_credentials \
                 (credential_id, account_id, webauthn_user_id, credential) \
             VALUES ($1, NULL, $2::uuid, '{}'::jsonb)",
        )
        .bind(format!("{fixture}-null-account-id"))
        .bind(Uuid::new_v4().to_string())
        .execute(&pool)
        .await,
    );
    assert_not_null_violation(
        "webauthn_user_id",
        sqlx::query(
            "INSERT INTO passkey_credentials \
                 (credential_id, account_id, webauthn_user_id, credential) \
             VALUES ($1, $2, NULL, '{}'::jsonb)",
        )
        .bind(format!("{fixture}-null-webauthn-user-id"))
        .bind(&account_id)
        .execute(&pool)
        .await,
    );
    assert_not_null_violation(
        "credential",
        sqlx::query(
            "INSERT INTO passkey_credentials \
                 (credential_id, account_id, webauthn_user_id, credential) \
             VALUES ($1, $2, $3::uuid, NULL)",
        )
        .bind(format!("{fixture}-null-credential"))
        .bind(&account_id)
        .bind(Uuid::new_v4().to_string())
        .execute(&pool)
        .await,
    );

    let duplicate_credential_id = format!("{fixture}-dup");
    let insert_sql = "INSERT INTO passkey_credentials \
             (credential_id, account_id, webauthn_user_id, credential) \
         VALUES ($1, $2, $3::uuid, '{}'::jsonb)";
    sqlx::query(insert_sql)
        .bind(&duplicate_credential_id)
        .bind(&account_id)
        .bind(Uuid::new_v4().to_string())
        .execute(&pool)
        .await
        .expect("first insert must succeed");
    let error = sqlx::query(insert_sql)
        .bind(&duplicate_credential_id)
        .bind(&account_id)
        .bind(Uuid::new_v4().to_string())
        .execute(&pool)
        .await
        .expect_err("duplicate credential_id insert must be rejected");
    let code = error
        .as_database_error()
        .and_then(|db| db.code())
        .map(|code| code.to_string());
    assert_eq!(
        code.as_deref(),
        Some("23505"),
        "duplicate credential_id must raise a unique violation, got {error:?}"
    );

    sqlx::query("DELETE FROM passkey_credentials WHERE account_id = $1")
        .bind(&account_id)
        .execute(&pool)
        .await
        .expect("fixture cleanup must succeed");
    pool.close().await;
}

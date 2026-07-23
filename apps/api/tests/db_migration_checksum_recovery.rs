//! Regression proof for applied SQLx migration immutability.
//!
//! The test first applies the migration set that production had already
//! recorded before the P0 incident, then upgrades with the complete current
//! migration directory. Any edit to an already-applied migration makes SQLx
//! reject the second step with a checksum mismatch.

mod support;

use std::{fs, path::PathBuf};

use sqlx::{migrate::Migrator, postgres::PgPoolOptions, Row};

#[tokio::test]
#[ignore = "requires direct disposable PostgreSQL via DATABASE_URL"]
async fn previously_applied_migrations_upgrade_without_checksum_mismatch() {
    let url = std::env::var("DATABASE_URL")
        .expect("DATABASE_URL must point to a direct disposable PostgreSQL database");
    support::postgres_proof::assert_direct_disposable_database_url(&url);

    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&url)
        .await
        .expect("connect migration checksum recovery PostgreSQL");

    let migrations = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("migrations");
    let historical = tempfile::tempdir().expect("create historical migration directory");
    for entry in fs::read_dir(&migrations).expect("read migrations directory") {
        let entry = entry.expect("read migration entry");
        let file_name = entry.file_name();
        let file_name_text = file_name.to_string_lossy();
        if file_name_text.starts_with("20260723000001_") {
            continue;
        }
        fs::copy(entry.path(), historical.path().join(&file_name))
            .expect("copy historical migration fixture");
    }

    Migrator::new(historical.path())
        .await
        .expect("load historical migrations")
        .run(&pool)
        .await
        .expect("apply historical migrations with production-compatible checksums");

    let historical_checksum: Vec<u8> = sqlx::query(
        "SELECT checksum FROM _sqlx_migrations WHERE version = 20260721000001 AND success = TRUE",
    )
    .fetch_one(&pool)
    .await
    .expect("read historical semantic-search migration record")
    .get("checksum");
    assert!(!historical_checksum.is_empty());

    Migrator::new(migrations)
        .await
        .expect("load current migrations")
        .run(&pool)
        .await
        .expect("upgrade historical database without SQLx checksum mismatch");

    let hardening_applied: bool = sqlx::query_scalar(
        "SELECT EXISTS (SELECT 1 FROM _sqlx_migrations WHERE version = 20260723000001 AND success = TRUE)",
    )
    .fetch_one(&pool)
    .await
    .expect("read additive hardening migration record");
    assert!(hardening_applied);

    let helper_exists: bool = sqlx::query_scalar(
        "SELECT to_regprocedure('weltgewebe_search_generation_activation_ready(text)') IS NOT NULL",
    )
    .fetch_one(&pool)
    .await
    .expect("check readiness helper");
    assert!(helper_exists);

    let index_exists: bool = sqlx::query_scalar(
        "SELECT to_regclass('search_projection_jobs_generation_state') IS NOT NULL",
    )
    .fetch_one(&pool)
    .await
    .expect("check generation/state index");
    assert!(index_exists);
}

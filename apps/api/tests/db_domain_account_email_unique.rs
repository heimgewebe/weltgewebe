//! Integration proof: TODO 2A normalized account-email uniqueness in PostgreSQL.
//!
//! Proves that the partial unique index `domain_accounts_email_normalized_unique`
//! (`lower(btrim(email)) WHERE email IS NOT NULL AND btrim(email) <> ''`) is the
//! race-safety boundary for the PostgreSQL account-create write path:
//!
//! - duplicate normalized non-empty emails are rejected by the database, not by
//!   the in-memory precheck, and surface as `AccountWriteError::DuplicateEmail`
//!   (classified by constraint name);
//! - case-only and surrounding-whitespace differences still collide;
//! - missing / NULL / after-trim-empty emails are not unique-relevant;
//! - the route maps the violation to `409 CONFLICT` without side effects.
//!
//! Scope: account-email uniqueness only. Node writes, edge writes, step-up email
//! persistence and WebAuthn credential writeback are NOT touched.
//!
//! Run with a direct-PostgreSQL connection URL exported in the standard
//! database environment variable (port 5432, not PgBouncer :6432):
//!   cargo test --locked -p weltgewebe-api --test db_domain_account_email_unique \
//!     -- --include-ignored --test-threads=1
//!
//! Notes:
//! - Tests are ignored by default to keep offline paths green.
//! - The connection must target direct PostgreSQL (not PgBouncer at :6432).
//! - Fixture rows use a recognizable UUID namespace and are cleaned before/after.

use anyhow::Result;
use axum::{
    body,
    http::{Request, StatusCode},
    middleware::from_fn_with_state,
    Router,
};
use serde_json::{json, Value};
use serial_test::serial;
use sqlx::{Executor, PgPool};
use std::{path::PathBuf, sync::Arc};
use tokio::sync::RwLock;
use tower::ServiceExt;
use weltgewebe_api::{
    auth::{
        accounts::AccountStore, rate_limit::AuthRateLimiter, role::Role, session::SessionBackend,
    },
    config::{
        AppConfig, DomainAccountWriteSource, DomainEdgeWriteSource, DomainNodeWriteSource,
        DomainReadSource,
    },
    domain_db::{insert_account_from_jsonl_record, AccountWriteError},
    middleware::{auth::auth_middleware, csrf::require_csrf},
    routes::{
        accounts::{AccountInternal, AccountMode, AccountPublic},
        api_router,
    },
    state::ApiState,
    telemetry::{BuildInfo, Metrics},
};

mod helpers;
use helpers::set_gewebe_in_dir;

// Only the mandated test domains are ever used; never real addresses.
const EMAIL_ALPHA: &str = "alpha@example.invalid";
const EMAIL_BETA: &str = "beta@example.invalid";

// Distinct fixture namespace so cleanup never touches other suites' rows. The
// ids are valid UUID syntax so the route's id validation accepts them too.
const FIXTURE_PREFIX: &str = "eeeeeeee-eeee-4eee-8eee-";

fn fixture_id(n: u32) -> String {
    format!("{FIXTURE_PREFIX}{n:012}")
}

fn direct_database_url() -> String {
    let url = std::env::var("DATABASE_URL")
        .expect("DATABASE_URL must point at a direct PostgreSQL database (port 5432)");
    assert!(
        !url.contains(":6432"),
        "DATABASE_URL must target direct PostgreSQL, not PgBouncer (port 6432)"
    );
    url
}

async fn connect_pool() -> PgPool {
    PgPool::connect(&direct_database_url())
        .await
        .expect("connect to direct PostgreSQL")
}

async fn run_migrations(pool: &PgPool) {
    let migrations_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("migrations");
    let migrator = sqlx::migrate::Migrator::new(migrations_dir)
        .await
        .expect("failed to load migrations");
    migrator.run(pool).await.expect("failed to run migrations");
}

async fn clean(pool: &PgPool) {
    pool.execute("DELETE FROM domain_accounts WHERE id LIKE 'eeeeeeee-eeee-4eee-8eee-%'")
        .await
        .expect("clean domain_accounts fixtures");
}

/// A minimal validated, JSONL-shaped account record as `insert_account_from_jsonl_record`
/// expects it. `email = None` omits the key entirely (missing email).
fn account_record(id: &str, email: Option<&str>) -> Value {
    let mut m = serde_json::Map::new();
    m.insert("id".into(), json!(id));
    m.insert("type".into(), json!("garnrolle"));
    m.insert("title".into(), json!("Email Unique Fixture"));
    if let Some(e) = email {
        m.insert("email".into(), json!(e));
    }
    Value::Object(m)
}

async fn insert(pool: &PgPool, id: &str, email: Option<&str>) -> Result<(), AccountWriteError> {
    insert_account_from_jsonl_record(pool, &account_record(id, email)).await
}

async fn normalized_email_count(pool: &PgPool, normalized: &str) -> i64 {
    sqlx::query_scalar("SELECT count(*) FROM domain_accounts WHERE lower(btrim(email)) = $1")
        .bind(normalized)
        .fetch_one(pool)
        .await
        .expect("count rows by normalized email")
}

// ── Direct write-path inserts: the DB constraint is the boundary ─────────────

/// Two identical non-empty emails: the second insert is rejected by the unique
/// index (no in-memory precheck involved) and exactly one row survives.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn db_rejects_exact_duplicate_normalized_email() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    insert(&pool, &fixture_id(1), Some(EMAIL_ALPHA))
        .await
        .expect("first non-empty email must insert");

    let err = insert(&pool, &fixture_id(2), Some(EMAIL_ALPHA))
        .await
        .expect_err("duplicate normalized email must be rejected by the DB");
    assert!(
        matches!(err, AccountWriteError::DuplicateEmail),
        "expected DuplicateEmail (constraint-classified), got {err:?}"
    );

    assert_eq!(
        normalized_email_count(&pool, EMAIL_ALPHA).await,
        1,
        "the unique index must leave exactly one winner"
    );

    clean(&pool).await;
    Ok(())
}

/// Case-only difference still collides: PostgreSQL lower() normalizes both.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn db_rejects_case_insensitive_duplicate_email() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    insert(&pool, &fixture_id(3), Some(EMAIL_ALPHA))
        .await
        .expect("first email must insert");

    let err = insert(&pool, &fixture_id(4), Some("ALPHA@example.invalid"))
        .await
        .expect_err("case-variant duplicate must be rejected");
    assert!(
        matches!(err, AccountWriteError::DuplicateEmail),
        "expected DuplicateEmail, got {err:?}"
    );

    clean(&pool).await;
    Ok(())
}

/// Surrounding whitespace still collides: btrim() normalizes the stored value.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn db_rejects_whitespace_normalized_duplicate_email() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    insert(&pool, &fixture_id(5), Some(EMAIL_ALPHA))
        .await
        .expect("first email must insert");

    let err = insert(&pool, &fixture_id(6), Some("  alpha@example.invalid  "))
        .await
        .expect_err("whitespace-variant duplicate must be rejected");
    assert!(
        matches!(err, AccountWriteError::DuplicateEmail),
        "expected DuplicateEmail, got {err:?}"
    );

    clean(&pool).await;
    Ok(())
}

/// Distinct non-empty emails are independent: the constraint must not over-reject.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn db_allows_distinct_non_empty_emails() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    insert(&pool, &fixture_id(7), Some(EMAIL_ALPHA))
        .await
        .expect("alpha must insert");
    insert(&pool, &fixture_id(8), Some(EMAIL_BETA))
        .await
        .expect("beta must insert (distinct email)");

    clean(&pool).await;
    Ok(())
}

/// Missing / NULL emails are not unique-relevant: multiple are allowed.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn db_allows_multiple_missing_emails() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    insert(&pool, &fixture_id(9), None)
        .await
        .expect("first account without email must insert");
    insert(&pool, &fixture_id(10), None)
        .await
        .expect("second account without email must also insert");

    clean(&pool).await;
    Ok(())
}

/// After-trim-empty emails are not unique-relevant: an empty string maps to NULL
/// and a whitespace-only string is excluded by the partial predicate, so any
/// number of them coexist.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn db_allows_multiple_empty_after_trim_emails() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    // Empty string is filtered to None on mapping (stored NULL).
    insert(&pool, &fixture_id(11), Some(""))
        .await
        .expect("empty-string email must insert (stored NULL)");
    insert(&pool, &fixture_id(12), Some(""))
        .await
        .expect("second empty-string email must also insert");

    // Whitespace-only is stored verbatim but excluded by `btrim(email) <> ''`.
    insert(&pool, &fixture_id(13), Some("   "))
        .await
        .expect("whitespace-only email must insert (excluded from the index)");
    insert(&pool, &fixture_id(14), Some("   "))
        .await
        .expect("second whitespace-only email must also insert");

    clean(&pool).await;
    Ok(())
}

// ── Route-level proof: 409 from the DB constraint, no side effects ───────────

fn test_metrics() -> Metrics {
    Metrics::try_new(BuildInfo {
        version: "test",
        commit: "test",
        build_timestamp: "test",
    })
    .expect("metrics")
}

fn admin_operator(id: &str) -> AccountInternal {
    AccountInternal {
        public: AccountPublic {
            id: id.to_string(),
            kind: "garnrolle".to_string(),
            title: format!("Operator {id}"),
            summary: None,
            public_pos: None,
            mode: AccountMode::Verortet,
            radius_m: 0,
            disabled: false,
            tags: vec![],
        },
        role: Role::Admin,
        email: None,
        webauthn_user_id: uuid::Uuid::new_v4(),
    }
}

/// Build a router with PostgreSQL read+write account sources, a real pool, and a
/// single in-memory admin operator with an active session.
async fn postgres_write_app(pool: PgPool, operator_id: &str) -> Result<(Router, String, ApiState)> {
    let mut accounts = AccountStore::new();
    accounts.insert(admin_operator(operator_id));

    let config = AppConfig {
        fade_days: 7,
        ron_days: 84,
        anonymize_opt_in: true,
        delegation_expire_days: 28,
        domain_read_source: DomainReadSource::Postgres,
        domain_account_write_source: DomainAccountWriteSource::Postgres,
        domain_node_write_source: DomainNodeWriteSource::Jsonl,
        domain_edge_write_source: DomainEdgeWriteSource::Jsonl,
        auth_public_login: false,
        app_base_url: None,
        auth_trusted_proxies: None,
        auth_allow_emails: None,
        auth_allow_email_domains: None,
        auth_auto_provision: false,
        auth_rl_ip_per_min: None,
        auth_rl_ip_per_hour: None,
        auth_rl_email_per_min: None,
        auth_rl_email_per_hour: None,
        smtp_host: None,
        smtp_port: None,
        smtp_user: None,
        smtp_pass: None,
        smtp_from: None,
        auth_log_magic_token: false,
        webauthn_rp_id: None,
        webauthn_rp_origin: None,
        webauthn_rp_name: None,
    };

    let rate_limiter = Arc::new(AuthRateLimiter::new(&config));

    let state = ApiState {
        db_pool: Some(pool),
        db_pool_configured: true,
        nats_client: None,
        nats_configured: false,
        config,
        metrics: test_metrics(),
        sessions: SessionBackend::new_in_memory(),
        challenges: Default::default(),
        tokens: weltgewebe_api::auth::tokens::TokenStore::new(),
        step_up_tokens: weltgewebe_api::auth::step_up_tokens::StepUpTokenStore::new(),
        accounts: Arc::new(RwLock::new(accounts)),
        nodes: Arc::new(RwLock::new(weltgewebe_api::state::OrderedCache::new())),
        nodes_persist: Arc::new(tokio::sync::Mutex::new(())),
        accounts_persist: Arc::new(tokio::sync::Mutex::new(())),
        edges: Arc::new(RwLock::new(weltgewebe_api::state::OrderedCache::new())),
        rate_limiter,
        mailer: None,
        webauthn: None,
        passkey_registrations: Default::default(),
        passkey_registration_grants: Default::default(),
        passkeys: Default::default(),
    };

    let session = state
        .sessions
        .create(operator_id.to_string(), None)
        .await
        .expect("session create");
    let cookie = format!("gewebe_session={}", session.id);

    let app = Router::new()
        .merge(api_router())
        .layer(from_fn_with_state(state.clone(), auth_middleware))
        .layer(axum::middleware::from_fn(require_csrf))
        .with_state(state.clone());

    Ok((app, cookie, state))
}

fn post_accounts(cookie: &str, json_body: &str) -> Request<body::Body> {
    Request::post("/accounts")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .header("Cookie", cookie)
        .body(body::Body::from(json_body.to_string()))
        .unwrap()
}

/// A pre-seeded row that exists in PostgreSQL but NOT in the in-memory cache
/// forces the conflict to be surfaced by the unique index, not the cache
/// precheck. The route must answer `409 CONFLICT` and leave the existing row,
/// the cache and JSONL untouched.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn route_maps_db_email_conflict_to_409_without_side_effects() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    // Seed a row directly in PostgreSQL (deliberately absent from the cache).
    let existing_id = fixture_id(50);
    sqlx::query(
        "INSERT INTO domain_accounts \
            (id, kind, title, mode, radius_m, role, email, public_payload, private_payload) \
         VALUES ($1, 'garnrolle', 'Existing', 'verortet', 0, 'weber', $2, '{}'::jsonb, '{}'::jsonb)",
    )
    .bind(&existing_id)
    .bind(EMAIL_ALPHA)
    .execute(&pool)
    .await
    .expect("seed existing domain_accounts row with an email");

    let (app, cookie, state) = postgres_write_app(pool.clone(), "email-unique-admin").await?;

    let new_id = fixture_id(51);
    let body = format!(
        r#"{{"id":"{new_id}","title":"Conflicting","location":{{"lat":1.0,"lon":2.0}},"email":"{EMAIL_ALPHA}"}}"#
    );
    let res = app.clone().oneshot(post_accounts(&cookie, &body)).await?;
    assert_eq!(
        res.status(),
        StatusCode::CONFLICT,
        "duplicate normalized email must map to 409 via the DB constraint"
    );

    // Existing row untouched (plain INSERT, no silent overwrite).
    let (title,): (String,) = sqlx::query_as("SELECT title FROM domain_accounts WHERE id = $1")
        .bind(&existing_id)
        .fetch_one(&pool)
        .await
        .expect("existing row still present");
    assert_eq!(title, "Existing", "create must never overwrite on conflict");

    // The conflicting account was never persisted.
    let new_exists: Option<(String,)> =
        sqlx::query_as("SELECT id FROM domain_accounts WHERE id = $1")
            .bind(&new_id)
            .fetch_optional(&pool)
            .await
            .expect("query conflicting id");
    assert!(
        new_exists.is_none(),
        "rejected account must not be persisted"
    );

    // Cache not mutated and JSONL not written on a failed insert.
    assert!(
        state.accounts.read().await.get(&new_id).is_none(),
        "failed DB insert must not populate the in-memory cache"
    );
    assert!(
        !in_dir.join("demo.accounts.jsonl").exists(),
        "PostgreSQL write mode must not append JSONL"
    );

    clean(&pool).await;
    Ok(())
}

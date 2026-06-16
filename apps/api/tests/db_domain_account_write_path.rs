//! Integration proof: OPT-ARC-001 Phase E-A account-create PostgreSQL write path.
//!
//! Proves that, when `domain_read_source=postgres` and
//! `domain_account_write_source=postgres`, `POST /accounts` writes one row into
//! `domain_accounts`, updates the in-memory `AccountStore`, never appends JSONL,
//! and that the Phase D loader reconstructs the same public projection and
//! stable WebAuthn user identity.
//!
//! Phase scope: account-create only. Node writes, edge writes, step-up email
//! persistence and WebAuthn credential writeback are NOT implemented.
//!
//! Run with:
//!   DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
//!     cargo test --locked -p weltgewebe-api --test db_domain_account_write_path \
//!     -- --include-ignored --test-threads=1
//!
//! Notes:
//! - Tests are ignored by default to keep offline paths green.
//! - DATABASE_URL must point to direct PostgreSQL (not PgBouncer at :6432).
//! - Fixture rows use a recognizable UUID namespace and are cleaned before/after.

use anyhow::{Context, Result};
use axum::{
    body,
    http::{Request, StatusCode},
    middleware::from_fn_with_state,
    Router,
};
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
    domain_db::{insert_account_from_jsonl_record, load_accounts_from_postgres, AccountWriteError},
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

// Account ids created through `POST /accounts` must be valid UUIDs (the route
// validates them), so fixtures use a recognizable UUID namespace that the
// cleanup matches with LIKE. Operator ids are in-memory only (never written to
// the database) and need not be UUIDs.
const RADIUS_ID: &str = "aaaaaaaa-aaaa-4aaa-8aaa-000000000002";
const DUP_ID: &str = "aaaaaaaa-aaaa-4aaa-8aaa-000000000003";
const WEBAUTHN_STABLE_ID: &str = "aaaaaaaa-aaaa-4aaa-8aaa-000000000004";

async fn clean(pool: &PgPool) {
    pool.execute("DELETE FROM domain_accounts WHERE id LIKE 'aaaaaaaa-aaaa-4aaa-8aaa-%'")
        .await
        .expect("clean domain_accounts fixtures");
}

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
/// single in-memory admin operator with an active session. Returns
/// (app, session_cookie, state). The returned `state` shares the same Arcs and
/// pool as the router, so direct cache/DB assertions observe route effects.
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

/// Core success proof: account create writes domain_accounts, updates the cache,
/// does not append JSONL, and reloads with the same public projection and
/// WebAuthn user identity.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn account_create_persists_stable_webauthn_user_id_across_reload() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, state) = postgres_write_app(pool.clone(), "writepath-admin-1").await?;

    let id = WEBAUTHN_STABLE_ID;
    let body = format!(
        r#"{{"id":"{id}","title":"Write Path","location":{{"lat":53.55,"lon":9.99}},"radius_m":0,"summary":"Hello","tags":["a","b"],"role":"weber"}}"#
    );

    let res = app.clone().oneshot(post_accounts(&cookie, &body)).await?;
    assert_eq!(res.status(), StatusCode::CREATED);

    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let created: serde_json::Value = serde_json::from_slice(&bytes)?;
    assert_eq!(created["id"], id);
    assert_eq!(created["title"], "Write Path");
    assert_eq!(created["type"], "garnrolle");
    assert_eq!(created["mode"], "verortet");
    // radius_m=0 => public_pos equals the submitted location exactly.
    assert_eq!(created["public_pos"]["lat"], 53.55);
    assert_eq!(created["public_pos"]["lon"], 9.99);
    // The private `location` field itself is never serialized; `public_pos` is the public projection.
    assert!(created.get("location").is_none());

    // domain_accounts row: explicit columns.
    let (kind, mode, role, title, lat, lon): (
        String,
        String,
        String,
        String,
        Option<f64>,
        Option<f64>,
    ) = sqlx::query_as(
        "SELECT kind, mode, role, title, location_lat, location_lon \
         FROM domain_accounts WHERE id = $1",
    )
    .bind(id)
    .fetch_one(&pool)
    .await
    .expect("account row must exist after create");
    assert_eq!(kind, "garnrolle");
    assert_eq!(mode, "verortet");
    assert_eq!(role, "weber");
    assert_eq!(title, "Write Path");
    assert!((lat.unwrap() - 53.55).abs() < 1e-9);
    assert!((lon.unwrap() - 9.99).abs() < 1e-9);

    let db_webauthn_user_id: Option<String> =
        sqlx::query_scalar("SELECT webauthn_user_id::text FROM domain_accounts WHERE id = $1")
            .bind(id)
            .fetch_one(&pool)
            .await?;
    let db_webauthn_user_id =
        db_webauthn_user_id.expect("new account must persist webauthn_user_id");
    let db_uuid = uuid::Uuid::parse_str(&db_webauthn_user_id)?;

    // JSONB payloads: public carries summary+tags; private mirrors backfill mode.
    let (public_text, private_text): (String, String) = sqlx::query_as(
        "SELECT public_payload::text, private_payload::text FROM domain_accounts WHERE id = $1",
    )
    .bind(id)
    .fetch_one(&pool)
    .await
    .expect("payloads readable");
    let public: serde_json::Value = serde_json::from_str(&public_text)?;
    let private: serde_json::Value = serde_json::from_str(&private_text)?;
    assert_eq!(
        public.get("summary").and_then(|v| v.as_str()),
        Some("Hello")
    );
    assert_eq!(
        public.get("tags").and_then(|v| v.as_array()).map(Vec::len),
        Some(2)
    );
    assert_eq!(
        private.get("mode").and_then(|v| v.as_str()),
        Some("verortet")
    );
    assert!(private.get("visibility").is_none());

    // JSONL must NOT be appended in PostgreSQL write mode.
    let accounts_file = in_dir.join("demo.accounts.jsonl");
    assert!(
        !accounts_file.exists(),
        "PostgreSQL write mode must not append the JSONL accounts file"
    );

    // In-memory cache contains the account immediately (read-your-writes).
    {
        let accounts = state.accounts.read().await;
        let internal = accounts.get(id).expect("created account present in cache");
        assert_eq!(internal.public.title, "Write Path");
        assert_eq!(internal.public.mode, AccountMode::Verortet);
        assert_eq!(internal.role, Role::Weber);
        assert_eq!(internal.webauthn_user_id, db_uuid);
    }

    // Loader reload reconstructs the same public projection.
    let reloaded = load_accounts_from_postgres(&pool)
        .await
        .expect("reload accounts from postgres");
    let internal = reloaded.get(id).expect("account reloaded from postgres");
    assert_eq!(internal.public.title, "Write Path");
    assert_eq!(internal.public.mode, AccountMode::Verortet);
    assert_eq!(internal.public.radius_m, 0);
    assert_eq!(internal.public.summary.as_deref(), Some("Hello"));
    assert_eq!(internal.webauthn_user_id, db_uuid);
    let pos = internal
        .public
        .public_pos
        .as_ref()
        .expect("verortet account has public_pos");
    assert!((pos.lat - 53.55).abs() < 1e-9);
    assert!((pos.lon - 9.99).abs() < 1e-9);

    clean(&pool).await;
    Ok(())
}

/// Privacy-sensitive proof: a non-zero radius persists the REAL residence and
/// radius (never the jittered public_pos), the response is obfuscated, and the
/// loader reproduces the exact same deterministic jitter on reload.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_account_create_radius_persists_obfuscated_public_pos() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, _state) = postgres_write_app(pool.clone(), "writepath-admin-2").await?;

    let id = RADIUS_ID;
    let lat = 53.55_f64;
    let lon = 9.99_f64;
    let radius_m = 500_u32;
    let body = format!(
        r#"{{"id":"{id}","title":"Obfuscated","location":{{"lat":{lat},"lon":{lon}}},"radius_m":{radius_m}}}"#
    );

    let res = app.clone().oneshot(post_accounts(&cookie, &body)).await?;
    assert_eq!(res.status(), StatusCode::CREATED);
    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let created: serde_json::Value = serde_json::from_slice(&bytes)?;

    let pub_lat = created["public_pos"]["lat"].as_f64().context("pub lat")?;
    let pub_lon = created["public_pos"]["lon"].as_f64().context("pub lon")?;
    // radius_m>0 => public_pos must be jittered, not the exact residence.
    assert_ne!(pub_lat, lat, "radius>0 must obfuscate latitude");
    assert_ne!(pub_lon, lon, "radius>0 must obfuscate longitude");
    assert!(created.get("location").is_none());

    // DB stores the real residence and radius — never the jittered public_pos.
    let (db_lat, db_lon, radius): (Option<f64>, Option<f64>, i64) = sqlx::query_as(
        "SELECT location_lat, location_lon, radius_m FROM domain_accounts WHERE id = $1",
    )
    .bind(id)
    .fetch_one(&pool)
    .await
    .expect("radius account row");
    assert!(
        (db_lat.unwrap() - lat).abs() < 1e-9,
        "DB must store the real residence latitude"
    );
    assert!(
        (db_lon.unwrap() - lon).abs() < 1e-9,
        "DB must store the real residence longitude"
    );
    assert_eq!(radius, 500);

    // Loader reproduces the exact same deterministic jitter (stable by id).
    let reloaded = load_accounts_from_postgres(&pool)
        .await
        .expect("reload accounts");
    let internal = reloaded.get(id).expect("radius account reloaded");
    let pos = internal.public.public_pos.as_ref().expect("public_pos");
    assert!(
        (pos.lat - pub_lat).abs() < 1e-9,
        "loader must reproduce the POST jitter latitude"
    );
    assert!(
        (pos.lon - pub_lon).abs() < 1e-9,
        "loader must reproduce the POST jitter longitude"
    );

    assert!(!in_dir.join("demo.accounts.jsonl").exists());

    clean(&pool).await;
    Ok(())
}

/// Negative proof: a primary-key collision at the database level returns 409,
/// does not overwrite the existing row, does not mutate the cache, and writes
/// no JSONL. The pre-seeded row is intentionally NOT in the in-memory cache so
/// the conflict is surfaced by the PostgreSQL constraint, not the cache check.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_account_create_duplicate_id_conflicts_without_side_effects() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let id = DUP_ID;
    sqlx::query(
        "INSERT INTO domain_accounts \
            (id, kind, title, mode, radius_m, role, public_payload, private_payload) \
         VALUES ($1, 'garnrolle', 'Existing', 'verortet', 0, 'weber', '{}'::jsonb, '{}'::jsonb)",
    )
    .bind(id)
    .execute(&pool)
    .await
    .expect("seed existing domain_accounts row");

    let (app, cookie, state) = postgres_write_app(pool.clone(), "writepath-admin-3").await?;

    let body =
        format!(r#"{{"id":"{id}","title":"Conflicting","location":{{"lat":1.0,"lon":2.0}}}}"#);
    let res = app.clone().oneshot(post_accounts(&cookie, &body)).await?;
    assert_eq!(res.status(), StatusCode::CONFLICT);

    // Existing row must be untouched (plain INSERT, no silent overwrite).
    let (title,): (String,) = sqlx::query_as("SELECT title FROM domain_accounts WHERE id = $1")
        .bind(id)
        .fetch_one(&pool)
        .await
        .expect("existing row still present");
    assert_eq!(
        title, "Existing",
        "account create must never overwrite an existing account"
    );

    // Cache not mutated and JSONL not written on a failed insert.
    assert!(
        state.accounts.read().await.get(id).is_none(),
        "failed DB insert must not populate the in-memory cache"
    );
    assert!(
        !in_dir.join("demo.accounts.jsonl").exists(),
        "failed DB insert must not append JSONL"
    );

    clean(&pool).await;
    Ok(())
}

// ── TODO 2A: normalized account-email uniqueness ─────────────────────────────
//
// These proofs live in the account-create write-path suite so they run in the
// existing `db-domain-account-write-path-proof` CI job (no separate proof job).

const EMAIL_ALPHA: &str = "alpha@example.invalid";
const EMAIL_BETA: &str = "beta@example.invalid";

fn email_fixture_id(n: u32) -> String {
    format!("aaaaaaaa-aaaa-4aaa-8aaa-{n:012}")
}

/// A minimal validated, JSONL-shaped account record for the write-path insert.
fn account_record(id: &str, email: Option<&str>) -> serde_json::Value {
    let mut m = serde_json::Map::new();
    m.insert("id".into(), serde_json::json!(id));
    m.insert("type".into(), serde_json::json!("garnrolle"));
    m.insert("title".into(), serde_json::json!("Email Unique Fixture"));
    if let Some(e) = email {
        m.insert("email".into(), serde_json::json!(e));
    }
    serde_json::Value::Object(m)
}

async fn try_insert(pool: &PgPool, id: &str, email: Option<&str>) -> Result<(), AccountWriteError> {
    insert_account_from_jsonl_record(pool, &account_record(id, email)).await
}

/// Direct write-path proof: the normalized unique index is the boundary. Exact,
/// case- and whitespace-variant duplicates all surface as `DuplicateEmail`
/// (no in-memory precheck), exactly one row survives, while a distinct email,
/// a missing email and after-trim-empty emails are allowed.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn insert_account_classifies_duplicate_email_and_allows_empties() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    try_insert(&pool, &email_fixture_id(20), Some(EMAIL_ALPHA))
        .await
        .expect("first non-empty email must insert");
    for (n, variant) in [
        (21u32, EMAIL_ALPHA),
        (22, "ALPHA@example.invalid"),
        (23, "  alpha@example.invalid  "),
    ] {
        let err = try_insert(&pool, &email_fixture_id(n), Some(variant))
            .await
            .expect_err("normalized duplicate email must be rejected by the DB");
        assert!(
            matches!(err, AccountWriteError::DuplicateEmail),
            "expected DuplicateEmail (constraint-classified), got {err:?}"
        );
    }

    let (count,): (i64,) =
        sqlx::query_as("SELECT count(*) FROM domain_accounts WHERE lower(btrim(email)) = $1")
            .bind(EMAIL_ALPHA)
            .fetch_one(&pool)
            .await
            .expect("count by normalized email");
    assert_eq!(count, 1, "the unique index must leave exactly one winner");

    // Distinct email is independent; missing and after-trim-empty are allowed
    // (the mapper folds "" and "   " to NULL, so multiple coexist).
    try_insert(&pool, &email_fixture_id(24), Some(EMAIL_BETA))
        .await
        .expect("distinct email must insert");
    try_insert(&pool, &email_fixture_id(25), None)
        .await
        .expect("missing email must insert");
    try_insert(&pool, &email_fixture_id(26), Some(""))
        .await
        .expect("empty-string email must insert as NULL");
    try_insert(&pool, &email_fixture_id(27), Some("   "))
        .await
        .expect("whitespace-only email must insert as NULL");

    clean(&pool).await;
    Ok(())
}

/// Route-level proof: a row that exists in PostgreSQL but NOT in the in-memory
/// cache forces the conflict to be surfaced by the unique index, not the cache
/// precheck. `POST /accounts` returns 409 and leaves the existing row, the cache
/// and JSONL untouched.
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

    let existing_id = email_fixture_id(10);
    let new_id = email_fixture_id(11);

    // Seed a row directly in PostgreSQL (deliberately absent from the cache).
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

    let body = format!(
        r#"{{"id":"{new_id}","title":"Conflicting","location":{{"lat":1.0,"lon":2.0}},"email":"{EMAIL_ALPHA}"}}"#
    );
    let res = app.clone().oneshot(post_accounts(&cookie, &body)).await?;
    assert_eq!(
        res.status(),
        StatusCode::CONFLICT,
        "duplicate normalized email must map to 409 via the DB constraint"
    );

    // Existing row untouched.
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

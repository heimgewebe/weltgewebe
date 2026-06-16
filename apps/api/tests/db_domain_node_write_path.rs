//! Integration proof: OPT-ARC-001 Phase E-B node-patch PostgreSQL write path.
//!
//! Proves that, when `domain_read_source=postgres` and
//! `domain_node_write_source=postgres`, `PATCH /nodes/{id}` writes the patch to
//! `domain_nodes`, updates the in-memory node cache, never touches JSONL, and
//! that `load_nodes_from_postgres` reconstructs the same projection.
//!
//! Phase scope: node patches only. Account writes, edge writes, step-up email
//! persistence and WebAuthn user-id writeback persistence are NOT implemented.
//!
//! Run with:
//!   DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
//!     cargo test --locked -p weltgewebe-api --test db_domain_node_write_path \
//!     -- --include-ignored --test-threads=1
//!
//! Notes:
//! - Tests are ignored by default to keep offline paths green.
//! - DATABASE_URL must point to direct PostgreSQL (not PgBouncer at :6432).
//! - Fixture rows use the `writepath-node-` id prefix and are cleaned before/after.

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
    domain_db::{load_nodes_from_postgres, patch_node_in_postgres, NodePatchInput},
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

const NODE_A: &str = "writepath-node-aaaaaaaaa";
const NODE_B: &str = "writepath-node-bbbbbbbbb";
const NODE_404: &str = "writepath-node-not-found";
const NODE_NULL_LOC: &str = "writepath-node-null-location";
const NODE_BAD_PAYLOAD: &str = "writepath-node-bad-payload";

async fn clean(pool: &PgPool) {
    pool.execute("DELETE FROM domain_nodes WHERE id LIKE 'writepath-node-%'")
        .await
        .expect("clean domain_nodes fixtures");
}

async fn seed_node(pool: &PgPool, id: &str, info: Option<&str>, steckbrief: Option<&str>) {
    let payload = match (info, steckbrief) {
        (Some(i), Some(s)) => format!(r#"{{"info": "{i}", "steckbrief": "{s}"}}"#),
        (Some(i), None) => format!(r#"{{"info": "{i}"}}"#),
        (None, Some(s)) => format!(r#"{{"steckbrief": "{s}"}}"#),
        (None, None) => "{}".to_string(),
    };
    sqlx::query(
        "INSERT INTO domain_nodes (id, kind, title, lat, lon, payload) \
         VALUES ($1, 'test', 'Test Node', 53.5, 10.0, $2::jsonb)",
    )
    .bind(id)
    .bind(&payload)
    .execute(pool)
    .await
    .expect("seed domain_nodes row");
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

async fn postgres_write_app(pool: PgPool, operator_id: &str) -> Result<(Router, String, ApiState)> {
    let mut accounts = AccountStore::new();
    accounts.insert(admin_operator(operator_id));

    let nodes = load_nodes_from_postgres(&pool)
        .await
        .context("load nodes for test")?;

    let config = AppConfig {
        fade_days: 7,
        ron_days: 84,
        anonymize_opt_in: true,
        delegation_expire_days: 28,
        domain_read_source: DomainReadSource::Postgres,
        domain_account_write_source: DomainAccountWriteSource::Postgres,
        domain_node_write_source: DomainNodeWriteSource::Postgres,
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
        nodes: Arc::new(RwLock::new(nodes)),
        nodes_persist: Arc::new(tokio::sync::Mutex::new(())),
        accounts_persist: Arc::new(tokio::sync::Mutex::new(())),
        edges: Arc::new(RwLock::new(weltgewebe_api::state::OrderedCache::new())),
        rate_limiter,
        mailer: None,
        webauthn: None,
        passkey_registrations: Default::default(),
        passkey_registration_grants: Default::default(),
        passkey_authentications: Default::default(),
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

fn patch_node_req(cookie: &str, id: &str, json_body: &str) -> Request<body::Body> {
    Request::builder()
        .method("PATCH")
        .uri(format!("/nodes/{id}"))
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .header("Cookie", cookie)
        .body(body::Body::from(json_body.to_string()))
        .unwrap()
}

/// A. PostgreSQL patch persists and reload sees the change.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_node_patch_persists_and_reload_sees_change() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;
    seed_node(&pool, NODE_A, None, None).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, state) = postgres_write_app(pool.clone(), "writepath-node-admin-1").await?;

    let res = app
        .clone()
        .oneshot(patch_node_req(&cookie, NODE_A, r#"{"info": "new info"}"#))
        .await?;
    assert_eq!(res.status(), StatusCode::OK);

    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let patched: serde_json::Value = serde_json::from_slice(&bytes)?;
    assert_eq!(patched["id"], NODE_A);
    assert_eq!(patched["info"], "new info");

    // DB row reflects the patch.
    let (payload_text,): (String,) =
        sqlx::query_as("SELECT payload::text FROM domain_nodes WHERE id = $1")
            .bind(NODE_A)
            .fetch_one(&pool)
            .await
            .expect("node row must exist");
    let payload: serde_json::Value = serde_json::from_str(&payload_text)?;
    assert_eq!(
        payload.get("info").and_then(|v| v.as_str()),
        Some("new info")
    );

    // In-memory cache sees the change immediately (read-your-writes).
    {
        let nodes = state.nodes.read().await;
        let node = nodes.get(NODE_A).expect("patched node in cache");
        assert_eq!(node.info.as_deref(), Some("new info"));
    }

    // load_nodes_from_postgres reconstructs the same projection.
    let reloaded = load_nodes_from_postgres(&pool)
        .await
        .context("reload nodes")?;
    let node = reloaded.get(NODE_A).expect("node reloaded from postgres");
    assert_eq!(node.info.as_deref(), Some("new info"));

    clean(&pool).await;
    Ok(())
}

/// B. No JSONL side-effect in PostgreSQL mode.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_node_patch_has_no_jsonl_side_effect() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;
    seed_node(&pool, NODE_B, Some("original"), None).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, _state) = postgres_write_app(pool.clone(), "writepath-node-admin-2").await?;

    let res = app
        .oneshot(patch_node_req(&cookie, NODE_B, r#"{"info": "updated"}"#))
        .await?;
    assert_eq!(res.status(), StatusCode::OK);

    // JSONL nodes file must NOT have been written.
    let nodes_file = in_dir.join("demo.nodes.jsonl");
    assert!(
        !nodes_file.exists(),
        "PostgreSQL write mode must not create or write the JSONL nodes file"
    );

    clean(&pool).await;
    Ok(())
}

/// C. Not-found returns 404.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_node_patch_not_found_returns_404() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, state) = postgres_write_app(pool.clone(), "writepath-node-admin-3").await?;

    let res = app
        .oneshot(patch_node_req(&cookie, NODE_404, r#"{"info": "ghost"}"#))
        .await?;
    assert_eq!(res.status(), StatusCode::NOT_FOUND);

    // Cache not touched.
    assert!(
        state.nodes.read().await.get(NODE_404).is_none(),
        "not-found patch must not insert into cache"
    );

    clean(&pool).await;
    Ok(())
}

/// D. Postgres read + JSONL node write is blocked with 409.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_read_jsonl_node_write_is_blocked() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;
    seed_node(&pool, NODE_A, Some("initial"), None).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let nodes = load_nodes_from_postgres(&pool).await?;

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

    let mut accounts = AccountStore::new();
    accounts.insert(admin_operator("writepath-node-admin-4"));
    let rate_limiter = Arc::new(AuthRateLimiter::new(&config));

    let state = ApiState {
        db_pool: Some(pool.clone()),
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
        nodes: Arc::new(RwLock::new(nodes)),
        nodes_persist: Arc::new(tokio::sync::Mutex::new(())),
        accounts_persist: Arc::new(tokio::sync::Mutex::new(())),
        edges: Arc::new(RwLock::new(weltgewebe_api::state::OrderedCache::new())),
        rate_limiter,
        mailer: None,
        webauthn: None,
        passkey_registrations: Default::default(),
        passkey_registration_grants: Default::default(),
        passkey_authentications: Default::default(),
        passkeys: Default::default(),
    };

    let session = state
        .sessions
        .create("writepath-node-admin-4".to_string(), None)
        .await?;
    let cookie = format!("gewebe_session={}", session.id);

    let app = Router::new()
        .merge(api_router())
        .layer(from_fn_with_state(state.clone(), auth_middleware))
        .layer(axum::middleware::from_fn(require_csrf))
        .with_state(state.clone());

    let res = app
        .oneshot(patch_node_req(&cookie, NODE_A, r#"{"info": "blocked"}"#))
        .await?;
    assert_eq!(res.status(), StatusCode::CONFLICT);

    let body_bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let body_str = String::from_utf8_lossy(&body_bytes);
    assert!(
        body_str.contains("DOMAIN_READ_SOURCE_READ_ONLY"),
        "body must contain DOMAIN_READ_SOURCE_READ_ONLY, got: {body_str}"
    );

    // DB row must be untouched.
    let (payload_text,): (String,) =
        sqlx::query_as("SELECT payload::text FROM domain_nodes WHERE id = $1")
            .bind(NODE_A)
            .fetch_one(&pool)
            .await
            .expect("row still present");
    let payload: serde_json::Value = serde_json::from_str(&payload_text)?;
    assert_eq!(
        payload.get("info").and_then(|v| v.as_str()),
        Some("initial"),
        "blocked patch must not mutate domain_nodes"
    );

    clean(&pool).await;
    Ok(())
}

/// E. steckbrief cleanup in PostgreSQL mode.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_node_patch_removes_steckbrief() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;
    seed_node(&pool, NODE_A, Some("kept"), Some("legacy")).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, _state) = postgres_write_app(pool.clone(), "writepath-node-admin-5").await?;

    // Patch with no info change (no-op for info) — only steckbrief cleanup.
    let res = app
        .oneshot(patch_node_req(&cookie, NODE_A, r#"{}"#))
        .await?;
    assert_eq!(res.status(), StatusCode::OK);

    let (payload_text,): (String,) =
        sqlx::query_as("SELECT payload::text FROM domain_nodes WHERE id = $1")
            .bind(NODE_A)
            .fetch_one(&pool)
            .await
            .expect("node row present");
    let payload: serde_json::Value = serde_json::from_str(&payload_text)?;
    assert!(
        payload.get("steckbrief").is_none(),
        "steckbrief must be removed by patch"
    );
    assert_eq!(
        payload.get("info").and_then(|v| v.as_str()),
        Some("kept"),
        "info must be preserved when not in patch"
    );

    clean(&pool).await;
    Ok(())
}

/// F. JSONL default mode continues to work (compile-only guard).
/// The full JSONL behaviour is covered by existing api_nodes tests.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn jsonl_default_node_patch_compiles_and_routes_correctly() -> Result<()> {
    // This test only verifies that the compile path for JSONL mode is reachable.
    // Actual JSONL semantics are covered by the offline api_nodes test suite.
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    // Write a minimal nodes JSONL so the JSONL handler can open it.
    let nodes_file = in_dir.join("demo.nodes.jsonl");
    std::fs::write(
        &nodes_file,
        r#"{"id":"writepath-node-jsonl-1","kind":"test","title":"T","location":{"lat":53.5,"lon":10.0},"created_at":"2024-01-01T00:00:00Z","updated_at":"2024-01-01T00:00:00Z"}"#,
    )?;

    let config = AppConfig {
        fade_days: 7,
        ron_days: 84,
        anonymize_opt_in: true,
        delegation_expire_days: 28,
        domain_read_source: DomainReadSource::Jsonl,
        domain_account_write_source: DomainAccountWriteSource::Jsonl,
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

    let mut accounts = AccountStore::new();
    accounts.insert(admin_operator("writepath-node-admin-6"));
    let rate_limiter = Arc::new(AuthRateLimiter::new(&config));

    let nodes = weltgewebe_api::routes::nodes::load_nodes().await;

    let state = ApiState {
        db_pool: None,
        db_pool_configured: false,
        nats_client: None,
        nats_configured: false,
        config,
        metrics: test_metrics(),
        sessions: SessionBackend::new_in_memory(),
        challenges: Default::default(),
        tokens: weltgewebe_api::auth::tokens::TokenStore::new(),
        step_up_tokens: weltgewebe_api::auth::step_up_tokens::StepUpTokenStore::new(),
        accounts: Arc::new(RwLock::new(accounts)),
        nodes: Arc::new(RwLock::new(nodes)),
        nodes_persist: Arc::new(tokio::sync::Mutex::new(())),
        accounts_persist: Arc::new(tokio::sync::Mutex::new(())),
        edges: Arc::new(RwLock::new(weltgewebe_api::state::OrderedCache::new())),
        rate_limiter,
        mailer: None,
        webauthn: None,
        passkey_registrations: Default::default(),
        passkey_registration_grants: Default::default(),
        passkey_authentications: Default::default(),
        passkeys: Default::default(),
    };

    let session = state
        .sessions
        .create("writepath-node-admin-6".to_string(), None)
        .await?;
    let cookie = format!("gewebe_session={}", session.id);

    let app = Router::new()
        .merge(api_router())
        .layer(from_fn_with_state(state.clone(), auth_middleware))
        .layer(axum::middleware::from_fn(require_csrf))
        .with_state(state.clone());

    let res = app
        .oneshot(patch_node_req(
            &cookie,
            "writepath-node-jsonl-1",
            r#"{"info": "via jsonl"}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let patched: serde_json::Value = serde_json::from_slice(&bytes)?;
    assert_eq!(patched["info"], "via jsonl");

    clean(&pool).await;
    Ok(())
}

/// G. Mapping failure (NULL lat/lon) does not commit — payload stays unchanged.
///
/// Inserts a row with NULL lat and lon (schema allows it). `patch_node_in_postgres`
/// must fail with `NodeWriteError::Mapping` before committing, leaving the payload
/// untouched.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_node_patch_mapping_failure_does_not_commit() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    // Seed a row with NULL lat/lon and a known payload.
    sqlx::query(
        "INSERT INTO domain_nodes (id, kind, title, lat, lon, payload) \
         VALUES ($1, 'test', 'Null Loc', NULL, NULL, '{\"info\":\"original\"}'::jsonb)",
    )
    .bind(NODE_NULL_LOC)
    .execute(&pool)
    .await
    .expect("seed null-location node");

    let result = patch_node_in_postgres(
        &pool,
        NODE_NULL_LOC,
        NodePatchInput {
            info: Some(Some("changed".to_string())),
        },
    )
    .await;

    // Must fail with a Mapping error — NULL location cannot be projected.
    let err = match result {
        Err(e) => e,
        Ok(_) => panic!("patch must fail for a node with NULL location, but returned Ok"),
    };
    let err_str = err.to_string();
    assert!(
        err_str.contains("failed to map"),
        "expected Mapping error, got: {err_str}"
    );

    // DB payload must be unchanged — no commit should have occurred.
    let (payload_text,): (String,) =
        sqlx::query_as("SELECT payload::text FROM domain_nodes WHERE id = $1")
            .bind(NODE_NULL_LOC)
            .fetch_one(&pool)
            .await
            .expect("row still present");
    let payload: serde_json::Value = serde_json::from_str(&payload_text)?;
    assert_eq!(
        payload.get("info").and_then(|v| v.as_str()),
        Some("original"),
        "payload must not have been modified by a failed patch"
    );

    clean(&pool).await;
    Ok(())
}

/// H. Non-object payload is rejected without committing.
///
/// Inserts a row with an array payload `[]` (valid JSONB, but not an object).
/// `patch_node_in_postgres` must return a Mapping error before any mutation.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_node_patch_non_object_payload_is_rejected_without_commit() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    // Seed a row with an array payload (non-object JSONB — data corruption scenario).
    sqlx::query(
        "INSERT INTO domain_nodes (id, kind, title, lat, lon, payload) \
         VALUES ($1, 'test', 'Bad Payload', 53.5, 10.0, '[]'::jsonb)",
    )
    .bind(NODE_BAD_PAYLOAD)
    .execute(&pool)
    .await
    .expect("seed non-object payload node");

    let result = patch_node_in_postgres(
        &pool,
        NODE_BAD_PAYLOAD,
        NodePatchInput {
            info: Some(Some("inject".to_string())),
        },
    )
    .await;

    let err = match result {
        Err(e) => e,
        Ok(_) => panic!("patch must fail for a node with non-object payload, but returned Ok"),
    };
    let err_str = err.to_string();
    assert!(
        err_str.contains("failed to map"),
        "expected Mapping error, got: {err_str}"
    );

    // DB payload must be unchanged.
    let (payload_text,): (String,) =
        sqlx::query_as("SELECT payload::text FROM domain_nodes WHERE id = $1")
            .bind(NODE_BAD_PAYLOAD)
            .fetch_one(&pool)
            .await
            .expect("row still present");
    assert_eq!(
        payload_text.trim(),
        "[]",
        "non-object payload must be untouched"
    );

    clean(&pool).await;
    Ok(())
}

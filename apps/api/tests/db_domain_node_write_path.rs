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
    domain_db::{
        delete_node_with_edges_in_postgres, insert_domain_node, load_nodes_from_postgres,
        patch_node_in_postgres, replace_node_in_postgres, NodeCreateError, NodePatchInput,
        NodeWriteError,
    },
    middleware::{auth::auth_middleware, csrf::require_csrf},
    routes::{
        accounts::{AccountInternal, AccountPublic, GarnrolleMapState},
        api_router,
        nodes::{Location, Node},
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
    pool.execute("DELETE FROM domain_edges WHERE id LIKE 'writepath-edge-%'")
        .await
        .expect("clean domain_edges fixtures");
    pool.execute("DELETE FROM domain_nodes WHERE id LIKE 'writepath-node-%'")
        .await
        .expect("clean domain_nodes fixtures");
    pool.execute("DELETE FROM domain_accounts WHERE id LIKE 'writepath-node-%'")
        .await
        .expect("clean colliding domain_accounts fixtures");
}

/// Node-create tests generate server-owned UUID ids (no `writepath-node-`
/// prefix), so their cleanup must not rely on the prefix-scoped `clean`.
async fn clean_all_nodes(pool: &PgPool) {
    // Derived Fäden can point at generated node ids. Remove them first so a
    // repeated integration run starts from one coherent graph state.
    pool.execute("DELETE FROM domain_edges")
        .await
        .expect("clean all domain_edges rows");
    pool.execute("DELETE FROM domain_nodes")
        .await
        .expect("clean all domain_nodes rows");
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
            map_state: GarnrolleMapState::NotOnMap,
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
    let operator = admin_operator(operator_id);
    sqlx::query(
        "INSERT INTO domain_accounts (id, kind, title, mode, role, disabled, webauthn_user_id) \
         VALUES ($1, 'garnrolle', $2, 'not_on_map', 'admin', FALSE, $3::uuid) \
         ON CONFLICT (id) DO UPDATE SET \
             kind = EXCLUDED.kind, title = EXCLUDED.title, mode = EXCLUDED.mode, \
             role = EXCLUDED.role, disabled = FALSE, webauthn_user_id = EXCLUDED.webauthn_user_id",
    )
    .bind(operator_id)
    .bind(&operator.public.title)
    .bind(operator.webauthn_user_id.to_string())
    .execute(&pool)
    .await
    .context("seed canonical PostgreSQL operator account")?;

    let mut accounts = AccountStore::new();
    accounts.insert(operator);

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
        domain_edge_write_source: DomainEdgeWriteSource::Postgres,
        passkey_credential_source: weltgewebe_api::config::PasskeyCredentialSource::InMemory,
        auth_public_login: false,
        auth_cookie_secure: weltgewebe_api::config::auth_cookie_secure_env_override()
            .unwrap_or(true),
        app_base_url: None,
        auth_trusted_proxies: None,
        auth_allow_emails: None,
        auth_allow_email_domains: None,
        auth_auto_provision: false,
        auth_auto_provision_role: weltgewebe_api::config::AutoProvisionRole::Gast,
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

    let (app, cookie, state) =
        postgres_write_app(pool.clone(), "10000000-0000-0000-0000-000000000001").await?;

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

    let (app, cookie, _state) =
        postgres_write_app(pool.clone(), "10000000-0000-0000-0000-000000000002").await?;

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

    let (app, cookie, state) =
        postgres_write_app(pool.clone(), "10000000-0000-0000-0000-000000000003").await?;

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
        passkey_credential_source: weltgewebe_api::config::PasskeyCredentialSource::InMemory,
        auth_public_login: false,
        auth_cookie_secure: weltgewebe_api::config::auth_cookie_secure_env_override()
            .unwrap_or(true),
        app_base_url: None,
        auth_trusted_proxies: None,
        auth_allow_emails: None,
        auth_allow_email_domains: None,
        auth_auto_provision: false,
        auth_auto_provision_role: weltgewebe_api::config::AutoProvisionRole::Gast,
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
    accounts.insert(admin_operator("10000000-0000-0000-0000-000000000004"));
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
        .create("10000000-0000-0000-0000-000000000004".to_string(), None)
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

    let (app, cookie, _state) =
        postgres_write_app(pool.clone(), "10000000-0000-0000-0000-000000000005").await?;

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
        passkey_credential_source: weltgewebe_api::config::PasskeyCredentialSource::InMemory,
        auth_public_login: false,
        auth_cookie_secure: weltgewebe_api::config::auth_cookie_secure_env_override()
            .unwrap_or(true),
        app_base_url: None,
        auth_trusted_proxies: None,
        auth_allow_emails: None,
        auth_allow_email_domains: None,
        auth_auto_provision: false,
        auth_auto_provision_role: weltgewebe_api::config::AutoProvisionRole::Gast,
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

// ── POST /nodes PostgreSQL write path ───────────────────────────────────────

fn post_node_req(cookie: &str, json_body: &str) -> Request<body::Body> {
    Request::post("/nodes")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .header("Cookie", cookie)
        .body(body::Body::from(json_body.to_string()))
        .unwrap()
}

/// I. `POST /nodes` persists a transactional insert, updates the cache after
/// persistence, never appends JSONL, and `load_nodes_from_postgres`
/// reconstructs the same node (including the new `address` field) after a
/// simulated restart.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_node_create_persists_and_reload_sees_it() -> Result<()> {
    const ACTOR_ID: &str = "10000000-0000-0000-0000-000000000003";

    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean_all_nodes(&pool).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, state) = postgres_write_app(pool.clone(), ACTOR_ID).await?;

    let body = r#"{"title":"New Node","kind":"Werkstatt","address":"Musterstraße 1, 12345 Musterstadt","location":{"lat":53.55,"lon":9.99},"summary":"Short summary","tags":["a","b"]}"#;
    let res = app.clone().oneshot(post_node_req(&cookie, body)).await?;
    assert_eq!(res.status(), StatusCode::CREATED);

    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let created: serde_json::Value = serde_json::from_slice(&bytes)?;
    let id = created["id"].as_str().context("id present")?.to_string();
    assert!(
        uuid::Uuid::parse_str(&id).is_ok(),
        "server must generate a UUID id"
    );
    assert_eq!(created["title"], "New Node");
    assert_eq!(created["kind"], "Werkstatt");
    assert_eq!(created["address"], "Musterstraße 1, 12345 Musterstadt");
    assert_eq!(created["location"]["lat"], 53.55);
    assert_eq!(created["location"]["lon"], 9.99);
    assert!(created["created_at"].as_str().is_some());
    assert_eq!(created["created_at"], created["updated_at"]);

    // DB row: explicit columns plus JSONB payload (summary, tags, address).
    let (kind, title, lat, lon): (String, String, Option<f64>, Option<f64>) =
        sqlx::query_as("SELECT kind, title, lat, lon FROM domain_nodes WHERE id = $1")
            .bind(&id)
            .fetch_one(&pool)
            .await
            .expect("node row must exist after create");
    assert_eq!(kind, "Werkstatt");
    assert_eq!(title, "New Node");
    assert!((lat.unwrap() - 53.55).abs() < 1e-9);
    assert!((lon.unwrap() - 9.99).abs() < 1e-9);

    let (payload_text,): (String,) =
        sqlx::query_as("SELECT payload::text FROM domain_nodes WHERE id = $1")
            .bind(&id)
            .fetch_one(&pool)
            .await
            .expect("payload readable");
    let payload: serde_json::Value = serde_json::from_str(&payload_text)?;
    assert_eq!(
        payload.get("address").and_then(|v| v.as_str()),
        Some("Musterstraße 1, 12345 Musterstadt")
    );
    assert_eq!(
        payload.get("summary").and_then(|v| v.as_str()),
        Some("Short summary")
    );
    assert_eq!(
        payload.get("tags").and_then(|v| v.as_array()).map(Vec::len),
        Some(2)
    );

    // The same Webungsaktion must also create exactly one durable derived
    // Faden in the configured PostgreSQL edge store.
    let (edge_source, edge_target, edge_kind): (String, String, String) = sqlx::query_as(
        "SELECT source_id, target_id, edge_kind FROM domain_edges WHERE target_id = $1",
    )
    .bind(&id)
    .fetch_one(&pool)
    .await
    .expect("derived Faden must exist after node create");
    assert_eq!(edge_source, ACTOR_ID);
    assert_eq!(edge_target, id);
    assert_eq!(edge_kind, "reference");

    // JSONL must NOT be appended in PostgreSQL write mode.
    let nodes_file = in_dir.join("demo.nodes.jsonl");
    assert!(
        !nodes_file.exists(),
        "PostgreSQL write mode must not create or write the JSONL nodes file"
    );

    // In-memory cache contains the node immediately (read-your-writes).
    {
        let nodes = state.nodes.read().await;
        let node = nodes.get(&id).expect("created node present in cache");
        assert_eq!(node.title, "New Node");
        assert_eq!(
            node.address.as_deref(),
            Some("Musterstraße 1, 12345 Musterstadt")
        );
    }

    // Simulated restart: reload from PostgreSQL alone reconstructs the node.
    let reloaded = load_nodes_from_postgres(&pool)
        .await
        .expect("reload nodes from postgres");
    let node = reloaded.get(&id).expect("node reloaded from postgres");
    assert_eq!(node.title, "New Node");
    assert_eq!(node.kind, "Werkstatt");
    assert_eq!(
        node.address.as_deref(),
        Some("Musterstraße 1, 12345 Musterstadt")
    );
    assert_eq!(node.summary.as_deref(), Some("Short summary"));
    assert_eq!(node.tags, vec!["a".to_string(), "b".to_string()]);
    assert!((node.location.lat - 53.55).abs() < 1e-9);
    assert!((node.location.lon - 9.99).abs() < 1e-9);

    clean_all_nodes(&pool).await;
    Ok(())
}

/// J. An account-scoped operation survives a simulated API restart. The first
/// request returns 201; the same semantic request from a newly built app returns
/// the existing node with 200; changed data under the same key returns 409.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_node_create_operation_replays_after_restart() -> Result<()> {
    const ACTOR_ID: &str = "20000000-0000-0000-0000-000000000001";
    const OPERATION_ID: &str = "30000000-0000-0000-0000-000000000001";

    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean_all_nodes(&pool).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);
    let request_body = format!(
        r#"{{"title":"Postgres Retry Node","kind":"Werkstatt","address":"Musterstraße 1","location":{{"lat":53.55,"lon":9.99}},"summary":"durable","operation_id":"{OPERATION_ID}"}}"#
    );

    let (first_app, first_cookie, _) = postgres_write_app(pool.clone(), ACTOR_ID).await?;
    let first_attempt = first_app
        .clone()
        .oneshot(post_node_req(&first_cookie, &request_body));
    let second_attempt = first_app
        .clone()
        .oneshot(post_node_req(&first_cookie, &request_body));
    let (first, second) = tokio::join!(first_attempt, second_attempt);
    let first = first?;
    let second = second?;
    let first_status = first.status();
    let second_status = second.status();
    assert!(
        (first_status == StatusCode::CREATED && second_status == StatusCode::OK)
            || (first_status == StatusCode::OK && second_status == StatusCode::CREATED),
        "parallel PostgreSQL retries must produce one 201 and one 200, got {first_status} and {second_status}"
    );
    let first_bytes = body::to_bytes(first.into_body(), usize::MAX).await?;
    let second_bytes = body::to_bytes(second.into_body(), usize::MAX).await?;
    let first_node: serde_json::Value = serde_json::from_slice(&first_bytes)?;
    let second_node: serde_json::Value = serde_json::from_slice(&second_bytes)?;
    assert_eq!(first_node["id"], second_node["id"]);
    let first_id = first_node["id"].as_str().context("created node id")?;

    // New app state and newly loaded PostgreSQL cache simulate an API restart.
    let (restarted_app, restarted_cookie, restarted_state) =
        postgres_write_app(pool.clone(), ACTOR_ID).await?;
    let replay = restarted_app
        .clone()
        .oneshot(post_node_req(&restarted_cookie, &request_body))
        .await?;
    assert_eq!(replay.status(), StatusCode::OK);
    let replay_bytes = body::to_bytes(replay.into_body(), usize::MAX).await?;
    let replay_node: serde_json::Value = serde_json::from_slice(&replay_bytes)?;
    assert_eq!(replay_node["id"], first_id);
    assert_eq!(restarted_state.nodes.read().await.len(), 1);

    let changed_body = format!(
        r#"{{"title":"Changed Retry Node","kind":"Werkstatt","address":"Musterstraße 1","location":{{"lat":53.55,"lon":9.99}},"summary":"durable","operation_id":"{OPERATION_ID}"}}"#
    );
    let conflict = restarted_app
        .oneshot(post_node_req(&restarted_cookie, &changed_body))
        .await?;
    assert_eq!(conflict.status(), StatusCode::CONFLICT);

    let (count, actor, operation): (i64, Option<String>, Option<String>) = sqlx::query_as(
        "SELECT count(*), min(create_actor_id), min(create_operation_id) FROM domain_nodes",
    )
    .fetch_one(&pool)
    .await?;
    assert_eq!(count, 1);
    assert_eq!(actor.as_deref(), Some(ACTOR_ID));
    assert_eq!(operation.as_deref(), Some(OPERATION_ID));

    let (edge_count, edge_source, edge_target): (i64, Option<String>, Option<String>) =
        sqlx::query_as("SELECT count(*), min(source_id), min(target_id) FROM domain_edges")
            .fetch_one(&pool)
            .await?;
    assert_eq!(edge_count, 1, "retries must project exactly one Faden");
    assert_eq!(edge_source.as_deref(), Some(ACTOR_ID));
    assert_eq!(edge_target.as_deref(), Some(first_id));

    clean_all_nodes(&pool).await;
    Ok(())
}

/// K. Invalid create payloads (missing required fields, out-of-bounds
/// coordinates) return a stable 400 and never touch the database.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_node_create_rejects_invalid_payload_without_side_effects() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean_all_nodes(&pool).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, state) =
        postgres_write_app(pool.clone(), "10000000-0000-0000-0000-000000000004").await?;

    // Missing required `address`.
    let res = app
        .clone()
        .oneshot(post_node_req(
            &cookie,
            r#"{"title":"No Address","kind":"Werkstatt","location":{"lat":53.5,"lon":10.0}}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    // Out-of-bounds latitude.
    let res = app
        .clone()
        .oneshot(post_node_req(
            &cookie,
            r#"{"title":"Bad Coords","kind":"Werkstatt","address":"Somewhere","location":{"lat":999.0,"lon":10.0}}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    let (count,): (i64,) = sqlx::query_as("SELECT count(*) FROM domain_nodes")
        .fetch_one(&pool)
        .await
        .expect("count domain_nodes rows");
    assert_eq!(count, 0, "invalid create requests must not persist a row");
    assert!(
        state.nodes.read().await.is_empty(),
        "invalid create requests must not populate the cache"
    );

    clean_all_nodes(&pool).await;
    Ok(())
}

/// L. Direct write-path proof: a primary-key collision at the database level
/// is classified as `DuplicateId` and leaves the existing row untouched.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn insert_domain_node_classifies_duplicate_id() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean_all_nodes(&pool).await;

    let id = "writepath-node-dup-id";
    let make_node = |title: &str| Node {
        id: id.to_string(),
        kind: "Werkstatt".to_string(),
        title: title.to_string(),
        created_at: "2026-06-12T10:00:00+00:00".to_string(),
        updated_at: "2026-06-12T10:00:00+00:00".to_string(),
        summary: None,
        info: None,
        tags: vec![],
        address: Some("Somewhere 1".to_string()),
        location: Location {
            lat: 53.5,
            lon: 10.0,
        },
    };

    insert_domain_node(&pool, &make_node("First"), None)
        .await
        .expect("first insert must succeed");

    let err = match insert_domain_node(&pool, &make_node("Second"), None).await {
        Err(error) => error,
        Ok(_) => panic!("duplicate id insert must fail"),
    };
    assert!(
        matches!(err, NodeCreateError::DuplicateId),
        "expected DuplicateId, got {err:?}"
    );

    let (title,): (String,) = sqlx::query_as("SELECT title FROM domain_nodes WHERE id = $1")
        .bind(id)
        .fetch_one(&pool)
        .await
        .expect("existing row still present");
    assert_eq!(
        title, "First",
        "duplicate insert must not overwrite the existing row"
    );

    clean_all_nodes(&pool).await;
    Ok(())
}

/// M. Full replacement preserves technical identity, and deletion removes only
/// node-typed edge projections in the same PostgreSQL transaction.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn replace_and_delete_node_cascade_is_transactional_in_postgres() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    seed_node(&pool, NODE_A, Some("old info"), None).await;
    sqlx::query(
        "INSERT INTO domain_edges \
         (id, source_id, target_id, edge_kind, payload) \
         VALUES \
         ('writepath-edge-node', $1, 'writepath-node-other', 'reference', \
          '{\"source_type\":\"node\",\"target_type\":\"node\"}'::jsonb), \
         ('writepath-edge-account-collision', $1, 'writepath-node-other', 'reference', \
          '{\"source_type\":\"account\",\"target_type\":\"node\"}'::jsonb), \
         ('writepath-edge-role-collision', 'writepath-node-other', $1, 'reference', \
          '{\"source_type\":\"node\",\"target_type\":\"role\"}'::jsonb)",
    )
    .bind(NODE_A)
    .execute(&pool)
    .await
    .context("seed node and account-typed edge fixtures")?;

    let replacement = Node {
        id: NODE_A.to_string(),
        kind: "Werkstatt".to_string(),
        title: "Gemeinsam gepflegt".to_string(),
        created_at: "2026-01-01T00:00:00Z".to_string(),
        updated_at: "2026-07-15T04:00:00Z".to_string(),
        summary: Some("Neue Zusammenfassung".to_string()),
        info: Some("Neue Information".to_string()),
        tags: vec!["commons".to_string()],
        address: Some("Neue Straße 1".to_string()),
        location: Location {
            lat: 53.55,
            lon: 10.05,
        },
    };
    replace_node_in_postgres(&pool, &replacement)
        .await
        .context("replace node")?;

    let row: (String, String, f64, f64, serde_json::Value) = sqlx::query_as(
        "SELECT kind, title, lat, lon, payload \
         FROM domain_nodes WHERE id = $1",
    )
    .bind(NODE_A)
    .fetch_one(&pool)
    .await
    .context("read replaced node")?;
    assert_eq!(row.0, "Werkstatt");
    assert_eq!(row.1, "Gemeinsam gepflegt");
    assert_eq!(row.2, 53.55);
    assert_eq!(row.3, 10.05);
    assert_eq!(row.4["summary"], "Neue Zusammenfassung");
    assert_eq!(row.4["info"], "Neue Information");
    assert_eq!(row.4["address"], "Neue Straße 1");
    assert_eq!(row.4["tags"], serde_json::json!(["commons"]));

    let mut removed = delete_node_with_edges_in_postgres(&pool, NODE_A)
        .await
        .context("delete node with projections")?;
    removed.sort();
    assert_eq!(removed, vec!["writepath-edge-node".to_string()]);

    let node_exists: bool =
        sqlx::query_scalar("SELECT EXISTS (SELECT 1 FROM domain_nodes WHERE id = $1)")
            .bind(NODE_A)
            .fetch_one(&pool)
            .await?;
    assert!(!node_exists);

    let node_edge_exists: bool = sqlx::query_scalar(
        "SELECT EXISTS (SELECT 1 FROM domain_edges WHERE id = 'writepath-edge-node')",
    )
    .fetch_one(&pool)
    .await?;
    assert!(!node_edge_exists);

    let account_edge_exists: bool = sqlx::query_scalar(
        "SELECT EXISTS (SELECT 1 FROM domain_edges \
         WHERE id = 'writepath-edge-account-collision')",
    )
    .fetch_one(&pool)
    .await?;
    assert!(account_edge_exists);

    let role_edge_exists: bool = sqlx::query_scalar(
        "SELECT EXISTS (SELECT 1 FROM domain_edges \
         WHERE id = 'writepath-edge-role-collision')",
    )
    .fetch_one(&pool)
    .await?;
    assert!(role_edge_exists);

    clean(&pool).await;
    Ok(())
}

/// N. Unique untyped legacy edges are classified as node projections and
/// deleted in the same PostgreSQL transaction.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn delete_node_removes_unique_untyped_legacy_postgres_edge() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    seed_node(&pool, NODE_A, Some("kept"), None).await;
    sqlx::query(
        "INSERT INTO domain_edges \
         (id, source_id, target_id, edge_kind, payload) \
         VALUES \
         ('writepath-edge-node', $1, 'writepath-node-other', 'reference', \
          '{\"source_type\":\"node\",\"target_type\":\"node\"}'::jsonb), \
         ('writepath-edge-untyped-legacy', $1, 'writepath-node-other', 'reference', \
          '{\"target_type\":\"node\"}'::jsonb), \
         ('writepath-edge-kept', 'writepath-node-other', 'writepath-node-third', 'reference', \
          '{\"source_type\":\"node\",\"target_type\":\"node\"}'::jsonb)",
    )
    .bind(NODE_A)
    .execute(&pool)
    .await
    .context("seed unique untyped edge fixtures")?;

    let mut removed = delete_node_with_edges_in_postgres(&pool, NODE_A)
        .await
        .context("delete node with legacy edge")?;
    removed.sort();
    assert_eq!(
        removed,
        vec![
            "writepath-edge-node".to_string(),
            "writepath-edge-untyped-legacy".to_string()
        ]
    );

    let node_exists: bool =
        sqlx::query_scalar("SELECT EXISTS (SELECT 1 FROM domain_nodes WHERE id = $1)")
            .bind(NODE_A)
            .fetch_one(&pool)
            .await?;
    assert!(!node_exists);

    for edge_id in ["writepath-edge-node", "writepath-edge-untyped-legacy"] {
        let edge_exists: bool =
            sqlx::query_scalar("SELECT EXISTS (SELECT 1 FROM domain_edges WHERE id = $1)")
                .bind(edge_id)
                .fetch_one(&pool)
                .await?;
        assert!(!edge_exists, "{edge_id} must be removed");
    }
    let kept_exists: bool =
        sqlx::query_scalar("SELECT EXISTS (SELECT 1 FROM domain_edges WHERE id = $1)")
            .bind("writepath-edge-kept")
            .fetch_one(&pool)
            .await?;
    assert!(kept_exists);

    clean(&pool).await;
    Ok(())
}

/// O. Account collisions make untyped endpoints ambiguous and abort
/// PostgreSQL node deletion before any node or edge mutation.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn delete_node_rejects_untyped_postgres_account_collision_without_partial_mutation(
) -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    seed_node(&pool, NODE_A, Some("kept"), None).await;
    sqlx::query(
        "INSERT INTO domain_accounts \
         (id, kind, title, mode, map_state, role, disabled, webauthn_user_id) \
         VALUES ($1, 'garnrolle', 'Colliding Account', NULL, 'not_on_map', 'weber', FALSE, $2::uuid)",
    )
    .bind(NODE_A)
    .bind(uuid::Uuid::new_v4().to_string())
    .execute(&pool)
    .await
    .context("seed colliding account fixture")?;
    sqlx::query(
        "INSERT INTO domain_edges \
         (id, source_id, target_id, edge_kind, payload) \
         VALUES \
         ('writepath-edge-node', $1, 'writepath-node-other', 'reference', \
          '{\"source_type\":\"node\",\"target_type\":\"node\"}'::jsonb), \
         ('writepath-edge-untyped-account-collision', $1, 'writepath-node-other', 'reference', \
          '{\"target_type\":\"node\"}'::jsonb)",
    )
    .bind(NODE_A)
    .execute(&pool)
    .await
    .context("seed ambiguous collision edge fixtures")?;

    let err = match delete_node_with_edges_in_postgres(&pool, NODE_A).await {
        Err(error) => error,
        Ok(_) => panic!("delete must fail for ambiguous edge endpoint collisions"),
    };
    assert!(
        matches!(err, NodeWriteError::InvalidEdgeReference(_)),
        "expected InvalidEdgeReference, got {err:?}"
    );

    let node_exists: bool =
        sqlx::query_scalar("SELECT EXISTS (SELECT 1 FROM domain_nodes WHERE id = $1)")
            .bind(NODE_A)
            .fetch_one(&pool)
            .await?;
    assert!(node_exists);

    for edge_id in [
        "writepath-edge-node",
        "writepath-edge-untyped-account-collision",
    ] {
        let edge_exists: bool =
            sqlx::query_scalar("SELECT EXISTS (SELECT 1 FROM domain_edges WHERE id = $1)")
                .bind(edge_id)
                .fetch_one(&pool)
                .await?;
        assert!(edge_exists, "{edge_id} must remain after failed delete");
    }

    clean(&pool).await;
    Ok(())
}

/// P. A role-typed collision evidence makes untyped endpoints ambiguous and
/// aborts before any node or edge mutation.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn delete_node_rejects_untyped_postgres_role_collision_without_partial_mutation() -> Result<()>
{
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    seed_node(&pool, NODE_A, Some("kept"), None).await;
    sqlx::query(
        "INSERT INTO domain_edges \
         (id, source_id, target_id, edge_kind, payload) \
         VALUES \
         ('writepath-edge-node', $1, 'writepath-node-other', 'reference', \
          '{\"source_type\":\"node\",\"target_type\":\"node\"}'::jsonb), \
         ('writepath-edge-role-evidence', 'writepath-node-other', $1, 'reference', \
          '{\"source_type\":\"node\",\"target_type\":\"role\"}'::jsonb), \
         ('writepath-edge-untyped-role-collision', $1, 'writepath-node-other', 'reference', \
          '{\"target_type\":\"node\"}'::jsonb)",
    )
    .bind(NODE_A)
    .execute(&pool)
    .await
    .context("seed role collision edge fixtures")?;

    let err = match delete_node_with_edges_in_postgres(&pool, NODE_A).await {
        Err(error) => error,
        Ok(_) => panic!("delete must fail for ambiguous role endpoint collision"),
    };
    assert!(
        matches!(err, NodeWriteError::InvalidEdgeReference(_)),
        "expected InvalidEdgeReference, got {err:?}"
    );

    let node_exists: bool =
        sqlx::query_scalar("SELECT EXISTS (SELECT 1 FROM domain_nodes WHERE id = $1)")
            .bind(NODE_A)
            .fetch_one(&pool)
            .await?;
    assert!(node_exists);

    for edge_id in [
        "writepath-edge-node",
        "writepath-edge-role-evidence",
        "writepath-edge-untyped-role-collision",
    ] {
        let edge_exists: bool =
            sqlx::query_scalar("SELECT EXISTS (SELECT 1 FROM domain_edges WHERE id = $1)")
                .bind(edge_id)
                .fetch_one(&pool)
                .await?;
        assert!(edge_exists, "{edge_id} must remain after failed delete");
    }

    clean(&pool).await;
    Ok(())
}

/// Q. Invalid typed endpoints still fail closed before mutation.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn delete_node_rejects_invalid_postgres_edge_type_without_partial_mutation() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    seed_node(&pool, NODE_A, Some("kept"), None).await;
    sqlx::query(
        "INSERT INTO domain_edges \
         (id, source_id, target_id, edge_kind, payload) \
         VALUES \
         ('writepath-edge-node', $1, 'writepath-node-other', 'reference', \
          '{\"source_type\":\"node\",\"target_type\":\"node\"}'::jsonb), \
         ('writepath-edge-invalid-collision', 'writepath-node-other', $1, 'reference', \
          '{\"source_type\":\"node\",\"target_type\":\"group\"}'::jsonb)",
    )
    .bind(NODE_A)
    .execute(&pool)
    .await
    .context("seed invalid edge fixtures")?;

    let err = match delete_node_with_edges_in_postgres(&pool, NODE_A).await {
        Err(error) => error,
        Ok(_) => panic!("delete must fail for invalid edge endpoint type"),
    };
    assert!(
        matches!(err, NodeWriteError::InvalidEdgeReference(_)),
        "expected InvalidEdgeReference, got {err:?}"
    );

    let node_exists: bool =
        sqlx::query_scalar("SELECT EXISTS (SELECT 1 FROM domain_nodes WHERE id = $1)")
            .bind(NODE_A)
            .fetch_one(&pool)
            .await?;
    assert!(node_exists);

    for edge_id in ["writepath-edge-node", "writepath-edge-invalid-collision"] {
        let edge_exists: bool =
            sqlx::query_scalar("SELECT EXISTS (SELECT 1 FROM domain_edges WHERE id = $1)")
                .bind(edge_id)
                .fetch_one(&pool)
                .await?;
        assert!(edge_exists, "{edge_id} must remain after failed delete");
    }

    clean(&pool).await;
    Ok(())
}

//! Integration proof: OPT-ARC-001 Phase E-C edge-create PostgreSQL write path.
//!
//! Proves that, when `domain_read_source=postgres` and
//! `domain_edge_write_source=postgres`, `POST /edges` inserts exactly one row
//! into `domain_edges` (plain INSERT, duplicate id -> 409), updates the
//! in-memory edge cache only after the successful insert, never touches JSONL,
//! and that `load_edges_from_postgres` reconstructs the stored edge including
//! `source_type`, `target_type`, `note` and `created_at`.
//!
//! Phase scope: edge creates only. Step-up email persistence and WebAuthn
//! user-id writeback persistence are NOT implemented; no cutover, no dual-write.
//!
//! Run with:
//!   DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
//!     cargo test --locked -p weltgewebe-api --test db_domain_edge_write_path \
//!     -- --include-ignored --test-threads=1
//!
//! Notes:
//! - Tests are ignored by default to keep offline paths green.
//! - DATABASE_URL must point to direct PostgreSQL (not PgBouncer at :6432).
//! - Fixture rows use the `edec0000-` id prefix (valid UUID hex) and are
//!   cleaned before/after.

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
    domain_db::load_edges_from_postgres,
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

// Fixture ids are UUID-formatted (the create contract validates them) and
// share the `edec0000-` hex prefix so cleanup can target them via LIKE.
const EDGE_ID_A: &str = "edec0000-0000-4000-8000-0000000000a1";
const EDGE_ID_DUP: &str = "edec0000-0000-4000-8000-0000000000d1";
const SOURCE_ID: &str = "edec0000-0000-4000-8000-00000000005a";
const TARGET_ID: &str = "edec0000-0000-4000-8000-00000000005b";

async fn clean(pool: &PgPool) {
    pool.execute("DELETE FROM domain_edges WHERE id LIKE 'edec0000-%'")
        .await
        .expect("clean domain_edges fixtures");
}

async fn fixture_row_count(pool: &PgPool) -> i64 {
    let (count,): (i64,) =
        sqlx::query_as("SELECT COUNT(*) FROM domain_edges WHERE id LIKE 'edec0000-%'")
            .fetch_one(pool)
            .await
            .expect("count domain_edges fixtures");
    count
}

fn test_metrics() -> Metrics {
    Metrics::try_new(BuildInfo {
        version: "test",
        commit: "test",
        build_timestamp: "test",
    })
    .expect("metrics")
}

fn writer_account(id: &str) -> AccountInternal {
    AccountInternal {
        public: AccountPublic {
            id: id.to_string(),
            kind: "garnrolle".to_string(),
            title: format!("Writer {id}"),
            summary: None,
            public_pos: None,
            mode: AccountMode::Verortet,
            radius_m: 0,
            disabled: false,
            tags: vec![],
        },
        role: Role::Weber,
        email: None,
        webauthn_user_id: uuid::Uuid::new_v4(),
    }
}

fn write_path_config(
    domain_read_source: DomainReadSource,
    domain_edge_write_source: DomainEdgeWriteSource,
) -> AppConfig {
    AppConfig {
        fade_days: 7,
        ron_days: 84,
        anonymize_opt_in: true,
        delegation_expire_days: 28,
        domain_read_source,
        domain_account_write_source: DomainAccountWriteSource::Postgres,
        domain_node_write_source: DomainNodeWriteSource::Postgres,
        domain_edge_write_source,
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
    }
}

/// App with a live pool, a writer session, and the given read/edge-write
/// sources. The edge cache is loaded from PostgreSQL, mirroring startup.
async fn edge_write_app(
    pool: PgPool,
    operator_id: &str,
    domain_read_source: DomainReadSource,
    domain_edge_write_source: DomainEdgeWriteSource,
) -> Result<(Router, String, ApiState)> {
    let mut accounts = AccountStore::new();
    accounts.insert(writer_account(operator_id));

    let edges = load_edges_from_postgres(&pool)
        .await
        .context("load edges for test")?;

    let config = write_path_config(domain_read_source, domain_edge_write_source);
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
        edges: Arc::new(RwLock::new(edges)),
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

fn post_edges_req(cookie: &str, json_body: &str) -> Request<body::Body> {
    Request::builder()
        .method("POST")
        .uri("/edges")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .header("Cookie", cookie)
        .body(body::Body::from(json_body.to_string()))
        .unwrap()
}

async fn read_json_body(res: axum::response::Response) -> Result<serde_json::Value> {
    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    Ok(serde_json::from_slice(&bytes)?)
}

async fn read_text_body(res: axum::response::Response) -> Result<String> {
    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    Ok(String::from_utf8_lossy(&bytes).into_owned())
}

fn create_body(id: &str, note: Option<&str>) -> String {
    match note {
        Some(note) => format!(
            r#"{{"id":"{id}","source_id":"{SOURCE_ID}","source_type":"node","target_id":"{TARGET_ID}","target_type":"account","edge_kind":"reference","note":"{note}"}}"#
        ),
        None => format!(
            r#"{{"id":"{id}","source_id":"{SOURCE_ID}","source_type":"node","target_id":"{TARGET_ID}","target_type":"account","edge_kind":"reference"}}"#
        ),
    }
}

/// A. PostgreSQL create persists one row, updates the cache, serves GET, and
/// the loader reconstructs the stored edge (three persistence levels: direct
/// row, cache/GET in-process, `load_edges_from_postgres` roundtrip).
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_edge_create_persists_row_cache_and_loader_roundtrip() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, state) = edge_write_app(
        pool.clone(),
        "writepath-edge-writer-1",
        DomainReadSource::Postgres,
        DomainEdgeWriteSource::Postgres,
    )
    .await?;

    let res = app
        .clone()
        .oneshot(post_edges_req(
            &cookie,
            &create_body(EDGE_ID_A, Some("edge via postgres")),
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::CREATED);
    let v = read_json_body(res).await?;
    assert_eq!(v["id"], EDGE_ID_A);
    assert_eq!(v["note"], "edge via postgres");
    let response_created_at = v["created_at"]
        .as_str()
        .context("created_at must be a string")?
        .to_string();
    let response_created = chrono::DateTime::parse_from_rfc3339(&response_created_at)
        .context("created_at must be RFC3339")?;

    // Level 1: exactly one direct domain_edges row with the expected mapping.
    assert_eq!(fixture_row_count(&pool).await, 1);
    let (source_id, target_id, edge_kind, db_created_at, payload_text): (
        String,
        String,
        String,
        Option<chrono::DateTime<chrono::Utc>>,
        String,
    ) = sqlx::query_as(
        "SELECT source_id, target_id, edge_kind, created_at, payload::text \
         FROM domain_edges WHERE id = $1",
    )
    .bind(EDGE_ID_A)
    .fetch_one(&pool)
    .await
    .expect("created edge row must exist");
    assert_eq!(source_id, SOURCE_ID);
    assert_eq!(target_id, TARGET_ID);
    assert_eq!(edge_kind, "reference");
    // created_at must not silently vanish; PostgreSQL stores microseconds, the
    // response carries nanoseconds, so compare at microsecond precision.
    let db_created_at = db_created_at.context("created_at column must not be NULL")?;
    assert_eq!(
        db_created_at.timestamp_micros(),
        response_created.timestamp_micros(),
        "domain_edges.created_at must carry the server-owned create timestamp"
    );
    let payload: serde_json::Value = serde_json::from_str(&payload_text)?;
    assert_eq!(
        payload.get("source_type").and_then(|v| v.as_str()),
        Some("node")
    );
    assert_eq!(
        payload.get("target_type").and_then(|v| v.as_str()),
        Some("account")
    );
    assert_eq!(
        payload.get("note").and_then(|v| v.as_str()),
        Some("edge via postgres")
    );

    // No JSONL side effect in PostgreSQL mode.
    let edges_file = in_dir.join("demo.edges.jsonl");
    assert!(
        !edges_file.exists(),
        "PostgreSQL write mode must not create or write the JSONL edges file"
    );

    // Level 2: cache holds the edge (read-your-writes) and GET serves it in
    // the same process with the exact response values.
    {
        let cache = state.edges.read().await;
        let cached = cache.get(EDGE_ID_A).context("edge must be in cache")?;
        assert_eq!(
            cached.created_at.as_deref(),
            Some(response_created_at.as_str())
        );
        assert_eq!(cached.note.as_deref(), Some("edge via postgres"));
    }
    let uri = format!("/edges/{EDGE_ID_A}");
    let res = app
        .oneshot(
            Request::get(uri.as_str())
                .header("Host", "localhost")
                .body(body::Body::empty())?,
        )
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let fetched = read_json_body(res).await?;
    assert_eq!(fetched["id"], EDGE_ID_A);
    assert_eq!(fetched["created_at"], response_created_at.as_str());

    // Level 3: load_edges_from_postgres reconstructs the stored edge.
    let reloaded = load_edges_from_postgres(&pool)
        .await
        .context("reload edges")?;
    let edge = reloaded
        .get(EDGE_ID_A)
        .context("edge reloaded from postgres")?;
    assert_eq!(edge.source_id, SOURCE_ID);
    assert_eq!(edge.source_type.as_deref(), Some("node"));
    assert_eq!(edge.target_id, TARGET_ID);
    assert_eq!(edge.target_type.as_deref(), Some("account"));
    assert_eq!(edge.edge_kind, "reference");
    assert_eq!(edge.note.as_deref(), Some("edge via postgres"));
    let reloaded_created = chrono::DateTime::parse_from_rfc3339(
        edge.created_at
            .as_deref()
            .context("reloaded edge must carry created_at")?,
    )?;
    assert_eq!(
        reloaded_created.timestamp_micros(),
        response_created.timestamp_micros(),
        "loader must reconstruct the stored create timestamp"
    );

    clean(&pool).await;
    Ok(())
}

/// B. Absent note stays absent: the payload carries no `note` key (never
/// `note: null`), and the loader reconstructs `note = None`.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_edge_create_omits_note_key_when_absent() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, _state) = edge_write_app(
        pool.clone(),
        "writepath-edge-writer-2",
        DomainReadSource::Postgres,
        DomainEdgeWriteSource::Postgres,
    )
    .await?;

    let res = app
        .oneshot(post_edges_req(&cookie, &create_body(EDGE_ID_A, None)))
        .await?;
    assert_eq!(res.status(), StatusCode::CREATED);

    let (payload_text,): (String,) =
        sqlx::query_as("SELECT payload::text FROM domain_edges WHERE id = $1")
            .bind(EDGE_ID_A)
            .fetch_one(&pool)
            .await
            .expect("created edge row must exist");
    let payload: serde_json::Value = serde_json::from_str(&payload_text)?;
    assert!(
        payload.get("note").is_none(),
        "absent note must be omitted from the payload, never null: {payload_text}"
    );
    assert_eq!(
        payload.get("source_type").and_then(|v| v.as_str()),
        Some("node")
    );
    assert_eq!(
        payload.get("target_type").and_then(|v| v.as_str()),
        Some("account")
    );

    let reloaded = load_edges_from_postgres(&pool).await?;
    let edge = reloaded
        .get(EDGE_ID_A)
        .context("edge reloaded from postgres")?;
    assert_eq!(edge.note, None);

    clean(&pool).await;
    Ok(())
}

/// C. Duplicate id from the database surfaces as 409 (plain INSERT, no
/// ON CONFLICT): the second create leaves exactly one row and no extra cache
/// entry.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_edge_create_duplicate_id_returns_409() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    // Seed the duplicate target directly in the DB so the in-memory cache of a
    // *fresh* app instance knows it too — then bypass the cache by seeding only
    // the DB row after app construction for the genuinely DB-level conflict.
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, state) = edge_write_app(
        pool.clone(),
        "writepath-edge-writer-3",
        DomainReadSource::Postgres,
        DomainEdgeWriteSource::Postgres,
    )
    .await?;

    // Insert the conflicting row AFTER the cache was loaded, so the route's
    // cache-level duplicate check cannot see it and the 409 must come from the
    // database unique violation.
    sqlx::query(
        "INSERT INTO domain_edges (id, source_id, target_id, edge_kind, created_at, payload) \
         VALUES ($1, $2, $3, 'reference', NOW(), '{}'::jsonb)",
    )
    .bind(EDGE_ID_DUP)
    .bind(SOURCE_ID)
    .bind(TARGET_ID)
    .execute(&pool)
    .await
    .expect("seed conflicting edge row");

    let res = app
        .oneshot(post_edges_req(&cookie, &create_body(EDGE_ID_DUP, None)))
        .await?;
    assert_eq!(res.status(), StatusCode::CONFLICT);
    let text = read_text_body(res).await?;
    assert!(text.contains("edge id already exists"), "body: {text}");

    // Still exactly one row; the failed create left no phantom cache entry.
    let (count,): (i64,) = sqlx::query_as("SELECT COUNT(*) FROM domain_edges WHERE id = $1")
        .bind(EDGE_ID_DUP)
        .fetch_one(&pool)
        .await?;
    assert_eq!(count, 1);
    assert!(
        state.edges.read().await.get(EDGE_ID_DUP).is_none(),
        "rejected duplicate create must not insert into the cache"
    );

    clean(&pool).await;
    Ok(())
}

/// D. Postgres read + JSONL edge write is blocked with 409 and writes nothing.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_read_jsonl_edge_write_is_blocked() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, state) = edge_write_app(
        pool.clone(),
        "writepath-edge-writer-4",
        DomainReadSource::Postgres,
        DomainEdgeWriteSource::Jsonl,
    )
    .await?;

    let res = app
        .oneshot(post_edges_req(&cookie, &create_body(EDGE_ID_A, None)))
        .await?;
    assert_eq!(res.status(), StatusCode::CONFLICT);
    let text = read_text_body(res).await?;
    assert!(
        text.contains("DOMAIN_READ_SOURCE_READ_ONLY"),
        "body: {text}"
    );

    // No DB row, no JSONL write, no cache entry.
    assert_eq!(fixture_row_count(&pool).await, 0);
    assert!(
        !in_dir.join("demo.edges.jsonl").exists(),
        "blocked create must not write JSONL"
    );
    assert!(state.edges.read().await.get(EDGE_ID_A).is_none());

    clean(&pool).await;
    Ok(())
}

/// E. Defensive invalid-config state (JSONL read + Postgres edge write, which
/// config load forbids) is rejected with 500 and writes nothing.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn jsonl_read_postgres_edge_write_invalid_config_returns_500() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, state) = edge_write_app(
        pool.clone(),
        "writepath-edge-writer-5",
        DomainReadSource::Jsonl,
        DomainEdgeWriteSource::Postgres,
    )
    .await?;

    let res = app
        .oneshot(post_edges_req(&cookie, &create_body(EDGE_ID_A, None)))
        .await?;
    assert_eq!(res.status(), StatusCode::INTERNAL_SERVER_ERROR);
    let text = read_text_body(res).await?;
    assert!(text.contains("INVALID_DOMAIN_WRITE_CONFIG"), "body: {text}");

    // No DB row, no JSONL write, no cache entry.
    assert_eq!(fixture_row_count(&pool).await, 0);
    assert!(
        !in_dir.join("demo.edges.jsonl").exists(),
        "invalid-config create must not write JSONL"
    );
    assert!(state.edges.read().await.get(EDGE_ID_A).is_none());

    clean(&pool).await;
    Ok(())
}

struct EnvVarGuard {
    key: &'static str,
    old: Option<String>,
}

impl EnvVarGuard {
    fn set(key: &'static str, value: String) -> Self {
        let old = std::env::var(key).ok();
        std::env::set_var(key, value);
        Self { key, old }
    }
}

impl Drop for EnvVarGuard {
    fn drop(&mut self) {
        if let Some(old) = &self.old {
            std::env::set_var(self.key, old);
        } else {
            std::env::remove_var(self.key);
        }
    }
}

/// F. PostgreSQL create rejects when domain_edges is already at MAX_EDGES_CACHE.
#[tokio::test]
#[ignore = "requires DATABASE_URL pointing to direct PostgreSQL"]
#[serial]
async fn postgres_edge_create_rejects_when_cache_limit_reached() -> Result<()> {
    let pool = connect_pool().await;
    run_migrations(&pool).await;
    clean(&pool).await;

    let (base_count,): (i64,) = sqlx::query_as("SELECT COUNT(*) FROM domain_edges")
        .fetch_one(&pool)
        .await?;

    // Set MAX_EDGES_CACHE to exactly one more than the base count.
    let target_limit = base_count + 1;
    let _env_guard = EnvVarGuard::set("MAX_EDGES_CACHE", target_limit.to_string());

    // Insert one fixture to exactly hit the limit.
    sqlx::query(
        "INSERT INTO domain_edges (id, source_id, target_id, edge_kind, created_at, payload) \
         VALUES ($1, $2, $3, 'reference', NOW(), '{}'::jsonb)",
    )
    .bind(EDGE_ID_DUP)
    .bind(SOURCE_ID)
    .bind(TARGET_ID)
    .execute(&pool)
    .await
    .expect("seed limit-filling edge row");

    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, state) = edge_write_app(
        pool.clone(),
        "writepath-edge-writer-limit",
        DomainReadSource::Postgres,
        DomainEdgeWriteSource::Postgres,
    )
    .await?;

    let res = app
        .oneshot(post_edges_req(&cookie, &create_body(EDGE_ID_A, None)))
        .await?;
    assert_eq!(res.status(), StatusCode::CONFLICT);
    let text = read_text_body(res).await?;
    assert!(text.contains("edge cache limit reached"), "body: {text}");

    // No new DB row, no JSONL write, no cache entry.
    let (total_count,): (i64,) = sqlx::query_as("SELECT COUNT(*) FROM domain_edges")
        .fetch_one(&pool)
        .await?;
    assert_eq!(total_count, target_limit);
    assert!(
        !in_dir.join("demo.edges.jsonl").exists(),
        "blocked create must not write JSONL"
    );
    assert!(state.edges.read().await.get(EDGE_ID_A).is_none());

    clean(&pool).await;
    Ok(())
}

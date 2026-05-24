use anyhow::{Context, Result};
use axum::{
    body,
    http::{Request, StatusCode},
    Router,
};
use serial_test::serial;
mod helpers;

use axum::middleware::from_fn_with_state;
use helpers::set_gewebe_in_dir;
use std::sync::Arc;
use tokio::sync::RwLock;
use tower::ServiceExt;
use weltgewebe_api::{
    auth::{
        accounts::AccountStore, rate_limit::AuthRateLimiter, role::Role, session::SessionBackend,
    },
    config::AppConfig,
    middleware::{auth::auth_middleware, csrf::require_csrf},
    routes::{
        accounts::{AccountInternal, AccountMode, AccountPublic},
        api_router,
    },
    state::ApiState,
    telemetry::{BuildInfo, Metrics},
};

async fn test_state() -> Result<ApiState> {
    let metrics = Metrics::try_new(BuildInfo {
        version: "test",
        commit: "test",
        build_timestamp: "test",
    })?;

    let config = AppConfig {
        fade_days: 7,
        ron_days: 84,
        anonymize_opt_in: true,
        delegation_expire_days: 28,
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

    Ok(ApiState {
        db_pool: None,
        db_pool_configured: false,
        nats_client: None,
        nats_configured: false,
        config,
        metrics,
        sessions: SessionBackend::new_in_memory(),
        challenges: Default::default(),
        tokens: weltgewebe_api::auth::tokens::TokenStore::new(),
        step_up_tokens: weltgewebe_api::auth::step_up_tokens::StepUpTokenStore::new(),
        accounts: Arc::new(RwLock::new(AccountStore::new())),
        nodes: Arc::new(tokio::sync::RwLock::new(
            weltgewebe_api::state::OrderedCache::new(),
        )),
        nodes_persist: Arc::new(tokio::sync::Mutex::new(())),
        accounts_persist: Arc::new(tokio::sync::Mutex::new(())),
        edges: Arc::new(tokio::sync::RwLock::new(
            weltgewebe_api::state::OrderedCache::new(),
        )),
        rate_limiter,
        mailer: None,
        webauthn: None,
        passkey_registrations: Default::default(),
        passkey_registration_grants: Default::default(),
        passkeys: Default::default(),
    })
}

fn operator(id: &str, role: Role) -> AccountInternal {
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
        role,
        email: None,
        webauthn_user_id: uuid::Uuid::new_v4(),
    }
}

/// Build a router (auth + csrf wired like prod) with a single operator account
/// and an active session for it. Returns (app, session_cookie, state).
async fn app_with_operator(
    in_dir: &std::path::Path,
    operator_id: &str,
    role: Role,
) -> Result<(Router, String, ApiState)> {
    let mut accounts = AccountStore::new();
    accounts.insert(operator(operator_id, role));

    let mut state = test_state().await?;
    state.accounts = Arc::new(RwLock::new(accounts));

    let session = state
        .sessions
        .create(operator_id.to_string(), None)
        .await
        .expect("session create");
    let cookie = format!("gewebe_session={}", session.id);

    let _ = in_dir; // GEWEBE_IN_DIR is set by the caller via EnvGuard
    let app = Router::new()
        .merge(api_router())
        .layer(from_fn_with_state(state.clone(), auth_middleware))
        .layer(axum::middleware::from_fn(require_csrf))
        .with_state(state.clone());
    Ok((app, cookie, state))
}

fn post_accounts(cookie: Option<&str>, json_body: &str) -> Request<body::Body> {
    let mut builder = Request::post("/accounts")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header("Origin", "http://localhost");
    if let Some(c) = cookie {
        builder = builder.header("Cookie", c);
    }
    builder
        .body(body::Body::from(json_body.to_string()))
        .unwrap()
}

#[tokio::test]
#[serial]
async fn admin_creates_account_persists_and_lists() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, _state) = app_with_operator(&in_dir, "admin1", Role::Admin).await?;

    // POST a new account with an exact public position (radius_m default 0).
    let res = app
        .clone()
        .oneshot(post_accounts(
            Some(&cookie),
            r#"{"title":"Alice","location":{"lat":53.5503,"lon":9.9932},"tags":["real"]}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::CREATED);

    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let created: serde_json::Value = serde_json::from_slice(&bytes)?;
    let new_id = created["id"].as_str().context("id present")?.to_string();
    assert_eq!(created["title"], "Alice");
    // radius_m=0 => public_pos equals the provided location.
    assert_eq!(created["public_pos"]["lat"], 53.5503);
    assert_eq!(created["public_pos"]["lon"], 9.9932);
    // location must never be exposed publicly.
    assert!(created.get("location").is_none());

    // GET /accounts contains the created account.
    let res = app
        .clone()
        .oneshot(Request::get("/accounts").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let list: serde_json::Value = serde_json::from_slice(&bytes)?;
    let found = list
        .as_array()
        .context("array")?
        .iter()
        .any(|a| a["id"] == serde_json::Value::String(new_id.clone()));
    assert!(found, "created account must appear in GET /accounts");

    // Durability: the JSONL file on disk contains the new account id.
    let file = in_dir.join("demo.accounts.jsonl");
    let contents = std::fs::read_to_string(&file)?;
    assert!(
        contents.contains(&new_id),
        "created account must be persisted to JSONL"
    );

    Ok(())
}

#[tokio::test]
#[serial]
async fn weber_cannot_create_account() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, _state) = app_with_operator(&in_dir, "weber1", Role::Weber).await?;

    let res = app
        .oneshot(post_accounts(
            Some(&cookie),
            r#"{"title":"X","location":{"lat":1.0,"lon":2.0}}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::FORBIDDEN);
    Ok(())
}

#[tokio::test]
#[serial]
async fn unauthenticated_cannot_create_account() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, _cookie, _state) = app_with_operator(&in_dir, "admin1", Role::Admin).await?;

    // No session cookie -> 401 (require_admin), CSRF is skipped without a cookie.
    let res = app
        .oneshot(post_accounts(
            None,
            r#"{"title":"X","location":{"lat":1.0,"lon":2.0}}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
    Ok(())
}

#[tokio::test]
#[serial]
async fn invalid_input_returns_400() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, _state) = app_with_operator(&in_dir, "admin1", Role::Admin).await?;

    // Out-of-range latitude.
    let res = app
        .clone()
        .oneshot(post_accounts(
            Some(&cookie),
            r#"{"title":"X","location":{"lat":91.0,"lon":2.0}}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    // Out-of-range longitude.
    let res = app
        .clone()
        .oneshot(post_accounts(
            Some(&cookie),
            r#"{"title":"X","location":{"lat":1.0,"lon":181.0}}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    // Missing location.
    let res = app
        .clone()
        .oneshot(post_accounts(Some(&cookie), r#"{"title":"X"}"#))
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    // Missing title.
    let res = app
        .clone()
        .oneshot(post_accounts(
            Some(&cookie),
            r#"{"location":{"lat":1.0,"lon":2.0}}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    // type=ron is rejected in v0.
    let res = app
        .oneshot(post_accounts(
            Some(&cookie),
            r#"{"title":"X","type":"ron","location":{"lat":1.0,"lon":2.0}}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    Ok(())
}

#[tokio::test]
#[serial]
async fn duplicate_id_returns_409() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, _state) = app_with_operator(&in_dir, "admin1", Role::Admin).await?;

    let id = "11111111-1111-4111-8111-111111111111";
    let body = format!(r#"{{"id":"{id}","title":"First","location":{{"lat":1.0,"lon":2.0}}}}"#);

    let res = app
        .clone()
        .oneshot(post_accounts(Some(&cookie), &body))
        .await?;
    assert_eq!(res.status(), StatusCode::CREATED);

    // Same id again -> 409 Conflict.
    let res = app.oneshot(post_accounts(Some(&cookie), &body)).await?;
    assert_eq!(res.status(), StatusCode::CONFLICT);
    Ok(())
}

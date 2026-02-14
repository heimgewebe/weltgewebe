use anyhow::Result;
use axum::{
    body,
    extract::connect_info::MockConnectInfo,
    http::{Request, StatusCode},
    Router,
};
use serial_test::serial;
use std::{collections::BTreeMap, net::SocketAddr, sync::Arc};
use tokio::sync::RwLock;
use tower::ServiceExt;
use weltgewebe_api::{
    auth::{rate_limit::AuthRateLimiter, session::SessionStore},
    config::AppConfig,
    routes::api_router,
    state::ApiState,
    telemetry::{BuildInfo, Metrics},
};

fn test_state(config: AppConfig) -> Result<ApiState> {
    let metrics = Metrics::try_new(BuildInfo {
        version: "test",
        commit: "test",
        build_timestamp: "test",
    })?;

    let rate_limiter = Arc::new(AuthRateLimiter::new(&config));

    Ok(ApiState {
        db_pool: None,
        db_pool_configured: false,
        nats_client: None,
        nats_configured: false,
        config,
        metrics,
        sessions: SessionStore::new(),
        tokens: weltgewebe_api::auth::tokens::TokenStore::new(),
        accounts: Arc::new(RwLock::new(BTreeMap::new())),
        nodes: Arc::new(tokio::sync::RwLock::new(Vec::new())),
        edges: Arc::new(tokio::sync::RwLock::new(Vec::new())),
        rate_limiter,
        mailer: None,
    })
}

fn app(state: ApiState) -> Router {
    Router::new()
        .merge(api_router())
        .layer(MockConnectInfo(SocketAddr::from(([127, 0, 0, 1], 8080))))
        .with_state(state)
}

fn default_config() -> AppConfig {
    AppConfig {
        fade_days: 7,
        ron_days: 84,
        anonymize_opt_in: true,
        delegation_expire_days: 28,
        auth_public_login: true,
        app_base_url: Some("http://localhost".to_string()),
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
        // Enable token logging to satisfy "delivery mechanism required" policy for tests
        auth_log_magic_token: true,
    }
}

#[tokio::test]
#[serial]
async fn rate_limit_enforced_by_ip() -> Result<()> {
    let mut config = default_config();
    config.auth_rl_ip_per_min = Some(2);

    let state = test_state(config)?;
    let app = app(state);

    let req = || {
        Request::post("/auth/login/request")
            .header("Content-Type", "application/json")
            .body(body::Body::from(r#"{"email":"u1@example.com"}"#))
    };

    // 1st request -> OK
    let res = app.clone().oneshot(req()?).await?;
    assert_eq!(res.status(), StatusCode::OK);

    // 2nd request -> OK
    let res = app.clone().oneshot(req()?).await?;
    assert_eq!(res.status(), StatusCode::OK);

    // 3rd request -> 429
    let res = app.clone().oneshot(req()?).await?;
    assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);

    Ok(())
}

#[tokio::test]
#[serial]
async fn rate_limit_enforced_by_email() -> Result<()> {
    let mut config = default_config();
    config.auth_rl_email_per_min = Some(2);
    // Ensure IP limit is higher so we hit email limit first
    config.auth_rl_ip_per_min = Some(100);

    let state = test_state(config)?;
    let app = app(state);

    let req = || {
        Request::post("/auth/login/request")
            .header("Content-Type", "application/json")
            .body(body::Body::from(r#"{"email":"u1@example.com"}"#))
    };

    // 1st request -> OK
    let res = app.clone().oneshot(req()?).await?;
    assert_eq!(res.status(), StatusCode::OK);

    // 2nd request -> OK
    let res = app.clone().oneshot(req()?).await?;
    assert_eq!(res.status(), StatusCode::OK);

    // 3rd request -> 429
    let res = app.clone().oneshot(req()?).await?;
    assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);

    // Using different email from same IP -> OK
    let req2 = Request::post("/auth/login/request")
        .header("Content-Type", "application/json")
        .body(body::Body::from(r#"{"email":"other@example.com"}"#))?;
    let res = app.clone().oneshot(req2).await?;
    assert_eq!(res.status(), StatusCode::OK);

    Ok(())
}

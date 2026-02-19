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
    test_helpers::EnvGuard,
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
        nodes_persist: Arc::new(tokio::sync::Mutex::new(())),
        edges: Arc::new(tokio::sync::RwLock::new(Vec::new())),
        rate_limiter,
        mailer: None,
    })
}

fn app(state: ApiState) -> Router {
    // Mock the peer address as the "Proxy" IP (e.g. Caddy)
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
        auth_log_magic_token: true,
    }
}

#[tokio::test]
#[serial]
async fn rate_limit_respects_forwarded_header_when_trusted() -> Result<()> {
    // 1. Setup: Trust localhost (127.0.0.1) as proxy via EnvGuard
    // The application logic reads this from env, so we must set it there.
    let _guard = EnvGuard::set("AUTH_TRUSTED_PROXIES", "127.0.0.1");

    let mut config = default_config();
    // We do NOT set this manually in config, relying on the fact that
    // effective_client_ip reads the environment variable (or config parser does).
    // Assuming logic uses the static/OnceLock that reads ENV.
    config.auth_rl_ip_per_min = Some(2);

    let state = test_state(config)?;
    let app = app(state);

    // 2. Client IP: 1.2.3.4 (Forwarded)
    let req_client_a = || {
        Request::post("/auth/login/request")
            .header("Content-Type", "application/json")
            .header("X-Forwarded-For", "1.2.3.4")
            .body(body::Body::from(r#"{"email":"u1@example.com"}"#))
    };

    // 3. Request 1 & 2 -> OK (Limit 2)
    let res = app.clone().oneshot(req_client_a()?).await?;
    assert_eq!(res.status(), StatusCode::OK);
    let res = app.clone().oneshot(req_client_a()?).await?;
    assert_eq!(res.status(), StatusCode::OK);

    // 4. Request 3 -> 429 (Limit Exceeded for 1.2.3.4)
    let res = app.clone().oneshot(req_client_a()?).await?;
    assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);

    // 5. Client IP: 5.6.7.8 (Different Forwarded IP) -> Should be OK
    let req_client_b = || {
        Request::post("/auth/login/request")
            .header("Content-Type", "application/json")
            .header("X-Forwarded-For", "5.6.7.8")
            .body(body::Body::from(r#"{"email":"u2@example.com"}"#))
    };
    let res = app.clone().oneshot(req_client_b()?).await?;
    assert_eq!(res.status(), StatusCode::OK);

    Ok(())
}

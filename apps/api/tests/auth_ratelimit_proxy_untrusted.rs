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
async fn rate_limit_ignores_forwarded_header_when_untrusted() -> Result<()> {
    // 1. Setup: Trust NOTHING (or non-matching IP). Peer is 127.0.0.1.
    // We explicitly set trusted proxies to something else to ensure 127.0.0.1 is untrusted.
    let _guard = EnvGuard::set("AUTH_TRUSTED_PROXIES", "10.0.0.1");

    let mut config = default_config();
    // Logic reads env via effective_client_ip -> get_trusted_proxies
    config.auth_rl_ip_per_min = Some(2);

    let state = test_state(config)?;
    let app = app(state);

    // 2. Client A claims to be 1.2.3.4
    let req_client_a = || {
        Request::post("/auth/login/request")
            .header("Content-Type", "application/json")
            .header("X-Forwarded-For", "1.2.3.4")
            .body(body::Body::from(r#"{"email":"u1@example.com"}"#))
    };

    // 3. Client B claims to be 5.6.7.8
    let req_client_b = || {
        Request::post("/auth/login/request")
            .header("Content-Type", "application/json")
            .header("X-Forwarded-For", "5.6.7.8")
            .body(body::Body::from(r#"{"email":"u2@example.com"}"#))
    };

    // Since proxy (127.0.0.1) is UNTRUSTED, both are treated as coming from 127.0.0.1
    // Limit is 2 per IP.

    // Req 1 (A) -> OK (127.0.0.1 count: 1)
    let res = app.clone().oneshot(req_client_a()?).await?;
    assert_eq!(res.status(), StatusCode::OK);

    // Req 2 (B) -> OK (127.0.0.1 count: 2)
    let res = app.clone().oneshot(req_client_b()?).await?;
    assert_eq!(res.status(), StatusCode::OK);

    // Req 3 (A) -> 429 (127.0.0.1 count: 3 > 2)
    // If it trusted the header, A would be at 2, and B at 1, so this would succeed.
    // Because it ignores the header, it sees 127.0.0.1 again and blocks.
    let res = app.clone().oneshot(req_client_a()?).await?;
    assert_eq!(res.status(), StatusCode::TOO_MANY_REQUESTS);

    Ok(())
}

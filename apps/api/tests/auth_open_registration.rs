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
    routes::{api_router, auth::GENERIC_LOGIN_MSG},
    state::ApiState,
    telemetry::{BuildInfo, Metrics},
};

fn test_state_open_reg() -> Result<ApiState> {
    let metrics = Metrics::try_new(BuildInfo {
        version: "test",
        commit: "test",
        build_timestamp: "test",
    })?;

    // Option C: Open Registration Configuration
    // - Public Login: true
    // - Auto Provision: true
    // - Allowlist (Email): None
    // - Allowlist (Domain): None
    // - Rate Limits: Set (> 0)
    let config = AppConfig {
        fade_days: 7,
        ron_days: 84,
        anonymize_opt_in: true,
        delegation_expire_days: 28,

        auth_public_login: true,
        app_base_url: Some("http://localhost".to_string()),
        auth_trusted_proxies: None,

        auth_allow_emails: None,        // Essential for Option C
        auth_allow_email_domains: None, // Essential for Option C
        auth_auto_provision: true,      // Essential for Option C

        // Mandatory Rate Limits for Option C
        auth_rl_ip_per_min: Some(100),
        auth_rl_ip_per_hour: Some(1000),
        auth_rl_email_per_min: Some(100),
        auth_rl_email_per_hour: Some(1000),

        smtp_host: None,
        smtp_port: None,
        smtp_user: None,
        smtp_pass: None,
        smtp_from: None,
        // Enable token logging to satisfy delivery requirement for tests without SMTP
        auth_log_magic_token: true,
    };

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
    Router::new()
        .merge(api_router())
        .layer(MockConnectInfo(SocketAddr::from(([127, 0, 0, 1], 8080))))
        .with_state(state)
}

#[tokio::test]
#[serial]
async fn test_open_registration_flow_auto_provisions_unknown_email() -> Result<()> {
    let state = test_state_open_reg()?;
    let app = app(state.clone());

    let email = "unknown_user@example.com";
    let req = Request::post("/auth/login/request")
        .header("Content-Type", "application/json")
        .body(body::Body::from(format!(r#"{{"email":"{}"}}"#, email)))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    // Check response body
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let body_val: serde_json::Value = serde_json::from_slice(&body)?;
    assert_eq!(body_val["ok"], true);
    assert_eq!(body_val["message"], GENERIC_LOGIN_MSG);

    // CRITICAL ASSERTION:
    // With current implementation (pre-fix), this should FAIL because account is NOT created.
    // After fix, this should PASS.
    {
        let accounts = state.accounts.read().await;
        let found = accounts
            .values()
            .any(|acc| acc.email.as_deref() == Some(email));

        assert!(
            found,
            "Account should be auto-provisioned for unknown email in Open Registration mode"
        );
    }

    Ok(())
}

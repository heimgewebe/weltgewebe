use anyhow::{Context, Result};
use axum::{
    body,
    http::{Request, StatusCode},
    Router,
};
use serial_test::serial;
mod helpers;

use std::{collections::BTreeMap, sync::Arc};
use tokio::sync::RwLock;
use tower::ServiceExt;
use weltgewebe_api::{
    auth::{rate_limit::AuthRateLimiter, role::Role, session::SessionStore},
    config::AppConfig,
    routes::{
        accounts::{AccountInternal, AccountPublic, Visibility},
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
        edges: Arc::new(tokio::sync::RwLock::new(Vec::new())),
        rate_limiter,
        mailer: None,
    })
}

#[tokio::test]
#[serial]
async fn accounts_list_is_sorted_and_limited() -> Result<()> {
    let mut state = test_state().await?;
    let mut accounts = BTreeMap::new();

    // Insert accounts in unsorted order: u2, a1, u1
    // Expected sort order (lexicographical by ID): a1, u1, u2
    let ids = vec!["u2", "a1", "u1"];

    for id in ids {
        accounts.insert(id.to_string(), AccountInternal {
            public: AccountPublic {
                id: id.to_string(),
                kind: "garnrolle".to_string(),
                title: format!("Title {}", id),
                summary: None,
                public_pos: None,
                visibility: Visibility::Public,
                radius_m: 0,
                ron_flag: false,
                disabled: false,
                tags: vec![],
            },
            role: Role::Gast,
            email: None,
        });
    }

    state.accounts = Arc::new(RwLock::new(accounts));

    let app = Router::new().merge(api_router()).with_state(state);

    // Request limit=2. Expect "a1", "u1".
    let req = Request::get("/accounts?limit=2").body(body::Body::empty())?;
    let res = app.oneshot(req).await?;

    assert_eq!(res.status(), StatusCode::OK);

    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let arr = v.as_array().context("must be array")?;

    assert_eq!(arr.len(), 2, "Should return exactly 2 accounts");
    assert_eq!(arr[0]["id"], "a1", "First account should be a1");
    assert_eq!(arr[1]["id"], "u1", "Second account should be u1");

    Ok(())
}

use anyhow::{Context, Result};
use axum::{
    body,
    http::{Request, StatusCode},
    Router,
};
use serial_test::serial;
use std::{collections::HashMap, sync::Arc};
use tower::ServiceExt;
use weltgewebe_api::{
    auth::{role::Role, session::SessionStore},
    config::AppConfig,
    routes::{
        accounts::{AccountInternal, AccountPublic, Visibility},
        api_router,
        auth::SESSION_COOKIE_NAME,
    },
    state::ApiState,
    telemetry::{BuildInfo, Metrics},
};

mod helpers;

fn test_state() -> Result<ApiState> {
    let metrics = Metrics::try_new(BuildInfo {
        version: "test",
        commit: "test",
        build_timestamp: "test",
    })?;

    Ok(ApiState {
        db_pool: None,
        db_pool_configured: false,
        nats_client: None,
        nats_configured: false,
        config: AppConfig {
            fade_days: 7,
            ron_days: 84,
            anonymize_opt_in: true,
            delegation_expire_days: 28,
        },
        metrics,
        sessions: SessionStore::new(),
        accounts: Arc::new(HashMap::new()),
    })
}

fn app(state: ApiState) -> Router {
    Router::new().merge(api_router()).with_state(state)
}

struct DeferEnvRemove(&'static str);
impl Drop for DeferEnvRemove {
    fn drop(&mut self) {
        unsafe {
            std::env::remove_var(self.0);
        }
    }
}
fn defer_env_remove(key: &'static str) -> DeferEnvRemove {
    DeferEnvRemove(key)
}

#[tokio::test]
#[serial]
async fn auth_login_fails_when_dev_login_disabled() -> Result<()> {
    unsafe {
        std::env::remove_var("AUTH_DEV_LOGIN");
    }
    let state = test_state()?;
    let app = app(state);

    let req = Request::post("/auth/login")
        .header("Content-Type", "application/json")
        .body(body::Body::from(r#"{"account_id":"any"}"#))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::NOT_FOUND);
    Ok(())
}

#[tokio::test]
#[serial]
async fn auth_login_succeeds_with_flag_and_account() -> Result<()> {
    unsafe {
        std::env::set_var("AUTH_DEV_LOGIN", "1");
    }
    let _defer = defer_env_remove("AUTH_DEV_LOGIN");

    let mut account_map = HashMap::new();
    let account = AccountPublic {
        id: "u1".to_string(),
        kind: "garnrolle".to_string(),
        title: "User".to_string(),
        summary: None,
        public_pos: None,
        visibility: Visibility::Public,
        radius_m: 0,
        ron_flag: false,
        tags: vec![],
    };
    account_map.insert(
        "u1".to_string(),
        AccountInternal {
            public: account,
            role: Role::Gast,
        },
    );

    let mut state = test_state()?;
    state.accounts = Arc::new(account_map);

    let app = app(state);

    let req = Request::post("/auth/login")
        .header("Content-Type", "application/json")
        .body(body::Body::from(r#"{"account_id":"u1"}"#))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    let cookie = res
        .headers()
        .get("set-cookie")
        .context("missing set-cookie")?
        .to_str()?;
    assert!(cookie.contains(SESSION_COOKIE_NAME));
    assert!(cookie.contains("Secure"));
    assert!(cookie.contains("HttpOnly"));
    assert!(cookie.contains("SameSite=Strict"));

    Ok(())
}

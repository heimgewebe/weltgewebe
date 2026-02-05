use anyhow::{Context, Result};
use axum::{
    body,
    extract::connect_info::MockConnectInfo,
    http::{Request, StatusCode},
    Router,
};
use serial_test::serial;
use std::{collections::HashMap, net::SocketAddr, sync::Arc};
use tower::ServiceExt;
use weltgewebe_api::{
    auth::{role::Role, session::SessionStore},
    config::AppConfig,
    routes::{
        accounts::{AccountInternal, AccountPublic, Visibility},
        api_router,
        auth::{GENERIC_LOGIN_MSG, NONCE_COOKIE_NAME, SESSION_COOKIE_NAME},
    },
    state::ApiState,
    telemetry::{BuildInfo, Metrics},
};

fn extract_cookie_value(headers: &axum::http::HeaderMap, cookie_name: &str) -> Option<String> {
    headers
        .get_all("set-cookie")
        .iter()
        .filter_map(|v| v.to_str().ok())
        .find(|s| s.trim().starts_with(cookie_name))
        .and_then(|s| {
            s.split(';')
                .find(|p| p.trim().starts_with(cookie_name))
                .and_then(|p| p.splitn(2, '=').nth(1))
                .map(|v| v.to_string())
        })
}

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
            auth_public_login: false,
            app_base_url: None,
            auth_trusted_proxies: None,
        },
        metrics,
        sessions: SessionStore::new(),
        tokens: weltgewebe_api::auth::tokens::TokenStore::new(),
        accounts: Arc::new(HashMap::new()),
        nodes: Arc::new(tokio::sync::RwLock::new(Vec::new())),
    })
}

fn test_state_with_accounts() -> Result<ApiState> {
    let mut state = test_state()?;
    let mut account_map = HashMap::new();

    account_map.insert(
        "u1".to_string(),
        AccountInternal {
            public: AccountPublic {
                id: "u1".to_string(),
                kind: "garnrolle".to_string(),
                title: "User One".to_string(),
                summary: Some("Summary 1".to_string()),
                public_pos: None,
                visibility: Visibility::Public,
                radius_m: 0,
                ron_flag: false,
                tags: vec![],
            },
            role: Role::Gast,
            email: Some("u1@example.com".to_string()),
        },
    );
    account_map.insert(
        "a1".to_string(),
        AccountInternal {
            public: AccountPublic {
                id: "a1".to_string(),
                kind: "garnrolle".to_string(),
                title: "Admin One".to_string(),
                summary: None,
                public_pos: None,
                visibility: Visibility::Public,
                radius_m: 0,
                ron_flag: false,
                tags: vec![],
            },
            role: Role::Admin,
            email: Some("a1@example.com".to_string()),
        },
    );

    state.accounts = Arc::new(account_map);
    Ok(state)
}

fn app(state: ApiState) -> Router {
    app_with_addr(state, "127.0.0.1:8080".parse().unwrap())
}

fn app_with_addr(state: ApiState, addr: SocketAddr) -> Router {
    Router::new()
        .merge(api_router())
        .layer(MockConnectInfo(addr))
        .with_state(state)
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

    let req = Request::post("/auth/dev/login")
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
            email: Some("u1@example.com".to_string()),
        },
    );

    let mut state = test_state()?;
    state.accounts = Arc::new(account_map);

    let app = app(state);

    let req = Request::post("/auth/dev/login")
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
    assert!(cookie.contains("SameSite=Lax"));

    Ok(())
}

#[tokio::test]
#[serial]
async fn list_dev_accounts_succeeds_ipv6_localhost() -> Result<()> {
    unsafe {
        std::env::set_var("AUTH_DEV_LOGIN", "1");
    }
    let _defer = defer_env_remove("AUTH_DEV_LOGIN");

    let state = test_state_with_accounts()?;
    // Use IPv6 loopback address
    let app = app_with_addr(state, "[::1]:8080".parse()?);

    let req = Request::get("/auth/dev/accounts").body(body::Body::empty())?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    Ok(())
}

#[tokio::test]
#[serial]
async fn list_dev_accounts_fails_when_dev_login_disabled() -> Result<()> {
    unsafe {
        std::env::remove_var("AUTH_DEV_LOGIN");
    }
    let state = test_state_with_accounts()?;
    let app = app(state);

    let req = Request::get("/auth/dev/accounts").body(body::Body::empty())?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::NOT_FOUND);
    Ok(())
}

#[tokio::test]
#[serial]
async fn list_dev_accounts_succeeds_localhost() -> Result<()> {
    unsafe {
        std::env::set_var("AUTH_DEV_LOGIN", "1");
    }
    let _defer = defer_env_remove("AUTH_DEV_LOGIN");

    let state = test_state_with_accounts()?;
    let app = app(state);

    let req = Request::get("/auth/dev/accounts").body(body::Body::empty())?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    let body_bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let accounts: Vec<serde_json::Value> = serde_json::from_slice(&body_bytes)?;
    assert_eq!(accounts.len(), 2);
    // Sort order check: a1 should be before u1
    assert_eq!(accounts[0]["id"], "a1");
    assert_eq!(accounts[1]["id"], "u1");
    assert_eq!(accounts[0]["role"], "admin");
    assert_eq!(accounts[1]["role"], "gast");

    Ok(())
}

#[tokio::test]
#[serial]
async fn list_dev_accounts_fails_remote() -> Result<()> {
    unsafe {
        std::env::set_var("AUTH_DEV_LOGIN", "1");
        std::env::remove_var("AUTH_DEV_LOGIN_ALLOW_REMOTE");
    }
    let _defer = defer_env_remove("AUTH_DEV_LOGIN");

    let state = test_state_with_accounts()?;
    // Use a non-localhost IP to simulate remote access
    let app = app_with_addr(state, "192.168.1.100:8080".parse()?);

    let req = Request::get("/auth/dev/accounts").body(body::Body::empty())?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::FORBIDDEN);
    Ok(())
}

#[tokio::test]
#[serial]
async fn list_dev_accounts_succeeds_remote_allowed() -> Result<()> {
    unsafe {
        std::env::set_var("AUTH_DEV_LOGIN", "1");
        std::env::set_var("AUTH_DEV_LOGIN_ALLOW_REMOTE", "1");
    }
    let _defer1 = defer_env_remove("AUTH_DEV_LOGIN");
    let _defer2 = defer_env_remove("AUTH_DEV_LOGIN_ALLOW_REMOTE");

    let state = test_state_with_accounts()?;
    // Use a non-localhost IP to simulate remote access
    let app = app_with_addr(state, "192.168.1.100:8080".parse()?);

    let req = Request::get("/auth/dev/accounts").body(body::Body::empty())?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);
    Ok(())
}

#[tokio::test]
#[serial]
async fn list_dev_accounts_rejects_spoofed_host_header() -> Result<()> {
    unsafe {
        std::env::set_var("AUTH_DEV_LOGIN", "1");
        std::env::remove_var("AUTH_DEV_LOGIN_ALLOW_REMOTE");
    }
    let _defer = defer_env_remove("AUTH_DEV_LOGIN");

    let state = test_state_with_accounts()?;
    // Use a non-localhost IP (actual client address)
    let app = app_with_addr(state, "203.0.113.42:12345".parse()?);

    // Try to bypass the guard by spoofing the Host header
    let req = Request::get("/auth/dev/accounts")
        .header("Host", "localhost:8080")
        .body(body::Body::empty())?;

    let res = app.oneshot(req).await?;
    // Should still be forbidden because actual socket address is not localhost
    assert_eq!(res.status(), StatusCode::FORBIDDEN);
    Ok(())
}

#[tokio::test]
#[serial]
async fn auth_login_fails_from_remote_without_allow_flag() -> Result<()> {
    unsafe {
        std::env::set_var("AUTH_DEV_LOGIN", "1");
        std::env::remove_var("AUTH_DEV_LOGIN_ALLOW_REMOTE");
    }
    let _defer = defer_env_remove("AUTH_DEV_LOGIN");

    let state = test_state_with_accounts()?;
    // Use a non-localhost IP to simulate remote access
    let app = app_with_addr(state, "192.168.1.100:8080".parse()?);

    let req = Request::post("/auth/dev/login")
        .header("Content-Type", "application/json")
        .body(body::Body::from(r#"{"account_id":"u1"}"#))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::FORBIDDEN);
    Ok(())
}

#[tokio::test]
#[serial]
async fn auth_login_succeeds_from_remote_with_allow_flag() -> Result<()> {
    unsafe {
        std::env::set_var("AUTH_DEV_LOGIN", "1");
        std::env::set_var("AUTH_DEV_LOGIN_ALLOW_REMOTE", "1");
    }
    let _defer1 = defer_env_remove("AUTH_DEV_LOGIN");
    let _defer2 = defer_env_remove("AUTH_DEV_LOGIN_ALLOW_REMOTE");

    let state = test_state_with_accounts()?;
    // Use a non-localhost IP to simulate remote access
    let app = app_with_addr(state, "192.168.1.100:8080".parse()?);

    let req = Request::post("/auth/dev/login")
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
    Ok(())
}

#[tokio::test]
#[serial]
async fn request_login_fails_when_public_login_disabled() -> Result<()> {
    let mut state = test_state()?;
    state.config.auth_public_login = false;
    let app = app(state);

    let req = Request::post("/auth/login/request")
        .header("Content-Type", "application/json")
        .body(body::Body::from(r#"{"email":"u1@example.com"}"#))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::NOT_FOUND);
    Ok(())
}

#[tokio::test]
#[serial]
async fn request_login_succeeds_when_public_login_enabled() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    let app = app(state);

    let req = Request::post("/auth/login/request")
        .header("Content-Type", "application/json")
        .body(body::Body::from(r#"{"email":"u1@example.com"}"#))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let body_val: serde_json::Value = serde_json::from_slice(&body)?;

    // Check JSON contract
    assert_eq!(body_val["ok"], true);
    assert_eq!(body_val["message"], GENERIC_LOGIN_MSG);

    // Security check: no token leak in the entire JSON string representation
    let body_str = body_val.to_string();
    assert!(!body_str.contains("token="));
    // Security check: ensure email is not echoed back
    assert!(!body_str.contains("u1@example.com"));

    Ok(())
}

#[tokio::test]
#[serial]
async fn request_login_unknown_user_returns_identical_response() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    let app = app(state);

    let req = Request::post("/auth/login/request")
        .header("Content-Type", "application/json")
        .body(body::Body::from(r#"{"email":"unknown@example.com"}"#))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let body_val: serde_json::Value = serde_json::from_slice(&body)?;

    assert_eq!(body_val["ok"], true);
    assert_eq!(body_val["message"], GENERIC_LOGIN_MSG);
    assert!(!body_val.to_string().contains("unknown@example.com"));

    Ok(())
}

#[tokio::test]
#[serial]
async fn consume_login_succeeds() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    // Create a valid token
    let token = state.tokens.create("u1@example.com".to_string());

    let app = app(state);

    // 1. GET request (Confirm step)
    let uri = format!("/auth/login/consume?token={}", token);
    let req = Request::get(&uri).body(body::Body::empty())?;

    // Clone app because we need to make a second request to the same app state
    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);
    let content_type = res.headers().get("content-type").unwrap().to_str()?;
    assert!(content_type.contains("text/html"));

    // Check nonce cookie presence
    let nonce_val = extract_cookie_value(res.headers(), NONCE_COOKIE_NAME)
        .context("nonce cookie missing in GET response")?;
    assert!(!nonce_val.is_empty());

    // Ensure NO session cookie is set
    assert!(extract_cookie_value(res.headers(), SESSION_COOKIE_NAME).is_none());

    // 2. POST request (Consume step)
    let body_str = format!("token={}&nonce={}", token, nonce_val);
    let req2 = Request::post("/auth/login/consume")
        .header("Content-Type", "application/x-www-form-urlencoded")
        .header("Cookie", format!("{}={}", NONCE_COOKIE_NAME, nonce_val))
        .body(body::Body::from(body_str))?;

    let res2 = app.oneshot(req2).await?;
    assert_eq!(res2.status(), StatusCode::SEE_OTHER);
    assert_eq!(res2.headers().get("location").unwrap(), "/");

    // Check Session Cookie is present
    let session_val = extract_cookie_value(res2.headers(), SESSION_COOKIE_NAME)
        .context("session cookie missing in POST response")?;
    assert!(!session_val.is_empty());

    // Check Nonce Cookie is cleared (Max-Age=0 or empty value)
    // Axum/Tower might merge headers, so we look at all Set-Cookie headers
    let cookies_str = res2
        .headers()
        .get_all("set-cookie")
        .iter()
        .map(|v| v.to_str().unwrap_or_default())
        .collect::<Vec<_>>()
        .join(" || ");

    assert!(cookies_str.contains(NONCE_COOKIE_NAME));
    assert!(cookies_str.contains("Max-Age=0") || cookies_str.contains("Expires="));

    Ok(())
}

#[tokio::test]
#[serial]
async fn consume_login_fails_invalid_token() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    let app = app(state);

    let req =
        Request::get("/auth/login/consume?token=invalid_token_123").body(body::Body::empty())?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::SEE_OTHER);
    assert_eq!(
        res.headers().get("location").unwrap(),
        "/login?error=invalid_token"
    );

    // Ensure no session cookie is set
    assert!(res.headers().get("set-cookie").is_none());

    Ok(())
}

#[tokio::test]
#[serial]
async fn consume_login_fails_reuse() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    let token = state.tokens.create("u1@example.com".to_string());

    let app = app(state);

    // 1. First full flow (Success)
    // GET
    let uri = format!("/auth/login/consume?token={}", token);
    let req_get = Request::get(&uri).body(body::Body::empty())?;
    let res_get = app.clone().oneshot(req_get).await?;

    let nonce_val =
        extract_cookie_value(res_get.headers(), NONCE_COOKIE_NAME).context("nonce missing")?;

    // POST
    let body_str = format!("token={}&nonce={}", token, nonce_val);
    let req_post = Request::post("/auth/login/consume")
        .header("Content-Type", "application/x-www-form-urlencoded")
        .header("Cookie", format!("{}={}", NONCE_COOKIE_NAME, nonce_val))
        .body(body::Body::from(body_str.clone()))?;

    let res_post = app.clone().oneshot(req_post).await?;
    assert_eq!(res_post.status(), StatusCode::SEE_OTHER);
    assert_eq!(res_post.headers().get("location").unwrap(), "/");

    // 2. Second attempt (Reuse Token)
    // Even if we have a valid nonce (or get a new one), the token is gone.
    // Let's assume we got a new nonce (simulating user clicking link again)
    let req_get2 = Request::get(&uri).body(body::Body::empty())?;
    let res_get2 = app.clone().oneshot(req_get2).await?;
    // GET should fail because peek checks expiry/existence.
    // Since consume removes the token, peek should fail.
    assert_eq!(res_get2.status(), StatusCode::SEE_OTHER);
    assert_eq!(
        res_get2.headers().get("location").unwrap(),
        "/login?error=invalid_token"
    );

    Ok(())
}

#[tokio::test]
#[serial]
async fn consume_login_fails_bad_nonce() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    let token = state.tokens.create("u1@example.com".to_string());
    let app = app(state);

    // GET to get a nonce
    let uri = format!("/auth/login/consume?token={}", token);
    let req = Request::get(&uri).body(body::Body::empty())?;
    let res = app.clone().oneshot(req).await?;

    let nonce_val =
        extract_cookie_value(res.headers(), NONCE_COOKIE_NAME).context("nonce missing")?;

    // POST with wrong nonce in form
    let body_str = format!("token={}&nonce=WRONG_NONCE", token);
    let req2 = Request::post("/auth/login/consume")
        .header("Content-Type", "application/x-www-form-urlencoded")
        .header("Cookie", format!("{}={}", NONCE_COOKIE_NAME, nonce_val))
        .body(body::Body::from(body_str))?;

    let res2 = app.oneshot(req2).await?;
    // Should fail
    assert_eq!(res2.status(), StatusCode::SEE_OTHER);
    assert_eq!(
        res2.headers().get("location").unwrap(),
        "/login?error=invalid_token"
    );

    Ok(())
}

#[tokio::test]
#[serial]
async fn consume_login_fails_expired_token() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    // Create an expired token (expired 1 second ago)
    let token = state
        .tokens
        .create_with_expiry("u1@example.com".to_string(), chrono::Duration::seconds(-1));

    let app = app(state);

    let uri = format!("/auth/login/consume?token={}", token);
    let req = Request::get(uri).body(body::Body::empty())?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::SEE_OTHER);
    assert_eq!(
        res.headers().get("location").unwrap(),
        "/login?error=invalid_token"
    );

    Ok(())
}

use anyhow::{Context, Result};
use axum::{
    body,
    extract::connect_info::MockConnectInfo,
    http::{HeaderMap, Request, StatusCode},
    Router,
};
use serial_test::serial;
use sha2::{Digest, Sha256};
use std::{collections::BTreeMap, net::SocketAddr, sync::Arc};
use tokio::sync::RwLock;
use tower::ServiceExt;
use weltgewebe_api::{
    auth::{rate_limit::AuthRateLimiter, role::Role, session::SessionStore},
    config::AppConfig,
    routes::{
        accounts::{AccountInternal, AccountPublic},
        api_router,
        auth::{GENERIC_LOGIN_MSG, NONCE_COOKIE_NAME, SESSION_COOKIE_NAME},
    },
    state::ApiState,
    telemetry::{BuildInfo, Metrics},
};

fn test_state() -> Result<ApiState> {
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
        // Enable token logging to satisfy "delivery mechanism required" policy for tests
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
        challenges: Default::default(),
        tokens: weltgewebe_api::auth::tokens::TokenStore::new(),
        step_up_tokens: weltgewebe_api::auth::step_up_tokens::StepUpTokenStore::new(),
        accounts: Arc::new(RwLock::new(BTreeMap::new())),
        nodes: Arc::new(tokio::sync::RwLock::new(Vec::new())),
        nodes_persist: Arc::new(tokio::sync::Mutex::new(())),
        edges: Arc::new(tokio::sync::RwLock::new(Vec::new())),
        rate_limiter,
        mailer: None,
    })
}

fn test_state_with_accounts() -> Result<ApiState> {
    let mut state = test_state()?;
    let mut account_map = BTreeMap::new();

    let account = AccountInternal {
        public: AccountPublic {
            id: "u1".to_string(),
            kind: "garnrolle".to_string(),
            title: "User One".to_string(),
            summary: Some("Summary 1".to_string()),
            public_pos: None,
            mode: weltgewebe_api::routes::accounts::AccountMode::Verortet,
            radius_m: 0,

            disabled: false,
            tags: vec![],
        },
        role: Role::Gast,
        email: Some("u1@example.com".to_string()),
    };
    account_map.insert(account.public.id.clone(), account);

    let account = AccountInternal {
        public: AccountPublic {
            id: "a1".to_string(),
            kind: "garnrolle".to_string(),
            title: "Admin One".to_string(),
            summary: None,
            public_pos: None,
            mode: weltgewebe_api::routes::accounts::AccountMode::Verortet,
            radius_m: 0,

            disabled: false,
            tags: vec![],
        },
        role: Role::Admin,
        email: Some("a1@example.com".to_string()),
    };
    account_map.insert(account.public.id.clone(), account);

    state.accounts = Arc::new(RwLock::new(account_map));
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
async fn request_login_denied_if_account_disabled() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    // Disable the account
    {
        let mut accounts = state.accounts.write().await;
        if let Some(acc) = accounts.get_mut("u1") {
            acc.public.disabled = true;
        }
    }

    let app = app(state.clone());

    let req = Request::post("/auth/magic-link/request")
        .header("Content-Type", "application/json")
        .body(body::Body::from(r#"{"email":"u1@example.com"}"#))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let body_val: serde_json::Value = serde_json::from_slice(&body)?;

    // Should return generic success
    assert_eq!(body_val["ok"], true);
    assert_eq!(body_val["message"], GENERIC_LOGIN_MSG);

    Ok(())
}

#[tokio::test]
#[serial]
async fn consume_login_fails_if_account_disabled() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    // Disable the account
    {
        let mut accounts = state.accounts.write().await;
        if let Some(acc) = accounts.get_mut("u1") {
            acc.public.disabled = true;
        }
    }

    // Create a valid token manually
    let token = state.tokens.create("u1@example.com".to_string());
    let app = app(state);

    // 1. GET (Confirm Page) - This might still work because it only validates token existence, not account status?
    // `consume_login_get` only calls `state.tokens.peek`. It doesn't look up the account.
    // So GET will show the form. This is acceptable (leaks nothing sensitive).

    let nonce_val = {
        // Helper to get nonce without full request flow
        // Or just do the GET request
        let uri = format!("/auth/magic-link/consume?token={}", token);
        let req_get = Request::get(&uri).body(body::Body::empty())?;
        let res_get = app.clone().oneshot(req_get).await?;
        assert_eq!(res_get.status(), StatusCode::OK);
        extract_cookie_value(res_get.headers(), NONCE_COOKIE_NAME).context("missing nonce")?
    };

    // Extract nonce from cookie (hash.nonce)
    let (_, nonce) = nonce_val.split_once('.').context("invalid nonce format")?;
    let nonce = nonce.to_string();

    // 2. POST (Consume)
    let body_str = format!("token={}&nonce={}", token, nonce);
    let req_post = Request::post("/auth/magic-link/consume")
        .header("Content-Type", "application/x-www-form-urlencoded")
        .header("Cookie", format!("{}={}", NONCE_COOKIE_NAME, nonce_val))
        .body(body::Body::from(body_str))?;

    let res_post = app.oneshot(req_post).await?;

    // Should fail and redirect to login error
    assert_eq!(res_post.status(), StatusCode::SEE_OTHER);
    let location = res_post
        .headers()
        .get("location")
        .unwrap()
        .to_str()
        .unwrap();
    assert_eq!(location, "/login?error=account_disabled");

    Ok(())
}

#[tokio::test]
#[serial]
async fn auth_login_succeeds_with_flag_and_account() -> Result<()> {
    unsafe {
        std::env::set_var("AUTH_DEV_LOGIN", "1");
    }
    let _defer = defer_env_remove("AUTH_DEV_LOGIN");
    let _guard_cookie = weltgewebe_api::test_helpers::EnvGuard::set("AUTH_COOKIE_SECURE", "1");

    let mut account_map = BTreeMap::new();
    let account = AccountInternal {
        public: AccountPublic {
            id: "u1".to_string(),
            kind: "garnrolle".to_string(),
            title: "User".to_string(),
            summary: None,
            public_pos: None,
            mode: weltgewebe_api::routes::accounts::AccountMode::Verortet,
            radius_m: 0,

            disabled: false,
            tags: vec![],
        },
        role: Role::Gast,
        email: Some("u1@example.com".to_string()),
    };
    account_map.insert(account.public.id.clone(), account);

    let mut state = test_state()?;
    state.accounts = Arc::new(RwLock::new(account_map));

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

    let req = Request::post("/auth/magic-link/request")
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

    let req = Request::post("/auth/magic-link/request")
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

    let req = Request::post("/auth/magic-link/request")
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

fn hash_token(token: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(token.as_bytes());
    format!("{:x}", hasher.finalize())
}

fn extract_cookie_value(headers: &HeaderMap, name: &str) -> Option<String> {
    headers.get_all("set-cookie").iter().find_map(|val| {
        let s = val.to_str().ok()?;
        let (cookie_part, _) = s.split_once(';').unwrap_or((s, ""));
        let (key, value) = cookie_part.split_once('=')?;
        if key.trim() == name {
            let v = value.trim();
            let v = v
                .strip_prefix('"')
                .and_then(|s| s.strip_suffix('"'))
                .unwrap_or(v);
            Some(v.to_string())
        } else {
            None
        }
    })
}

#[tokio::test]
#[serial]
async fn consume_legacy_alias_flow_succeeds() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    let token = state.tokens.create("u1@example.com".to_string());
    let app = app(state);

    // 1. GET (Confirm Page via Legacy Alias)
    let uri = format!("/auth/login/consume?token={}", token);
    let req_get = Request::get(&uri).body(body::Body::empty())?;
    let res_get = app.clone().oneshot(req_get).await?;

    assert_eq!(res_get.status(), StatusCode::OK);

    // Extract nonce for POST
    let set_cookies = res_get.headers().get_all("set-cookie");
    let mut nonce_val = String::new();
    for c in set_cookies.iter() {
        let cookie_str = c.to_str()?;
        if cookie_str.starts_with(NONCE_COOKIE_NAME) {
            let parts: Vec<&str> = cookie_str.split('=').collect();
            if parts.len() > 1 {
                let val_part = parts[1].split(';').next().unwrap_or("");
                nonce_val = val_part.to_string();
            }
        }
    }
    assert!(!nonce_val.is_empty(), "Nonce cookie missing on GET");
    let nonce = nonce_val.split('.').next_back().unwrap_or("").to_string();

    // 2. POST (Consume via Legacy Alias)
    let body_str = format!("token={}&nonce={}", token, nonce);
    let req_post = Request::post("/auth/login/consume")
        .header("Content-Type", "application/x-www-form-urlencoded")
        .header("Cookie", format!("{}={}", NONCE_COOKIE_NAME, nonce_val))
        .body(body::Body::from(body_str))?;

    let res_post = app.oneshot(req_post).await?;
    assert_eq!(res_post.status(), StatusCode::SEE_OTHER);

    // Should set session cookie on success
    let mut session_found = false;
    for c in res_post.headers().get_all("set-cookie").iter() {
        if c.to_str()?.starts_with(SESSION_COOKIE_NAME) {
            session_found = true;
        }
    }
    assert!(
        session_found,
        "Session cookie not set after successful legacy POST"
    );

    Ok(())
}

#[tokio::test]
#[serial]
async fn consume_login_flow_succeeds() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    // Create a valid token
    let token = state.tokens.create("u1@example.com".to_string());
    let app = app(state);

    // 1. GET (Confirm Page)
    let uri = format!("/auth/magic-link/consume?token={}", token);
    let req_get = Request::get(&uri).body(body::Body::empty())?;
    let res_get = app.clone().oneshot(req_get).await?;

    assert_eq!(res_get.status(), StatusCode::OK);
    // Should NOT set session cookie yet
    let set_cookies = res_get.headers().get_all("set-cookie");
    for c in set_cookies.iter() {
        assert!(!c.to_str()?.contains(SESSION_COOKIE_NAME));
    }
    // Should set nonce cookie
    let nonce_val = extract_cookie_value(res_get.headers(), NONCE_COOKIE_NAME)
        .context("missing nonce cookie")?;

    // Extract nonce from cookie (hash.nonce)
    let (_, nonce) = nonce_val.split_once('.').context("invalid nonce format")?;
    let nonce = nonce.to_string(); // Keep only nonce part for form

    // 2. POST (Consume)
    let body_str = format!("token={}&nonce={}", token, nonce);
    let req_post = Request::post("/auth/magic-link/consume")
        .header("Content-Type", "application/x-www-form-urlencoded")
        .header("Cookie", format!("{}={}", NONCE_COOKIE_NAME, nonce_val))
        .body(body::Body::from(body_str))?;

    let res_post = app.oneshot(req_post).await?;

    assert_eq!(res_post.status(), StatusCode::SEE_OTHER);
    assert_eq!(res_post.headers().get("location").unwrap(), "/");

    let set_cookies = res_post.headers().get_all("set-cookie");
    let session_cookie_present = set_cookies
        .iter()
        .any(|c| c.to_str().unwrap_or("").contains(SESSION_COOKIE_NAME));
    assert!(
        session_cookie_present,
        "Session cookie not found in response"
    );

    // Ensure nonce cookie is cleared (Max-Age=0 or Expires)
    let nonce_cleared = set_cookies.iter().any(|c| {
        let val = c.to_str().unwrap_or("");
        val.contains(NONCE_COOKIE_NAME) && (val.contains("Max-Age=0") || val.contains("Expires="))
    });
    assert!(nonce_cleared, "Nonce cookie should be cleared in response");

    Ok(())
}

#[tokio::test]
#[serial]
async fn consume_login_fails_invalid_token() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    let app = app(state);

    let req = Request::get("/auth/magic-link/consume?token=invalid_token_123")
        .body(body::Body::empty())?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::SEE_OTHER);
    assert_eq!(
        res.headers().get("location").unwrap(),
        "/login?error=invalid_token"
    );

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

    // 1. GET (Confirm Page)
    let uri = format!("/auth/magic-link/consume?token={}", token);
    let req_get = Request::get(&uri).body(body::Body::empty())?;
    let res_get = app.clone().oneshot(req_get).await?;

    assert_eq!(res_get.status(), StatusCode::OK);

    let nonce_val = extract_cookie_value(res_get.headers(), NONCE_COOKIE_NAME)
        .context("missing nonce cookie")?;

    // Extract nonce from cookie (hash.nonce)
    let (_, nonce) = nonce_val.split_once('.').context("invalid nonce format")?;
    let nonce = nonce.to_string(); // Keep only nonce part for form

    // 2. POST (Consume)
    let body_str = format!("token={}&nonce={}", token, nonce);
    let req_post = Request::post("/auth/magic-link/consume")
        .header("Content-Type", "application/x-www-form-urlencoded")
        .header("Cookie", format!("{}={}", NONCE_COOKIE_NAME, nonce_val))
        .body(body::Body::from(body_str))?;

    let res_post = app.clone().oneshot(req_post).await?;

    assert_eq!(res_post.status(), StatusCode::SEE_OTHER);
    assert_eq!(res_post.headers().get("location").unwrap(), "/");

    // 3. GET Reuse (Should fail)
    let req_reuse = Request::get(&uri).body(body::Body::empty())?;
    let res_reuse = app.oneshot(req_reuse).await?;

    assert_eq!(res_reuse.status(), StatusCode::SEE_OTHER);
    assert_eq!(
        res_reuse.headers().get("location").unwrap(),
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

    // GET should fail
    let uri = format!("/auth/magic-link/consume?token={}", token);
    let req = Request::get(uri).body(body::Body::empty())?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::SEE_OTHER);
    assert_eq!(
        res.headers().get("location").unwrap(),
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
    let app = app(state.clone());

    // Mismatch nonce
    let nonce_cookie = "nonce1";
    let nonce_form = "nonce2";
    let token_hash = hash_token(&token);
    let cookie_val = format!("{}.{}", token_hash, nonce_cookie);
    let body_str = format!("token={}&nonce={}", token, nonce_form);

    let req = Request::post("/auth/magic-link/consume")
        .header("Content-Type", "application/x-www-form-urlencoded")
        .header("Cookie", format!("{}={}", NONCE_COOKIE_NAME, cookie_val))
        .body(body::Body::from(body_str))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::SEE_OTHER);
    assert_eq!(
        res.headers().get("location").unwrap(),
        "/login?error=invalid_token"
    );
    // Token should NOT be consumed
    assert!(state.tokens.peek(&token).is_some());

    Ok(())
}

#[tokio::test]
#[serial]
async fn consume_login_fails_bad_token_binding() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    let token = state.tokens.create("u1@example.com".to_string());
    let other_token = state.tokens.create("u1@example.com".to_string());
    let app = app(state.clone());

    let nonce = "nonce1";
    let token_hash = hash_token(&other_token); // Hash of WRONG token
    let cookie_val = format!("{}.{}", token_hash, nonce);
    let body_str = format!("token={}&nonce={}", token, nonce); // Correct token in form

    let req = Request::post("/auth/magic-link/consume")
        .header("Content-Type", "application/x-www-form-urlencoded")
        .header("Cookie", format!("{}={}", NONCE_COOKIE_NAME, cookie_val))
        .body(body::Body::from(body_str))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::SEE_OTHER);
    assert_eq!(
        res.headers().get("location").unwrap(),
        "/login?error=invalid_token"
    );
    // Token should NOT be consumed
    assert!(state.tokens.peek(&token).is_some());

    Ok(())
}

#[tokio::test]
#[serial]
async fn request_login_provisioning_disabled_for_unknown() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());
    state.config.auth_auto_provision = false;

    let app = app(state.clone());

    let email = "newuser@example.com";
    let req = Request::post("/auth/magic-link/request")
        .header("Content-Type", "application/json")
        .body(body::Body::from(format!(r#"{{"email":"{}"}}"#, email)))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    // Should NOT have created an account
    let accounts = state.accounts.read().await;
    let found = accounts
        .values()
        .any(|acc| acc.email.as_deref() == Some(email));
    assert!(!found);

    Ok(())
}

#[tokio::test]
#[serial]
async fn request_login_provisioning_enabled_success() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());
    state.config.auth_auto_provision = true;
    state.config.auth_allow_emails = Some(vec!["allowed@example.com".to_string()]);

    let app = app(state.clone());

    let email = "allowed@example.com";
    let req = Request::post("/auth/magic-link/request")
        .header("Content-Type", "application/json")
        .body(body::Body::from(format!(r#"{{"email":"{}"}}"#, email)))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    // Should have created an account
    {
        let accounts = state.accounts.read().await;
        let found = accounts
            .values()
            .find(|acc| acc.email.as_deref() == Some(email));
        assert!(found.is_some());
        let acc = found.unwrap();
        assert_eq!(acc.role, Role::Gast);
        // Verify auto-provisioning privacy invariants
        assert_eq!(acc.public.title, "Rolle ohne Namen");
        assert_eq!(acc.public.kind, "ron");
        assert_eq!(
            acc.public.mode,
            weltgewebe_api::routes::accounts::AccountMode::Ron
        );
        assert!(acc.public.public_pos.is_none());
    }

    // Should have created a token
    // We can't easily peek by email with current TokenStore public API in tests (peek takes token string)
    // But we can rely on the fact that if account was created, token generation follows.
    // However, let's verify if we can check token count or something?
    // TokenStore::create returns the token string. We don't have it here.
    // But we know it succeeded if we see the account.

    Ok(())
}

#[tokio::test]
#[serial]
async fn request_login_provisioning_enabled_denied() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());
    state.config.auth_auto_provision = true;
    state.config.auth_allow_emails = Some(vec!["allowed@example.com".to_string()]);

    let app = app(state.clone());

    let email = "denied@example.com";
    let req = Request::post("/auth/magic-link/request")
        .header("Content-Type", "application/json")
        .body(body::Body::from(format!(r#"{{"email":"{}"}}"#, email)))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    // Should NOT have created an account
    {
        let accounts = state.accounts.read().await;
        let found = accounts
            .values()
            .any(|acc| acc.email.as_deref() == Some(email));
        assert!(!found);
    }

    Ok(())
}

#[tokio::test]
#[serial]
async fn request_login_provisioning_enabled_domain_allowlist() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());
    state.config.auth_auto_provision = true;
    state.config.auth_allow_email_domains = Some(vec!["allowed.com".to_string()]);

    let app = app(state.clone());

    let email = "user@allowed.com";
    let req = Request::post("/auth/magic-link/request")
        .header("Content-Type", "application/json")
        .body(body::Body::from(format!(r#"{{"email":"{}"}}"#, email)))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    // Should have created an account
    {
        let accounts = state.accounts.read().await;
        let found = accounts
            .values()
            .any(|acc| acc.email.as_deref() == Some(email));
        assert!(found);
    }

    Ok(())
}

#[tokio::test]
#[serial]
async fn request_login_provisioning_domain_allowlist_rejects_multi_at_attack() -> Result<()> {
    // Attack vector: attacker@allowed.com@evil.com
    // Should NOT match "allowed.com"
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());
    state.config.auth_auto_provision = true;
    state.config.auth_allow_email_domains = Some(vec!["allowed.com".to_string()]);

    let app = app(state.clone());

    let email = "attacker@allowed.com@evil.com";
    let req = Request::post("/auth/magic-link/request")
        .header("Content-Type", "application/json")
        .body(body::Body::from(format!(r#"{{"email":"{}"}}"#, email)))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    // Verify account NOT created
    // We check against the normalized email because if it were created, it would be normalized.
    let email_norm = email.trim().to_ascii_lowercase();
    {
        let accounts = state.accounts.read().await;
        let found = accounts
            .values()
            .any(|acc| acc.email.as_deref() == Some(email_norm.as_str()));
        assert!(
            !found,
            "Account should not be created for multi-@ attack email"
        );
    }

    Ok(())
}

#[tokio::test]
#[serial]
async fn request_login_provisioning_empty_domain_rejected() -> Result<()> {
    // Edge case: "user@" (empty domain)
    // Config: "allowed.com" (and potentially empty strings filtered out)
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());
    state.config.auth_auto_provision = true;
    state.config.auth_allow_email_domains = Some(vec!["allowed.com".to_string()]);

    let app = app(state.clone());

    let email = "user@";
    let req = Request::post("/auth/magic-link/request")
        .header("Content-Type", "application/json")
        .body(body::Body::from(format!(r#"{{"email":"{}"}}"#, email)))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    // Verify account NOT created
    let email_norm = email.trim().to_ascii_lowercase();
    {
        let accounts = state.accounts.read().await;
        let found = accounts
            .values()
            .any(|acc| acc.email.as_deref() == Some(email_norm.as_str()));
        assert!(!found, "Account should not be created for empty domain");
    }

    Ok(())
}

#[tokio::test]
#[serial]
async fn request_login_provisioning_email_normalization_works() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());
    state.config.auth_auto_provision = true;
    // Config uses lowercase
    state.config.auth_allow_emails = Some(vec!["allowed@example.com".to_string()]);

    let app = app(state.clone());

    // Input has whitespace and mixed case
    let input_email = "  Allowed@EXAMPLE.com  ";
    let normalized_email = "allowed@example.com";

    let req = Request::post("/auth/magic-link/request")
        .header("Content-Type", "application/json")
        .body(body::Body::from(format!(
            r#"{{"email":"{}"}}"#,
            input_email
        )))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    // Verify account created with normalized email
    {
        let accounts = state.accounts.read().await;
        let found = accounts
            .values()
            .find(|acc| acc.email.as_deref() == Some(normalized_email));
        assert!(
            found.is_some(),
            "Account should be created with normalized email"
        );
    }

    Ok(())
}

#[tokio::test]
#[serial]
async fn request_login_mixed_case_stored_email_no_duplicate() -> Result<()> {
    // Regression test: eq_ignore_ascii_case in request_login's account lookup ensures that a
    // pre-existing account whose stored email has Mixed-Case (e.g. legacy data) is found when a
    // login request arrives with the normalised lowercase form.
    // Without the fix the lookup would miss the stored account and provision_account would create a
    // duplicate entry, because that path's own collision check was also case-sensitive before.
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());
    state.config.auth_auto_provision = true;
    // Allow the normalized email so the provisioning path would be entered if the lookup fails.
    state.config.auth_allow_emails = Some(vec!["user@mixedcase.example".to_string()]);

    // Insert a legacy account with a Mixed-Case stored email.
    let mixed_id = "legacy-mixed-case".to_string();
    {
        let mut accounts = state.accounts.write().await;
        accounts.insert(
            mixed_id.clone(),
            AccountInternal {
                public: AccountPublic {
                    id: mixed_id.clone(),
                    kind: "garnrolle".to_string(),
                    title: "Mixed Case Legacy".to_string(),
                    summary: None,
                    public_pos: None,
                    mode: weltgewebe_api::routes::accounts::AccountMode::Ron,
                    radius_m: 0,
                    disabled: false,
                    tags: vec![],
                },
                role: Role::Gast,
                email: Some("User@MixedCase.Example".to_string()), // Mixed-Case stored
            },
        );
    }

    let account_count_before = state.accounts.read().await.len();

    let app = app(state.clone());
    let req = Request::post("/auth/magic-link/request")
        .header("Content-Type", "application/json")
        .body(body::Body::from(r#"{"email":"user@mixedcase.example"}"#))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    let accounts = state.accounts.read().await;

    // No duplicate must have been created: the case-insensitive lookup finds the existing
    // account, so provision_account is never called.
    assert_eq!(
        accounts.len(),
        account_count_before,
        "No new account should be created when the stored Mixed-Case email matches case-insensitively"
    );

    // The original account must be the sole case-insensitive match for the request email.
    let matches: Vec<_> = accounts
        .values()
        .filter(|acc| {
            acc.email
                .as_deref()
                .map(|e| e.eq_ignore_ascii_case("user@mixedcase.example"))
                .unwrap_or(false)
        })
        .collect();
    assert_eq!(
        matches.len(),
        1,
        "Exactly one account should match the email case-insensitively"
    );
    assert_eq!(
        matches[0].public.id, mixed_id,
        "The matched account must be the original Mixed-Case account, not a new one"
    );

    Ok(())
}

#[tokio::test]
async fn session_endpoint_unauthenticated() -> Result<()> {
    let state = test_state_with_accounts()?;
    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state);

    let req = Request::get("/auth/session")
        .header("Host", "localhost")
        .body(body::Body::empty())?;

    let res = app.oneshot(req).await?;

    let status = res.status();
    let body_bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    if status != StatusCode::OK {
        println!("FAIL BODY: {:?}", String::from_utf8_lossy(&body_bytes));
    }
    assert_eq!(status, StatusCode::OK);

    let body_json: serde_json::Value = serde_json::from_slice(&body_bytes)?;

    assert_eq!(body_json["authenticated"], false);
    assert!(
        body_json.get("expires_at").is_none(),
        "expires_at must be completely omitted"
    );
    assert!(body_json.get("device_id").is_none());

    Ok(())
}

#[tokio::test]
async fn session_endpoint_authenticated() -> Result<()> {
    let state = test_state_with_accounts()?;
    // Mock a valid session for user u1
    let session = state.sessions.create("u1".to_string(), None);
    let session_id = session.id;

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state);

    let req = Request::get("/auth/session")
        .header("Host", "localhost")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                session_id
            ),
        )
        .body(body::Body::empty())?;

    let res = app.oneshot(req).await?;

    let status = res.status();
    let body_bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    if status != StatusCode::OK {
        println!("FAIL BODY: {:?}", String::from_utf8_lossy(&body_bytes));
    }
    assert_eq!(status, StatusCode::OK);

    let body_json: serde_json::Value = serde_json::from_slice(&body_bytes)?;

    assert_eq!(body_json["authenticated"], true);
    assert!(body_json.get("expires_at").is_some());
    assert_eq!(body_json["device_id"].as_str().unwrap(), session.device_id);

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_session_refresh_success() -> Result<()> {
    let _guard = weltgewebe_api::test_helpers::EnvGuard::set("AUTH_DEV_LOGIN", "1");
    let _guard_cookie = weltgewebe_api::test_helpers::EnvGuard::set("AUTH_COOKIE_SECURE", "1");
    let mut account_map = BTreeMap::new();
    let account = AccountInternal {
        public: AccountPublic {
            id: "u-admin".to_string(),
            kind: "garnrolle".to_string(),
            title: "User".to_string(),
            summary: None,
            public_pos: None,
            mode: weltgewebe_api::routes::accounts::AccountMode::Verortet,
            radius_m: 0,
            disabled: false,
            tags: vec![],
        },
        role: Role::Admin,
        email: Some("u1@example.com".to_string()),
    };
    account_map.insert(account.public.id.clone(), account);

    let mut state = test_state()?;
    state.accounts = Arc::new(RwLock::new(account_map));
    let app = Router::new()
        .merge(api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .layer(MockConnectInfo(
            "127.0.0.1:8080".parse::<SocketAddr>().unwrap(),
        ))
        .layer(axum::middleware::from_fn(
            weltgewebe_api::middleware::csrf::require_csrf,
        ))
        .with_state(state.clone());

    // 1. Login to get a session cookie
    let req = Request::post("/auth/dev/login")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::from(r#"{"account_id": "u-admin"}"#))?;

    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    let set_cookie = res.headers().get("Set-Cookie").unwrap().to_str().unwrap();
    let session_cookie = set_cookie.split(';').next().unwrap();
    assert!(set_cookie.contains("Secure"));
    assert!(set_cookie.contains("HttpOnly"));
    assert!(set_cookie.contains("SameSite=Lax"));

    // 2. Refresh session
    let req_refresh = Request::post("/auth/session/refresh")
        .header("Cookie", session_cookie)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())?;

    let res_refresh = app.clone().oneshot(req_refresh).await?;
    assert_eq!(res_refresh.status(), StatusCode::OK);

    // Verify new cookie is set
    let refresh_set_cookie = res_refresh
        .headers()
        .get("Set-Cookie")
        .unwrap()
        .to_str()
        .unwrap();
    let new_session_cookie = refresh_set_cookie.split(';').next().unwrap().to_string();
    assert!(refresh_set_cookie.contains("Secure"));
    assert!(refresh_set_cookie.contains("HttpOnly"));
    assert!(refresh_set_cookie.contains("SameSite=Lax"));
    assert_ne!(
        session_cookie, new_session_cookie,
        "Session cookie should be rotated"
    );

    let body_bytes = body::to_bytes(res_refresh.into_body(), usize::MAX).await?;
    let body: serde_json::Value = serde_json::from_slice(&body_bytes).unwrap();
    assert_eq!(body["authenticated"], true);
    assert!(body["expires_at"].is_string());
    assert!(
        body["device_id"].is_string(),
        "session refresh response must include device_id"
    );

    // 3. New cookie should be valid
    let req_new = Request::get("/auth/session")
        .header("Cookie", &new_session_cookie)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())?;

    let res_new = app.clone().oneshot(req_new).await?;
    let new_body_bytes = body::to_bytes(res_new.into_body(), usize::MAX).await?;
    let new_body: serde_json::Value = serde_json::from_slice(&new_body_bytes).unwrap();
    assert_eq!(new_body["authenticated"], true);
    assert!(new_body["expires_at"].is_string());

    // 4. Old cookie should now be invalid

    let req_old = Request::get("/auth/session")
        .header("Cookie", session_cookie)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())?;

    let res_old = app.clone().oneshot(req_old).await?;
    let old_body_bytes = body::to_bytes(res_old.into_body(), usize::MAX).await?;
    let old_body: serde_json::Value = serde_json::from_slice(&old_body_bytes).unwrap();
    assert_eq!(old_body["authenticated"], false);

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_session_refresh_invalid_token() -> Result<()> {
    let state = test_state()?;
    let app = Router::new()
        .merge(api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .layer(MockConnectInfo(
            "127.0.0.1:8080".parse::<SocketAddr>().unwrap(),
        ))
        .layer(axum::middleware::from_fn(
            weltgewebe_api::middleware::csrf::require_csrf,
        ))
        .with_state(state.clone());

    // Refresh with no cookie
    let req = Request::post("/auth/session/refresh")
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())?;

    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::UNAUTHORIZED);

    let body_bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let body: serde_json::Value = serde_json::from_slice(&body_bytes).unwrap();
    assert_eq!(body["error"], "SESSION_EXPIRED");

    // Refresh with invalid cookie
    let req2 = Request::post("/auth/session/refresh")
        .header("Cookie", "weltgewebe_session=invalid-session-id")
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())?;

    let res2 = app.clone().oneshot(req2).await?;
    assert_eq!(res2.status(), StatusCode::UNAUTHORIZED);

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_session_refresh_csrf_rejected() -> Result<()> {
    let _guard = weltgewebe_api::test_helpers::EnvGuard::set("AUTH_DEV_LOGIN", "1");
    let mut account_map = BTreeMap::new();
    let account = AccountInternal {
        public: AccountPublic {
            id: "u-admin".to_string(),
            kind: "garnrolle".to_string(),
            title: "User".to_string(),
            summary: None,
            public_pos: None,
            mode: weltgewebe_api::routes::accounts::AccountMode::Verortet,
            radius_m: 0,
            disabled: false,
            tags: vec![],
        },
        role: Role::Admin,
        email: Some("u1@example.com".to_string()),
    };
    account_map.insert(account.public.id.clone(), account);

    let mut state = test_state()?;
    state.accounts = Arc::new(RwLock::new(account_map));
    let app = Router::new()
        .merge(api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .layer(axum::middleware::from_fn(
            weltgewebe_api::middleware::csrf::require_csrf,
        ))
        .layer(MockConnectInfo(
            "127.0.0.1:8080".parse::<SocketAddr>().unwrap(),
        ))
        .with_state(state.clone());

    // 1. Login to get a session cookie
    let req = Request::post("/auth/dev/login")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::from(r#"{"account_id": "u-admin"}"#))?;

    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    let set_cookie = res.headers().get("Set-Cookie").unwrap().to_str().unwrap();
    let session_cookie = set_cookie.split(';').next().unwrap();

    // 2. Refresh session without Origin/Referer (CSRF failure)
    let req_refresh = Request::post("/auth/session/refresh")
        .header("Cookie", session_cookie)
        .header("Host", "localhost")
        .body(body::Body::empty())?;

    let res_refresh = app.clone().oneshot(req_refresh).await?;
    assert_eq!(res_refresh.status(), StatusCode::FORBIDDEN); // CSRF blocks it

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_session_refresh_account_disabled() -> Result<()> {
    let _guard = weltgewebe_api::test_helpers::EnvGuard::set("AUTH_DEV_LOGIN", "1");
    let mut account_map = BTreeMap::new();
    let mut account = AccountInternal {
        public: AccountPublic {
            id: "u-admin".to_string(),
            kind: "garnrolle".to_string(),
            title: "User".to_string(),
            summary: None,
            public_pos: None,
            mode: weltgewebe_api::routes::accounts::AccountMode::Verortet,
            radius_m: 0,
            disabled: false,
            tags: vec![],
        },
        role: Role::Admin,
        email: Some("u1@example.com".to_string()),
    };
    account_map.insert(account.public.id.clone(), account.clone());

    let mut state = test_state()?;
    state.accounts = Arc::new(RwLock::new(account_map.clone()));
    let app = Router::new()
        .merge(api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .layer(MockConnectInfo(
            "127.0.0.1:8080".parse::<SocketAddr>().unwrap(),
        ))
        .with_state(state.clone());

    // 1. Login to get a session cookie
    let req = Request::post("/auth/dev/login")
        .header("Content-Type", "application/json")
        .body(body::Body::from(r#"{"account_id": "u-admin"}"#))?;

    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    let set_cookie = res.headers().get("Set-Cookie").unwrap().to_str().unwrap();
    let session_cookie = set_cookie.split(';').next().unwrap().to_string();

    // 2. Disable account
    account.public.disabled = true;
    state
        .accounts
        .write()
        .await
        .insert(account.public.id.clone(), account);

    // 3. Refresh session (should fail)
    let req_refresh = Request::post("/auth/session/refresh")
        .header("Cookie", &session_cookie)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())?;

    let res_refresh = app.clone().oneshot(req_refresh).await?;
    assert_eq!(res_refresh.status(), StatusCode::UNAUTHORIZED);

    let refresh_set_cookie = res_refresh
        .headers()
        .get("Set-Cookie")
        .unwrap()
        .to_str()
        .unwrap();
    assert!(
        refresh_set_cookie.contains("Max-Age=0"),
        "Cookie should be deleted"
    );

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_logout() -> Result<()> {
    let _guard = weltgewebe_api::test_helpers::EnvGuard::set("AUTH_DEV_LOGIN", "1");
    let mut account_map = BTreeMap::new();
    let account = AccountInternal {
        public: AccountPublic {
            id: "u-admin".to_string(),
            kind: "garnrolle".to_string(),
            title: "User".to_string(),
            summary: None,
            public_pos: None,
            mode: weltgewebe_api::routes::accounts::AccountMode::Verortet,
            radius_m: 0,
            disabled: false,
            tags: vec![],
        },
        role: Role::Admin,
        email: Some("u1@example.com".to_string()),
    };
    account_map.insert(account.public.id.clone(), account);

    let mut state = test_state()?;
    state.accounts = Arc::new(RwLock::new(account_map));
    let app = Router::new()
        .merge(api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .layer(MockConnectInfo(
            "127.0.0.1:8080".parse::<SocketAddr>().unwrap(),
        ))
        .layer(axum::middleware::from_fn(
            weltgewebe_api::middleware::csrf::require_csrf,
        ))
        .with_state(state.clone());

    // 1. Login to get a session cookie
    let req = Request::post("/auth/dev/login")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::from(r#"{"account_id": "u-admin"}"#))?;

    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    let set_cookie = res.headers().get("Set-Cookie").unwrap().to_str().unwrap();
    let session_cookie = set_cookie.split(';').next().unwrap();

    // 2. Logout
    let req_logout = Request::post("/auth/logout")
        .header("Cookie", session_cookie)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())?;

    let res_logout = app.clone().oneshot(req_logout).await?;
    assert_eq!(res_logout.status(), StatusCode::OK);

    let logout_set_cookie = res_logout
        .headers()
        .get("Set-Cookie")
        .unwrap()
        .to_str()
        .unwrap();
    assert!(
        logout_set_cookie.contains("Max-Age=0"),
        "Cookie should be deleted"
    );

    // 3. Old cookie should now be invalid
    let req_old = Request::get("/auth/session")
        .header("Cookie", session_cookie)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())?;

    let res_old = app.clone().oneshot(req_old).await?;
    let old_body_bytes = body::to_bytes(res_old.into_body(), usize::MAX).await?;
    let old_body: serde_json::Value = serde_json::from_slice(&old_body_bytes).unwrap();
    assert_eq!(old_body["authenticated"], false);

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_logout_all_requires_step_up_and_preserves_sessions() -> Result<()> {
    let _guard = weltgewebe_api::test_helpers::EnvGuard::set("AUTH_DEV_LOGIN", "1");
    let mut account_map = BTreeMap::new();
    let account = AccountInternal {
        public: AccountPublic {
            id: "u-admin".to_string(),
            kind: "garnrolle".to_string(),
            title: "User".to_string(),
            summary: None,
            public_pos: None,
            mode: weltgewebe_api::routes::accounts::AccountMode::Verortet,
            radius_m: 0,
            disabled: false,
            tags: vec![],
        },
        role: Role::Admin,
        email: Some("u1@example.com".to_string()),
    };
    account_map.insert(account.public.id.clone(), account);

    let mut state = test_state()?;
    state.accounts = Arc::new(RwLock::new(account_map));
    let app = Router::new()
        .merge(api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .layer(MockConnectInfo(
            "127.0.0.1:8080".parse::<SocketAddr>().unwrap(),
        ))
        .layer(axum::middleware::from_fn(
            weltgewebe_api::middleware::csrf::require_csrf,
        ))
        .with_state(state.clone());

    // 1. Login once to get session 1
    let req1 = Request::post("/auth/dev/login")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::from(r#"{"account_id": "u-admin"}"#))?;

    let res1 = app.clone().oneshot(req1).await?;
    assert_eq!(res1.status(), StatusCode::OK);
    let set_cookie1 = res1.headers().get("Set-Cookie").unwrap().to_str().unwrap();
    let session_cookie1 = set_cookie1.split(';').next().unwrap().to_string();

    // 2. Login again to get session 2
    let req2 = Request::post("/auth/dev/login")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::from(r#"{"account_id": "u-admin"}"#))?;

    let res2 = app.clone().oneshot(req2).await?;
    assert_eq!(res2.status(), StatusCode::OK);
    let set_cookie2 = res2.headers().get("Set-Cookie").unwrap().to_str().unwrap();
    let session_cookie2 = set_cookie2.split(';').next().unwrap().to_string();

    assert_ne!(session_cookie1, session_cookie2);

    // 3. Logout All using session 1
    let req_logout_all = Request::post("/auth/logout-all")
        .header("Cookie", &session_cookie1)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())?;

    let res_logout_all = app.clone().oneshot(req_logout_all).await?;
    // It should now return 403 Forbidden as Step-Up Auth is required
    assert_eq!(res_logout_all.status(), StatusCode::FORBIDDEN);

    let body_bytes_logout_all = body::to_bytes(res_logout_all.into_body(), usize::MAX).await?;
    let body_logout_all: serde_json::Value =
        serde_json::from_slice(&body_bytes_logout_all).unwrap();
    assert_eq!(body_logout_all["error"], "STEP_UP_REQUIRED");
    assert!(body_logout_all["challenge_id"].is_string());

    let req_check_device_1 = Request::get("/auth/session")
        .header("Cookie", &session_cookie1)
        .header("Host", "localhost")
        .body(body::Body::empty())
        .unwrap();
    let res_check_device_1 = app.clone().oneshot(req_check_device_1).await.unwrap();
    let body_bytes_dev_1 = axum::body::to_bytes(res_check_device_1.into_body(), usize::MAX)
        .await
        .unwrap();
    let body_dev_1: serde_json::Value = serde_json::from_slice(&body_bytes_dev_1).unwrap();
    let expected_device_id_1 = body_dev_1["device_id"].as_str().unwrap().to_string();

    let challenge_id = body_logout_all["challenge_id"].as_str().unwrap();
    let challenge = state
        .challenges
        .get(challenge_id)
        .expect("Challenge not found in store");
    assert_eq!(challenge.account_id, "u-admin");
    assert_eq!(challenge.device_id, expected_device_id_1);
    assert_eq!(
        challenge.intent,
        weltgewebe_api::auth::challenges::ChallengeIntent::LogoutAll
    );

    // 4. Verify session 1 is STILL valid (no deletion without Step-Up)
    let req_check1 = Request::get("/auth/session")
        .header("Cookie", &session_cookie1)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())?;

    let res_check1 = app.clone().oneshot(req_check1).await?;
    let body_bytes1 = body::to_bytes(res_check1.into_body(), usize::MAX).await?;
    let body1: serde_json::Value = serde_json::from_slice(&body_bytes1).unwrap();
    assert_eq!(body1["authenticated"], true);

    // 5. Verify session 2 is ALSO STILL valid
    let req_check2 = Request::get("/auth/session")
        .header("Cookie", &session_cookie2)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())?;

    let res_check2 = app.clone().oneshot(req_check2).await?;
    let body_bytes2 = body::to_bytes(res_check2.into_body(), usize::MAX).await?;
    let body2: serde_json::Value = serde_json::from_slice(&body_bytes2).unwrap();
    assert_eq!(body2["authenticated"], true);

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_logout_all_unauthenticated_rejected() -> Result<()> {
    let state = test_state()?;
    let app = Router::new()
        .merge(api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .layer(MockConnectInfo(
            "127.0.0.1:8080".parse::<SocketAddr>().unwrap(),
        ))
        .layer(axum::middleware::from_fn(
            weltgewebe_api::middleware::csrf::require_csrf,
        ))
        .with_state(state.clone());

    let req = Request::post("/auth/logout-all")
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())?;

    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::UNAUTHORIZED);

    let body_bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let body_json: serde_json::Value = serde_json::from_slice(&body_bytes).unwrap();
    assert_eq!(body_json["error"], "UNAUTHORIZED");

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_device_management() -> Result<()> {
    let _guard = weltgewebe_api::test_helpers::EnvGuard::set("AUTH_DEV_LOGIN", "1");
    let mut account_map = std::collections::BTreeMap::new();
    let account = weltgewebe_api::routes::accounts::AccountInternal {
        public: weltgewebe_api::routes::accounts::AccountPublic {
            id: "u-admin".to_string(),
            kind: "garnrolle".to_string(),
            title: "User".to_string(),
            summary: None,
            public_pos: None,
            mode: weltgewebe_api::routes::accounts::AccountMode::Verortet,
            radius_m: 0,
            disabled: false,
            tags: vec![],
        },
        role: Role::Admin,
        email: Some("u1@example.com".to_string()),
    };
    account_map.insert(account.public.id.clone(), account);

    let state = test_state()?;
    state.accounts.write().await.insert(
        "u-admin".to_string(),
        account_map.get("u-admin").unwrap().clone(),
    );

    let app = Router::new()
        .merge(api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .layer(MockConnectInfo(
            "127.0.0.1:8080".parse::<std::net::SocketAddr>().unwrap(),
        ))
        .layer(axum::middleware::from_fn(
            weltgewebe_api::middleware::csrf::require_csrf,
        ))
        .with_state(state.clone());

    // 1. Login to get a session (Device A)
    let req1 = Request::post("/auth/dev/login")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::from(r#"{"account_id": "u-admin"}"#))?;

    let res1 = app.clone().oneshot(req1).await?;
    assert_eq!(res1.status(), StatusCode::OK);
    let set_cookie1 = res1.headers().get("Set-Cookie").unwrap().to_str().unwrap();
    let session_cookie1 = set_cookie1.split(';').next().unwrap().to_string();

    // 2. Refresh session 1 (should preserve device A)
    let req_refresh = Request::post("/auth/session/refresh")
        .header("Cookie", &session_cookie1)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())?;

    let res_refresh = app.clone().oneshot(req_refresh).await?;
    assert_eq!(res_refresh.status(), StatusCode::OK);
    let refresh_set_cookie = res_refresh
        .headers()
        .get("Set-Cookie")
        .unwrap()
        .to_str()
        .unwrap();
    let refresh_cookie = refresh_set_cookie.split(';').next().unwrap().to_string();

    // Verify session 1 gives device A
    let req_check_session1 = Request::get("/auth/session")
        .header("Cookie", &refresh_cookie)
        .header("Host", "localhost")
        .body(body::Body::empty())?;

    let res_check_session1 = app.clone().oneshot(req_check_session1).await?;
    let body_bytes1 = body::to_bytes(res_check_session1.into_body(), usize::MAX).await?;
    let body1: serde_json::Value = serde_json::from_slice(&body_bytes1).unwrap();
    let device_a_id = body1["device_id"].as_str().unwrap().to_string();

    // 3. Login again (Device B)
    let req2 = Request::post("/auth/dev/login")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::from(r#"{"account_id": "u-admin"}"#))?;

    let res2 = app.clone().oneshot(req2).await?;
    let set_cookie2 = res2.headers().get("Set-Cookie").unwrap().to_str().unwrap();
    let session_cookie2 = set_cookie2.split(';').next().unwrap().to_string();

    let req_check_session2 = Request::get("/auth/session")
        .header("Cookie", &session_cookie2)
        .header("Host", "localhost")
        .body(body::Body::empty())?;

    let res_check_session2 = app.clone().oneshot(req_check_session2).await?;
    let body_bytes2 = body::to_bytes(res_check_session2.into_body(), usize::MAX).await?;
    let body2: serde_json::Value = serde_json::from_slice(&body_bytes2).unwrap();
    let device_b_id = body2["device_id"].as_str().unwrap().to_string();

    assert_ne!(
        device_a_id, device_b_id,
        "Different logins should generate different device IDs"
    );

    // 4. GET /auth/devices using Device A
    let req_devices = Request::get("/auth/devices")
        .header("Cookie", &refresh_cookie)
        .header("Host", "localhost")
        .body(body::Body::empty())?;

    let res_devices = app.clone().oneshot(req_devices).await?;
    assert_eq!(res_devices.status(), StatusCode::OK);
    let body_bytes_dev = body::to_bytes(res_devices.into_body(), usize::MAX).await?;
    let devices: Vec<serde_json::Value> = serde_json::from_slice(&body_bytes_dev).unwrap();

    // There should be exactly 2 devices (the original session 1 was rotated out and replaced, so still 1 device for A)
    assert_eq!(devices.len(), 2);

    let current_dev = devices
        .iter()
        .find(|d| d["current"].as_bool().unwrap())
        .unwrap();
    assert_eq!(current_dev["device_id"].as_str().unwrap(), device_a_id);

    // 5. DELETE /auth/devices/:device_b_id using Device A (should return 403 Step-up required)
    let req_del_foreign = Request::delete(format!("/auth/devices/{}", device_b_id))
        .header("Cookie", &refresh_cookie)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())?;

    let res_del_foreign = app.clone().oneshot(req_del_foreign).await?;
    assert_eq!(res_del_foreign.status(), StatusCode::FORBIDDEN);

    let body_bytes_del_foreign = body::to_bytes(res_del_foreign.into_body(), usize::MAX).await?;
    let body_del_foreign: serde_json::Value =
        serde_json::from_slice(&body_bytes_del_foreign).unwrap();
    assert_eq!(body_del_foreign["error"], "STEP_UP_REQUIRED");
    assert!(body_del_foreign["challenge_id"].is_string());

    let challenge_id = body_del_foreign["challenge_id"].as_str().unwrap();
    let challenge = state
        .challenges
        .get(challenge_id)
        .expect("Challenge not found in store");
    assert_eq!(challenge.account_id, "u-admin");
    assert_eq!(challenge.device_id, device_a_id);
    if let weltgewebe_api::auth::challenges::ChallengeIntent::RemoveDevice { target_device_id } =
        challenge.intent
    {
        assert_eq!(target_device_id, device_b_id);
    } else {
        panic!("Incorrect challenge intent");
    }

    // Attempt to delete a non-existent foreign device (should return 404 NOT_FOUND)
    let req_del_fake = Request::delete(format!("/auth/devices/{}", "fake-device-id"))
        .header("Cookie", &refresh_cookie)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())
        .unwrap();

    let res_del_fake = app.clone().oneshot(req_del_fake).await.unwrap();
    assert_eq!(res_del_fake.status(), StatusCode::NOT_FOUND);

    let body_bytes_del_fake = axum::body::to_bytes(res_del_fake.into_body(), usize::MAX)
        .await
        .unwrap();
    let body_del_fake: serde_json::Value = serde_json::from_slice(&body_bytes_del_fake).unwrap();
    assert_eq!(body_del_fake["error"], "NOT_FOUND");
    assert!(body_del_fake.get("challenge_id").is_none());

    // Explicitly verify that the foreign device (Device B) is STILL valid
    let req_check_foreign = Request::get("/auth/session")
        .header("Cookie", &session_cookie2)
        .header("Host", "localhost")
        .body(body::Body::empty())?;

    let res_check_foreign = app.clone().oneshot(req_check_foreign).await?;
    let body_bytes_foreign = body::to_bytes(res_check_foreign.into_body(), usize::MAX).await?;
    let body_foreign: serde_json::Value = serde_json::from_slice(&body_bytes_foreign).unwrap();
    assert_eq!(
        body_foreign["authenticated"], true,
        "Foreign device should remain authenticated after 403 deletion attempt"
    );
    assert_eq!(body_foreign["device_id"].as_str().unwrap(), device_b_id);

    // 6. DELETE /auth/devices/:device_a_id using Device A (should delete current device)
    let req_del_self = Request::delete(format!("/auth/devices/{}", device_a_id))
        .header("Cookie", &refresh_cookie)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())?;

    let res_del_self = app.clone().oneshot(req_del_self).await?;
    assert_eq!(res_del_self.status(), StatusCode::NO_CONTENT);

    let logout_set_cookie = res_del_self
        .headers()
        .get("Set-Cookie")
        .unwrap()
        .to_str()
        .unwrap();
    assert!(
        logout_set_cookie.contains("Max-Age=0"),
        "Cookie should be deleted on self device removal"
    );

    // Verify Device A is gone
    let req_check_deleted = Request::get("/auth/session")
        .header("Cookie", &refresh_cookie)
        .header("Host", "localhost")
        .body(body::Body::empty())?;

    let res_check_deleted = app.clone().oneshot(req_check_deleted).await?;
    let body_bytes_deleted = body::to_bytes(res_check_deleted.into_body(), usize::MAX).await?;
    let body_deleted: serde_json::Value = serde_json::from_slice(&body_bytes_deleted).unwrap();
    assert_eq!(body_deleted["authenticated"], false);

    // Verify Device B is now the ONLY device left by querying /auth/devices using Device B's session
    let req_devices_b = Request::get("/auth/devices")
        .header("Cookie", &session_cookie2)
        .header("Host", "localhost")
        .body(body::Body::empty())?;

    let res_devices_b = app.clone().oneshot(req_devices_b).await?;
    assert_eq!(res_devices_b.status(), StatusCode::OK);
    let body_bytes_dev_b = body::to_bytes(res_devices_b.into_body(), usize::MAX).await?;
    let devices_b: Vec<serde_json::Value> = serde_json::from_slice(&body_bytes_dev_b).unwrap();

    assert_eq!(
        devices_b.len(),
        1,
        "Only Device B should remain after Device A was deleted"
    );
    assert_eq!(devices_b[0]["device_id"].as_str().unwrap(), device_b_id);
    assert!(
        devices_b[0]["current"].as_bool().unwrap(),
        "Device B should be current"
    );

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_step_up_magic_link_request_missing_mailer() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    let session = state.sessions.create("u1".to_string(), None);
    let session_id = session.id.clone();
    let device_id = session.device_id.clone();

    let challenge = state.challenges.create(
        "u1".to_string(),
        device_id,
        weltgewebe_api::auth::challenges::ChallengeIntent::LogoutAll,
    );

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    let req = Request::post("/auth/step-up/magic-link/request")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                session_id
            ),
        )
        .body(body::Body::from(format!(
            r#"{{"challenge_id":"{}"}}"#,
            challenge.id
        )))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::SERVICE_UNAVAILABLE);

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_step_up_magic_link_request_unauthenticated() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    let req = Request::post("/auth/step-up/magic-link/request")
        .header("Content-Type", "application/json")
        .body(body::Body::from(r#"{"challenge_id":"any-id"}"#))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
    Ok(())
}

#[tokio::test]
#[serial]
async fn test_step_up_magic_link_request_invalid_challenge() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    let session = state.sessions.create("u1".to_string(), None);
    let session_id = session.id;

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    let req = Request::post("/auth/step-up/magic-link/request")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                session_id
            ),
        )
        .body(body::Body::from(r#"{"challenge_id":"invalid-id"}"#))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    let body_bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let body_str = String::from_utf8_lossy(&body_bytes);
    assert!(body_str.contains("CHALLENGE_INVALID"));

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_step_up_magic_link_request_binding_mismatch() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    {
        let mut accounts = state.accounts.write().await;
        let account = weltgewebe_api::routes::accounts::AccountInternal {
            public: weltgewebe_api::routes::accounts::AccountPublic {
                id: "u2".to_string(),
                kind: "garnrolle".to_string(),
                title: "u2".to_string(),
                summary: None,
                public_pos: None,
                mode: weltgewebe_api::routes::accounts::AccountMode::Verortet,
                radius_m: 0,
                disabled: false,
                tags: vec![],
            },
            role: weltgewebe_api::auth::role::Role::Gast,
            email: Some("u2@example.com".to_string()),
        };
        accounts.insert("u2".to_string(), account);
    }
    let session2 = state.sessions.create("u2".to_string(), None);
    let session_id2 = session2.id;

    let session1 = state.sessions.create("u1".to_string(), None);
    let device_id1 = session1.device_id;
    let challenge1 = state.challenges.create(
        "u1".to_string(),
        device_id1,
        weltgewebe_api::auth::challenges::ChallengeIntent::LogoutAll,
    );

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    let req = Request::post("/auth/step-up/magic-link/request")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                session_id2
            ),
        )
        .body(body::Body::from(format!(
            r#"{{"challenge_id":"{}"}}"#,
            challenge1.id
        )))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    let body_bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let body_str = String::from_utf8_lossy(&body_bytes);
    assert!(body_str.contains("CHALLENGE_INVALID"));

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_step_up_magic_link_request_account_invalid() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    // Create u2 but without email
    {
        let mut accounts = state.accounts.write().await;
        let account = weltgewebe_api::routes::accounts::AccountInternal {
            public: weltgewebe_api::routes::accounts::AccountPublic {
                id: "u2".to_string(),
                kind: "garnrolle".to_string(),
                title: "u2".to_string(),
                summary: None,
                public_pos: None,
                mode: weltgewebe_api::routes::accounts::AccountMode::Verortet,
                radius_m: 0,
                disabled: false,
                tags: vec![],
            },
            role: weltgewebe_api::auth::role::Role::Gast,
            email: None, // Missing email
        };
        accounts.insert("u2".to_string(), account);
    }

    let session = state.sessions.create("u2".to_string(), None);
    let session_id = session.id.clone();
    let device_id = session.device_id.clone();

    let challenge = state.challenges.create(
        "u2".to_string(),
        device_id,
        weltgewebe_api::auth::challenges::ChallengeIntent::LogoutAll,
    );

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    let req = Request::post("/auth/step-up/magic-link/request")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                session_id
            ),
        )
        .body(body::Body::from(format!(
            r#"{{"challenge_id":"{}"}}"#,
            challenge.id
        )))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    let body_bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let body_str = String::from_utf8_lossy(&body_bytes);
    assert!(body_str.contains("ACCOUNT_INVALID"));

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_step_up_magic_link_request_missing_base_url() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = None; // explicitly missing

    let session = state.sessions.create("u1".to_string(), None);
    let session_id = session.id.clone();
    let device_id = session.device_id.clone();

    let challenge = state.challenges.create(
        "u1".to_string(),
        device_id,
        weltgewebe_api::auth::challenges::ChallengeIntent::LogoutAll,
    );

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    let req = Request::post("/auth/step-up/magic-link/request")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                session_id
            ),
        )
        .body(body::Body::from(
            r#"{"challenge_id":"any"}"#.replace("any", &challenge.id),
        ))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::INTERNAL_SERVER_ERROR);
    Ok(())
}

#[tokio::test]
#[serial]
async fn test_step_up_consume_unauthenticated() -> Result<()> {
    let state = test_state_with_accounts()?;
    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state);

    let req = Request::post("/auth/step-up/magic-link/consume")
        .header("Content-Type", "application/json")
        .body(body::Body::from(
            r#"{"token":"any-token","challenge_id":"any-id"}"#,
        ))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
    Ok(())
}

#[tokio::test]
#[serial]
async fn test_step_up_consume_invalid_token() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;

    let session = state.sessions.create("u1".to_string(), None);
    let session_id = session.id.clone();

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state);

    let req = Request::post("/auth/step-up/magic-link/consume")
        .header("Content-Type", "application/json")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                session_id
            ),
        )
        .body(body::Body::from(
            r#"{"token":"nonexistent-token","challenge_id":"any-id"}"#,
        ))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
    let body_bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let body: serde_json::Value = serde_json::from_slice(&body_bytes)?;
    assert_eq!(body["error"], "TOKEN_INVALID");
    Ok(())
}

#[tokio::test]
#[serial]
async fn test_step_up_consume_challenge_id_mismatch() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;

    let session = state.sessions.create("u1".to_string(), None);
    let session_id = session.id.clone();
    let device_id = session.device_id.clone();

    let challenge = state.challenges.create(
        "u1".to_string(),
        device_id.clone(),
        weltgewebe_api::auth::challenges::ChallengeIntent::LogoutAll,
    );
    // Token references challenge.id, but request claims a different challenge_id
    let token = state
        .step_up_tokens
        .create(challenge.id.clone(), "u1".to_string(), device_id);

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state);

    let req = Request::post("/auth/step-up/magic-link/consume")
        .header("Content-Type", "application/json")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                session_id
            ),
        )
        .body(body::Body::from(format!(
            r#"{{"token":"{}","challenge_id":"wrong-challenge-id"}}"#,
            token
        )))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
    let body_bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let body: serde_json::Value = serde_json::from_slice(&body_bytes)?;
    assert_eq!(body["error"], "TOKEN_INVALID");
    Ok(())
}

#[tokio::test]
#[serial]
// Documents the deliberate asymmetry: once consume_if_matches succeeds (token removed),
// a missing/expired challenge causes a 401 and the token cannot be reused — client must
// request a new step-up link.
async fn test_step_up_consume_challenge_missing_token_gone() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;

    let session = state.sessions.create("u1".to_string(), None);
    let session_id = session.id.clone();
    let device_id = session.device_id.clone();

    let challenge = state.challenges.create(
        "u1".to_string(),
        device_id.clone(),
        weltgewebe_api::auth::challenges::ChallengeIntent::LogoutAll,
    );
    let challenge_id = challenge.id.clone();
    let token = state
        .step_up_tokens
        .create(challenge_id.clone(), "u1".to_string(), device_id);

    // Pre-consume the challenge so it is gone when the HTTP call arrives
    state.challenges.consume(&challenge_id);

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    // Bindings match → token is removed; challenge is absent → 401
    let req = Request::post("/auth/step-up/magic-link/consume")
        .header("Content-Type", "application/json")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                session_id
            ),
        )
        .body(body::Body::from(format!(
            r#"{{"token":"{}","challenge_id":"{}"}}"#,
            token, challenge_id
        )))?;

    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
    let body_bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let body: serde_json::Value = serde_json::from_slice(&body_bytes)?;
    assert_eq!(body["error"], "TOKEN_INVALID");

    // Token is gone — retry with the exact same session, challenge_id, and token also fails.
    // This isolates the cause: the token was consumed during the first call (binding-match
    // succeeded) and is now NotFound in the store, regardless of challenge state.
    let req_retry = Request::post("/auth/step-up/magic-link/consume")
        .header("Content-Type", "application/json")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                session_id
            ),
        )
        .body(body::Body::from(format!(
            r#"{{"token":"{}","challenge_id":"{}"}}"#,
            token, challenge_id
        )))?;

    let res_retry = app.oneshot(req_retry).await?;
    assert_eq!(res_retry.status(), StatusCode::UNAUTHORIZED);
    let body_bytes = body::to_bytes(res_retry.into_body(), usize::MAX).await?;
    let body: serde_json::Value = serde_json::from_slice(&body_bytes)?;
    assert_eq!(body["error"], "TOKEN_INVALID");

    // Confirm at store level: the token is gone (NotFound, not BindingMismatch)
    use weltgewebe_api::auth::step_up_tokens::ConsumeMatchResult;
    let device_id = state.sessions.get(&session_id).unwrap().device_id;
    assert!(matches!(
        state
            .step_up_tokens
            .consume_if_matches(&token, &challenge_id, "u1", &device_id),
        ConsumeMatchResult::NotFound
    ));
    Ok(())
}

#[tokio::test]
#[serial]
// Verifies the 401/TOKEN_INVALID error response when a token is presented from the wrong session.
// See also: test_step_up_consume_session_mismatch_token_survives, which proves the token is preserved.
async fn test_step_up_consume_session_mismatch() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;

    // session1 belongs to u1/device1 — token is bound to this
    let session1 = state.sessions.create("u1".to_string(), None);
    let device_id1 = session1.device_id.clone();
    let challenge = state.challenges.create(
        "u1".to_string(),
        device_id1.clone(),
        weltgewebe_api::auth::challenges::ChallengeIntent::LogoutAll,
    );
    let token = state
        .step_up_tokens
        .create(challenge.id.clone(), "u1".to_string(), device_id1);

    // session2 belongs to u1 but a different device — we present this session
    let session2 = state.sessions.create("u1".to_string(), None);
    let session_id2 = session2.id.clone();

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state);

    let req = Request::post("/auth/step-up/magic-link/consume")
        .header("Content-Type", "application/json")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                session_id2
            ),
        )
        .body(body::Body::from(format!(
            r#"{{"token":"{}","challenge_id":"{}"}}"#,
            token, challenge.id
        )))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
    let body_bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let body: serde_json::Value = serde_json::from_slice(&body_bytes)?;
    assert_eq!(body["error"], "TOKEN_INVALID");
    Ok(())
}

#[tokio::test]
#[serial]
// Verifies the token-survival invariant: a wrong-session attempt returns 401 but does NOT burn
// the token, so the legitimate caller can still succeed on a subsequent attempt.
// See also: test_step_up_consume_session_mismatch, which focuses only on the error response.
async fn test_step_up_consume_session_mismatch_token_survives() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;

    // session1 belongs to u1/device1 — token and challenge are bound to this session
    let session1 = state.sessions.create("u1".to_string(), None);
    let session_id1 = session1.id.clone();
    let device_id1 = session1.device_id.clone();
    let challenge = state.challenges.create(
        "u1".to_string(),
        device_id1.clone(),
        weltgewebe_api::auth::challenges::ChallengeIntent::LogoutAll,
    );
    let token = state
        .step_up_tokens
        .create(challenge.id.clone(), "u1".to_string(), device_id1);

    // session2 belongs to u1 but a different device — wrong session
    let session2 = state.sessions.create("u1".to_string(), None);
    let session_id2 = session2.id.clone();

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    // First attempt: wrong session — must return 401 and must NOT burn the token
    let req_mismatch = Request::post("/auth/step-up/magic-link/consume")
        .header("Content-Type", "application/json")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                session_id2
            ),
        )
        .body(body::Body::from(format!(
            r#"{{"token":"{}","challenge_id":"{}"}}"#,
            token, challenge.id
        )))?;

    let res_mismatch = app.clone().oneshot(req_mismatch).await?;
    assert_eq!(res_mismatch.status(), StatusCode::UNAUTHORIZED);
    let body_bytes = body::to_bytes(res_mismatch.into_body(), usize::MAX).await?;
    let body: serde_json::Value = serde_json::from_slice(&body_bytes)?;
    assert_eq!(body["error"], "TOKEN_INVALID");

    // Second attempt: correct session — must succeed, proving the token was not burned
    let req_correct = Request::post("/auth/step-up/magic-link/consume")
        .header("Content-Type", "application/json")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                session_id1
            ),
        )
        .body(body::Body::from(format!(
            r#"{{"token":"{}","challenge_id":"{}"}}"#,
            token, challenge.id
        )))?;

    let res_correct = app.oneshot(req_correct).await?;
    assert_eq!(res_correct.status(), StatusCode::NO_CONTENT);
    Ok(())
}

#[tokio::test]
#[serial]
async fn test_step_up_consume_token_reuse_rejected() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;

    let session = state.sessions.create("u1".to_string(), None);
    let session_id = session.id.clone();
    let device_id = session.device_id.clone();

    let challenge = state.challenges.create(
        "u1".to_string(),
        device_id.clone(),
        weltgewebe_api::auth::challenges::ChallengeIntent::LogoutAll,
    );
    let token = state
        .step_up_tokens
        .create(challenge.id.clone(), "u1".to_string(), device_id);

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    // First call — should succeed
    let req1 = Request::post("/auth/step-up/magic-link/consume")
        .header("Content-Type", "application/json")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                session_id
            ),
        )
        .body(body::Body::from(format!(
            r#"{{"token":"{}","challenge_id":"{}"}}"#,
            token, challenge.id
        )))?;

    let res1 = app.clone().oneshot(req1).await?;
    assert_eq!(res1.status(), StatusCode::NO_CONTENT);

    // Recreate a session since all were deleted by LogoutAll
    let new_session = state.sessions.create("u1".to_string(), None);
    let new_session_id = new_session.id.clone();

    // Second call with the same token — must be rejected
    let req2 = Request::post("/auth/step-up/magic-link/consume")
        .header("Content-Type", "application/json")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                new_session_id
            ),
        )
        .body(body::Body::from(format!(
            r#"{{"token":"{}","challenge_id":"{}"}}"#,
            token, challenge.id
        )))?;

    let res2 = app.oneshot(req2).await?;
    assert_eq!(res2.status(), StatusCode::UNAUTHORIZED);
    let body_bytes = body::to_bytes(res2.into_body(), usize::MAX).await?;
    let body: serde_json::Value = serde_json::from_slice(&body_bytes)?;
    assert_eq!(body["error"], "TOKEN_INVALID");
    Ok(())
}

#[tokio::test]
#[serial]
async fn test_step_up_consume_logout_all_success() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;

    // Create two sessions for the same account
    let session1 = state.sessions.create("u1".to_string(), None);
    let session_id1 = session1.id.clone();
    let device_id1 = session1.device_id.clone();
    let session2 = state.sessions.create("u1".to_string(), None);
    let session_id2 = session2.id.clone();

    let challenge = state.challenges.create(
        "u1".to_string(),
        device_id1.clone(),
        weltgewebe_api::auth::challenges::ChallengeIntent::LogoutAll,
    );
    let token = state
        .step_up_tokens
        .create(challenge.id.clone(), "u1".to_string(), device_id1);

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    let req = Request::post("/auth/step-up/magic-link/consume")
        .header("Content-Type", "application/json")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                session_id1
            ),
        )
        .body(body::Body::from(format!(
            r#"{{"token":"{}","challenge_id":"{}"}}"#,
            token, challenge.id
        )))?;

    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::NO_CONTENT);

    // Session 1 must be gone
    assert!(state.sessions.get(&session_id1).is_none());
    // Session 2 must also be gone (LogoutAll)
    assert!(state.sessions.get(&session_id2).is_none());

    // The challenge must be consumed (single-use)
    assert!(state.challenges.get(&challenge.id).is_none());
    Ok(())
}

#[tokio::test]
#[serial]
async fn test_step_up_consume_remove_device_success() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;

    // session1 is the requesting session (device1)
    let session1 = state.sessions.create("u1".to_string(), None);
    let session_id1 = session1.id.clone();
    let device_id1 = session1.device_id.clone();

    // session2 is the target device to remove (device2)
    let session2 = state
        .sessions
        .create("u1".to_string(), Some("target-device".to_string()));
    let session_id2 = session2.id.clone();

    let challenge = state.challenges.create(
        "u1".to_string(),
        device_id1.clone(),
        weltgewebe_api::auth::challenges::ChallengeIntent::RemoveDevice {
            target_device_id: "target-device".to_string(),
        },
    );
    let token = state
        .step_up_tokens
        .create(challenge.id.clone(), "u1".to_string(), device_id1);

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    let req = Request::post("/auth/step-up/magic-link/consume")
        .header("Content-Type", "application/json")
        .header(
            "Cookie",
            format!(
                "{}={}",
                weltgewebe_api::routes::auth::SESSION_COOKIE_NAME,
                session_id1
            ),
        )
        .body(body::Body::from(format!(
            r#"{{"token":"{}","challenge_id":"{}"}}"#,
            token, challenge.id
        )))?;

    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::NO_CONTENT);

    // Target device (session2) must be removed
    assert!(state.sessions.get(&session_id2).is_none());
    // Requesting session (session1) must still be valid
    assert!(state.sessions.get(&session_id1).is_some());

    // The challenge must be consumed (single-use)
    assert!(state.challenges.get(&challenge.id).is_none());
    Ok(())
}

#[tokio::test]
#[serial]
async fn test_update_email_no_op_returns_204() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;

    let session = state
        .sessions
        .create("u1".to_string(), Some("dev1".to_string()));
    let cookie = format!("{}={}", SESSION_COOKIE_NAME, session.id);

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    let req = Request::builder()
        .method("PUT")
        .uri("/auth/me/email")
        .header("Cookie", cookie.clone())
        .header("Origin", "http://localhost")
        .header("Content-Type", "application/json")
        .header("X-Forwarded-For", "127.0.0.1")
        .body(body::Body::from(r#"{"new_email": "u1@example.com"}"#))?;

    let res = app.oneshot(req).await?;
    // Should be a no-op since the email is already u1@example.com
    assert_eq!(res.status(), StatusCode::NO_CONTENT);

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_update_email_full_e2e_flow() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    // Inject the mock mailer with a test sink
    let sink = std::sync::Arc::new(std::sync::Mutex::new(Vec::new()));
    state.config.smtp_host = Some("localhost".to_string());
    state.config.smtp_from = Some("noreply@example.com".to_string());
    let mailer = weltgewebe_api::mailer::Mailer::new(&state.config)
        .unwrap()
        .with_test_sink(sink.clone());
    state.mailer = Some(std::sync::Arc::new(mailer));

    let session = state
        .sessions
        .create("u1".to_string(), Some("dev1".to_string()));
    let cookie = format!("{}={}", SESSION_COOKIE_NAME, session.id);

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    // 1. PUT /auth/me/email
    let req1 = Request::builder()
        .method("PUT")
        .uri("/auth/me/email")
        .header("Cookie", cookie.clone())
        .header("Origin", "http://localhost")
        .header("Content-Type", "application/json")
        .header("X-Forwarded-For", "127.0.0.1")
        .body(body::Body::from(r#"{"new_email": "e2e@example.com"}"#))?;

    let res1 = app.clone().oneshot(req1).await?;
    assert_eq!(res1.status(), StatusCode::FORBIDDEN);

    let body_bytes = axum::body::to_bytes(res1.into_body(), usize::MAX).await?;
    let body_json: serde_json::Value = serde_json::from_slice(&body_bytes)?;
    let challenge_id = body_json["challenge_id"].as_str().unwrap().to_string();

    // 2. POST /auth/step-up/magic-link/request
    let req2 = Request::builder()
        .method("POST")
        .uri("/auth/step-up/magic-link/request")
        .header("Cookie", cookie.clone())
        .header("Content-Type", "application/json")
        .header("Origin", "http://localhost")
        .header("X-Forwarded-For", "127.0.0.1")
        .body(body::Body::from(
            serde_json::json!({
                "challenge_id": challenge_id
            })
            .to_string(),
        ))?;

    let res2 = app.clone().oneshot(req2).await?;
    assert_eq!(res2.status(), StatusCode::NO_CONTENT);

    // 3. Extract token from mail sink
    let token = {
        let messages = sink.lock().unwrap();
        assert_eq!(messages.len(), 1);
        assert_eq!(messages[0].0, "e2e@example.com"); // Mail went to new address

        let link = &messages[0].1;
        // The link format is "{base_url}/auth/step-up/consume?token={token}&challenge_id={id}"
        let parts: Vec<&str> = link.split("?token=").collect();
        parts[1].split("&challenge_id=").next().unwrap().to_string()
    };

    // 4. POST /auth/step-up/magic-link/consume
    let req3 = Request::builder()
        .method("POST")
        .uri("/auth/step-up/magic-link/consume")
        .header("Cookie", cookie)
        .header("Content-Type", "application/json")
        .header("Origin", "http://localhost")
        .header("X-Forwarded-For", "127.0.0.1")
        .body(body::Body::from(
            serde_json::json!({
                "token": token,
                "challenge_id": challenge_id
            })
            .to_string(),
        ))?;

    let res3 = app.oneshot(req3).await?;
    assert_eq!(res3.status(), StatusCode::NO_CONTENT);

    // 5. Assert the database email has changed
    let accounts = state.accounts.read().await;
    let acc = accounts.get("u1").unwrap();
    assert_eq!(acc.email, Some("e2e@example.com".to_string()));

    // Ensure challenge is consumed and gone
    assert!(state.challenges.get(&challenge_id).is_none());

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_update_email_invalid_format() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;

    let session = state
        .sessions
        .create("u1".to_string(), Some("dev1".to_string()));
    let cookie = format!("{}={}", SESSION_COOKIE_NAME, session.id);

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    let req1 = Request::builder()
        .method("PUT")
        .uri("/auth/me/email")
        .header("Cookie", cookie.clone())
        .header("Origin", "http://localhost")
        .header("Content-Type", "application/json")
        .header("X-Forwarded-For", "127.0.0.1")
        .body(body::Body::from(r#"{"new_email": "invalidemail"}"#))?;

    let res1 = app.clone().oneshot(req1).await?;
    assert_eq!(res1.status(), StatusCode::BAD_REQUEST);

    let req2 = Request::builder()
        .method("PUT")
        .uri("/auth/me/email")
        .header("Cookie", cookie.clone())
        .header("Origin", "http://localhost")
        .header("Content-Type", "application/json")
        .header("X-Forwarded-For", "127.0.0.1")
        .body(body::Body::from(
            r#"{"new_email": "invalid email@example.com"}"#, // space
        ))?;

    let res2 = app.clone().oneshot(req2).await?;
    assert_eq!(res2.status(), StatusCode::BAD_REQUEST);

    let req3 = Request::builder()
        .method("PUT")
        .uri("/auth/me/email")
        .header("Cookie", cookie.clone())
        .header("Origin", "http://localhost")
        .header("Content-Type", "application/json")
        .header("X-Forwarded-For", "127.0.0.1")
        .body(body::Body::from(
            r#"{"new_email": "nodomain@a"}"#, // missing dot
        ))?;

    let res3 = app.oneshot(req3).await?;
    assert_eq!(res3.status(), StatusCode::BAD_REQUEST);

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_update_email_requires_step_up() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;

    let session = state
        .sessions
        .create("u1".to_string(), Some("dev1".to_string()));
    let cookie = format!("{}={}", SESSION_COOKIE_NAME, session.id);

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    let req = Request::builder()
        .method("PUT")
        .uri("/auth/me/email")
        .header("Cookie", cookie.clone())
        .header("Origin", "http://localhost")
        .header("Content-Type", "application/json")
        .header("X-Forwarded-For", "127.0.0.1")
        .body(body::Body::from(r#"{"new_email": "new@example.com"}"#))?;

    let res = app.oneshot(req).await?;

    let status = res.status();
    let body_bytes = axum::body::to_bytes(res.into_body(), usize::MAX).await?;
    let body_str = String::from_utf8_lossy(&body_bytes);

    assert_eq!(status, StatusCode::FORBIDDEN);

    let body_json: serde_json::Value = serde_json::from_str(&body_str)?;
    assert_eq!(body_json["error"], "STEP_UP_REQUIRED");
    assert!(body_json.get("challenge_id").is_some());
    Ok(())
}

#[tokio::test]
#[serial]
async fn test_update_email_conflict_with_existing_account() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;

    let session = state
        .sessions
        .create("u1".to_string(), Some("dev1".to_string()));
    let cookie = format!("{}={}", SESSION_COOKIE_NAME, session.id);

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    // We must add u2 to state.accounts so there is a conflict
    {
        let mut accounts = state.accounts.write().await;
        accounts.insert(
            "u2".to_string(),
            weltgewebe_api::routes::accounts::AccountInternal {
                public: weltgewebe_api::routes::accounts::AccountPublic {
                    id: "u2".to_string(),
                    kind: "garnrolle".to_string(),
                    title: "User Two".to_string(),
                    summary: None,
                    public_pos: None,
                    mode: weltgewebe_api::routes::accounts::AccountMode::Verortet,
                    radius_m: 0,
                    disabled: false,
                    tags: vec![],
                },
                role: weltgewebe_api::auth::role::Role::Gast,
                email: Some("u2@example.com".to_string()),
            },
        );
    }

    // Try to update to an email that is already used by u2
    let req = Request::builder()
        .method("PUT")
        .uri("/auth/me/email")
        .header("Cookie", cookie.clone())
        .header("Origin", "http://localhost")
        .header("Content-Type", "application/json")
        .header("X-Forwarded-For", "127.0.0.1")
        .body(body::Body::from(r#"{"new_email": "u2@example.com"}"#))?;

    let res = app.oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::CONFLICT);
    Ok(())
}

#[tokio::test]
#[serial]
async fn test_update_email_consume_wrong_session() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;

    // Session 1 is the one that initiated the update
    let session1 = state
        .sessions
        .create("u1".to_string(), Some("dev1".to_string()));

    // Session 2 is an attacker or just another session
    let session2 = state
        .sessions
        .create("u2".to_string(), Some("dev2".to_string()));
    let wrong_cookie = format!("{}={}", SESSION_COOKIE_NAME, session2.id);

    use weltgewebe_api::auth::challenges::ChallengeIntent;

    let challenge = state.challenges.create(
        session1.account_id.clone(),
        session1.device_id.clone(),
        ChallengeIntent::UpdateEmail {
            new_email: "hacked@example.com".to_string(),
        },
    );

    let token = state.step_up_tokens.create(
        challenge.id.clone(),
        session1.account_id.clone(),
        session1.device_id.clone(),
    );

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    let req = Request::builder()
        .method("POST")
        .uri("/auth/step-up/magic-link/consume")
        .header("Cookie", wrong_cookie) // Attack attempt
        .header("Content-Type", "application/json")
        .header("Origin", "http://localhost")
        .header("X-Forwarded-For", "127.0.0.1")
        .body(body::Body::from(
            serde_json::json!({
                "token": token,
                "challenge_id": challenge.id
            })
            .to_string(),
        ))?;

    let res = app.oneshot(req).await?;
    // The binding mismatch rejects it
    assert_eq!(res.status(), StatusCode::UNAUTHORIZED);

    // Ensure the email wasn't updated
    let accounts = state.accounts.read().await;
    let acc = accounts.get("u1").unwrap();
    assert_ne!(acc.email, Some("hacked@example.com".to_string()));

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_update_email_consume_session_rotation() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;

    // Session 1 is the one that initiated the update (same device)
    let session1 = state
        .sessions
        .create("u1".to_string(), Some("dev1".to_string()));

    use weltgewebe_api::auth::challenges::ChallengeIntent;

    let challenge = state.challenges.create(
        session1.account_id.clone(),
        session1.device_id.clone(),
        ChallengeIntent::UpdateEmail {
            new_email: "rotated@example.com".to_string(),
        },
    );

    let token = state.step_up_tokens.create(
        challenge.id.clone(),
        session1.account_id.clone(),
        session1.device_id.clone(),
    );

    // Simulate session rotation: Session 1 expires, new Session 2 is created for the *same* device
    state.sessions.delete(&session1.id);
    let session2 = state
        .sessions
        .create("u1".to_string(), Some("dev1".to_string()));

    let new_cookie = format!("{}={}", SESSION_COOKIE_NAME, session2.id);

    let app = Router::new()
        .merge(weltgewebe_api::routes::api_router())
        .route_layer(axum::middleware::from_fn_with_state(
            state.clone(),
            weltgewebe_api::middleware::auth::auth_middleware,
        ))
        .with_state(state.clone());

    let req = Request::builder()
        .method("POST")
        .uri("/auth/step-up/magic-link/consume")
        .header("Cookie", new_cookie) // Consume with rotated session
        .header("Content-Type", "application/json")
        .header("Origin", "http://localhost")
        .header("X-Forwarded-For", "127.0.0.1")
        .body(body::Body::from(
            serde_json::json!({
                "token": token,
                "challenge_id": challenge.id
            })
            .to_string(),
        ))?;

    let res = app.oneshot(req).await?;

    // The binding matches because account_id and device_id match, despite the different session_id
    assert_eq!(res.status(), StatusCode::NO_CONTENT);

    // Ensure the email was updated
    let accounts = state.accounts.read().await;
    let acc = accounts.get("u1").unwrap();
    assert_eq!(acc.email, Some("rotated@example.com".to_string()));

    Ok(())
}

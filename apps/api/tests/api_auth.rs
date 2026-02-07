use anyhow::{Context, Result};
use axum::{
    body,
    extract::connect_info::MockConnectInfo,
    http::{HeaderMap, Request, StatusCode},
    Router,
};
use serial_test::serial;
use sha2::{Digest, Sha256};
use std::{collections::HashMap, net::SocketAddr, sync::Arc};
use tokio::sync::RwLock;
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
            auth_allow_emails: None,
            auth_allow_email_domains: None,
            auth_auto_provision: false,
        },
        metrics,
        sessions: SessionStore::new(),
        tokens: weltgewebe_api::auth::tokens::TokenStore::new(),
        accounts: Arc::new(RwLock::new(HashMap::new())),
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
async fn consume_login_flow_succeeds() -> Result<()> {
    let mut state = test_state_with_accounts()?;
    state.config.auth_public_login = true;
    state.config.app_base_url = Some("http://localhost".to_string());

    // Create a valid token
    let token = state.tokens.create("u1@example.com".to_string());
    let app = app(state);

    // 1. GET (Confirm Page)
    let uri = format!("/auth/login/consume?token={}", token);
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
    let req_post = Request::post("/auth/login/consume")
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

    let req =
        Request::get("/auth/login/consume?token=invalid_token_123").body(body::Body::empty())?;

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
    let uri = format!("/auth/login/consume?token={}", token);
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
    let req_post = Request::post("/auth/login/consume")
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

    let req = Request::post("/auth/login/consume")
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

    let req = Request::post("/auth/login/consume")
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
    let req = Request::post("/auth/login/request")
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
    let req = Request::post("/auth/login/request")
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
        assert_eq!(acc.public.title, "allowed");
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
    let req = Request::post("/auth/login/request")
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
    let req = Request::post("/auth/login/request")
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
    let req = Request::post("/auth/login/request")
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
    let req = Request::post("/auth/login/request")
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

    let req = Request::post("/auth/login/request")
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

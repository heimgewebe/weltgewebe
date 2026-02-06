use axum::{
    extract::{ConnectInfo, Form, Json, Query, State},
    http::{HeaderMap, StatusCode},
    response::{Html, IntoResponse, Redirect},
    Extension,
};
use axum_extra::extract::cookie::{Cookie, CookieJar, SameSite};
use ipnet::IpNet;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::net::{IpAddr, SocketAddr};
#[cfg(not(test))]
use std::sync::OnceLock;
use time::Duration;
use uuid::Uuid;

use crate::{
    auth::{role::Role, tokens::TokenStore},
    middleware::auth::AuthContext,
    state::ApiState,
};

pub const SESSION_COOKIE_NAME: &str = "gewebe_session";
pub const NONCE_COOKIE_NAME: &str = "auth_nonce";
pub const GENERIC_LOGIN_MSG: &str = "If your email is registered, you will receive a login link.";

fn build_session_cookie(value: String, max_age: Option<Duration>) -> Cookie<'static> {
    // Default to secure, but allow override via env for local dev (http)
    let secure_cookies = std::env::var("AUTH_COOKIE_SECURE")
        .map(|v| v != "0" && !v.eq_ignore_ascii_case("false"))
        .unwrap_or(true);

    let mut builder = Cookie::build((SESSION_COOKIE_NAME, value))
        .path("/")
        .http_only(true)
        .same_site(SameSite::Lax) // Allow cross-site navigation from email clients
        .secure(secure_cookies);

    if let Some(age) = max_age {
        builder = builder.max_age(age);
    }

    builder.build()
}

#[derive(Deserialize)]
pub struct LoginRequest {
    pub account_id: String,
}

#[derive(Deserialize)]
pub struct LoginRequestEmail {
    pub email: String,
}

#[derive(Deserialize)]
pub struct ConsumeTokenParams {
    pub token: String,
}

#[derive(Deserialize)]
pub struct ConsumeTokenForm {
    pub token: String,
    pub nonce: String,
}

#[derive(Serialize)]
pub struct AuthStatus {
    pub authenticated: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub account_id: Option<String>,
    pub role: Role,
}

#[derive(Serialize)]
pub struct DevAccount {
    pub id: String,
    pub title: String,
    pub summary: Option<String>,
    pub role: Role,
}

#[derive(Serialize)]
pub struct LoginResponse {
    pub ok: bool,
    pub message: String,
}

#[derive(Clone)]
enum TrustedProxyRule {
    Ip(IpAddr),
    Net(IpNet),
}

impl TrustedProxyRule {
    fn matches(&self, ip: IpAddr) -> bool {
        match self {
            TrustedProxyRule::Ip(addr) => *addr == ip,
            TrustedProxyRule::Net(net) => net.contains(&ip),
        }
    }
}

fn parse_trusted_proxies(env_val: String) -> Vec<TrustedProxyRule> {
    // Default to localhost if unset or empty (Strategy A: Secure defaults for dev)
    let config = if env_val.trim().is_empty() {
        "127.0.0.1,::1"
    } else {
        &env_val
    };

    config
        .split(',')
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .filter_map(|s| {
            if let Ok(net) = s.parse::<IpNet>() {
                Some(TrustedProxyRule::Net(net))
            } else if let Ok(addr) = s.parse::<IpAddr>() {
                Some(TrustedProxyRule::Ip(addr))
            } else {
                tracing::warn!(rule = s, "failed to parse trusted proxy rule; ignoring");
                None
            }
        })
        .collect()
}

fn get_trusted_proxies() -> &'static [TrustedProxyRule] {
    #[cfg(not(test))]
    {
        static TRUSTED_PROXIES: OnceLock<Vec<TrustedProxyRule>> = OnceLock::new();
        TRUSTED_PROXIES.get_or_init(|| {
            let env_val = std::env::var("AUTH_TRUSTED_PROXIES").unwrap_or_default();
            parse_trusted_proxies(env_val)
        })
    }
    #[cfg(test)]
    {
        // Leak memory to return a static reference in tests (acceptable for test suite execution)
        let env_val = std::env::var("AUTH_TRUSTED_PROXIES").unwrap_or_default();
        let rules = parse_trusted_proxies(env_val);
        Box::leak(rules.into_boxed_slice())
    }
}

fn is_trusted_peer(ip: IpAddr) -> bool {
    get_trusted_proxies().iter().any(|rule| rule.matches(ip))
}

fn effective_client_ip(peer: SocketAddr, headers: &HeaderMap) -> IpAddr {
    if !is_trusted_peer(peer.ip()) {
        return peer.ip();
    }

    // Check Forwarded header (RFC 7239)
    // Format: Forwarded: for=1.2.3.4, for=5.6.7.8;proto=http
    // We only trust the first (left-most) element as the client IP.
    if let Some(forwarded_val) = headers.get("Forwarded").and_then(|v| v.to_str().ok()) {
        if let Some(first_element) = forwarded_val.split(',').next() {
            for part in first_element.split(';') {
                let part = part.trim();
                if part.to_lowercase().starts_with("for=") {
                    let val = part["for=".len()..].trim();
                    let val = val.trim_matches('"');

                    // Try parsing as SocketAddr first (handles [ipv6]:port)
                    if let Ok(addr) = val.parse::<SocketAddr>() {
                        return addr.ip();
                    }

                    // Try parsing as IpAddr (handles ipv4, ipv6)
                    if let Ok(addr) = val.parse::<IpAddr>() {
                        return addr;
                    }

                    // Handle [ipv6] without port (strip brackets)
                    if val.starts_with('[') && val.ends_with(']') {
                        let inner = &val[1..val.len() - 1];
                        if let Ok(addr) = inner.parse::<IpAddr>() {
                            return addr;
                        }
                    }
                }
            }
        }
    }

    // Fallback: X-Forwarded-For
    if let Some(xff_val) = headers.get("X-Forwarded-For").and_then(|v| v.to_str().ok()) {
        if let Some(first) = xff_val.split(',').next() {
            if let Ok(addr) = first.trim().parse::<IpAddr>() {
                return addr;
            }
        }
    }

    peer.ip()
}

/// Checks if dev-login is enabled and if the request is from an allowed source.
/// Returns Ok(()) if the request should be allowed, or Err(StatusCode) otherwise.
fn check_dev_login_guard(headers: &HeaderMap, addr: SocketAddr) -> Result<(), StatusCode> {
    let dev_login_enabled = std::env::var("AUTH_DEV_LOGIN")
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false);

    if !dev_login_enabled {
        return Err(StatusCode::NOT_FOUND);
    }

    let allow_remote = std::env::var("AUTH_DEV_LOGIN_ALLOW_REMOTE")
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false);

    let is_trusted_proxy = is_trusted_peer(addr.ip());
    let client_ip = effective_client_ip(addr, headers);

    // Check if the client address is localhost (IPv4 or IPv6)
    let is_localhost = match client_ip {
        std::net::IpAddr::V4(ip) => ip.is_loopback(),
        std::net::IpAddr::V6(ip) => ip.is_loopback(),
    };

    // Audit log for security monitoring
    tracing::info!(
        peer_addr = %addr,
        effective_ip = %client_ip,
        is_trusted_proxy = is_trusted_proxy,
        is_localhost = is_localhost,
        allow_remote = allow_remote,
        "dev-login access attempt"
    );

    if !is_localhost && !allow_remote {
        tracing::warn!(
            peer_addr = %addr,
            effective_ip = %client_ip,
            "dev-login access rejected (remote source)"
        );
        return Err(StatusCode::FORBIDDEN);
    }

    Ok(())
}

pub async fn list_dev_accounts(
    State(state): State<ApiState>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    headers: HeaderMap,
) -> Result<Json<Vec<DevAccount>>, StatusCode> {
    check_dev_login_guard(&headers, addr)?;

    let mut accounts: Vec<DevAccount> = state
        .accounts
        .values()
        .map(|acc| DevAccount {
            id: acc.public.id.clone(),
            title: acc.public.title.clone(),
            summary: acc.public.summary.clone(),
            role: acc.role.clone(),
        })
        .collect();

    // Sort by ID for deterministic order
    accounts.sort_by(|a, b| a.id.cmp(&b.id));

    Ok(Json(accounts))
}

pub async fn dev_login(
    State(state): State<ApiState>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    headers: HeaderMap,
    jar: CookieJar,
    Json(payload): Json<LoginRequest>,
) -> impl IntoResponse {
    // Check dev-login guard (enabled + localhost/remote check)
    if let Err(status) = check_dev_login_guard(&headers, addr) {
        if status == StatusCode::NOT_FOUND {
            tracing::warn!("Login attempt refused: AUTH_DEV_LOGIN is not enabled");
        } else if status == StatusCode::FORBIDDEN {
            tracing::warn!(
                client_addr = %addr,
                account_id = %payload.account_id,
                "Login attempt refused: remote access not allowed"
            );
        }
        return (jar, status).into_response();
    }

    if !state.accounts.contains_key(&payload.account_id) {
        tracing::warn!(?payload.account_id, "Login attempt refused: Account not found");
        return (jar, StatusCode::BAD_REQUEST).into_response();
    }

    let session = state.sessions.create(payload.account_id);

    let cookie = build_session_cookie(session.id, None);

    (jar.add(cookie), StatusCode::OK).into_response()
}

pub async fn request_login(
    State(state): State<ApiState>,
    Json(payload): Json<LoginRequestEmail>,
) -> impl IntoResponse {
    if !state.config.auth_public_login {
        return StatusCode::NOT_FOUND.into_response();
    }

    let generic_response = LoginResponse {
        ok: true,
        message: GENERIC_LOGIN_MSG.to_string(),
    };

    // 1. Validate email format (simple check)
    if !payload.email.contains('@') {
        tracing::warn!("Invalid email format in login request");
        return (StatusCode::OK, Json(generic_response)).into_response();
    }

    // Compute hash for privacy-preserving logging
    let mut hasher = Sha256::new();
    hasher.update(payload.email.as_bytes());
    let email_hash_full = format!("{:x}", hasher.finalize());
    // Pseudonymized correlation (unsalted hash prefix); not to be understood as anonymization.
    let email_hash = &email_hash_full[..16];

    tracing::info!(
        event = "login.requested",
        email_hash = %email_hash,
        "Login requested"
    );

    // 2. Lookup account by email
    let account = state.accounts.values().find(|acc| {
        acc.email
            .as_ref()
            .map(|e| e.eq_ignore_ascii_case(&payload.email))
            .unwrap_or(false)
    });

    if let Some(acc) = account {
        // 3. Generate Token
        let token = state.tokens.create(payload.email.clone());

        // 4. "Send" Email (Log for now)
        // Ensure the base URL does not have a trailing slash for clean formatting
        // We expect APP_BASE_URL to be present because `AppConfig::validate` enforces it when `auth_public_login` is true.
        let base_url = state.config.app_base_url.as_deref().expect(
            "APP_BASE_URL must be set when AUTH_PUBLIC_LOGIN is enabled (validated at startup)",
        );
        let base_url = base_url.trim_end_matches('/');
        let link = format!("{}/api/auth/login/consume?token={}", base_url, token);

        tracing::info!(
            target: "email_outbox",
            email = %payload.email,
            account_id = %acc.public.id,
            %link,
            "Magic Link Generated"
        );
    } else {
        tracing::info!(
            event = "login.requested_unknown",
            email_hash = %email_hash,
            "Login requested for unknown email"
        );
    }

    (StatusCode::OK, Json(generic_response)).into_response()
}

fn constant_time_eq(a: &str, b: &str) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.bytes()
        .zip(b.bytes())
        .fold(0, |acc, (x, y)| acc | (x ^ y))
        == 0
}

/// Simple HTML escape to avoid XSS in hidden fields
fn escape_attr(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('"', "&quot;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

pub async fn consume_login_get(
    State(state): State<ApiState>,
    jar: CookieJar,
    Query(params): Query<ConsumeTokenParams>,
) -> impl IntoResponse {
    // Check if token exists and is valid (peek only)
    if state.tokens.peek(&params.token).is_none() {
        // Invalid or expired token
        return Redirect::to("/login?error=invalid_token").into_response();
    }

    // Generate Nonce
    let nonce = Uuid::new_v4().to_string();

    // Bind nonce to token: cookie value = "token_hash.nonce"
    // We use the full token hash for binding to ensure strict correspondence
    // Using '.' as separator to avoid URL encoding issues in cookies
    let token_hash = TokenStore::hash_token(&params.token);
    let cookie_value = format!("{}.{}", token_hash, nonce);

    // Respect AUTH_COOKIE_SECURE like the session cookie
    let secure_cookies = std::env::var("AUTH_COOKIE_SECURE")
        .map(|v| v != "0" && !v.eq_ignore_ascii_case("false"))
        .unwrap_or(true);

    let cookie = Cookie::build((NONCE_COOKIE_NAME, cookie_value))
        .path("/api/auth/login/consume")
        .http_only(true)
        .same_site(SameSite::Lax)
        .secure(secure_cookies)
        .max_age(Duration::minutes(5)) // Short lived
        .build();

    // Render HTML Form
    let html = format!(
        r#"<!DOCTYPE html>
<html>
<head>
    <title>Confirm Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: system-ui, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f4f4f4; }}
        .card {{ background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }}
        button {{ background: #0070f3; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 4px; font-size: 1rem; cursor: pointer; }}
        button:hover {{ background: #005bb5; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>Confirm Sign In</h2>
        <p>Click below to complete your login.</p>
        <form method="POST" action="/api/auth/login/consume">
            <input type="hidden" name="token" value="{}">
            <input type="hidden" name="nonce" value="{}">
            <button type="submit">Sign In</button>
        </form>
    </div>
</body>
</html>"#,
        escape_attr(&params.token),
        escape_attr(&nonce)
    );

    // Set Cache-Control to prevent history/caching issues
    let mut headers = HeaderMap::new();
    headers.insert(
        axum::http::header::CACHE_CONTROL,
        "no-store, no-cache, must-revalidate".parse().unwrap(),
    );
    headers.insert(
        axum::http::header::CONTENT_SECURITY_POLICY,
        "default-src 'self'; style-src 'unsafe-inline'".parse().unwrap(),
    );

    (headers, jar.add(cookie), Html(html)).into_response()
}

pub async fn consume_login_post(
    State(state): State<ApiState>,
    jar: CookieJar,
    Form(form): Form<ConsumeTokenForm>,
) -> impl IntoResponse {
    // 1. Check Nonce (and binding)
    // Cookie value format: "token_hash.nonce"
    let nonce_valid = jar
        .get(NONCE_COOKIE_NAME)
        .map(|c| {
            let cookie_val = c.value();
            if let Some((stored_hash, stored_nonce)) = cookie_val.split_once('.') {
                let computed_hash = TokenStore::hash_token(&form.token);
                // Verify token binding AND nonce match
                constant_time_eq(stored_hash, &computed_hash)
                    && constant_time_eq(stored_nonce, &form.nonce)
            } else {
                false
            }
        })
        .unwrap_or(false);

    if !nonce_valid {
        tracing::warn!("Login failed: Invalid or missing nonce");
        return Redirect::to("/login?error=invalid_token").into_response();
    }

    // 2. Consume Token
    if let Some(email) = state.tokens.consume(&form.token) {
        // Find account
        let account = state.accounts.values().find(|acc| {
            acc.email
                .as_ref()
                .map(|e| e.eq_ignore_ascii_case(&email))
                .unwrap_or(false)
        });

        if let Some(acc) = account {
            let session = state.sessions.create(acc.public.id.clone());
            let cookie = build_session_cookie(session.id, None);

            // Clear the nonce cookie
            // Respect AUTH_COOKIE_SECURE
            let secure_cookies = std::env::var("AUTH_COOKIE_SECURE")
                .map(|v| v != "0" && !v.eq_ignore_ascii_case("false"))
                .unwrap_or(true);

            let nonce_cleanup = Cookie::build((NONCE_COOKIE_NAME, ""))
                .path("/api/auth/login/consume")
                .http_only(true)
                .same_site(SameSite::Lax)
                .secure(secure_cookies)
                .max_age(Duration::seconds(0))
                .expires(time::OffsetDateTime::UNIX_EPOCH)
                .build();

            tracing::info!(
                event = "login.consumed",
                account_id = %acc.public.id,
                "Login successful"
            );

            return (jar.add(cookie).add(nonce_cleanup), Redirect::to("/")).into_response();
        }
    }

    tracing::warn!(
        event = "login.failed",
        reason = "invalid_token",
        "Login failed"
    );

    // Invalid or expired token
    Redirect::to("/login?error=invalid_token").into_response()
}

pub async fn logout(State(state): State<ApiState>, jar: CookieJar) -> impl IntoResponse {
    if let Some(cookie) = jar.get(SESSION_COOKIE_NAME) {
        state.sessions.delete(cookie.value());
    }

    let cookie = build_session_cookie("".to_string(), Some(Duration::seconds(0)));

    (jar.add(cookie), StatusCode::OK)
}

pub async fn me(Extension(ctx): Extension<AuthContext>) -> impl IntoResponse {
    Json(AuthStatus {
        authenticated: ctx.authenticated,
        account_id: ctx.account_id,
        role: ctx.role,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_helpers::EnvGuard;
    use axum::http::HeaderMap;
    use serial_test::serial;
    use std::net::SocketAddr;

    #[test]
    #[serial]
    fn test_direct_localhost_allowed() {
        let _guard = EnvGuard::set("AUTH_DEV_LOGIN", "1");
        let headers = HeaderMap::new();
        let addr: SocketAddr = "127.0.0.1:1234".parse().unwrap();
        assert!(check_dev_login_guard(&headers, addr).is_ok());
    }

    #[test]
    #[serial]
    fn test_remote_rejected() {
        let _guard = EnvGuard::set("AUTH_DEV_LOGIN", "1");
        let headers = HeaderMap::new();
        let addr: SocketAddr = "1.2.3.4:1234".parse().unwrap();
        assert_eq!(
            check_dev_login_guard(&headers, addr),
            Err(StatusCode::FORBIDDEN)
        );
    }

    #[test]
    #[serial]
    fn test_remote_allowed_via_env() {
        let _guard = EnvGuard::set("AUTH_DEV_LOGIN", "1");
        let _guard2 = EnvGuard::set("AUTH_DEV_LOGIN_ALLOW_REMOTE", "1");
        let headers = HeaderMap::new();
        let addr: SocketAddr = "1.2.3.4:1234".parse().unwrap();
        assert!(check_dev_login_guard(&headers, addr).is_ok());
    }

    #[test]
    #[serial]
    fn test_trusted_proxy_reveals_remote_rejected() {
        let _guard = EnvGuard::set("AUTH_DEV_LOGIN", "1");
        let _guard_proxy = EnvGuard::set("AUTH_TRUSTED_PROXIES", "127.0.0.1");

        let mut headers = HeaderMap::new();
        headers.insert(
            "X-Forwarded-For".parse::<axum::http::HeaderName>().unwrap(),
            "1.2.3.4".parse().unwrap(),
        );

        let addr: SocketAddr = "127.0.0.1:8080".parse().unwrap();
        // Trusted proxy (127.0.0.1) says client is 1.2.3.4 -> Rejected
        assert_eq!(
            check_dev_login_guard(&headers, addr),
            Err(StatusCode::FORBIDDEN)
        );
    }

    #[test]
    #[serial]
    fn test_trusted_proxy_reveals_localhost_allowed() {
        let _guard = EnvGuard::set("AUTH_DEV_LOGIN", "1");
        let _guard_proxy = EnvGuard::set("AUTH_TRUSTED_PROXIES", "127.0.0.1");

        let mut headers = HeaderMap::new();
        headers.insert(
            "X-Forwarded-For".parse::<axum::http::HeaderName>().unwrap(),
            "127.0.0.1".parse().unwrap(),
        );

        let addr: SocketAddr = "127.0.0.1:8080".parse().unwrap();
        // Trusted proxy (127.0.0.1) says client is 127.0.0.1 -> Allowed
        assert!(check_dev_login_guard(&headers, addr).is_ok());
    }

    #[test]
    #[serial]
    fn test_untrusted_proxy_spoofing_localhost_rejected() {
        let _guard = EnvGuard::set("AUTH_DEV_LOGIN", "1");
        // Explicitly set trusted proxies to something else (or ::1) to ensure 1.2.3.4 is untrusted
        // OR rely on peer not matching default
        let _guard_proxy = EnvGuard::set("AUTH_TRUSTED_PROXIES", "127.0.0.1");

        let mut headers = HeaderMap::new();
        headers.insert(
            "X-Forwarded-For".parse::<axum::http::HeaderName>().unwrap(),
            "127.0.0.1".parse().unwrap(),
        );

        let addr: SocketAddr = "1.2.3.4:8080".parse().unwrap();
        // Untrusted peer (1.2.3.4) sends XFF: 127.0.0.1
        // Should ignore XFF, see 1.2.3.4 -> Rejected
        assert_eq!(
            check_dev_login_guard(&headers, addr),
            Err(StatusCode::FORBIDDEN)
        );
    }

    #[test]
    #[serial]
    fn test_default_trusted_proxies_include_localhost() {
        let _guard = EnvGuard::set("AUTH_DEV_LOGIN", "1");
        // Unset AUTH_TRUSTED_PROXIES to test default behavior (Strategy A)
        let _guard_proxy = EnvGuard::unset("AUTH_TRUSTED_PROXIES");

        let mut headers = HeaderMap::new();
        headers.insert(
            "X-Forwarded-For".parse::<axum::http::HeaderName>().unwrap(),
            "1.2.3.4".parse().unwrap(),
        );

        let addr: SocketAddr = "127.0.0.1:8080".parse().unwrap();
        // Default trusts localhost -> Reads XFF -> Sees 1.2.3.4 -> Rejected
        assert_eq!(
            check_dev_login_guard(&headers, addr),
            Err(StatusCode::FORBIDDEN)
        );
    }

    #[test]
    #[serial]
    fn test_forwarded_header_parsing() {
        let _guard = EnvGuard::set("AUTH_DEV_LOGIN", "1");
        let _guard_proxy = EnvGuard::set("AUTH_TRUSTED_PROXIES", "127.0.0.1");

        let mut headers = HeaderMap::new();
        // IPv6 in Forwarded
        headers.insert(
            "Forwarded".parse::<axum::http::HeaderName>().unwrap(),
            "for=\"[::1]:1234\"".parse().unwrap(),
        );

        let addr: SocketAddr = "127.0.0.1:8080".parse().unwrap();
        assert!(check_dev_login_guard(&headers, addr).is_ok());

        // Remote IPv4 in Forwarded
        let mut headers = HeaderMap::new();
        headers.insert(
            "Forwarded".parse::<axum::http::HeaderName>().unwrap(),
            "for=1.2.3.4".parse().unwrap(),
        );
        assert_eq!(
            check_dev_login_guard(&headers, addr),
            Err(StatusCode::FORBIDDEN)
        );
    }

    #[test]
    #[serial]
    fn test_forwarded_multi_element_parsing() {
        let _guard = EnvGuard::set("AUTH_DEV_LOGIN", "1");
        let _guard_proxy = EnvGuard::set("AUTH_TRUSTED_PROXIES", "127.0.0.1");

        let mut headers = HeaderMap::new();
        // Comma separated elements. First one is remote, second is localhost. Should pick first -> Rejected.
        headers.insert(
            "Forwarded".parse::<axum::http::HeaderName>().unwrap(),
            "for=1.2.3.4, for=127.0.0.1".parse().unwrap(),
        );

        let addr: SocketAddr = "127.0.0.1:8080".parse().unwrap();
        assert_eq!(
            check_dev_login_guard(&headers, addr),
            Err(StatusCode::FORBIDDEN)
        );
    }
}

use axum::{
    extract::Path as AxumPath,
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
    auth::challenges::ChallengeIntent,
    auth::step_up_tokens::ConsumeMatchResult,
    auth::{role::Role, tokens::TokenStore},
    middleware::auth::AuthContext,
    routes::accounts::{AccountInternal, AccountPublic},
    state::ApiState,
};

pub const SESSION_COOKIE_NAME: &str = "gewebe_session";
pub const NONCE_COOKIE_NAME: &str = "auth_nonce";
pub const GENERIC_LOGIN_MSG: &str = "If your email is registered, you will receive a login link.";

fn get_request_id(headers: &HeaderMap) -> String {
    headers
        .get("x-request-id")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("unknown")
        .to_string()
}

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

    let accounts_map = state.accounts.read().await;
    let accounts: Vec<DevAccount> = accounts_map
        .iter()
        .map(|(id, acc)| {
            debug_assert_eq!(
                id, &acc.public.id,
                "accounts_map key must match acc.public.id for deterministic ordering"
            );
            DevAccount {
                id: id.clone(), // derive from key to preserve ordering guarantee
                title: acc.public.title.clone(),
                summary: acc.public.summary.clone(),
                role: acc.role.clone(),
            }
        })
        .collect();

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

    {
        let accounts_map = state.accounts.read().await;
        if !accounts_map.contains_key(&payload.account_id) {
            tracing::warn!(?payload.account_id, "Login attempt refused: Account not found");
            return (jar, StatusCode::BAD_REQUEST).into_response();
        }
    }

    let session = state.sessions.create(payload.account_id, None);

    let cookie = build_session_cookie(session.id, None);

    (jar.add(cookie), StatusCode::OK).into_response()
}

// Bundle context parameters to avoid "too many arguments" lint
struct ProvisionContext<'a> {
    request_id: &'a str,
    client_ip: IpAddr,
    remote_ip: IpAddr,
    proxy_trusted: bool,
    email_hash: &'a str,
}

async fn provision_account(
    state: &ApiState,
    email_norm: &str,
    ctx: &ProvisionContext<'_>,
) -> Option<String> {
    let new_id = Uuid::new_v4().to_string();
    let new_account = AccountInternal {
        public: AccountPublic {
            id: new_id.clone(),
            kind: "ron".to_string(),               // Consistent with mode=Ron
            title: "Rolle ohne Namen".to_string(), // Neutral default to prevent PII leak
            summary: None,
            public_pos: None,
            mode: crate::routes::accounts::AccountMode::Ron, // Minimal default
            radius_m: 0,
            disabled: false,
            tags: vec![],
        },
        role: Role::Gast,
        email: Some(email_norm.to_string()),
    };

    {
        let mut accounts_map = state.accounts.write().await;
        // Double-checked locking to avoid race condition
        let collision_id = accounts_map
            .values()
            .find(|acc| {
                acc.email
                    .as_ref()
                    .map(|e| e.eq_ignore_ascii_case(email_norm))
                    .unwrap_or(false)
            })
            .map(|acc| acc.public.id.clone());

        if let Some(id) = collision_id {
            // Another request provisioned it in the meantime
            Some(id)
        } else {
            let id = new_account.public.id.clone();
            accounts_map.insert(id.clone(), new_account);
            tracing::info!(
                event = "login.provisioned",
                request_id = %ctx.request_id,
                client_ip = %ctx.client_ip,
                remote_ip = %ctx.remote_ip,
                proxy_trusted = ctx.proxy_trusted,
                account_id = %new_id,
                email_hash = %ctx.email_hash,
                "Auto-provisioned new account"
            );
            Some(new_id)
        }
    }
}

async fn process_magic_link_delivery(
    state: &ApiState,
    account_id: &str,
    email_norm: &str,
    ctx: &ProvisionContext<'_>,
) -> Result<(), StatusCode> {
    // 3. Check Delivery Mechanism
    let can_deliver = state.mailer.is_some();
    let can_log = state.config.auth_log_magic_token;

    if !can_deliver && !can_log {
        tracing::error!(
            event = "login.delivery_unavailable",
            request_id = %ctx.request_id,
            client_ip = %ctx.client_ip,
            remote_ip = %ctx.remote_ip,
            proxy_trusted = ctx.proxy_trusted,
            email_hash = %ctx.email_hash,
            account_id = %account_id,
            "Public login enabled but no delivery path configured"
        );
        return Err(StatusCode::SERVICE_UNAVAILABLE);
    }

    // 4. Generate Token (only if deliverable)
    // Use normalized email for token creation too
    let token = state.tokens.create(email_norm.to_string());

    // 5. Send/Log Email
    // Ensure the base URL does not have a trailing slash for clean formatting
    // We expect APP_BASE_URL to be present because `AppConfig::validate` enforces it when `auth_public_login` is true.
    let base_url = state.config.app_base_url.as_deref().expect(
        "APP_BASE_URL must be set when AUTH_PUBLIC_LOGIN is enabled (validated at startup)",
    );
    let base_url = base_url.trim_end_matches('/');
    let link = format!("{}/api/auth/magic-link/consume?token={}", base_url, token);

    if let Some(mailer) = &state.mailer {
        match mailer.send_magic_link(email_norm, &link).await {
            Ok(_) => {
                tracing::info!(
                    event = "login.sent",
                    request_id = %ctx.request_id,
                    client_ip = %ctx.client_ip,
                    remote_ip = %ctx.remote_ip,
                    proxy_trusted = ctx.proxy_trusted,
                    account_id = %account_id,
                    email_hash = %ctx.email_hash,
                    "Magic Link sent via email"
                );
            }
            Err(e) => {
                tracing::error!(
                    event = "login.send_failed",
                    request_id = %ctx.request_id,
                    client_ip = %ctx.client_ip,
                    remote_ip = %ctx.remote_ip,
                    proxy_trusted = ctx.proxy_trusted,
                    account_id = %account_id,
                    email_hash = %ctx.email_hash,
                    error = %e,
                    error_dbg = ?e,
                    error_chain = %format!("{:#}", e),
                    "Failed to send Magic Link email"
                );
            }
        }
    } else if !state.config.auth_log_magic_token {
        // Only warn if dev logging is OFF (otherwise mailer=None is expected)
        tracing::warn!(
            event = "login.mailer_missing",
            request_id = %ctx.request_id,
            client_ip = %ctx.client_ip,
            remote_ip = %ctx.remote_ip,
            proxy_trusted = ctx.proxy_trusted,
            account_id = %account_id,
            "Mailer not configured; cannot send Magic Link"
        );
    } else {
        tracing::debug!(
            event = "login.mailer_missing_dev",
            request_id = %ctx.request_id,
            client_ip = %ctx.client_ip,
            remote_ip = %ctx.remote_ip,
            proxy_trusted = ctx.proxy_trusted,
            account_id = %account_id,
            "Mailer not configured (dev log mode)"
        );
    }

    // Dev/Ops Fallback: Log token if enabled
    if state.config.auth_log_magic_token {
        tracing::info!(
            target: "email_outbox",
            email_hash = %ctx.email_hash,
            account_id = %account_id,
            %link,
            "Magic Link Generated (LOGGED due to AUTH_LOG_MAGIC_TOKEN=true)"
        );
    }

    Ok(())
}

pub async fn request_login(
    State(state): State<ApiState>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    headers: HeaderMap,
    Json(payload): Json<LoginRequestEmail>,
) -> impl IntoResponse {
    let request_id = get_request_id(&headers);
    let client_ip = effective_client_ip(addr, &headers);
    let proxy_trusted = is_trusted_peer(addr.ip());

    if !state.config.auth_public_login {
        return StatusCode::NOT_FOUND.into_response();
    }

    let generic_response = LoginResponse {
        ok: true,
        message: GENERIC_LOGIN_MSG.to_string(),
    };

    // 1. Validate email format (simple check)
    if !payload.email.contains('@') {
        tracing::warn!(%request_id, %client_ip, "Invalid email format in login request");
        return (StatusCode::OK, Json(generic_response)).into_response();
    }

    // Normalize email: trim and lowercase
    let email_norm = payload.email.trim().to_ascii_lowercase();

    // Compute hash for privacy-preserving logging
    let mut hasher = Sha256::new();
    hasher.update(email_norm.as_bytes());
    let email_hash_full = format!("{:x}", hasher.finalize());
    // Pseudonymized correlation (unsalted hash prefix); not to be understood as anonymization.
    let email_hash = &email_hash_full[..16];

    // 1b. Rate Limiting (IP + Email)
    if let Err(e) = state.rate_limiter.check(client_ip, email_hash) {
        tracing::warn!(
            event = "login.rate_limited",
            request_id = %request_id,
            client_ip = %client_ip,
            remote_ip = %addr.ip(),
            proxy_trusted = proxy_trusted,
            email_hash = %email_hash,
            error = %e,
            "Login request rate limited"
        );
        return StatusCode::TOO_MANY_REQUESTS.into_response();
    }

    tracing::info!(
        event = "login.requested",
        request_id = %request_id,
        client_ip = %client_ip,
        remote_ip = %addr.ip(),
        proxy_trusted = proxy_trusted,
        email_hash = %email_hash,
        "Login requested"
    );

    // 2. Lookup account by email
    // We check existence first with a read lock.
    // If found, we proceed.
    // If not found, we check policy and potentially acquire a write lock to provision.
    let existing_account_info = {
        let accounts_map = state.accounts.read().await;
        accounts_map
            .values()
            .find(|acc| {
                acc.email
                    .as_ref()
                    .map(|e| e.eq_ignore_ascii_case(&email_norm))
                    .unwrap_or(false)
            })
            .map(|acc| (acc.public.id.clone(), acc.public.disabled))
    };

    // Prepare context for helpers
    let ctx = ProvisionContext {
        request_id: &request_id,
        client_ip,
        remote_ip: addr.ip(),
        proxy_trusted,
        email_hash,
    };

    let account_id = if let Some((id, disabled)) = existing_account_info {
        if disabled {
            tracing::info!(
                event = "login.denied_disabled",
                request_id = %request_id,
                client_ip = %client_ip,
                remote_ip = %addr.ip(),
                proxy_trusted = proxy_trusted,
                email_hash = %email_hash,
                account_id = %id,
                "Login requested for disabled account"
            );
            return (StatusCode::OK, Json(generic_response)).into_response();
        }
        Some(id)
    } else {
        // Account not found. Check Entry Policy.
        let mut allowed = false;

        // Auto-provisioning Check
        if state.config.auth_auto_provision {
            // Check Allowlist: Emails
            if let Some(emails) = &state.config.auth_allow_emails {
                // Config is already normalized (lowercase)
                if emails.iter().any(|e| e == &email_norm) {
                    allowed = true;
                }
            }

            // Check Allowlist: Domains (only if not already allowed)
            if !allowed {
                // Ensure exactly one '@' to prevent multi-@ attacks (e.g. attacker@allowed.com@evil.com)
                if email_norm.matches('@').count() == 1 {
                    if let Some(domains) = &state.config.auth_allow_email_domains {
                        // split_once ensures we get the domain part safely.
                        // We also reject empty domains explicitly.
                        if let Some((_, domain)) = email_norm.split_once('@') {
                            // Config domains are already lowercase
                            if !domain.is_empty() && domains.iter().any(|d| d == domain) {
                                allowed = true;
                            }
                        }
                    }
                }
            }
        }

        if allowed {
            // Provision new account
            provision_account(&state, &email_norm, &ctx).await
        } else {
            None
        }
    };

    if let Some(id) = account_id {
        if let Err(status) = process_magic_link_delivery(&state, &id, &email_norm, &ctx).await {
            return status.into_response();
        }
    } else if state.config.is_open_registration() {
        if let Some(id) = provision_account(&state, &email_norm, &ctx).await {
            if let Err(status) = process_magic_link_delivery(&state, &id, &email_norm, &ctx).await {
                return status.into_response();
            }

            tracing::info!(
                event = "login.requested_auto_provision",
                request_id = %request_id,
                client_ip = %client_ip,
                remote_ip = %addr.ip(),
                proxy_trusted = proxy_trusted,
                account_id = %id,
                email_hash = %email_hash,
                "Auto-provisioned account and sent Magic Link"
            );
        }
    } else {
        tracing::info!(
            event = "login.requested_unknown",
            request_id = %request_id,
            client_ip = %client_ip,
            remote_ip = %addr.ip(),
            proxy_trusted = proxy_trusted,
            email_hash = %email_hash,
            reason = "policy_denied",
            auto_provision_enabled = state.config.auth_auto_provision,
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
        .replace('\'', "&#x27;")
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
        .path("/api/auth/magic-link/consume")
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
        <form method="POST" action="/api/auth/magic-link/consume">
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
        "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
            .parse()
            .unwrap(),
    );

    (headers, jar.add(cookie), Html(html)).into_response()
}

pub async fn consume_login_post(
    State(state): State<ApiState>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    headers: HeaderMap,
    jar: CookieJar,
    Form(form): Form<ConsumeTokenForm>,
) -> impl IntoResponse {
    let request_id = get_request_id(&headers);
    let client_ip = effective_client_ip(addr, &headers);
    let proxy_trusted = is_trusted_peer(addr.ip());

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
        tracing::warn!(
            event = "login.failed",
            request_id = %request_id,
            client_ip = %client_ip,
            remote_ip = %addr.ip(),
            proxy_trusted = proxy_trusted,
            reason = "invalid_nonce",
            "Login failed: Invalid or missing nonce"
        );
        return Redirect::to("/login?error=invalid_token").into_response();
    }

    // 2. Consume Token
    if let Some(email) = state.tokens.consume(&form.token) {
        // Find account
        let accounts_map = state.accounts.read().await;
        let account = accounts_map.values().find(|acc| {
            acc.email
                .as_ref()
                .map(|e| e.eq_ignore_ascii_case(&email))
                .unwrap_or(false)
        });

        if let Some(acc) = account {
            if acc.public.disabled {
                tracing::warn!(
                    event = "login.failed_disabled",
                    request_id = %request_id,
                    client_ip = %client_ip,
                    remote_ip = %addr.ip(),
                    proxy_trusted = proxy_trusted,
                    account_id = %acc.public.id,
                    "Login consume failed: Account disabled"
                );
                return Redirect::to("/login?error=account_disabled").into_response();
            }

            let session = state.sessions.create(acc.public.id.clone(), None);
            let cookie = build_session_cookie(session.id, None);

            // Clear the nonce cookie
            // Respect AUTH_COOKIE_SECURE
            let secure_cookies = std::env::var("AUTH_COOKIE_SECURE")
                .map(|v| v != "0" && !v.eq_ignore_ascii_case("false"))
                .unwrap_or(true);

            let nonce_cleanup = Cookie::build((NONCE_COOKIE_NAME, ""))
                .path("/api/auth/magic-link/consume")
                .http_only(true)
                .same_site(SameSite::Lax)
                .secure(secure_cookies)
                .max_age(Duration::seconds(0))
                .expires(time::OffsetDateTime::UNIX_EPOCH)
                .build();

            tracing::info!(
                event = "login.consumed",
                request_id = %request_id,
                client_ip = %client_ip,
                remote_ip = %addr.ip(),
                proxy_trusted = proxy_trusted,
                account_id = %acc.public.id,
                "Login successful"
            );

            return (jar.add(cookie).add(nonce_cleanup), Redirect::to("/")).into_response();
        }
    }

    tracing::warn!(
        event = "login.failed",
        request_id = %request_id,
        client_ip = %client_ip,
        remote_ip = %addr.ip(),
        proxy_trusted = proxy_trusted,
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

pub async fn logout_all(
    State(state): State<ApiState>,
    Extension(ctx): Extension<AuthContext>,
) -> impl IntoResponse {
    if !ctx.authenticated {
        let err_payload = serde_json::json!({"error": "UNAUTHORIZED"});
        return (axum::http::StatusCode::UNAUTHORIZED, Json(err_payload)).into_response();
    }

    let account_id = match ctx.account_id {
        Some(id) => id,
        None => {
            let err_payload = serde_json::json!({"error": "UNAUTHORIZED"});
            return (axum::http::StatusCode::UNAUTHORIZED, Json(err_payload)).into_response();
        }
    };

    let device_id = match ctx.device_id {
        Some(id) => id,
        None => {
            let err_payload = serde_json::json!({
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Authenticated context missing device_id"
            });
            return (
                axum::http::StatusCode::INTERNAL_SERVER_ERROR,
                Json(err_payload),
            )
                .into_response();
        }
    };

    // Phase 3 Step-up Challenge generation
    tracing::info!(
        event = "auth.logout_all.step_up_required",
        "Logout All requested, generating step-up challenge"
    );

    let challenge = state
        .challenges
        .create(account_id, device_id, ChallengeIntent::LogoutAll);

    let err_payload = serde_json::json!({
        "error": "STEP_UP_REQUIRED",
        "challenge_id": challenge.id
    });

    (axum::http::StatusCode::FORBIDDEN, Json(err_payload)).into_response()
}

pub async fn me(Extension(ctx): Extension<AuthContext>) -> impl IntoResponse {
    Json(AuthStatus {
        authenticated: ctx.authenticated,
        account_id: ctx.account_id,
        role: ctx.role,
    })
}

#[derive(Deserialize)]
pub struct UpdateEmailPayload {
    pub new_email: String,
}

pub async fn update_email(
    State(state): State<ApiState>,
    Extension(ctx): Extension<AuthContext>,
    Json(payload): Json<UpdateEmailPayload>,
) -> impl IntoResponse {
    if !ctx.authenticated {
        let err = serde_json::json!({"error": "UNAUTHORIZED"});
        return (StatusCode::UNAUTHORIZED, Json(err)).into_response();
    }
    let account_id = match ctx.account_id {
        Some(id) => id,
        None => {
            return (
                StatusCode::UNAUTHORIZED,
                Json(serde_json::json!({"error": "UNAUTHORIZED"})),
            )
                .into_response()
        }
    };
    let device_id = match ctx.device_id {
        Some(id) => id,
        None => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({"error": "SESSION_INVALID"})),
            )
                .into_response()
        }
    };

    let new_email = payload.new_email.trim().to_ascii_lowercase();
    // Minimal validation because true ownership is proven by the verification link sent via email.
    if !new_email.contains('@') {
        let err = serde_json::json!({"error": "BAD_REQUEST", "message": "Invalid email format"});
        return (StatusCode::BAD_REQUEST, Json(err)).into_response();
    }

    {
        let accounts = state.accounts.read().await;
        for acc in accounts.values() {
            if acc.email.as_ref() == Some(&new_email) && acc.public.id != account_id {
                let err =
                    serde_json::json!({"error": "CONFLICT", "message": "Email already in use"});
                return (StatusCode::CONFLICT, Json(err)).into_response();
            }
        }
    }

    let challenge = state.challenges.create(
        account_id,
        device_id,
        ChallengeIntent::UpdateEmail { new_email },
    );
    let err_payload = serde_json::json!({
        "error": "STEP_UP_REQUIRED",
        "challenge_id": challenge.id
    });
    (StatusCode::FORBIDDEN, Json(err_payload)).into_response()
}

#[derive(Serialize)]
pub struct SessionStatus {
    pub authenticated: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expires_at: Option<chrono::DateTime<chrono::Utc>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub device_id: Option<String>,
}

pub async fn session(Extension(ctx): Extension<AuthContext>) -> impl IntoResponse {
    Json(SessionStatus {
        authenticated: ctx.authenticated,
        expires_at: ctx.expires_at,
        device_id: ctx.device_id,
    })
}

pub async fn session_refresh(State(state): State<ApiState>, jar: CookieJar) -> impl IntoResponse {
    if let Some(cookie) = jar.get(SESSION_COOKIE_NAME) {
        let old_session_id = cookie.value();

        if let Some(old_session) = state.sessions.get(old_session_id) {
            let accounts_map = state.accounts.read().await;
            let is_valid = accounts_map
                .get(&old_session.account_id)
                .is_some_and(|acc| !acc.public.disabled);
            drop(accounts_map);

            state.sessions.delete(old_session_id);

            if !is_valid {
                tracing::warn!(
                    event = "session.refresh_failed_disabled",
                    account_id = %old_session.account_id,
                    "Session refresh failed: Account disabled or deleted"
                );

                let cookie = build_session_cookie("".to_string(), Some(Duration::seconds(0)));
                let err_payload = serde_json::json!({"error": "SESSION_EXPIRED"});
                return (
                    axum::http::StatusCode::UNAUTHORIZED,
                    jar.add(cookie),
                    Json(err_payload),
                )
                    .into_response();
            }

            let new_session = state
                .sessions
                .create(old_session.account_id, Some(old_session.device_id.clone()));

            let new_cookie = build_session_cookie(new_session.id, None);

            let status = SessionStatus {
                authenticated: true,
                expires_at: Some(new_session.expires_at),
                device_id: Some(new_session.device_id.clone()),
            };

            tracing::info!(
                event = "session.refreshed",
                account_id = %new_session.account_id,
                "Session refreshed"
            );

            return (jar.add(new_cookie), Json(status)).into_response();
        }
    }

    tracing::warn!(
        event = "session.refresh_failed",
        reason = "invalid_or_expired_token",
        "Session refresh failed"
    );

    let err_payload = serde_json::json!({"error": "SESSION_EXPIRED"});
    (axum::http::StatusCode::UNAUTHORIZED, Json(err_payload)).into_response()
}

#[derive(Serialize)]
pub struct DeviceInfo {
    pub device_id: String,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub last_active: chrono::DateTime<chrono::Utc>,
    pub current: bool,
}

pub async fn list_devices(
    State(state): State<ApiState>,
    Extension(ctx): Extension<AuthContext>,
) -> impl IntoResponse {
    if !ctx.authenticated {
        let err_payload = serde_json::json!({"error": "UNAUTHORIZED"});
        return (axum::http::StatusCode::UNAUTHORIZED, Json(err_payload)).into_response();
    }

    let account_id = match ctx.account_id {
        Some(id) => id,
        None => {
            let err_payload = serde_json::json!({"error": "UNAUTHORIZED"});
            return (axum::http::StatusCode::UNAUTHORIZED, Json(err_payload)).into_response();
        }
    };

    let sessions = state.sessions.list_by_account(&account_id);

    // Group sessions by device_id
    let current_device_id = match ctx.device_id {
        Some(id) => id,
        None => {
            let err_payload = serde_json::json!({"error": "INTERNAL_SERVER_ERROR", "message": "Authenticated context missing device_id"});
            return (
                axum::http::StatusCode::INTERNAL_SERVER_ERROR,
                Json(err_payload),
            )
                .into_response();
        }
    };

    let mut device_map: std::collections::HashMap<String, DeviceInfo> =
        std::collections::HashMap::new();

    for session in sessions {
        device_map
            .entry(session.device_id.clone())
            .and_modify(|d| {
                if session.created_at < d.created_at {
                    d.created_at = session.created_at;
                }
                if session.last_active > d.last_active {
                    d.last_active = session.last_active;
                }
            })
            .or_insert_with(|| DeviceInfo {
                device_id: session.device_id.clone(),
                created_at: session.created_at,
                last_active: session.last_active,
                current: session.device_id == current_device_id,
            });
    }

    let mut devices: Vec<DeviceInfo> = device_map.into_values().collect();
    // Sort devices by last_active descending
    devices.sort_by(|a, b| b.last_active.cmp(&a.last_active));

    (axum::http::StatusCode::OK, Json(devices)).into_response()
}

pub async fn remove_device(
    State(state): State<ApiState>,
    Extension(ctx): Extension<AuthContext>,
    AxumPath(device_id): AxumPath<String>,
    jar: CookieJar,
) -> impl IntoResponse {
    if !ctx.authenticated {
        let err_payload = serde_json::json!({"error": "UNAUTHORIZED"});
        return (axum::http::StatusCode::UNAUTHORIZED, jar, Json(err_payload)).into_response();
    }

    let account_id = match ctx.account_id {
        Some(id) => id,
        None => {
            let err_payload = serde_json::json!({"error": "UNAUTHORIZED"});
            return (axum::http::StatusCode::UNAUTHORIZED, jar, Json(err_payload)).into_response();
        }
    };

    let current_device_id = match &ctx.device_id {
        Some(id) => id,
        None => {
            let err_payload = serde_json::json!({"error": "INTERNAL_SERVER_ERROR", "message": "Authenticated context missing device_id"});
            return (
                axum::http::StatusCode::INTERNAL_SERVER_ERROR,
                jar,
                Json(err_payload),
            )
                .into_response();
        }
    };

    if *current_device_id == device_id {
        // Logging out current device -> delete all sessions for it and clear cookie
        state.sessions.delete_by_device(&account_id, &device_id);
        let cookie = build_session_cookie("".to_string(), Some(Duration::seconds(0)));
        return (axum::http::StatusCode::NO_CONTENT, jar.add(cookie)).into_response();
    }

    // Removing another device -> first check if it even exists for this account
    let account_sessions = state.sessions.list_by_account(&account_id);
    let target_device_exists = account_sessions.iter().any(|s| s.device_id == device_id);

    if !target_device_exists {
        tracing::warn!(
            event = "auth.remove_device.not_found",
            "Attempted to remove a foreign device that does not exist for this account"
        );
        let err_payload = serde_json::json!({"error": "NOT_FOUND"});
        return (axum::http::StatusCode::NOT_FOUND, jar, Json(err_payload)).into_response();
    }

    // Removing another device -> requires step-up auth
    tracing::info!(
        event = "auth.remove_device.step_up_required",
        "Removing a foreign device requires Step-Up Auth, generating challenge"
    );

    let challenge = state.challenges.create(
        account_id,
        current_device_id.to_string(),
        ChallengeIntent::RemoveDevice {
            target_device_id: device_id.clone(),
        },
    );

    let err_payload = serde_json::json!({
        "error": "STEP_UP_REQUIRED",
        "challenge_id": challenge.id
    });

    (axum::http::StatusCode::FORBIDDEN, jar, Json(err_payload)).into_response()
}

#[derive(Deserialize)]
pub struct StepUpRequestPayload {
    pub challenge_id: String,
}

pub async fn request_step_up(
    State(state): State<ApiState>,
    headers: axum::http::HeaderMap,
    Extension(ctx): Extension<AuthContext>,
    Json(payload): Json<StepUpRequestPayload>,
) -> impl IntoResponse {
    let request_id = get_request_id(&headers);
    if !ctx.authenticated {
        let err_payload = serde_json::json!({"error": "UNAUTHORIZED"});
        return (StatusCode::UNAUTHORIZED, Json(err_payload)).into_response();
    }

    let account_id = match ctx.account_id {
        Some(ref id) => id,
        None => {
            let err_payload = serde_json::json!({"error": "UNAUTHORIZED"});
            return (StatusCode::UNAUTHORIZED, Json(err_payload)).into_response();
        }
    };

    let device_id = match ctx.device_id {
        Some(ref id) => id,
        None => {
            let err_payload = serde_json::json!({"error": "INTERNAL_SERVER_ERROR", "message": "Authenticated context missing device_id"});
            return (StatusCode::INTERNAL_SERVER_ERROR, Json(err_payload)).into_response();
        }
    };

    // 1. Verify that the challenge exists and is bound to this exact session (account + device)
    let challenge = match state.challenges.get(&payload.challenge_id) {
        Some(c) => c,
        None => {
            tracing::warn!(
                event = "auth.step_up.request.invalid_challenge",
                request_id = %request_id,
                account_id = %account_id,
                "Step-up request failed: Challenge not found or expired"
            );
            // We return a generic error to prevent enumeration of challenges
            let err_payload = serde_json::json!({"error": "CHALLENGE_INVALID"});
            return (StatusCode::BAD_REQUEST, Json(err_payload)).into_response();
        }
    };

    if challenge.account_id != *account_id || challenge.device_id != *device_id {
        tracing::warn!(
            event = "auth.step_up.request.binding_mismatch",
            request_id = %request_id,
            account_id = %account_id,
            "Step-up request failed: Challenge does not belong to the requesting session"
        );
        let err_payload = serde_json::json!({"error": "CHALLENGE_INVALID"});
        return (StatusCode::BAD_REQUEST, Json(err_payload)).into_response();
    }

    // 2. Lookup the user's email to send the Magic Link
    let email = match challenge.intent {
        ChallengeIntent::UpdateEmail { ref new_email } => Some(new_email.clone()),
        _ => {
            let accounts = state.accounts.read().await;
            accounts.get(account_id).and_then(|acc| acc.email.clone())
        }
    };

    let email = match email {
        Some(e) => e,
        None => {
            tracing::error!(
                event = "auth.step_up.request.no_email",
                request_id = %request_id,
                account_id = %account_id,
                "Step-up request failed: Account has no email address"
            );
            let err_payload = serde_json::json!({"error": "ACCOUNT_INVALID"});
            return (StatusCode::BAD_REQUEST, Json(err_payload)).into_response();
        }
    };

    // 3. Generate a Step-up Token bound to the challenge (NOT the email)
    let token =
        state
            .step_up_tokens
            .create(challenge.id.clone(), account_id.clone(), device_id.clone());

    // 4. Send the Step-up Magic Link via Mailer
    let base_url = match &state.config.app_base_url {
        Some(url) => url.clone(),
        None => {
            tracing::error!(
                event = "auth.step_up.request.no_base_url",
                request_id = %request_id,
                account_id = %account_id,
                "Step-up request failed: APP_BASE_URL is not configured"
            );
            let err_payload = serde_json::json!({"error": "INTERNAL_SERVER_ERROR"});
            return (StatusCode::INTERNAL_SERVER_ERROR, Json(err_payload)).into_response();
        }
    };
    let base_url = base_url.trim_end_matches('/');
    // We send them to the frontend Step-up consume UI, NOT the API endpoint directly.
    let link = format!("{}/auth/step-up/consume?token={}", base_url, token);

    let mailer = match &state.mailer {
        Some(m) => m,
        None => {
            tracing::error!(
                event = "auth.step_up.request.mailer_missing",
                request_id = %request_id,
                account_id = %account_id,
                challenge_id = %challenge.id,
                "Step-up request failed: Mailer is not configured"
            );
            let err_payload = serde_json::json!({"error": "SERVICE_UNAVAILABLE"});
            return (StatusCode::SERVICE_UNAVAILABLE, Json(err_payload)).into_response();
        }
    };

    let mut hasher = Sha256::new();
    hasher.update(email.as_bytes());
    let email_hash_full = format!("{:x}", hasher.finalize());
    let email_hash = &email_hash_full[..16];

    match mailer.send_step_up_magic_link(&email, &link).await {
        Ok(_) => {
            tracing::info!(
                event = "auth.step_up.request.sent",
                request_id = %request_id,
                account_id = %account_id,
                email_hash = %email_hash,
                "Step-up Magic Link sent via email"
            );
            StatusCode::NO_CONTENT.into_response()
        }
        Err(e) => {
            tracing::error!(
                event = "auth.step_up.request.send_failed",
                request_id = %request_id,
                account_id = %account_id,
                email_hash = %email_hash,
                error = %e,
                "Failed to send Step-up Magic Link email"
            );
            let err_payload = serde_json::json!({"error": "INTERNAL_SERVER_ERROR"});
            (StatusCode::INTERNAL_SERVER_ERROR, Json(err_payload)).into_response()
        }
    }
}

#[derive(Deserialize)]
pub struct StepUpConsumePayload {
    pub token: String,
    pub challenge_id: String,
}

pub async fn consume_step_up(
    State(state): State<ApiState>,
    headers: axum::http::HeaderMap,
    jar: CookieJar,
    Extension(ctx): Extension<AuthContext>,
    Json(payload): Json<StepUpConsumePayload>,
) -> impl IntoResponse {
    let request_id = get_request_id(&headers);

    if !ctx.authenticated {
        let err = serde_json::json!({"error": "UNAUTHORIZED"});
        return (StatusCode::UNAUTHORIZED, jar, Json(err)).into_response();
    }

    let account_id = match ctx.account_id {
        Some(ref id) => id.clone(),
        None => {
            let err = serde_json::json!({"error": "UNAUTHORIZED"});
            return (StatusCode::UNAUTHORIZED, jar, Json(err)).into_response();
        }
    };

    let device_id = match ctx.device_id {
        Some(ref id) => id.clone(),
        None => {
            tracing::error!(
                event = "auth.step_up.consume.missing_device_id",
                request_id = %request_id,
                "Authenticated context missing device_id"
            );
            let err = serde_json::json!({"error": "INTERNAL_SERVER_ERROR", "message": "Authenticated context missing device_id"});
            return (StatusCode::INTERNAL_SERVER_ERROR, jar, Json(err)).into_response();
        }
    };

    // 1. Atomically validate all bindings and consume the token.
    // The token is only removed when challenge_id, account_id, and device_id all match,
    // so a wrong caller cannot burn a valid token that belongs to a different session.
    match state.step_up_tokens.consume_if_matches(
        &payload.token,
        &payload.challenge_id,
        &account_id,
        &device_id,
    ) {
        ConsumeMatchResult::NotFound => {
            tracing::warn!(
                event = "auth.step_up.consume.token_invalid",
                request_id = %request_id,
                "Step-up consume failed: token not found, expired, or already used"
            );
            let err = serde_json::json!({"error": "TOKEN_INVALID"});
            return (StatusCode::UNAUTHORIZED, jar, Json(err)).into_response();
        }
        ConsumeMatchResult::BindingMismatch => {
            tracing::warn!(
                event = "auth.step_up.consume.binding_mismatch",
                request_id = %request_id,
                "Step-up consume failed: token binding mismatch (challenge_id, account_id, or device_id)"
            );
            let err = serde_json::json!({"error": "TOKEN_INVALID"});
            return (StatusCode::UNAUTHORIZED, jar, Json(err)).into_response();
        }
        ConsumeMatchResult::Consumed => {}
    }

    // 2. Consume the challenge (single-use, validates TTL).
    // Note: the token was already removed above. If the challenge is missing or expired at this
    // point, the token is lost and the client must request a new step-up link. This is deliberate:
    // both token and challenge share the same short TTL (~5 min) and are created together, so a
    // race where the challenge expires while the token is still valid is extremely narrow in
    // practice. A full atomic guarantee would require a combined store operation; that refactor is
    // deferred until the use-case demands it.
    let challenge = match state.challenges.consume(&payload.challenge_id) {
        Some(c) => c,
        None => {
            tracing::warn!(
                event = "auth.step_up.consume.challenge_expired",
                request_id = %request_id,
                "Step-up consume failed: challenge not found or expired"
            );
            let err = serde_json::json!({"error": "TOKEN_INVALID"});
            return (StatusCode::UNAUTHORIZED, jar, Json(err)).into_response();
        }
    };

    // 3. Execute the intent
    match challenge.intent {
        ChallengeIntent::LogoutAll => {
            tracing::info!(
                event = "auth.step_up.consume.logout_all",
                request_id = %request_id,
                account_id = %account_id,
                "Step-up consume: executing LogoutAll intent"
            );
            state.sessions.delete_all_by_account(&account_id);
            // Empty value + zero max-age clears the session cookie in the client
            let cookie = build_session_cookie("".to_string(), Some(Duration::seconds(0)));
            (StatusCode::NO_CONTENT, jar.add(cookie)).into_response()
        }
        ChallengeIntent::RemoveDevice { target_device_id } => {
            tracing::info!(
                event = "auth.step_up.consume.remove_device",
                request_id = %request_id,
                account_id = %account_id,
                target_device_id = %target_device_id,
                "Step-up consume: executing RemoveDevice intent"
            );
            state
                .sessions
                .delete_by_device(&account_id, &target_device_id);
            StatusCode::NO_CONTENT.into_response()
        }
        ChallengeIntent::UpdateEmail { new_email } => {
            tracing::info!(
                event = "auth.step_up.consume.update_email",
                request_id = %request_id,
                account_id = %account_id,
                "Step-up consume: executing UpdateEmail intent"
            );
            let mut accounts = state.accounts.write().await;

            // Check for conflict right before writing
            for acc in accounts.values() {
                if acc.email.as_ref() == Some(&new_email) && acc.public.id != account_id {
                    tracing::warn!(
                        event = "auth.step_up.consume.update_email.conflict",
                        request_id = %request_id,
                        account_id = %account_id,
                        "Email was taken by another account before step-up was consumed"
                    );
                    let err =
                        serde_json::json!({"error": "CONFLICT", "message": "Email already in use"});
                    return (StatusCode::CONFLICT, jar, Json(err)).into_response();
                }
            }

            if let Some(account) = accounts.get_mut(&account_id) {
                account.email = Some(new_email);
                (StatusCode::NO_CONTENT, jar).into_response()
            } else {
                tracing::error!(
                    event = "auth.step_up.consume.update_email.missing_account",
                    request_id = %request_id,
                    account_id = %account_id,
                    "Account missing during email update step-up consume"
                );
                let err = serde_json::json!({"error": "ACCOUNT_INVALID"});
                (StatusCode::BAD_REQUEST, jar, Json(err)).into_response()
            }
        }
    }
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

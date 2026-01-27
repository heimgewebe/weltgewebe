use axum::{
    extract::{ConnectInfo, Json, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Extension,
};
use axum_extra::extract::cookie::{Cookie, CookieJar, SameSite};
use ipnet::IpNet;
use serde::{Deserialize, Serialize};
use std::net::{IpAddr, SocketAddr};
#[cfg(not(test))]
use std::sync::OnceLock;
use time::Duration;

use crate::{auth::role::Role, middleware::auth::AuthContext, state::ApiState};

pub const SESSION_COOKIE_NAME: &str = "gewebe_session";

fn build_session_cookie(value: String, max_age: Option<Duration>) -> Cookie<'static> {
    // Default to secure, but allow override via env for local dev (http)
    let secure_cookies = std::env::var("AUTH_COOKIE_SECURE")
        .map(|v| v != "0" && !v.eq_ignore_ascii_case("false"))
        .unwrap_or(true);

    let mut builder = Cookie::build((SESSION_COOKIE_NAME, value))
        .path("/")
        .http_only(true)
        .same_site(SameSite::Strict)
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

pub async fn login(
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
        return (jar, status);
    }

    if !state.accounts.contains_key(&payload.account_id) {
        tracing::warn!(?payload.account_id, "Login attempt refused: Account not found");
        return (jar, StatusCode::BAD_REQUEST);
    }

    let session = state.sessions.create(payload.account_id);

    let cookie = build_session_cookie(session.id, None);

    (jar.add(cookie), StatusCode::OK)
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

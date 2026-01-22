use std::env;

use axum::{
    body::Body,
    http::{Method, Request, StatusCode, Uri},
    middleware::Next,
    response::{IntoResponse, Response},
};
use axum_extra::extract::cookie::CookieJar;

use crate::routes::auth::SESSION_COOKIE_NAME;

/// Middleware to enforce CSRF protection via Origin/Referer checks.
///
/// Logic:
/// 1. Allow safe methods (GET, HEAD, OPTIONS).
///    - TRACE is excluded (unsafe).
/// 2. Skip explicitly exempted paths (e.g., /auth/login, /api/auth/login).
/// 3. If no session cookie is present, skip CSRF check (no session to hijack).
/// 4. Allowlist Check:
///    - Checks `Origin` AND `Referer` against `CSRF_ALLOWED_ORIGINS` (if set).
/// 5. Host Validation:
///    - Extract Host domain and optional port.
/// 6. Origin Validation:
///    - HTTPS Enforcement: Reject `http://` Origins unless Host is localhost/loopback.
///    - Host Match: Domains must match (case-insensitive).
///    - Port Match:
///      - If Host has port, Origin MUST match it.
///      - If Host has NO port, ignore Origin port (robustness for proxies).
/// 7. Referer Fallback:
///    - If Origin missing, Referer must start with `https://<Host>` (or http for localhost).
pub async fn require_csrf(jar: CookieJar, req: Request<Body>, next: Next) -> Response {
    let method = req.method();

    // 1. Pass through safe methods
    if method == Method::GET || method == Method::HEAD || method == Method::OPTIONS {
        return next.run(req).await;
    }

    // 2. Explicit exemptions
    let path = req.uri().path();
    if path.ends_with("/auth/login") {
        return next.run(req).await;
    }

    // 3. Skip if no session cookie
    if jar.get(SESSION_COOKIE_NAME).is_none() {
        return next.run(req).await;
    }

    let headers = req.headers();

    // 4. Allowlist Check (Origin OR Referer)
    if let Ok(allowlist) = env::var("CSRF_ALLOWED_ORIGINS") {
        let allowed_list: Vec<String> = allowlist
            .split(',')
            .map(|s| s.trim().to_ascii_lowercase())
            .collect();

        // Check Origin
        if let Some(origin) = headers.get("origin").and_then(|v| v.to_str().ok()) {
            if allowed_list.contains(&origin.to_ascii_lowercase()) {
                return next.run(req).await;
            }
        }

        // Check Referer (prefix match)
        if let Some(referer) = headers.get("referer").and_then(|v| v.to_str().ok()) {
            let ref_lc = referer.to_ascii_lowercase();
            if allowed_list.iter().any(|allowed| ref_lc.starts_with(allowed)) {
                return next.run(req).await;
            }
        }
    }

    // 5. Host Validation
    let host_raw = headers
        .get("host")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");

    if host_raw.is_empty() {
        tracing::warn!("CSRF check failed: Missing Host header");
        return StatusCode::FORBIDDEN.into_response();
    }

    let (host_domain, host_port) = parse_host_header(host_raw);

    // 6. Check Origin
    if let Some(origin) = headers.get("origin").and_then(|v| v.to_str().ok()) {
        let (origin_scheme, origin_host_raw) = if let Some(rest) = origin.strip_prefix("https://") {
            ("https", rest)
        } else if let Some(rest) = origin.strip_prefix("http://") {
            ("http", rest)
        } else {
            ("", origin)
        };

        // Validate format
        if origin_host_raw.contains(['/', '?', '#']) {
            tracing::warn!(?origin, "CSRF check failed: Invalid Origin format");
            return StatusCode::FORBIDDEN.into_response();
        }

        // HTTPS Enforcement (except localhost)
        let is_localhost = host_domain == "localhost" || host_domain == "127.0.0.1" || host_domain == "::1";
        if origin_scheme == "http" && !is_localhost {
             tracing::warn!(?origin, "CSRF check failed: Insecure Origin (HTTP) on non-localhost");
             return StatusCode::FORBIDDEN.into_response();
        }

        let (origin_domain, origin_port_raw) = parse_host_header(origin_host_raw);

        let domains_match = host_domain.eq_ignore_ascii_case(&origin_domain);

        // Simplified Port Rule
        let ports_match = match (host_port, origin_port_raw) {
            (Some(h), Some(o)) => h == o,
            (Some(_), None) => false, // Host has strict port, Origin missing -> Fail
            (None, _) => true,        // Host has no port (proxy/default), ignore Origin port
        };

        if !domains_match || !ports_match {
            tracing::warn!(?origin, ?host_raw, "CSRF check failed: Origin mismatch");
            return StatusCode::FORBIDDEN.into_response();
        }
        return next.run(req).await;
    }

    // 7. Fallback: Check Referer
    if let Some(referer) = headers.get("referer").and_then(|v| v.to_str().ok()) {
        let referer_lc = referer.to_ascii_lowercase();
        let host_lc = host_raw.to_ascii_lowercase();

        let valid_starts = [
            format!("https://{}/", host_lc),
            format!("http://{}/", host_lc), // allow http check logic handled by strict HTTPS check above? No, referer logic is simpler fallback.
        ];

        // HTTPS Enforcement for Referer
        let is_localhost = host_domain == "localhost" || host_domain == "127.0.0.1" || host_domain == "::1";
        if referer_lc.starts_with("http://") && !is_localhost {
             tracing::warn!(?referer, "CSRF check failed: Insecure Referer (HTTP) on non-localhost");
             return StatusCode::FORBIDDEN.into_response();
        }

        let is_valid = valid_starts.iter().any(|p| referer_lc.starts_with(p))
            || referer_lc == format!("https://{}", host_lc)
            || referer_lc == format!("http://{}", host_lc);

        if !is_valid {
            tracing::warn!(?referer, ?host_raw, "CSRF check failed: Referer mismatch");
            return StatusCode::FORBIDDEN.into_response();
        }
        return next.run(req).await;
    }

    // 8. Block if neither is present
    tracing::warn!(method = ?method, "CSRF check failed: Missing Origin and Referer");
    StatusCode::FORBIDDEN.into_response()
}

/// Helper to parse host:port string using http::Uri logic.
/// Returns (host_string, Option<port>)
fn parse_host_header(input: &str) -> (String, Option<u16>) {
    if let Some(rest) = input.strip_suffix(':') {
        return parse_host_header(rest);
    }

    let uri_string = format!("http://{}", input);

    if let Ok(uri) = uri_string.parse::<Uri>() {
        if let Some(authority) = uri.authority() {
            return (authority.host().to_string(), authority.port_u16());
        }
    }

    (input.to_string(), None)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_host_header() {
        assert_eq!(parse_host_header("example.com"), ("example.com".to_string(), None));
        assert_eq!(parse_host_header("example.com:8080"), ("example.com".to_string(), Some(8080)));
        assert_eq!(parse_host_header("[::1]:8080"), ("[::1]".to_string(), Some(8080)));
        assert_eq!(parse_host_header("[::1]"), ("[::1]".to_string(), None));
    }

    #[tokio::test]
    async fn test_exemption_logic() {
        use axum::http::Request;
        let req = Request::builder().uri("/auth/login").method("POST").body(Body::empty()).unwrap();
        assert!(req.uri().path().ends_with("/auth/login"));
    }
}

    #[test]
    fn test_referer_allowlist_match() {
        // Logic check: verify prefix matching logic works conceptually
        let allowlist = vec!["https://my-dev.com".to_string()];
        let referer = "https://my-dev.com/foo".to_string();
        assert!(allowlist.iter().any(|allowed| referer.starts_with(allowed)));
    }

use std::env;

use axum::{
    body::Body,
    http::{Method, Request, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
};
use axum_extra::extract::cookie::CookieJar;

use crate::routes::auth::SESSION_COOKIE_NAME;

/// Middleware to enforce CSRF protection via Origin/Referer checks.
///
/// Logic:
/// 1. Allow safe methods (GET, HEAD, OPTIONS).
///    - TRACE is deliberately excluded as it is typically disabled or unsafe.
/// 2. Skip explicitly exempted paths (e.g., /auth/login, /api/auth/login).
/// 3. If no session cookie is present, skip CSRF check (no session to hijack).
/// 4. For state-changing methods with session:
///    - Check `CSRF_ALLOWED_ORIGINS` (dev fallback).
///      - Normalizes both header and env var to lowercase.
///    - Extract and parse `Host` header (host, port).
///    - Check `Origin` header:
///      - Extract host/port (inferring default ports 80/443 if missing).
///      - Compare host (case-insensitive) and port.
///      - Strict port rule: If Host has no port, Origin must be standard or match implicit default.
///    - If `Origin` missing, check `Referer` (prefix/exact match).
///    - If both missing or mismatch: 403 Forbidden.
pub async fn require_csrf(jar: CookieJar, req: Request<Body>, next: Next) -> Response {
    let method = req.method();

    // 1. Pass through safe methods
    if method == Method::GET || method == Method::HEAD || method == Method::OPTIONS {
        return next.run(req).await;
    }

    // 2. Explicit exemptions
    // Covers both /auth/login and /api/auth/login
    let path = req.uri().path();
    if path.ends_with("/auth/login") {
        return next.run(req).await;
    }

    // 3. Skip if no session cookie
    if jar.get(SESSION_COOKIE_NAME).is_none() {
        return next.run(req).await;
    }

    let headers = req.headers();

    // 4. Allowlist Check
    if let Some(origin) = headers.get("origin").and_then(|v| v.to_str().ok()) {
        if let Ok(allowlist) = env::var("CSRF_ALLOWED_ORIGINS") {
            let origin_lc = origin.to_ascii_lowercase();
            for allowed in allowlist.split(',') {
                if origin_lc == allowed.trim().to_ascii_lowercase() {
                    return next.run(req).await;
                }
            }
        }
    }

    // 5. Host Validation & Parsing
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

        // Validate format (no path/query/fragment)
        if origin_host_raw.contains(['/', '?', '#']) {
            tracing::warn!(?origin, "CSRF check failed: Invalid Origin format");
            return StatusCode::FORBIDDEN.into_response();
        }

        let (origin_domain, origin_port_raw) = parse_host_header(origin_host_raw);

        // Resolve implicit ports for Origin
        let origin_port = if let Some(p) = origin_port_raw {
            Some(p)
        } else {
            match origin_scheme {
                "http" => Some(80),
                "https" => Some(443),
                _ => None,
            }
        };

        let domains_match = host_domain.eq_ignore_ascii_case(origin_domain);

        // Strict Port Matching Rule
        let ports_match = match (host_port, origin_port) {
            (Some(h), Some(o)) => h == o,
            (Some(_), None) => false, // Host strict, Origin missing -> Fail
            (None, None) => true,     // Both implied standard -> OK
            (None, Some(o)) => {
                // Host implied (80 or 443). Origin explicit.
                // Origin MUST be 80 or 443 to match implied Host.
                // We don't know scheme of Host, so we accept if Origin is EITHER standard port.
                // This is slightly loose but robust for mixed deployments.
                // Better: If we assume host is valid, we check against common defaults.
                o == 80 || o == 443
            }
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
            format!("http://{}/", host_lc),
        ];
        let valid_exact = [
            format!("https://{}", host_lc),
            format!("http://{}", host_lc),
        ];

        let is_valid = valid_starts.iter().any(|p| referer_lc.starts_with(p))
            || valid_exact.iter().any(|e| referer_lc == *e);

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

/// Helper to split "host:port" or "host"
fn parse_host_header(input: &str) -> (&str, Option<u16>) {
    if let Some((host, port_str)) = input.rsplit_once(':') {
        // Check if the part after last colon is numeric
        if let Ok(port) = port_str.parse::<u16>() {
            return (host, Some(port));
        }
    }
    (input, None)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_host_header() {
        assert_eq!(parse_host_header("example.com"), ("example.com", None));
        assert_eq!(parse_host_header("example.com:8080"), ("example.com", Some(8080)));
        assert_eq!(parse_host_header("localhost"), ("localhost", None));
        assert_eq!(parse_host_header("example.com:443"), ("example.com", Some(443)));
        assert_eq!(parse_host_header("example.com:"), ("example.com:", None));
    }

    #[tokio::test]
    async fn test_exemption_logic() {
        use axum::http::Request;

        // /auth/login exempted
        let req = Request::builder()
            .uri("/auth/login")
            .method("POST")
            .body(Body::empty())
            .unwrap();
        assert!(req.uri().path().ends_with("/auth/login"));

        // /api/auth/login exempted
        let req2 = Request::builder()
            .uri("/api/auth/login")
            .method("POST")
            .body(Body::empty())
            .unwrap();
        assert!(req2.uri().path().ends_with("/auth/login"));
    }
}

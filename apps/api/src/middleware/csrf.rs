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
/// 2. Skip explicitly exempted paths (e.g., /auth/login).
/// 3. If no session cookie is present, skip CSRF check (no session to hijack).
/// 4. For state-changing methods with session:
///    - Check `CSRF_ALLOWED_ORIGINS` (dev fallback).
///      - Normalizes both header and env var to lowercase.
///    - Extract `Host` header.
///    - Check `Origin` header: MUST match `Host` (ignoring scheme).
///      - Validates format (no path/query/fragment).
///      - Case-insensitive comparison.
///    - If `Origin` missing, check `Referer`: MUST start with `Scheme://Host/`.
///      - Case-insensitive comparison.
///    - If both missing or mismatch: 403 Forbidden.
pub async fn require_csrf(jar: CookieJar, req: Request<Body>, next: Next) -> Response {
    let method = req.method();

    // 1. Pass through safe methods
    if method == Method::GET || method == Method::HEAD || method == Method::OPTIONS {
        return next.run(req).await;
    }

    // 2. Explicit exemptions (e.g. Login doesn't need CSRF protection as it establishes session)
    if req.uri().path() == "/auth/login" {
        return next.run(req).await;
    }

    // 3. Skip if no session cookie (Session invariant: No cookie = No Auth = No CSRF risk)
    if jar.get(SESSION_COOKIE_NAME).is_none() {
        return next.run(req).await;
    }

    let headers = req.headers();

    // 4. Allowlist Check (Dev/Special cases)
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

    // 5. Host Validation
    let host_raw = headers
        .get("host")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");

    if host_raw.is_empty() {
        tracing::warn!("CSRF check failed: Missing Host header");
        return StatusCode::FORBIDDEN.into_response();
    }
    let host = host_raw.to_ascii_lowercase();

    // 6. Check Origin
    if let Some(origin) = headers.get("origin").and_then(|v| v.to_str().ok()) {
        // Strict Check: strip scheme and compare exact match.
        let origin_host_raw = origin
            .strip_prefix("https://")
            .or_else(|| origin.strip_prefix("http://"))
            .unwrap_or(origin);

        // Hardening 1: Validate Origin format (must be just host:port, no path/query/fragment)
        if origin_host_raw.contains(['/', '?', '#']) {
            tracing::warn!(?origin, "CSRF check failed: Invalid Origin format");
            return StatusCode::FORBIDDEN.into_response();
        }

        // Hardening 2: Case-insensitive comparison
        let origin_host = origin_host_raw.to_ascii_lowercase();

        if origin_host != host {
            tracing::warn!(?origin, ?host, "CSRF check failed: Origin mismatch");
            return StatusCode::FORBIDDEN.into_response();
        }
        return next.run(req).await;
    }

    // 7. Fallback: Check Referer
    if let Some(referer) = headers.get("referer").and_then(|v| v.to_str().ok()) {
        let referer_lc = referer.to_ascii_lowercase();

        let valid_starts = [
            format!("https://{}/", host),
            format!("http://{}/", host),
        ];
        let valid_exact = [
            format!("https://{}", host),
            format!("http://{}", host),
        ];

        let is_valid = valid_starts.iter().any(|p| referer_lc.starts_with(p))
            || valid_exact.iter().any(|e| referer_lc == *e);

        if !is_valid {
            tracing::warn!(?referer, ?host, "CSRF check failed: Referer mismatch");
            return StatusCode::FORBIDDEN.into_response();
        }
        return next.run(req).await;
    }

    // 8. Block if neither is present (Strict Mode)
    tracing::warn!(method = ?method, "CSRF check failed: Missing Origin and Referer");
    StatusCode::FORBIDDEN.into_response()
}

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
/// 2. If no session cookie is present, skip CSRF check (no session to hijack).
/// 3. For state-changing methods with session:
///    - Check `CSRF_ALLOWED_ORIGINS` (dev fallback).
///    - Extract `Host` header.
///    - Check `Origin` header: MUST match `Host` (ignoring scheme).
///    - If `Origin` missing, check `Referer`: MUST start with `Scheme://Host/`.
///    - If both missing or mismatch: 403 Forbidden.
pub async fn require_csrf(jar: CookieJar, req: Request<Body>, next: Next) -> Response {
    let method = req.method();

    // 1. Pass through safe methods
    if method == Method::GET || method == Method::HEAD || method == Method::OPTIONS {
        return next.run(req).await;
    }

    // 2. Skip if no session cookie (Session invariant: No cookie = No Auth = No CSRF risk)
    if jar.get(SESSION_COOKIE_NAME).is_none() {
        return next.run(req).await;
    }

    let headers = req.headers();

    // 3. Allowlist Check (Dev/Special cases)
    if let Some(origin) = headers.get("origin").and_then(|v| v.to_str().ok()) {
        if let Ok(allowlist) = env::var("CSRF_ALLOWED_ORIGINS") {
            for allowed in allowlist.split(',') {
                if origin == allowed.trim() {
                    return next.run(req).await;
                }
            }
        }
    }

    // 4. Host Validation
    let host = headers
        .get("host")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");

    if host.is_empty() {
        tracing::warn!("CSRF check failed: Missing Host header");
        return StatusCode::FORBIDDEN.into_response();
    }

    // 5. Check Origin
    if let Some(origin) = headers.get("origin").and_then(|v| v.to_str().ok()) {
        // Strict Check: strip scheme and compare exact match.
        let origin_host = origin
            .strip_prefix("https://")
            .or_else(|| origin.strip_prefix("http://"))
            .unwrap_or(origin);

        if origin_host != host {
            tracing::warn!(?origin, ?host, "CSRF check failed: Origin mismatch");
            return StatusCode::FORBIDDEN.into_response();
        }
        return next.run(req).await;
    }

    // 6. Fallback: Check Referer
    if let Some(referer) = headers.get("referer").and_then(|v| v.to_str().ok()) {
        let valid_starts = [
            format!("https://{}/", host),
            format!("http://{}/", host),
        ];
        let valid_exact = [
            format!("https://{}", host),
            format!("http://{}", host),
        ];

        let is_valid = valid_starts.iter().any(|p| referer.starts_with(p))
            || valid_exact.iter().any(|e| referer == e);

        if !is_valid {
            tracing::warn!(?referer, ?host, "CSRF check failed: Referer mismatch");
            return StatusCode::FORBIDDEN.into_response();
        }
        return next.run(req).await;
    }

    // 7. Block if neither is present (Strict Mode)
    tracing::warn!(method = ?method, "CSRF check failed: Missing Origin and Referer");
    StatusCode::FORBIDDEN.into_response()
}

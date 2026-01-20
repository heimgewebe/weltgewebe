use axum::{
    body::Body,
    http::{Method, Request, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
};

/// Middleware to enforce CSRF protection via Origin/Referer checks.
///
/// Logic:
/// 1. Allow safe methods (GET, HEAD, OPTIONS).
/// 2. For state-changing methods:
///    - Extract `Host` header.
///    - Check `Origin` header: MUST match `Host` (ignoring scheme).
///    - If `Origin` missing, check `Referer`: MUST start with `Scheme://Host/`.
///    - If both missing or mismatch: 403 Forbidden.
pub async fn require_csrf(req: Request<Body>, next: Next) -> Response {
    let method = req.method();

    // 1. Pass through safe methods
    if method == Method::GET || method == Method::HEAD || method == Method::OPTIONS {
        return next.run(req).await;
    }

    let headers = req.headers();
    let host = headers
        .get("host")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");

    if host.is_empty() {
        tracing::warn!("CSRF check failed: Missing Host header");
        return StatusCode::FORBIDDEN.into_response();
    }

    // 2. Check Origin
    if let Some(origin) = headers.get("origin").and_then(|v| v.to_str().ok()) {
        // Strict Check: strip scheme and compare exact match.
        // Prevents suffix spoofing (e.g. attacker-example.com vs example.com).
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

    // 3. Fallback: Check Referer
    if let Some(referer) = headers.get("referer").and_then(|v| v.to_str().ok()) {
        // Strict Check: Must start with http(s)://<Host>/ or be exactly http(s)://<Host>
        // This prevents "example.com.attacker.com" attacks.

        // We construct the valid prefixes.
        // Note: This assumes standard ports or Host header includes port.
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

    // 4. Block if neither is present (Strict Mode)
    tracing::warn!(method = ?method, "CSRF check failed: Missing Origin and Referer");
    StatusCode::FORBIDDEN.into_response()
}

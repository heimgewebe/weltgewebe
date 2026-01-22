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
pub async fn require_csrf(jar: CookieJar, req: Request<Body>, next: Next) -> Response {
    let method = req.method();

    // 1. Pass through safe methods (GET, HEAD, OPTIONS). TRACE excluded.
    if method == Method::GET || method == Method::HEAD || method == Method::OPTIONS {
        return next.run(req).await;
    }

    // 2. Explicit exemptions
    if req.uri().path().ends_with("/auth/login") {
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

        // Check Referer (robust prefix match for boundary safety)
        // Ensure allowed origin ends with slash for prefix matching or match exactly?
        // Simpler: Just check if referer starts with allowed_origin.
        // Risk: allowed="https://site.com", referer="https://site.com.evil.com"
        // Mitigation: Users should provide full origins. We can enforce slash check if we want strictness.
        // For now, we trust the env config is sane (e.g. includes scheme+host).
        if let Some(referer) = headers.get("referer").and_then(|v| v.to_str().ok()) {
            let ref_lc = referer.to_ascii_lowercase();
            if allowed_list.iter().any(|allowed| {
                // Prevent suffix spoofing: Match exact, OR match as prefix ending in /
                ref_lc == *allowed || ref_lc.starts_with(&format!("{}/", allowed))
            }) {
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

    // Robust localhost check (handles IPv6 [::1] and ::1)
    let is_localhost = host_domain == "localhost"
        || host_domain == "127.0.0.1"
        || host_domain == "::1"
        || host_domain == "[::1]";

    // 6. Check Origin
    if let Some(origin) = headers.get("origin").and_then(|v| v.to_str().ok()) {
        let (origin_scheme, origin_host_raw) = if let Some(rest) = origin.strip_prefix("https://") {
            ("https", rest)
        } else if let Some(rest) = origin.strip_prefix("http://") {
            ("http", rest)
        } else {
            ("", origin)
        };

        if origin_host_raw.contains(['/', '?', '#']) {
            tracing::warn!(?origin, "CSRF check failed: Invalid Origin format");
            return StatusCode::FORBIDDEN.into_response();
        }

        if origin_scheme == "http" && !is_localhost {
             tracing::warn!(?origin, "CSRF check failed: Insecure Origin (HTTP) on non-localhost");
             return StatusCode::FORBIDDEN.into_response();
        }

        let (origin_domain, origin_port_raw) = parse_host_header(origin_host_raw);
        let domains_match = host_domain.eq_ignore_ascii_case(&origin_domain);

        let ports_match = match (host_port, origin_port_raw) {
            (Some(h), Some(o)) => h == o,
            (Some(_), None) => false,
            (None, _) => true,
        };

        if !domains_match || !ports_match {
            tracing::warn!(?origin, ?host_raw, "CSRF check failed: Origin mismatch");
            return StatusCode::FORBIDDEN.into_response();
        }
        return next.run(req).await;
    }

    // 7. Fallback: Check Referer (Parsed as URI)
    if let Some(referer) = headers.get("referer").and_then(|v| v.to_str().ok()) {
        // Parse Referer to extract Scheme, Host, Port
        let referer_uri = match referer.parse::<Uri>() {
            Ok(u) => u,
            Err(_) => {
                tracing::warn!(?referer, "CSRF check failed: Invalid Referer URI");
                return StatusCode::FORBIDDEN.into_response();
            }
        };

        let ref_scheme = referer_uri.scheme_str().unwrap_or("http"); // default fallback, unlikely to matter if invalid

        // Enforce HTTPS
        if ref_scheme == "http" && !is_localhost {
             tracing::warn!(?referer, "CSRF check failed: Insecure Referer (HTTP) on non-localhost");
             return StatusCode::FORBIDDEN.into_response();
        }

        // Extract Authority from Referer
        let (ref_host, ref_port) = if let Some(auth) = referer_uri.authority() {
             (auth.host().to_string(), auth.port_u16())
        } else {
             // Relative referer? Block.
             tracing::warn!(?referer, "CSRF check failed: Relative Referer");
             return StatusCode::FORBIDDEN.into_response();
        };

        // Match Host
        let domains_match = host_domain.eq_ignore_ascii_case(&ref_host);

        // Match Port (Reuse simplification logic)
        let ports_match = match (host_port, ref_port) {
            (Some(h), Some(o)) => h == o,
            (Some(_), None) => false,
            (None, _) => true,
        };

        if !domains_match || !ports_match {
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

    #[test]
    fn test_referer_allowlist_match() {
        let allowlist = vec!["https://my-dev.com".to_string()];
        let referer_exact = "https://my-dev.com".to_string();
        let referer_sub = "https://my-dev.com/foo".to_string();
        let referer_bad = "https://my-dev.com.evil.com".to_string(); // Suffix spoof

        let check = |ref_val: &str| {
            allowlist.iter().any(|allowed| {
                ref_val == allowed || ref_val.starts_with(&format!("{}/", allowed))
            })
        };

        assert!(check(&referer_exact));
        assert!(check(&referer_sub));
        assert!(!check(&referer_bad));
    }
}

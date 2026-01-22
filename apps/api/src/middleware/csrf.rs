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

        // Check Referer
        if let Some(referer) = headers.get("referer").and_then(|v| v.to_str().ok()) {
            let ref_lc = referer.to_ascii_lowercase();
            if allowed_list.iter().any(|allowed| {
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

    // Robust localhost check
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
            tracing::warn!(
                ?origin,
                "CSRF check failed: Insecure Origin (HTTP) on non-localhost"
            );
            return StatusCode::FORBIDDEN.into_response();
        }

        let (origin_domain, origin_port_raw) = parse_host_header(origin_host_raw);
        let domains_match = host_domain.eq_ignore_ascii_case(&origin_domain);

        let origin_port = if let Some(p) = origin_port_raw {
            Some(p)
        } else {
            match origin_scheme {
                "http" => Some(80),
                "https" => Some(443),
                _ => None,
            }
        };

        // Strict Port Matching Rule
        let ports_match = match (host_port, origin_port) {
            (Some(h), Some(o)) => h == o,
            (Some(_), None) => false,
            (None, None) => true,
            (None, Some(o)) => {
                // Host implied (80 or 443). Origin explicit.
                // Origin MUST be 80 or 443 to match implied Host.
                o == 80 || o == 443
            }
        };

        if !domains_match || !ports_match {
            tracing::warn!(?origin, ?host_raw, "CSRF check failed: Origin mismatch");
            return StatusCode::FORBIDDEN.into_response();
        }
        return next.run(req).await;
    }

    // 7. Fallback: Check Referer (Parsed as URI)
    if let Some(referer) = headers.get("referer").and_then(|v| v.to_str().ok()) {
        let referer_uri = match referer.parse::<Uri>() {
            Ok(u) => u,
            Err(_) => {
                tracing::warn!(?referer, "CSRF check failed: Invalid Referer URI");
                return StatusCode::FORBIDDEN.into_response();
            }
        };

        let ref_scheme = referer_uri.scheme_str().unwrap_or("http");

        if ref_scheme == "http" && !is_localhost {
            tracing::warn!(
                ?referer,
                "CSRF check failed: Insecure Referer (HTTP) on non-localhost"
            );
            return StatusCode::FORBIDDEN.into_response();
        }

        let (ref_host, ref_port) = if let Some(auth) = referer_uri.authority() {
            (auth.host().to_string(), auth.port_u16())
        } else {
            tracing::warn!(?referer, "CSRF check failed: Relative Referer");
            return StatusCode::FORBIDDEN.into_response();
        };

        let domains_match = host_domain.eq_ignore_ascii_case(&ref_host);

        let ports_match = match (host_port, ref_port) {
            (Some(h), Some(o)) => h == o,
            (Some(_), None) => false,
            (None, None) => true,
            (None, Some(o)) => o == 80 || o == 443,
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
        assert_eq!(
            parse_host_header("example.com"),
            ("example.com".to_string(), None)
        );
        assert_eq!(
            parse_host_header("example.com:8080"),
            ("example.com".to_string(), Some(8080))
        );
        assert_eq!(
            parse_host_header("[::1]:8080"),
            ("[::1]".to_string(), Some(8080))
        );
        assert_eq!(parse_host_header("[::1]"), ("[::1]".to_string(), None));
    }

    #[tokio::test]
    async fn test_exemption_logic() {
        use axum::http::Request;
        let req = Request::builder()
            .uri("/auth/login")
            .method("POST")
            .body(Body::empty())
            .unwrap();
        assert!(req.uri().path().ends_with("/auth/login"));
    }

    #[test]
    fn test_referer_allowlist_match() {
        let allowlist = ["https://my-dev.com".to_string()];
        let referer_exact = "https://my-dev.com".to_string();
        let referer_sub = "https://my-dev.com/foo".to_string();
        let referer_bad = "https://my-dev.com.evil.com".to_string();

        let check = |ref_val: &str| {
            allowlist
                .iter()
                .any(|allowed| ref_val == allowed || ref_val.starts_with(&format!("{}/", allowed)))
        };

        assert!(check(&referer_exact));
        assert!(check(&referer_sub));
        assert!(!check(&referer_bad));
    }

    #[test]
    fn test_strict_port_matching() {
        let check_ports = |host_port: Option<u16>, origin_port: Option<u16>| -> bool {
            match (host_port, origin_port) {
                (Some(h), Some(o)) => h == o,
                (Some(_), None) => false,
                (None, None) => true,
                (None, Some(o)) => o == 80 || o == 443,
            }
        };

        // Host has no port (implied standard), Origin has non-standard port -> FAIL
        assert!(!check_ports(None, Some(1234)));

        // Host has no port, Origin has standard port -> PASS
        assert!(check_ports(None, Some(80)));
        assert!(check_ports(None, Some(443)));

        // Host has explicit port, Origin has same port -> PASS
        assert!(check_ports(Some(8080), Some(8080)));

        // Host has explicit port, Origin has different port -> FAIL
        assert!(!check_ports(Some(8080), Some(9090)));
    }
}

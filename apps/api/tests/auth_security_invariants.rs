//! Reproducible Auth security-invariant proofs (auth-roadmap Phase 7).
//!
//! Closes the two clearest gaps named in `docs/reports/auth-status-matrix.md` §2.9:
//!   1. Systematic CSRF coverage of all currently listed CSRF-relevant mutating
//!      endpoints (previously only `/auth/session/refresh` was covered).
//!   2. Anti-enumeration *parity*: a known and an unknown email must yield a
//!      byte-identical response (previously only the unknown side was checked).
//!
//! These tests run against the same middleware stack wired in `src/lib.rs`
//! (`auth_middleware` as a route layer, `require_csrf` as the outer layer).

use anyhow::Result;
use axum::{
    body,
    extract::connect_info::MockConnectInfo,
    http::{Method, Request, StatusCode},
    Router,
};
use serial_test::serial;
use std::{net::SocketAddr, sync::Arc};
use tokio::sync::RwLock;
use tower::ServiceExt;
use weltgewebe_api::{
    auth::{
        accounts::AccountStore, rate_limit::AuthRateLimiter, role::Role, session::SessionBackend,
    },
    config::AppConfig,
    routes::{
        accounts::{AccountInternal, AccountMode, AccountPublic},
        api_router,
        auth::GENERIC_LOGIN_MSG,
    },
    state::ApiState,
    telemetry::{BuildInfo, Metrics},
    test_helpers::EnvGuard,
};

const KNOWN_EMAIL: &str = "u1@example.com";
const ADMIN_ID: &str = "u-admin";

fn account(id: &str, title: &str, role: Role, email: &str) -> AccountInternal {
    AccountInternal {
        public: AccountPublic {
            id: id.to_string(),
            kind: "garnrolle".to_string(),
            title: title.to_string(),
            summary: None,
            public_pos: None,
            mode: AccountMode::Verortet,
            radius_m: 0,
            disabled: false,
            tags: vec![],
        },
        role,
        email: Some(email.to_string()),
        webauthn_user_id: uuid::Uuid::new_v4(),
    }
}

fn build_state() -> Result<ApiState> {
    let metrics = Metrics::try_new(BuildInfo {
        version: "test",
        commit: "test",
        build_timestamp: "test",
    })?;

    // Public login on (so `/auth/magic-link/request` is reachable) with token
    // delivery via log (no SMTP). Rate limits stay unset so the limiter is a
    // no-op and `is_open_registration()` is false — an unknown email therefore
    // stays unknown instead of being auto-provisioned.
    let config = AppConfig {
        fade_days: 7,
        ron_days: 84,
        anonymize_opt_in: true,
        delegation_expire_days: 28,
        auth_public_login: true,
        app_base_url: Some("http://localhost".to_string()),
        auth_trusted_proxies: None,
        auth_allow_emails: None,
        auth_allow_email_domains: None,
        auth_auto_provision: false,
        auth_rl_ip_per_min: None,
        auth_rl_ip_per_hour: None,
        auth_rl_email_per_min: None,
        auth_rl_email_per_hour: None,
        smtp_host: None,
        smtp_port: None,
        smtp_user: None,
        smtp_pass: None,
        smtp_from: None,
        auth_log_magic_token: true,
        webauthn_rp_id: None,
        webauthn_rp_origin: None,
        webauthn_rp_name: None,
    };

    let rate_limiter = Arc::new(AuthRateLimiter::new(&config));

    let mut accounts = AccountStore::new();
    accounts.insert(account(ADMIN_ID, "Admin", Role::Admin, "admin@example.com"));
    accounts.insert(account("u1", "User One", Role::Gast, KNOWN_EMAIL));

    Ok(ApiState {
        db_pool: None,
        db_pool_configured: false,
        nats_client: None,
        nats_configured: false,
        config,
        metrics,
        sessions: SessionBackend::new_in_memory(),
        challenges: Default::default(),
        tokens: weltgewebe_api::auth::tokens::TokenStore::new(),
        step_up_tokens: weltgewebe_api::auth::step_up_tokens::StepUpTokenStore::new(),
        accounts: Arc::new(RwLock::new(accounts)),
        nodes: Arc::new(tokio::sync::RwLock::new(
            weltgewebe_api::state::OrderedCache::new(),
        )),
        nodes_persist: Arc::new(tokio::sync::Mutex::new(())),
        edges: Arc::new(tokio::sync::RwLock::new(
            weltgewebe_api::state::OrderedCache::new(),
        )),
        rate_limiter,
        mailer: None,
        webauthn: None,
        passkey_registrations: Default::default(),
        passkey_registration_grants: Default::default(),
        passkeys: Default::default(),
    })
}

/// Plain router (no security middleware) — used for the public `/auth/magic-link/request`
/// path, which carries no session cookie and is therefore not CSRF-relevant.
fn app_plain(state: ApiState) -> Router {
    Router::new()
        .merge(api_router())
        .layer(MockConnectInfo(SocketAddr::from(([127, 0, 0, 1], 8080))))
        .with_state(state)
}

/// Router wired exactly like production (`src/lib.rs`): `auth_middleware` as a
/// route layer, `require_csrf` as the outer layer that runs first on ingress.
fn app_with_security(state: ApiState) -> Router {
    Router::new()
        .merge(
            api_router()
                .route_layer(axum::middleware::from_fn_with_state(
                    state.clone(),
                    weltgewebe_api::middleware::auth::auth_middleware,
                ))
                .layer(axum::middleware::from_fn(
                    weltgewebe_api::middleware::csrf::require_csrf,
                )),
        )
        .layer(MockConnectInfo(SocketAddr::from(([127, 0, 0, 1], 8080))))
        .with_state(state)
}

/// A CSRF rejection from `require_csrf` is a bare `403 Forbidden` with an empty
/// body. This distinguishes it from a handler-level `403 STEP_UP_REQUIRED`,
/// which carries a JSON body.
async fn assert_csrf_blocked(app: &Router, method: Method, path: &str, session_cookie: &str) {
    let req = Request::builder()
        .method(method.clone())
        .uri(path)
        .header("Cookie", session_cookie)
        .header("Host", "localhost")
        .body(body::Body::empty())
        .expect("request builds");

    let res = app.clone().oneshot(req).await.expect("router responds");
    let status = res.status();
    let bytes = body::to_bytes(res.into_body(), usize::MAX)
        .await
        .expect("body reads");

    assert_eq!(
        status,
        StatusCode::FORBIDDEN,
        "cross-site {method} {path} (no Origin/Referer) must be rejected by CSRF middleware"
    );
    assert!(
        bytes.is_empty(),
        "CSRF rejection for {method} {path} must have an empty body (got {} bytes), \
         otherwise the 403 came from a handler and not the CSRF guard",
        bytes.len()
    );
}

/// Systematic CSRF proof: every mutating endpoint behind the CSRF layer rejects
/// a request that carries a session cookie but no same-origin Origin/Referer.
#[tokio::test]
#[serial]
async fn csrf_blocks_all_mutating_endpoints_without_origin() -> Result<()> {
    let _dev = EnvGuard::set("AUTH_DEV_LOGIN", "1");
    // Ensure the optional origin allowlist does not short-circuit the check.
    let _allow = EnvGuard::unset("CSRF_ALLOWED_ORIGINS");

    let state = build_state()?;
    let app = app_with_security(state);

    // Obtain a real session cookie via dev login (no cookie yet -> CSRF skips it).
    let login = Request::post("/auth/dev/login")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::from(format!(
            r#"{{"account_id":"{ADMIN_ID}"}}"#
        )))?;
    let login_res = app.clone().oneshot(login).await?;
    assert_eq!(login_res.status(), StatusCode::OK, "dev login must succeed");
    let set_cookie = login_res
        .headers()
        .get("Set-Cookie")
        .expect("dev login sets session cookie")
        .to_str()?;
    let session_cookie = set_cookie
        .split(';')
        .next()
        .expect("cookie has a value")
        .to_string();

    // All currently listed CSRF-relevant mutating endpoints reachable under the
    // CSRF layer. `/auth/login` and `/auth/logout` are intentionally exempt;
    // the magic-link request/consume entry points carry no session cookie and
    // are therefore not listed here.
    let mutating_endpoints: &[(Method, &str)] = &[
        (Method::POST, "/auth/session/refresh"),
        (Method::POST, "/auth/logout-all"),
        (Method::DELETE, "/auth/devices/any-device-id"),
        (Method::PUT, "/auth/me/email"),
        (Method::POST, "/auth/step-up/magic-link/request"),
        (Method::POST, "/auth/step-up/magic-link/consume"),
        (Method::POST, "/auth/passkeys/register/options"),
        // Cross-cutting (non-auth) mutating route to prove the guard is global.
        (Method::PATCH, "/nodes/any-node-id"),
    ];

    for (method, path) in mutating_endpoints {
        assert_csrf_blocked(&app, method.clone(), path, &session_cookie).await;
    }

    // Positive control: the same refresh request *with* a matching Origin passes
    // the CSRF guard, proving the rejections above are specifically CSRF-driven
    // and the middleware does not blanket-block legitimate same-origin traffic.
    let allowed = Request::post("/auth/session/refresh")
        .header("Cookie", &session_cookie)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::empty())?;
    let allowed_res = app.clone().oneshot(allowed).await?;
    assert_eq!(
        allowed_res.status(),
        StatusCode::OK,
        "same-origin refresh must pass the CSRF guard"
    );

    Ok(())
}

/// Anti-enumeration parity: a magic-link request for a known vs. an unknown
/// email must be indistinguishable — identical status and byte-identical body —
/// and must never echo the address or a token back to the caller.
#[tokio::test]
#[serial]
async fn magic_link_request_is_indistinguishable_for_known_and_unknown_email() -> Result<()> {
    let app = app_plain(build_state()?);

    let request_for = |email: &str| -> Result<Request<body::Body>> {
        Ok(Request::post("/auth/magic-link/request")
            .header("Content-Type", "application/json")
            .body(body::Body::from(format!(r#"{{"email":"{email}"}}"#)))?)
    };

    let known_res = app.clone().oneshot(request_for(KNOWN_EMAIL)?).await?;
    let known_status = known_res.status();
    let known_body = body::to_bytes(known_res.into_body(), usize::MAX).await?;

    let unknown_res = app
        .clone()
        .oneshot(request_for("nobody@example.com")?)
        .await?;
    let unknown_status = unknown_res.status();
    let unknown_body = body::to_bytes(unknown_res.into_body(), usize::MAX).await?;

    assert_eq!(known_status, StatusCode::OK);
    assert_eq!(
        known_status, unknown_status,
        "status must be identical for known vs. unknown email"
    );
    assert_eq!(
        known_body, unknown_body,
        "response body must be byte-identical for known vs. unknown email"
    );

    // Shape and non-leakage of the shared response.
    let body_val: serde_json::Value = serde_json::from_slice(&known_body)?;
    assert_eq!(body_val["ok"], true);
    assert_eq!(body_val["message"], GENERIC_LOGIN_MSG);

    let body_str = String::from_utf8_lossy(&known_body);
    assert!(
        !body_str.contains(KNOWN_EMAIL),
        "response must not echo the requested email"
    );
    assert!(
        !body_str.contains('@'),
        "response must not contain any email- or token-like material"
    );

    Ok(())
}

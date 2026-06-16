use anyhow::{Context, Result};
use axum::{
    body,
    http::{Request, StatusCode},
    Router,
};
use serial_test::serial;
mod helpers;

use axum::middleware::from_fn_with_state;
use helpers::set_gewebe_in_dir;
use std::sync::Arc;
use tokio::sync::RwLock;
use tower::ServiceExt;
use weltgewebe_api::{
    auth::{
        accounts::AccountStore, rate_limit::AuthRateLimiter, role::Role, session::SessionBackend,
    },
    config::{
        AppConfig, DomainAccountWriteSource, DomainEdgeWriteSource, DomainNodeWriteSource,
        DomainReadSource,
    },
    middleware::{auth::auth_middleware, csrf::require_csrf},
    routes::{
        accounts::{AccountInternal, AccountMode, AccountPublic},
        api_router,
    },
    state::ApiState,
    telemetry::{BuildInfo, Metrics},
};

async fn test_state() -> Result<ApiState> {
    let metrics = Metrics::try_new(BuildInfo {
        version: "test",
        commit: "test",
        build_timestamp: "test",
    })?;

    let config = AppConfig {
        fade_days: 7,
        ron_days: 84,
        anonymize_opt_in: true,
        delegation_expire_days: 28,
        domain_read_source: DomainReadSource::Jsonl,
        domain_account_write_source: DomainAccountWriteSource::Jsonl,
        domain_node_write_source: DomainNodeWriteSource::Jsonl,
        domain_edge_write_source: DomainEdgeWriteSource::Jsonl,
        auth_public_login: false,
        app_base_url: None,
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
        auth_log_magic_token: false,
        webauthn_rp_id: None,
        webauthn_rp_origin: None,
        webauthn_rp_name: None,
    };

    let rate_limiter = Arc::new(AuthRateLimiter::new(&config));

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
        accounts: Arc::new(RwLock::new(AccountStore::new())),
        nodes: Arc::new(tokio::sync::RwLock::new(
            weltgewebe_api::state::OrderedCache::new(),
        )),
        nodes_persist: Arc::new(tokio::sync::Mutex::new(())),
        accounts_persist: Arc::new(tokio::sync::Mutex::new(())),
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

fn operator(id: &str, role: Role) -> AccountInternal {
    AccountInternal {
        public: AccountPublic {
            id: id.to_string(),
            kind: "garnrolle".to_string(),
            title: format!("Operator {id}"),
            summary: None,
            public_pos: None,
            mode: AccountMode::Verortet,
            radius_m: 0,
            disabled: false,
            tags: vec![],
        },
        role,
        email: None,
        webauthn_user_id: uuid::Uuid::new_v4(),
    }
}

/// Build a router (auth + csrf wired like prod) with a single operator account
/// and an active session for it. Returns (app, session_cookie, state).
async fn app_with_operator(
    in_dir: &std::path::Path,
    operator_id: &str,
    role: Role,
) -> Result<(Router, String, ApiState)> {
    app_with_operator_read_source(in_dir, operator_id, role, DomainReadSource::Jsonl).await
}

async fn app_with_operator_read_source(
    in_dir: &std::path::Path,
    operator_id: &str,
    role: Role,
    domain_read_source: DomainReadSource,
) -> Result<(Router, String, ApiState)> {
    app_with_operator_sources(
        in_dir,
        operator_id,
        role,
        domain_read_source,
        DomainAccountWriteSource::Jsonl,
    )
    .await
}

async fn app_with_operator_sources(
    in_dir: &std::path::Path,
    operator_id: &str,
    role: Role,
    domain_read_source: DomainReadSource,
    domain_account_write_source: DomainAccountWriteSource,
) -> Result<(Router, String, ApiState)> {
    let mut accounts = AccountStore::new();
    accounts.insert(operator(operator_id, role));

    let mut state = test_state().await?;
    state.config.domain_read_source = domain_read_source;
    state.config.domain_account_write_source = domain_account_write_source;
    state.accounts = Arc::new(RwLock::new(accounts));

    let session = state
        .sessions
        .create(operator_id.to_string(), None)
        .await
        .expect("session create");
    let cookie = format!("gewebe_session={}", session.id);

    let _ = in_dir; // GEWEBE_IN_DIR is set by the caller via EnvGuard
    let app = Router::new()
        .merge(api_router())
        .layer(from_fn_with_state(state.clone(), auth_middleware))
        .layer(axum::middleware::from_fn(require_csrf))
        .with_state(state.clone());
    Ok((app, cookie, state))
}

fn post_accounts(cookie: Option<&str>, json_body: &str) -> Request<body::Body> {
    let mut builder = Request::post("/accounts")
        .header("Content-Type", "application/json")
        .header("Host", "localhost")
        .header("Origin", "http://localhost");
    if let Some(c) = cookie {
        builder = builder.header("Cookie", c);
    }
    builder
        .body(body::Body::from(json_body.to_string()))
        .unwrap()
}

#[tokio::test]
#[serial]
async fn admin_creates_account_persists_and_lists() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, _state) = app_with_operator(&in_dir, "admin1", Role::Admin).await?;

    // POST a new account with an exact public position (radius_m default 0).
    let res = app
        .clone()
        .oneshot(post_accounts(
            Some(&cookie),
            r#"{"title":"Alice","location":{"lat":53.5503,"lon":9.9932},"tags":["real"]}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::CREATED);

    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let created: serde_json::Value = serde_json::from_slice(&bytes)?;
    let new_id = created["id"].as_str().context("id present")?.to_string();
    assert_eq!(created["title"], "Alice");
    // radius_m=0 => public_pos equals the provided location.
    assert_eq!(created["public_pos"]["lat"], 53.5503);
    assert_eq!(created["public_pos"]["lon"], 9.9932);
    // location must never be exposed publicly.
    assert!(created.get("location").is_none());

    // GET /accounts contains the created account.
    let res = app
        .clone()
        .oneshot(Request::get("/accounts").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let list: serde_json::Value = serde_json::from_slice(&bytes)?;
    let found = list
        .as_array()
        .context("array")?
        .iter()
        .any(|a| a["id"] == serde_json::Value::String(new_id.clone()));
    assert!(found, "created account must appear in GET /accounts");

    // Durability: the JSONL file on disk contains the new account id.
    let file = in_dir.join("demo.accounts.jsonl");
    let contents = std::fs::read_to_string(&file)?;
    assert!(
        contents.contains(&new_id),
        "created account must be persisted to JSONL"
    );

    Ok(())
}

#[tokio::test]
#[serial]
async fn weber_cannot_create_account() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, _state) = app_with_operator(&in_dir, "weber1", Role::Weber).await?;

    let res = app
        .oneshot(post_accounts(
            Some(&cookie),
            r#"{"title":"X","location":{"lat":1.0,"lon":2.0}}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::FORBIDDEN);
    Ok(())
}

#[tokio::test]
#[serial]
async fn unauthenticated_cannot_create_account() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, _cookie, _state) = app_with_operator(&in_dir, "admin1", Role::Admin).await?;

    // No session cookie -> 401 (require_admin), CSRF is skipped without a cookie.
    let res = app
        .oneshot(post_accounts(
            None,
            r#"{"title":"X","location":{"lat":1.0,"lon":2.0}}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
    Ok(())
}

#[tokio::test]
#[serial]
async fn invalid_input_returns_400() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, _state) = app_with_operator(&in_dir, "admin1", Role::Admin).await?;

    // Out-of-range latitude.
    let res = app
        .clone()
        .oneshot(post_accounts(
            Some(&cookie),
            r#"{"title":"X","location":{"lat":91.0,"lon":2.0}}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    // Out-of-range longitude.
    let res = app
        .clone()
        .oneshot(post_accounts(
            Some(&cookie),
            r#"{"title":"X","location":{"lat":1.0,"lon":181.0}}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    // Missing location.
    let res = app
        .clone()
        .oneshot(post_accounts(Some(&cookie), r#"{"title":"X"}"#))
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    // Missing title.
    let res = app
        .clone()
        .oneshot(post_accounts(
            Some(&cookie),
            r#"{"location":{"lat":1.0,"lon":2.0}}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    // type=ron is rejected in v0.
    let res = app
        .oneshot(post_accounts(
            Some(&cookie),
            r#"{"title":"X","type":"ron","location":{"lat":1.0,"lon":2.0}}"#,
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    Ok(())
}

#[tokio::test]
#[serial]
async fn invalid_domain_write_config_blocks_account_create_without_side_effects() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, state) = app_with_operator_sources(
        &in_dir,
        "admin1",
        Role::Admin,
        DomainReadSource::Jsonl,
        DomainAccountWriteSource::Postgres,
    )
    .await?;

    let id = "44444444-4444-4444-8444-444444444444";
    let body =
        format!(r#"{{"id":"{id}","title":"InvalidCfg","location":{{"lat":53.55,"lon":9.99}}}}"#);

    let res = app
        .clone()
        .oneshot(post_accounts(Some(&cookie), &body))
        .await?;
    assert_eq!(res.status(), StatusCode::INTERNAL_SERVER_ERROR);
    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let response = String::from_utf8(bytes.to_vec())?;
    assert!(response.contains("INVALID_DOMAIN_WRITE_CONFIG"));

    assert!(state.accounts.read().await.get(id).is_none());
    let accounts_path = in_dir.join("demo.accounts.jsonl");
    assert!(
        !accounts_path.exists(),
        "invalid config must not append the account JSONL file"
    );

    Ok(())
}

#[tokio::test]
#[serial]
async fn postgres_read_source_blocks_account_create_without_persisting() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, state) =
        app_with_operator_read_source(&in_dir, "admin1", Role::Admin, DomainReadSource::Postgres)
            .await?;

    let id = "33333333-3333-4333-8333-333333333333";
    let body =
        format!(r#"{{"id":"{id}","title":"Blocked","location":{{"lat":53.55,"lon":9.99}}}}"#);

    let res = app
        .clone()
        .oneshot(post_accounts(Some(&cookie), &body))
        .await?;
    assert_eq!(res.status(), StatusCode::CONFLICT);
    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let response = String::from_utf8(bytes.to_vec())?;
    assert!(response.contains("DOMAIN_READ_SOURCE_READ_ONLY"));

    assert!(state.accounts.read().await.get(id).is_none());
    let accounts_path = in_dir.join("demo.accounts.jsonl");
    assert!(
        !accounts_path.exists(),
        "blocked create must not append the account JSONL file"
    );

    Ok(())
}

#[tokio::test]
#[serial]
async fn duplicate_id_returns_409() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, _state) = app_with_operator(&in_dir, "admin1", Role::Admin).await?;

    let id = "11111111-1111-4111-8111-111111111111";
    let body = format!(r#"{{"id":"{id}","title":"First","location":{{"lat":1.0,"lon":2.0}}}}"#);

    let res = app
        .clone()
        .oneshot(post_accounts(Some(&cookie), &body))
        .await?;
    assert_eq!(res.status(), StatusCode::CREATED);

    // Same id again -> 409 Conflict.
    let res = app.oneshot(post_accounts(Some(&cookie), &body)).await?;
    assert_eq!(res.status(), StatusCode::CONFLICT);
    Ok(())
}

/// radius_m=0 (default): public_pos must equal the submitted location exactly.
/// This proves the create path does not silently discard or alter exact coordinates.
#[tokio::test]
#[serial]
async fn radius_m_zero_public_pos_is_exact() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, _state) = app_with_operator(&in_dir, "admin1", Role::Admin).await?;

    let id = "22222222-2222-4222-8222-222222222222";
    let lat = 53.5503_f64;
    let lon = 9.9932_f64;

    let res = app
        .oneshot(post_accounts(
            Some(&cookie),
            &format!(
                r#"{{"id":"{id}","title":"Exact","location":{{"lat":{lat},"lon":{lon}}},"radius_m":0}}"#
            ),
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::CREATED);

    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let created: serde_json::Value = serde_json::from_slice(&bytes)?;

    // radius_m=0 => public_pos must equal the submitted location exactly.
    assert_eq!(
        created["public_pos"]["lat"], lat,
        "radius_m=0: public_pos.lat must equal submitted location.lat"
    );
    assert_eq!(
        created["public_pos"]["lon"], lon,
        "radius_m=0: public_pos.lon must equal submitted location.lon"
    );
    // location must never be exposed publicly.
    assert!(created.get("location").is_none());
    Ok(())
}

/// radius_m>0: public_pos must be deterministically jittered — not the exact
/// input location. This proves radius_m is not a fake field: the API actually
/// applies obfuscation rather than accepting the value and silently ignoring it.
#[tokio::test]
#[serial]
async fn radius_m_positive_jitters_public_pos() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, _state) = app_with_operator(&in_dir, "admin1", Role::Admin).await?;

    // Use a fixed id so the jitter is deterministic across test runs.
    let id = "33333333-3333-4333-8333-333333333333";
    let lat = 53.5503_f64;
    let lon = 9.9932_f64;
    let radius_m = 500_u32;

    let res = app
        .clone()
        .oneshot(post_accounts(
            Some(&cookie),
            &format!(
                r#"{{"id":"{id}","title":"Jittered","location":{{"lat":{lat},"lon":{lon}}},"radius_m":{radius_m}}}"#
            ),
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::CREATED);

    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let created: serde_json::Value = serde_json::from_slice(&bytes)?;

    let jitter_lat = created["public_pos"]["lat"]
        .as_f64()
        .context("public_pos.lat must be a number")?;
    let jitter_lon = created["public_pos"]["lon"]
        .as_f64()
        .context("public_pos.lon must be a number")?;

    // location must never be exposed publicly.
    assert!(created.get("location").is_none());

    // radius_m>0 => public_pos must NOT equal the exact submitted location.
    // (The jitter algorithm derives r1, r2 from a djb2 hash: r1 = (hash & 0xFFFF)/65535*2-1.
    // r1==0 would require hash & 0xFFFF == 32767.5 — impossible for integers — so
    // jitter is guaranteed non-zero for any id.)
    assert_ne!(
        jitter_lat, lat,
        "radius_m>0: public_pos.lat must differ from exact location.lat (jitter not applied)"
    );
    assert_ne!(
        jitter_lon, lon,
        "radius_m>0: public_pos.lon must differ from exact location.lon (jitter not applied)"
    );

    // The jitter must stay within the declared radius (square bounding box in degrees).
    let max_deg = radius_m as f64 / 111_000.0;
    assert!(
        (jitter_lat - lat).abs() <= max_deg + 1e-9,
        "public_pos.lat jitter exceeds radius bound: |{jitter_lat} - {lat}| > {max_deg}"
    );
    // longitude bound is scaled by 1/cos(lat) near equator; use generous tolerance.
    let cos_lat = lat.to_radians().cos().max(1e-3);
    let max_deg_lon = max_deg / cos_lat;
    let lon_delta = {
        let d = (jitter_lon - lon).abs();
        if d > 180.0 {
            360.0 - d
        } else {
            d
        }
    };
    assert!(
        lon_delta <= max_deg_lon + 1e-9,
        "public_pos.lon jitter exceeds radius bound: lon_delta={lon_delta} > {max_deg_lon}"
    );
    Ok(())
}

/// radius_m>0 with the same id and location produces the same public_pos on every
/// request (deterministic jitter, stable across GET).
#[tokio::test]
#[serial]
async fn radius_m_positive_public_pos_is_deterministic() -> Result<()> {
    let tmp = tempfile::tempdir()?;
    let in_dir = tmp.path().join("in");
    std::fs::create_dir_all(&in_dir)?;
    let _env = set_gewebe_in_dir(&in_dir);

    let (app, cookie, _state) = app_with_operator(&in_dir, "admin1", Role::Admin).await?;

    let id = "44444444-4444-4444-8444-444444444444";
    let lat = 53.55_f64;
    let lon = 9.99_f64;
    let radius_m = 250_u32;

    // POST: create the account and record the public_pos from the 201 response.
    let res = app
        .clone()
        .oneshot(post_accounts(
            Some(&cookie),
            &format!(
                r#"{{"id":"{id}","title":"Det","location":{{"lat":{lat},"lon":{lon}}},"radius_m":{radius_m}}}"#
            ),
        ))
        .await?;
    assert_eq!(res.status(), StatusCode::CREATED);
    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let created: serde_json::Value = serde_json::from_slice(&bytes)?;
    let post_lat = created["public_pos"]["lat"]
        .as_f64()
        .context("public_pos.lat")?;
    let post_lon = created["public_pos"]["lon"]
        .as_f64()
        .context("public_pos.lon")?;

    // GET /accounts/{id}: the same public_pos must be returned.
    let res = app
        .oneshot(axum::http::Request::get(format!("/accounts/{id}")).body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let fetched: serde_json::Value = serde_json::from_slice(&bytes)?;
    let get_lat = fetched["public_pos"]["lat"]
        .as_f64()
        .context("public_pos.lat in GET")?;
    let get_lon = fetched["public_pos"]["lon"]
        .as_f64()
        .context("public_pos.lon in GET")?;

    assert_eq!(
        post_lat, get_lat,
        "public_pos.lat must be deterministic: POST={post_lat}, GET={get_lat}"
    );
    assert_eq!(
        post_lon, get_lon,
        "public_pos.lon must be deterministic: POST={post_lon}, GET={get_lon}"
    );
    Ok(())
}

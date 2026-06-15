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
use std::{fs, path::PathBuf, sync::Arc};
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
        accounts::{AccountInternal, AccountPublic},
        api_router,
    },
    state::ApiState,
    telemetry::{BuildInfo, Metrics},
    test_helpers::EnvGuard,
};

async fn create_session(
    state: &ApiState,
    account_id: &str,
    existing_device_id: Option<&str>,
) -> weltgewebe_api::auth::session::Session {
    state
        .sessions
        .create(
            account_id.to_string(),
            existing_device_id.map(std::string::ToString::to_string),
        )
        .await
        .expect("in-memory session backend must create session")
}

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
            weltgewebe_api::routes::nodes::load_nodes().await,
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
        passkey_authentications: Default::default(),
        passkeys: Default::default(),
    })
}

fn make_tmp_dir() -> tempfile::TempDir {
    tempfile::tempdir().expect("tmpdir")
}

fn write_lines(path: &PathBuf, lines: &[&str]) {
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(path, lines.join("\n")).unwrap();
}

/// Helper: Ensures correct setup order (File Write -> Env -> State Init)
async fn app_with_nodes(in_dir: &std::path::Path, lines: &[&str]) -> (Router, EnvGuard) {
    let nodes_path = in_dir.join("demo.nodes.jsonl");
    write_lines(&nodes_path, lines);
    let env = set_gewebe_in_dir(in_dir);
    let state = test_state().await.unwrap();
    let app = Router::new().merge(api_router()).with_state(state);
    (app, env)
}

#[tokio::test]
#[serial]
async fn nodes_bbox_and_limit() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");

    let (app, _env) = app_with_nodes(
        &in_dir,
        &[
            r#"{"id":"n1","location":{"lon":9.9,"lat":53.55},"title":"A"}"#,
            r#"{"id":"n2","location":{"lon":11.0,"lat":54.2},"title":"B"}"#,
            r#"{"id":"n3","location":{"lon":10.2,"lat":53.6},"title":"C"}"#,
        ],
    )
    .await;

    // BBox über Hamburg herum (soll n1 & n3 treffen)
    let res = app
        .clone()
        .oneshot(Request::get("/nodes?bbox=9.5,53.4,10.5,53.8&limit=10").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let arr = v.as_array().context("must be array")?;
    assert_eq!(arr.len(), 2);
    let ids: Vec<_> = arr
        .iter()
        .map(|x| {
            x.get("id")
                .expect("id missing")
                .as_str()
                .expect("must be string")
                .to_string()
        })
        .collect();
    assert!(ids.contains(&"n1".to_string()) && ids.contains(&"n3".to_string()));

    // Vertauschte BBox-Koordinaten sollen ebenfalls normalisiert werden
    let res = app
        .clone()
        .oneshot(Request::get("/nodes?bbox=10.5,53.8,9.5,53.4&limit=10").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let arr = v.as_array().context("must be array")?;
    assert_eq!(arr.len(), 2);
    let ids: Vec<_> = arr
        .iter()
        .map(|x| {
            x.get("id")
                .expect("id missing")
                .as_str()
                .expect("must be string")
                .to_string()
        })
        .collect();
    assert!(ids.contains(&"n1".to_string()) && ids.contains(&"n3".to_string()));

    // Ungültige BBox ergibt 400 Bad Request
    let res = app
        .clone()
        .oneshot(Request::get("/nodes?bbox=oops").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    // Limit=1
    let res = app
        .oneshot(Request::get("/nodes?limit=1").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    assert_eq!(v.as_array().context("must be array")?.len(), 1);

    Ok(())
}

#[tokio::test]
#[serial]
async fn nodes_patch_info_lifecycle() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");
    let nodes_path = in_dir.join("demo.nodes.jsonl");

    write_lines(
        &nodes_path,
        &[r#"{"id":"n1","location":{"lon":10.0,"lat":53.5},"title":"A","info":"Old Info"}"#],
    );
    let _env = set_gewebe_in_dir(&in_dir);

    // Setup Auth State with Account
    let mut account_map = AccountStore::new();
    let account = AccountPublic {
        id: "weber1".to_string(),
        kind: "garnrolle".to_string(),
        title: "Weber".to_string(),
        summary: None,
        public_pos: None,
        mode: weltgewebe_api::routes::accounts::AccountMode::Verortet,
        radius_m: 0,

        disabled: false,
        tags: vec![],
    };
    account_map.insert(AccountInternal {
        public: account,
        role: Role::Weber,
        email: Some("weber1@example.com".to_string()),
        webauthn_user_id: uuid::Uuid::new_v4(),
    });

    let mut state = test_state().await?;
    state.accounts = Arc::new(RwLock::new(account_map));

    // Create Session
    let session = create_session(&state, "weber1", None).await;
    let cookie_val = format!("gewebe_session={}", session.id);

    let app = Router::new()
        .merge(api_router())
        .layer(from_fn_with_state(state.clone(), auth_middleware))
        .layer(axum::middleware::from_fn(require_csrf))
        .with_state(state);

    // 1. Update info -> "New Info"
    // Note: We MUST provide Origin or Referer because a session cookie is present,
    // otherwise CSRF middleware will block it.
    let req = Request::patch("/nodes/n1")
        .header("Content-Type", "application/json")
        .header("Cookie", &cookie_val)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::from(r#"{"info":"New Info"}"#))?;
    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);

    // Check response
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    assert_eq!(v["info"], "New Info");

    // Check persistence by reading via GET
    let req = Request::get("/nodes/n1").body(body::Body::empty())?;
    let res = app.clone().oneshot(req).await?;
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    assert_eq!(v["info"], "New Info");

    // 2. Empty PATCH (No-op) -> Info remains "New Info"
    let req = Request::patch("/nodes/n1")
        .header("Content-Type", "application/json")
        .header("Cookie", &cookie_val)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::from(r#"{}"#))?;
    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    assert_eq!(v["info"], "New Info"); // Still there

    // 3. Set info to null -> Info removed
    let req = Request::patch("/nodes/n1")
        .header("Content-Type", "application/json")
        .header("Cookie", &cookie_val)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::from(r#"{"info":null}"#))?;
    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    assert!(v.get("info").is_none() || v["info"].is_null());

    // Check persistence
    let req = Request::get("/nodes/n1").body(body::Body::empty())?;
    let res = app.clone().oneshot(req).await?;
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    assert!(v.get("info").is_none() || v["info"].is_null());

    Ok(())
}

#[tokio::test]
#[serial]
async fn postgres_read_source_blocks_node_patch_without_persisting() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");
    let nodes_path = in_dir.join("demo.nodes.jsonl");
    let original_line =
        r#"{"id":"n1","location":{"lon":10.0,"lat":53.5},"title":"A","info":"Old Info"}"#;
    write_lines(&nodes_path, &[original_line]);
    let _env = set_gewebe_in_dir(&in_dir);

    let mut account_map = AccountStore::new();
    let account = AccountPublic {
        id: "weber1".to_string(),
        kind: "garnrolle".to_string(),
        title: "Weber".to_string(),
        summary: None,
        public_pos: None,
        mode: weltgewebe_api::routes::accounts::AccountMode::Verortet,
        radius_m: 0,
        disabled: false,
        tags: vec![],
    };
    account_map.insert(AccountInternal {
        public: account,
        role: Role::Weber,
        email: Some("weber1@example.com".to_string()),
        webauthn_user_id: uuid::Uuid::new_v4(),
    });

    let mut state = test_state().await?;
    state.config.domain_read_source = DomainReadSource::Postgres;
    state.accounts = Arc::new(RwLock::new(account_map));

    let session = create_session(&state, "weber1", None).await;
    let cookie_val = format!("gewebe_session={}", session.id);

    let app = Router::new()
        .merge(api_router())
        .layer(from_fn_with_state(state.clone(), auth_middleware))
        .layer(axum::middleware::from_fn(require_csrf))
        .with_state(state.clone());

    let req = Request::patch("/nodes/n1")
        .header("Content-Type", "application/json")
        .header("Cookie", &cookie_val)
        .header("Host", "localhost")
        .header("Origin", "http://localhost")
        .body(body::Body::from(r#"{"info":"New Info"}"#))?;
    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::CONFLICT);
    let bytes = body::to_bytes(res.into_body(), usize::MAX).await?;
    let response = String::from_utf8(bytes.to_vec())?;
    assert!(response.contains("DOMAIN_READ_SOURCE_READ_ONLY"));

    let cached_info = state
        .nodes
        .read()
        .await
        .get("n1")
        .and_then(|node| node.info.as_deref().map(str::to_string));
    assert_eq!(cached_info.as_deref(), Some("Old Info"));
    assert_eq!(fs::read_to_string(&nodes_path)?, original_line);

    Ok(())
}

#[tokio::test]
#[serial]
async fn nodes_accept_string_coordinates() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");

    let (app, _env) = app_with_nodes(
        &in_dir,
        &[r#"{"id":"n1","location":{"lon":"9.9","lat":"53.55"},"title":"A"}"#],
    )
    .await;

    let res = app
        .oneshot(Request::get("/nodes").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);

    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let arr = v.as_array().context("must be array")?;
    assert_eq!(arr.len(), 1);

    let node = arr.first().context("node missing")?;
    assert_eq!(node.get("id").and_then(|value| value.as_str()), Some("n1"));
    assert_eq!(
        node.get("location")
            .and_then(|value| value.get("lat"))
            .and_then(|value| value.as_f64()),
        Some(53.55)
    );
    assert_eq!(
        node.get("location")
            .and_then(|value| value.get("lon"))
            .and_then(|value| value.as_f64()),
        Some(9.9)
    );

    Ok(())
}

#[tokio::test]
#[serial]
async fn nodes_fill_missing_updated_at_from_created_at() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");

    let (app, _env) = app_with_nodes(&in_dir, &[
        r#"{"id":"n1","location":{"lon":9.9,"lat":53.55},"title":"A","created_at":"2024-01-02T03:04:05Z"}"#,
    ]).await;

    let res = app
        .oneshot(Request::get("/nodes").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);

    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let arr = v.as_array().context("must be array")?;
    assert_eq!(arr.len(), 1);

    let node = arr.first().context("node missing")?;
    let created_at = node
        .get("created_at")
        .and_then(|value| value.as_str())
        .context("created_at missing")?;
    let updated_at = node
        .get("updated_at")
        .and_then(|value| value.as_str())
        .context("updated_at missing")?;

    assert_eq!(created_at, "2024-01-02T03:04:05Z");
    assert_eq!(updated_at, created_at);

    Ok(())
}

#[tokio::test]
#[serial]
async fn nodes_patch_without_origin_fails() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");
    let nodes = in_dir.join("demo.nodes.jsonl");
    let _env = set_gewebe_in_dir(&in_dir);

    // Initial node
    write_lines(
        &nodes,
        &[r#"{"id":"n1","location":{"lon":10.0,"lat":53.5},"title":"A","info":"Old Info"}"#],
    );

    // Setup Auth State with Account
    let mut account_map = AccountStore::new();
    let account = AccountPublic {
        id: "weber1".to_string(),
        kind: "garnrolle".to_string(),
        title: "Weber".to_string(),
        summary: None,
        public_pos: None,
        mode: weltgewebe_api::routes::accounts::AccountMode::Verortet,
        radius_m: 0,

        disabled: false,
        tags: vec![],
    };
    account_map.insert(AccountInternal {
        public: account,
        role: Role::Weber,
        email: Some("weber1@example.com".to_string()),
        webauthn_user_id: uuid::Uuid::new_v4(),
    });

    let mut state = test_state().await?;
    state.accounts = Arc::new(RwLock::new(account_map));

    // Create Session
    let session = create_session(&state, "weber1", None).await;
    let cookie_val = format!("gewebe_session={}", session.id);

    let app = Router::new()
        .merge(api_router())
        .layer(from_fn_with_state(state.clone(), auth_middleware))
        .layer(axum::middleware::from_fn(require_csrf))
        .with_state(state);

    // Attempt PATCH with cookie but NO Origin/Referer logic that satisfies CSRF.
    // We explicitly set Host to ensure the 403 comes from the missing Origin/Referer check,
    // not from a missing Host header check.
    let req = Request::patch("/nodes/n1")
        .header("Content-Type", "application/json")
        .header("Cookie", &cookie_val)
        .header("Host", "localhost")
        // No Origin, No Referer
        .body(body::Body::from(r#"{"info":"Hacked Info"}"#))?;

    let res = app.clone().oneshot(req).await?;
    assert_eq!(res.status(), StatusCode::FORBIDDEN);

    Ok(())
}

#[tokio::test]
#[serial]
async fn nodes_offset_pagination() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");

    let (app, _env) = app_with_nodes(
        &in_dir,
        &[
            r#"{"id":"n1","location":{"lon":9.9,"lat":53.55},"title":"A"}"#,
            r#"{"id":"n2","location":{"lon":10.1,"lat":53.6},"title":"B"}"#,
            r#"{"id":"n3","location":{"lon":10.2,"lat":53.7},"title":"C"}"#,
        ],
    )
    .await;

    // limit=1&offset=0 liefert erstes Element (n1)
    let res = app
        .clone()
        .oneshot(Request::get("/nodes?limit=1&offset=0").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let arr = v.as_array().context("must be array")?;
    assert_eq!(arr.len(), 1);
    assert_eq!(arr[0]["id"], "n1");

    // limit=1&offset=1 liefert zweites Element (n2)
    let res = app
        .clone()
        .oneshot(Request::get("/nodes?limit=1&offset=1").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let arr = v.as_array().context("must be array")?;
    assert_eq!(arr.len(), 1);
    assert_eq!(arr[0]["id"], "n2");

    // Offset außerhalb der Ergebnislänge liefert leere Liste
    let res = app
        .clone()
        .oneshot(Request::get("/nodes?limit=10&offset=100").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let arr = v.as_array().context("must be array")?;
    assert_eq!(arr.len(), 0);

    // Ungültiger Offset (negativ) -> 400
    let res = app
        .clone()
        .oneshot(Request::get("/nodes?offset=-1").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    // Ungültiger Offset (kein Integer) -> 400
    let res = app
        .oneshot(Request::get("/nodes?offset=abc").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    Ok(())
}

#[tokio::test]
#[serial]
async fn nodes_invalid_limit() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");

    let (app, _env) = app_with_nodes(
        &in_dir,
        &[r#"{"id":"n1","location":{"lon":9.9,"lat":53.55},"title":"A"}"#],
    )
    .await;

    // limit=abc -> 400
    let res = app
        .clone()
        .oneshot(Request::get("/nodes?limit=abc").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    // limit=-1 -> 400
    let res = app
        .oneshot(Request::get("/nodes?limit=-1").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    Ok(())
}

#[tokio::test]
#[serial]
async fn nodes_robustness_with_dirty_data() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");

    // We verify:
    // n1: Clean
    // n2: Kind is number -> Unknown
    // n3: Summary is array -> None
    // n4: Title is boolean -> Untitled
    // n5: Info is object -> None
    let (app, _env) = app_with_nodes(
        &in_dir,
        &[
            r#"{"id": "n1", "kind": "Clean", "title": "Clean Node", "location": {"lat": 52.5, "lon": 13.4}}"#,
            r#"{"id": "n2", "kind": 123, "title": "Dirty Kind", "location": {"lat": 52.5, "lon": 13.4}}"#,
            r#"{"id": "n3", "kind": "Dirty Summary", "title": "Dirty Summary", "summary": ["oops"], "location": {"lat": 52.5, "lon": 13.4}}"#,
            r#"{"id": "n4", "kind": "Dirty Title", "title": true, "location": {"lat": 52.5, "lon": 13.4}}"#,
            r#"{"id": "n5", "kind": "Dirty Info", "title": "Dirty Info", "info": {"foo": "bar"}, "location": {"lat": 52.5, "lon": 13.4}}"#,
            r#"{"id": "n6", "title": "Dirty Tags", "tags": ["clean", 123, null, "also-clean"], "location": {"lat": 52.5, "lon": 13.4}}"#,
            r#"{broken_json"#, // Malformed JSON line -> should be skipped
        ],
    )
    .await;

    let res = app
        .oneshot(Request::get("/nodes").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);

    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let arr = v.as_array().context("must be array")?;

    // Check that all 6 nodes loaded (robustness)
    assert_eq!(arr.len(), 6);

    // Helper to find node by id
    let find_node = |id: &str| arr.iter().find(|n| n["id"] == id).unwrap();

    // n1: Clean
    let n1 = find_node("n1");
    assert_eq!(n1["kind"], "Clean");

    // n2: Kind is number -> Unknown
    let n2 = find_node("n2");
    assert_eq!(n2["kind"], "Unknown");

    // n3: Summary is array -> None (null)
    let n3 = find_node("n3");
    assert!(n3.get("summary").is_none() || n3["summary"].is_null());

    // n4: Title is boolean -> Untitled
    let n4 = find_node("n4");
    assert_eq!(n4["title"], "Untitled");

    // n5: Info is object -> None (null)
    let n5 = find_node("n5");
    assert!(n5.get("info").is_none() || n5["info"].is_null());

    // n6: Tags mixed -> ["clean", "also-clean"]
    let n6 = find_node("n6");
    let tags = n6["tags"].as_array().expect("tags must be array");
    assert_eq!(tags.len(), 2);
    assert_eq!(tags[0], "clean");
    assert_eq!(tags[1], "also-clean");

    Ok(())
}

#[tokio::test]
#[serial]
async fn nodes_limit_is_clamped_to_max_page_size() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");

    // Seed more nodes than the page-size cap so the clamp is observable.
    let lines: Vec<String> = (0..1100)
        .map(|i| format!(r#"{{"id":"n{i}","location":{{"lon":10.0,"lat":53.5}},"title":"N{i}"}}"#))
        .collect();
    let line_refs: Vec<&str> = lines.iter().map(String::as_str).collect();

    let (app, _env) = app_with_nodes(&in_dir, &line_refs).await;

    // A limit above MAX_PAGE_SIZE (1000) must be clamped, mirroring /edges.
    let res = app
        .oneshot(Request::get("/nodes?limit=5000").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    assert_eq!(v.as_array().context("must be array")?.len(), 1000);

    Ok(())
}

#[tokio::test]
#[serial]
async fn nodes_cursor_pagination_envelope_and_walk() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");

    // Insertion order is deliberately unsorted to prove cursor mode sorts by
    // stable id ascending, independent of the legacy file/insertion order.
    let (app, _env) = app_with_nodes(
        &in_dir,
        &[
            r#"{"id":"n3","location":{"lon":10.0,"lat":53.5},"title":"C"}"#,
            r#"{"id":"n1","location":{"lon":10.0,"lat":53.5},"title":"A"}"#,
            r#"{"id":"n5","location":{"lon":10.0,"lat":53.5},"title":"E"}"#,
            r#"{"id":"n2","location":{"lon":10.0,"lat":53.5},"title":"B"}"#,
            r#"{"id":"n4","location":{"lon":10.0,"lat":53.5},"title":"D"}"#,
        ],
    )
    .await;

    // Page 1: cursor mode returns the {items, page} envelope, not a bare array.
    let res = app
        .clone()
        .oneshot(Request::get("/nodes?pagination=cursor&limit=2").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    assert!(v.is_object(), "cursor mode must return an envelope object");
    let items = v["items"].as_array().context("items must be array")?;
    assert_eq!(items.len(), 2);
    assert_eq!(items[0]["id"], "n1");
    assert_eq!(items[1]["id"], "n2");
    assert_eq!(v["page"]["limit"], 2);
    assert_eq!(v["page"]["has_more"], true);
    let cursor1 = v["page"]["next_cursor"]
        .as_str()
        .context("next_cursor must be present on page 1")?
        .to_string();

    // Page 2: following next_cursor yields the next id-ordered slice with no
    // duplicates from page 1.
    let uri = format!("/nodes?cursor={cursor1}&limit=2");
    let res = app
        .clone()
        .oneshot(Request::get(uri.as_str()).body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let items = v["items"].as_array().context("items must be array")?;
    assert_eq!(items.len(), 2);
    assert_eq!(items[0]["id"], "n3");
    assert_eq!(items[1]["id"], "n4");
    assert_eq!(v["page"]["has_more"], true);
    let cursor2 = v["page"]["next_cursor"]
        .as_str()
        .context("next_cursor must be present on page 2")?
        .to_string();

    // Page 3 (last): has_more is false and next_cursor is null.
    let uri = format!("/nodes?cursor={cursor2}&limit=2");
    let res = app
        .oneshot(Request::get(uri.as_str()).body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let items = v["items"].as_array().context("items must be array")?;
    assert_eq!(items.len(), 1);
    assert_eq!(items[0]["id"], "n5");
    assert_eq!(v["page"]["has_more"], false);
    assert!(
        v["page"]["next_cursor"].is_null(),
        "last page next_cursor must be null"
    );

    Ok(())
}

#[tokio::test]
#[serial]
async fn nodes_cursor_invalid_is_bad_request() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");
    let (app, _env) = app_with_nodes(
        &in_dir,
        &[r#"{"id":"n1","location":{"lon":9.9,"lat":53.55},"title":"A"}"#],
    )
    .await;

    // A malformed cursor token is a deterministic 400, never silent mis-pagination.
    let res = app
        .oneshot(Request::get("/nodes?cursor=zz").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    Ok(())
}

#[tokio::test]
#[serial]
async fn nodes_cursor_limit_is_clamped_to_max_page_size() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");

    // Zero-padded ids keep lexicographic order aligned with numeric order.
    let lines: Vec<String> = (0..1100)
        .map(|i| {
            format!(r#"{{"id":"n{i:04}","location":{{"lon":10.0,"lat":53.5}},"title":"N{i}"}}"#)
        })
        .collect();
    let line_refs: Vec<&str> = lines.iter().map(String::as_str).collect();
    let (app, _env) = app_with_nodes(&in_dir, &line_refs).await;

    // Even in cursor mode, a limit above MAX_PAGE_SIZE (1000) is clamped.
    let res = app
        .oneshot(Request::get("/nodes?pagination=cursor&limit=5000").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let items = v["items"].as_array().context("items must be array")?;
    assert_eq!(items.len(), 1000);
    assert_eq!(v["page"]["limit"], 1000);
    assert_eq!(v["page"]["has_more"], true);

    Ok(())
}

#[tokio::test]
#[serial]
async fn nodes_cursor_limit_zero_is_bad_request() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");

    let lines = vec![
        r#"{"id":"n1","location":{"lon":10.0,"lat":53.5},"title":"N1"}"#,
        r#"{"id":"n2","location":{"lon":10.0,"lat":53.5},"title":"N2"}"#,
    ];
    let (app, _env) = app_with_nodes(&in_dir, &lines).await;

    // In cursor mode, limit=0 must return 400 Bad Request.
    let res = app
        .oneshot(Request::get("/nodes?pagination=cursor&limit=0").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    Ok(())
}

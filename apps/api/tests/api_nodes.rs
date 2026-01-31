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
use std::{collections::HashMap, fs, path::PathBuf, sync::Arc};
use tower::ServiceExt;
use weltgewebe_api::{
    auth::{role::Role, session::SessionStore},
    config::AppConfig,
    middleware::{auth::auth_middleware, csrf::require_csrf},
    routes::{
        accounts::{AccountInternal, AccountPublic, Visibility},
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

    Ok(ApiState {
        db_pool: None,
        db_pool_configured: false,
        nats_client: None,
        nats_configured: false,
        config: AppConfig {
            fade_days: 7,
            ron_days: 84,
            anonymize_opt_in: true,
            delegation_expire_days: 28,
        },
        metrics,
        sessions: SessionStore::new(),
        tokens: weltgewebe_api::auth::tokens::TokenStore::new(),
        accounts: Arc::new(HashMap::new()),
        nodes: Arc::new(tokio::sync::RwLock::new(
            weltgewebe_api::routes::nodes::load_nodes().await,
        )),
    })
}

fn make_tmp_dir() -> tempfile::TempDir {
    tempfile::tempdir().expect("tmpdir")
}

fn write_lines(path: &PathBuf, lines: &[&str]) {
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(path, lines.join("\n")).unwrap();
}

async fn app() -> Router {
    Router::new()
        .merge(api_router())
        .with_state(test_state().await.unwrap())
}

#[tokio::test]
#[serial]
async fn nodes_bbox_and_limit() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");
    let nodes = in_dir.join("demo.nodes.jsonl");
    let _env = set_gewebe_in_dir(&in_dir);

    write_lines(
        &nodes,
        &[
            r#"{"id":"n1","location":{"lon":9.9,"lat":53.55},"title":"A"}"#,
            r#"{"id":"n2","location":{"lon":11.0,"lat":54.2},"title":"B"}"#,
            r#"{"id":"n3","location":{"lon":10.2,"lat":53.6},"title":"C"}"#,
        ],
    );

    let app = app().await;

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
    let nodes = in_dir.join("demo.nodes.jsonl");
    let _env = set_gewebe_in_dir(&in_dir);

    // Initial node
    write_lines(
        &nodes,
        &[r#"{"id":"n1","location":{"lon":10.0,"lat":53.5},"title":"A","info":"Old Info"}"#],
    );

    // Setup Auth State with Account
    let mut account_map = HashMap::new();
    let account = AccountPublic {
        id: "weber1".to_string(),
        kind: "garnrolle".to_string(),
        title: "Weber".to_string(),
        summary: None,
        public_pos: None,
        visibility: Visibility::Public,
        radius_m: 0,
        ron_flag: false,
        tags: vec![],
    };
    account_map.insert(
        "weber1".to_string(),
        AccountInternal {
            public: account,
            role: Role::Weber,
            email: Some("weber1@example.com".to_string()),
        },
    );

    let mut state = test_state().await?;
    state.accounts = Arc::new(account_map);

    // Create Session
    let session = state.sessions.create("weber1".to_string());
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
async fn nodes_accept_string_coordinates() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");
    let nodes = in_dir.join("demo.nodes.jsonl");
    let _env = set_gewebe_in_dir(&in_dir);

    write_lines(
        &nodes,
        &[r#"{"id":"n1","location":{"lon":"9.9","lat":"53.55"},"title":"A"}"#],
    );

    let app = app().await;

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
    let nodes = in_dir.join("demo.nodes.jsonl");
    let _env = set_gewebe_in_dir(&in_dir);

    write_lines(
        &nodes,
        &[
            r#"{"id":"n1","location":{"lon":9.9,"lat":53.55},"title":"A","created_at":"2024-01-02T03:04:05Z"}"#,
        ],
    );

    let app = app().await;

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
    let mut account_map = HashMap::new();
    let account = AccountPublic {
        id: "weber1".to_string(),
        kind: "garnrolle".to_string(),
        title: "Weber".to_string(),
        summary: None,
        public_pos: None,
        visibility: Visibility::Public,
        radius_m: 0,
        ron_flag: false,
        tags: vec![],
    };
    account_map.insert(
        "weber1".to_string(),
        AccountInternal {
            public: account,
            role: Role::Weber,
            email: Some("weber1@example.com".to_string()),
        },
    );

    let mut state = test_state().await?;
    state.accounts = Arc::new(account_map);

    // Create Session
    let session = state.sessions.create("weber1".to_string());
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

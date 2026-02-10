use anyhow::{Context, Result};
use axum::{
    body,
    http::{Request, StatusCode},
    Router,
};
use serial_test::serial;
mod helpers;

use helpers::set_gewebe_in_dir;
use std::{collections::HashMap, fs, path::PathBuf, sync::Arc};
use tokio::sync::RwLock;
use tower::ServiceExt;
use weltgewebe_api::{
    auth::{rate_limit::AuthRateLimiter, session::SessionStore},
    config::AppConfig,
    routes::api_router,
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
    };

    let rate_limiter = Arc::new(AuthRateLimiter::new(&config));

    // Load edges from file (environment variable must be set before calling this)
    let edges = weltgewebe_api::routes::edges::load_edges().await;

    Ok(ApiState {
        db_pool: None,
        db_pool_configured: false,
        nats_client: None,
        nats_configured: false,
        config,
        metrics,
        sessions: SessionStore::new(),
        tokens: weltgewebe_api::auth::tokens::TokenStore::new(),
        accounts: Arc::new(RwLock::new(HashMap::new())),
        nodes: Arc::new(tokio::sync::RwLock::new(Vec::new())),
        edges: Arc::new(tokio::sync::RwLock::new(edges)),
        rate_limiter,
        mailer: None,
    })
}

fn make_tmp_dir() -> tempfile::TempDir {
    tempfile::tempdir().expect("tmpdir")
}
fn write_lines(path: &PathBuf, lines: &[&str]) {
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(path, lines.join("\n")).unwrap();
}

#[tokio::test]
#[serial]
async fn edges_filter_src_dst() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");
    let edges_path = in_dir.join("demo.edges.jsonl");
    let _env = set_gewebe_in_dir(&in_dir);

    write_lines(
        &edges_path,
        &[
            r#"{"id":"e1","source_id":"n1","target_id":"n2","edge_kind":"reference"}"#,
            r#"{"id":"e2","source_id":"n1","target_id":"n3","edge_kind":"reference"}"#,
            r#"{"id":"e3","source_id":"n2","target_id":"n3","edge_kind":"reference"}"#,
        ],
    );

    let state = test_state().await?;
    let app = Router::new()
        .merge(api_router())
        .with_state(state);

    let res = app
        .clone()
        .oneshot(Request::get("/edges?source_id=n1").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    assert_eq!(v.as_array().context("must be array")?.len(), 2);

    let res = app
        .oneshot(Request::get("/edges?source_id=n1&target_id=n2").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    let arr = v.as_array().context("must be array")?;
    assert_eq!(arr.len(), 1);
    assert_eq!(
        arr[0]
            .get("id")
            .context("id missing")?
            .as_str()
            .context("must be string")?,
        "e1"
    );

    Ok(())
}

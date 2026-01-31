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
use tower::ServiceExt;
use weltgewebe_api::{
    auth::session::SessionStore,
    config::AppConfig,
    routes::api_router,
    state::ApiState,
    telemetry::{BuildInfo, Metrics},
};

fn test_state() -> Result<ApiState> {
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
    })
}

fn make_tmp_dir() -> tempfile::TempDir {
    tempfile::tempdir().expect("tmpdir")
}
fn write_lines(path: &PathBuf, lines: &[&str]) {
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(path, lines.join("\n")).unwrap();
}

fn app() -> Router {
    Router::new()
        .merge(api_router())
        .with_state(test_state().unwrap())
}

#[tokio::test]
#[serial]
async fn edges_filter_src_dst() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");
    let edges = in_dir.join("demo.edges.jsonl");
    let _env = set_gewebe_in_dir(&in_dir);

    write_lines(
        &edges,
        &[
            r#"{"id":"e1","source_id":"n1","target_id":"n2","edge_kind":"reference"}"#,
            r#"{"id":"e2","source_id":"n1","target_id":"n3","edge_kind":"reference"}"#,
            r#"{"id":"e3","source_id":"n2","target_id":"n3","edge_kind":"reference"}"#,
        ],
    );

    let app = app();

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

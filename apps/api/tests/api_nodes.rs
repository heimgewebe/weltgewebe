use anyhow::{Context, Result};
use axum::{
    body,
    http::{Request, StatusCode},
    Router,
};
use std::{fs, path::PathBuf};
use tower::ServiceExt;
use weltgewebe_api::{
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
        .nest("/api", api_router())
        .with_state(test_state().unwrap())
}

#[tokio::test]
async fn nodes_bbox_and_limit() -> anyhow::Result<()> {
    let tmp = make_tmp_dir();
    let in_dir = tmp.path().join("in");
    let nodes = in_dir.join("demo.nodes.jsonl");
    std::env::set_var("GEWEBE_IN_DIR", &in_dir);

    write_lines(
        &nodes,
        &[
            r#"{"id":"n1","location":{"lon":9.9,"lat":53.55},"title":"A"}"#,
            r#"{"id":"n2","location":{"lon":11.0,"lat":54.2},"title":"B"}"#,
            r#"{"id":"n3","location":{"lon":10.2,"lat":53.6},"title":"C"}"#,
        ],
    );

    let app = app();

    // BBox über Hamburg herum (soll n1 & n3 treffen)
    let res = app
        .clone()
        .oneshot(
            Request::get("/api/nodes?bbox=9.5,53.4,10.5,53.8&limit=10").body(body::Body::empty())?,
        )
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
        .oneshot(
            Request::get("/api/nodes?bbox=10.5,53.8,9.5,53.4&limit=10").body(body::Body::empty())?,
        )
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
        .oneshot(Request::get("/api/nodes?bbox=oops").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::BAD_REQUEST);

    // Limit=1
    let res = app
        .oneshot(Request::get("/api/nodes?limit=1").body(body::Body::empty())?)
        .await?;
    assert_eq!(res.status(), StatusCode::OK);
    let body = body::to_bytes(res.into_body(), usize::MAX).await?;
    let v: serde_json::Value = serde_json::from_slice(&body)?;
    assert_eq!(v.as_array().context("must be array")?.len(), 1);

    Ok(())
}

use std::{env, fs, path::{Path, PathBuf}};

use axum::{
    extract::State,
    http::{header, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    routing::get,
    Json, Router,
};
use serde_json::json;
use sqlx::query_scalar;

use crate::{
    state::ApiState,
    telemetry::health::{readiness_check_failed, readiness_checks_succeeded},
};

pub fn health_routes() -> Router<ApiState> {
    Router::new()
        .route("/health/live", get(live))
        .route("/health/ready", get(ready))
}

async fn live() -> Response {
    let body = Json(json!({ "status": "ok" }));
    let mut response = body.into_response();
    response
        .headers_mut()
        .insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));
    response
}

async fn ready(State(state): State<ApiState>) -> Response {
    let nats_ready = if state.nats_configured {
        match state.nats_client.as_ref() {
            Some(client) => match client.flush().await {
                Ok(_) => true,
                Err(error) => {
                    readiness_check_failed("nats", &error);
                    false
                }
            },
            None => false,
        }
    } else {
        true
    };

    let database_ready = if state.db_pool_configured {
        match state.db_pool.as_ref() {
            Some(pool) => match query_scalar::<_, i32>("SELECT 1")
                .fetch_optional(pool)
                .await
            {
                Ok(_) => true,
                Err(error) => {
                    readiness_check_failed("database", &error);
                    false
                }
            },
            None => false,
        }
    } else {
        true
    };

    // Prefer an explicit configuration via env var to avoid hard-coded path assumptions.
    // Fallbacks stay for dev/CI convenience.
    let env_path = env::var_os("POLICY_LIMITS_PATH").map(PathBuf::from);
    let fallback_paths = [
        Path::new("policies/limits.yaml").to_path_buf(),
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies/limits.yaml"),
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../policies/limits.yaml"),
    ];
    let policy_ready = env_path
        .into_iter()
        .chain(fallback_paths)
        .find(|p| p.exists())
        .and_then(|p| fs::read_to_string(p).ok())
        .is_some();

    let status = if database_ready && nats_ready && policy_ready {
        StatusCode::OK
    } else {
        StatusCode::SERVICE_UNAVAILABLE
    };

    if status == StatusCode::OK {
        readiness_checks_succeeded();
    }

    let body = Json(json!({
        "status": if status == StatusCode::OK { "ok" } else { "error" },
        "checks": {
            "database": database_ready,
            "nats": nats_ready,
            "policy": policy_ready,
        }
    }));

    let mut response = body.into_response();
    *response.status_mut() = status;
    response
        .headers_mut()
        .insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));
    response
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        config::AppConfig,
        telemetry::{BuildInfo, Metrics},
    };
    use anyhow::Result;
    use axum::{body, extract::State, http::header};
    use serde_json::Value;

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

    #[tokio::test]
    async fn live_returns_ok_status_and_no_store_header() -> Result<()> {
        let response = live().await;
        let status = response.status();
        let cache_control = response.headers().get(header::CACHE_CONTROL).cloned();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::OK);
        assert_eq!(
            cache_control.as_ref().and_then(|value| value.to_str().ok()),
            Some("no-store")
        );
        assert_eq!(body["status"], "ok");

        Ok(())
    }

    #[tokio::test]
    async fn readiness_succeeds_when_optional_dependencies_are_disabled() -> Result<()> {
        let state = test_state()?;

        let response = ready(State(state)).await;
        let status = response.status();
        let cache_control = response.headers().get(header::CACHE_CONTROL).cloned();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::OK);
        assert_eq!(
            cache_control.as_ref().and_then(|value| value.to_str().ok()),
            Some("no-store")
        );
        assert_eq!(body["status"], "ok");
        assert_eq!(body["checks"]["database"], true);
        assert_eq!(body["checks"]["nats"], true);
        assert_eq!(body["checks"]["policy"], true);

        Ok(())
    }
}

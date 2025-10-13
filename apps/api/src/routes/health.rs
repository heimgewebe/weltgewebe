use std::{
    env, fs,
    path::{Path, PathBuf},
};

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

fn check_policy_file(path: &Path) -> Result<(), String> {
    match fs::read_to_string(path) {
        Ok(_) => Ok(()),
        Err(error) => {
            let message = format!(
                "failed to read policy file at {}: {}",
                path.display(),
                error
            );
            readiness_check_failed("policy", &message);
            Err(message)
        }
    }
}

fn check_policy_fallbacks(paths: &[PathBuf]) -> bool {
    let mut errors = Vec::new();
    for path in paths {
        if check_policy_file(path).is_ok() {
            return true;
        }
        errors.push(path.display().to_string());
    }

    let message = format!(
        "no policy file found in fallback locations: {}",
        errors.join(", ")
    );
    readiness_check_failed("policy", &message);
    false
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
            None => {
                readiness_check_failed("nats", "client not initialised");
                false
            }
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
            None => {
                readiness_check_failed("database", "connection pool not initialised");
                false
            }
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
    let policy_ready = if let Some(path) = env_path {
        check_policy_file(&path).is_ok()
    } else {
        check_policy_fallbacks(&fallback_paths)
    };

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
        test_helpers::EnvGuard,
    };
    use anyhow::Result;
    use axum::{body, extract::State, http::header};
    use serde_json::Value;
    use serial_test::serial;

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
    #[serial]
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
    #[serial]
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

    #[tokio::test]
    #[serial]
    async fn readiness_fails_when_policy_path_is_invalid() -> Result<()> {
        let _policy = EnvGuard::set("POLICY_LIMITS_PATH", "/does/not/exist");
        let state = test_state()?;

        let response = ready(State(state)).await;
        let status = response.status();
        let cache_control = response.headers().get(header::CACHE_CONTROL).cloned();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(
            cache_control.as_ref().and_then(|value| value.to_str().ok()),
            Some("no-store")
        );
        assert_eq!(body["status"], "error");
        assert_eq!(body["checks"]["database"], true);
        assert_eq!(body["checks"]["nats"], true);
        assert_eq!(body["checks"]["policy"], false);

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_fails_when_database_pool_missing() -> Result<()> {
        let mut state = test_state()?;
        state.db_pool_configured = true;

        let response = ready(State(state)).await;
        let status = response.status();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(body["checks"]["database"], false);
        assert_eq!(body["checks"]["nats"], true);
        assert_eq!(body["checks"]["policy"], true);

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_fails_when_nats_client_missing() -> Result<()> {
        let mut state = test_state()?;
        state.nats_configured = true;

        let response = ready(State(state)).await;
        let status = response.status();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(body["checks"]["database"], true);
        assert_eq!(body["checks"]["nats"], false);
        assert_eq!(body["checks"]["policy"], true);

        Ok(())
    }
}

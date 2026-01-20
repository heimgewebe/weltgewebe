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
use serde_json::{json, Map};
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

#[derive(Debug, Default, Clone, Copy)]
enum CheckStatus {
    #[default]
    Ready,
    Skipped,
    Failed,
}

#[derive(Debug, Default)]
struct CheckResult {
    status: CheckStatus,
    errors: Vec<String>,
}

impl CheckResult {
    fn ready() -> Self {
        Self {
            status: CheckStatus::Ready,
            errors: Vec::new(),
        }
    }

    fn skipped() -> Self {
        Self {
            status: CheckStatus::Skipped,
            errors: Vec::new(),
        }
    }

    fn failure(errors: Vec<String>) -> Self {
        Self {
            status: CheckStatus::Failed,
            errors,
        }
    }

    fn failure_with_message(message: String) -> Self {
        Self::failure(vec![message])
    }
}

fn readiness_verbose() -> bool {
    env::var("READINESS_VERBOSE")
        .map(|value| {
            let trimmed = value.trim();
            trimmed == "1" || trimmed.eq_ignore_ascii_case("true")
        })
        .unwrap_or(false)
}

fn check_policy_file(path: &Path) -> Result<(), String> {
    fs::read_to_string(path).map(|_| ()).map_err(|error| {
        format!(
            "failed to read policy file at {}: {}",
            path.display(),
            error
        )
    })
}

fn check_policy_fallbacks(paths: &[PathBuf]) -> CheckResult {
    let mut errors = Vec::new();
    for path in paths {
        match check_policy_file(path) {
            Ok(()) => return CheckResult::ready(),
            Err(message) => errors.push(message),
        }
    }

    if !errors.is_empty() {
        for error in &errors {
            readiness_check_failed("policy", error);
        }

        let message = format!(
            "no policy file found in fallback locations: {}",
            paths
                .iter()
                .map(|path| path.display().to_string())
                .collect::<Vec<_>>()
                .join(", ")
        );
        readiness_check_failed("policy", &message);
        errors.push(message);
    }

    CheckResult::failure(errors)
}

async fn check_nats(state: &ApiState) -> CheckResult {
    if !state.nats_configured {
        return CheckResult::skipped();
    }

    match state.nats_client.as_ref() {
        Some(client) => match client.flush().await {
            Ok(_) => CheckResult::ready(),
            Err(error) => {
                let message = error.to_string();
                readiness_check_failed("nats", &message);
                CheckResult::failure_with_message(message)
            }
        },
        None => {
            let message = "client not initialised".to_string();
            readiness_check_failed("nats", &message);
            CheckResult::failure_with_message(message)
        }
    }
}

async fn check_database(state: &ApiState) -> CheckResult {
    if !state.db_pool_configured {
        return CheckResult::skipped();
    }

    match state.db_pool.as_ref() {
        Some(pool) => match query_scalar::<_, i32>("SELECT 1")
            .fetch_optional(pool)
            .await
        {
            Ok(_) => CheckResult::ready(),
            Err(error) => {
                let message = error.to_string();
                readiness_check_failed("database", &message);
                CheckResult::failure_with_message(message)
            }
        },
        None => {
            let message = "connection pool not initialised".to_string();
            readiness_check_failed("database", &message);
            CheckResult::failure_with_message(message)
        }
    }
}

fn check_policy() -> CheckResult {
    // Prefer an explicit configuration via env var to avoid hard-coded path assumptions.
    // Fallbacks stay for dev/CI convenience.
    let env_path = env::var_os("POLICY_LIMITS_PATH").map(PathBuf::from);
    let fallback_paths = [
        Path::new("policies/limits.yaml").to_path_buf(),
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies/limits.yaml"),
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../policies/limits.yaml"),
    ];

    if let Some(path) = env_path {
        match check_policy_file(&path) {
            Ok(()) => CheckResult::ready(),
            Err(message) => {
                readiness_check_failed("policy", &message);
                CheckResult::failure_with_message(message)
            }
        }
    } else {
        check_policy_fallbacks(&fallback_paths)
    }
}

async fn ready(State(state): State<ApiState>) -> Response {
    let nats = check_nats(&state).await;
    let database = check_database(&state).await;
    let policy = check_policy();

    let status = if matches!(database.status, CheckStatus::Failed)
        || matches!(nats.status, CheckStatus::Failed)
        || matches!(policy.status, CheckStatus::Failed)
    {
        StatusCode::SERVICE_UNAVAILABLE
    } else {
        StatusCode::OK
    };

    if status == StatusCode::OK {
        readiness_checks_succeeded();
    }

    let verbose = readiness_verbose();

    let body = Json(json!({
        "status": if status == StatusCode::OK { "ok" } else { "error" },
        "checks": {
            "database": matches!(database.status, CheckStatus::Ready),
            "nats": matches!(nats.status, CheckStatus::Ready),
            "policy": matches!(policy.status, CheckStatus::Ready),
        }
    }));

    let mut value = body.0;

    if verbose {
        let mut errors = Map::new();

        if !database.errors.is_empty() {
            errors.insert("database".to_string(), json!(database.errors));
        }

        if !nats.errors.is_empty() {
            errors.insert("nats".to_string(), json!(nats.errors));
        }

        if !policy.errors.is_empty() {
            errors.insert("policy".to_string(), json!(policy.errors));
        }

        if !errors.is_empty() {
            if let Some(object) = value.as_object_mut() {
                object.insert("errors".to_string(), json!(errors));
            }
        }
    }

    let mut response = Json(value).into_response();
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
        auth::session::SessionStore,
        config::AppConfig,
        telemetry::{BuildInfo, Metrics},
        test_helpers::EnvGuard,
    };
    use anyhow::Result;
    use axum::{body, extract::State, http::header};
    use serde_json::Value;
    use serial_test::serial;
    use std::{collections::HashMap, sync::Arc};

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
            accounts: Arc::new(HashMap::new()),
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
        assert_eq!(body["checks"]["database"], false);
        assert_eq!(body["checks"]["nats"], false);
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
        assert_eq!(body["checks"]["database"], false);
        assert_eq!(body["checks"]["nats"], false);
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
        assert_eq!(body["checks"]["nats"], false);
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
        assert_eq!(body["checks"]["database"], false);
        assert_eq!(body["checks"]["nats"], false);
        assert_eq!(body["checks"]["policy"], true);

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_includes_error_details_when_verbose_enabled() -> Result<()> {
        let _policy = EnvGuard::set("POLICY_LIMITS_PATH", "/does/not/exist");
        let _verbose = EnvGuard::set("READINESS_VERBOSE", "1");
        let state = test_state()?;

        let response = ready(State(state)).await;
        let status = response.status();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(body["checks"]["policy"], false);

        let errors = body["errors"]["policy"].as_array().expect("policy errors");
        assert!(!errors.is_empty());
        assert!(errors
            .iter()
            .filter_map(|value| value.as_str())
            .any(|message| message.contains("failed to read policy file")));

        Ok(())
    }
}

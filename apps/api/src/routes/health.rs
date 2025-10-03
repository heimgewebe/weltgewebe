use axum::{
    extract::State,
    http::{header, HeaderMap, HeaderValue, StatusCode},
    response::IntoResponse,
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        config::AppConfig,
        telemetry::{BuildInfo, Metrics},
    };
    use anyhow::Result;
    use axum::extract::State;
    use axum::Json;

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
    async fn readiness_succeeds_when_optional_dependencies_are_disabled() -> Result<()> {
        let state = test_state()?;

        let (status, _headers, Json(body)) = ready(State(state)).await;

        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["status"], "ok");
        assert_eq!(body["checks"]["database"], true);
        assert_eq!(body["checks"]["nats"], true);

        Ok(())
    }
}

async fn live() -> impl IntoResponse {
    let mut headers = HeaderMap::new();
    headers.insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));

    (StatusCode::OK, headers, Json(json!({ "status": "ok" })))
}

async fn ready(State(state): State<ApiState>) -> impl IntoResponse {
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

    let status = if database_ready && nats_ready {
        StatusCode::OK
    } else {
        StatusCode::SERVICE_UNAVAILABLE
    };

    if status == StatusCode::OK {
        readiness_checks_succeeded();
    }

    let mut headers = HeaderMap::new();
    headers.insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));

    (
        status,
        headers,
        Json(json!({
            "status": if status == StatusCode::OK { "ok" } else { "error" },
            "checks": {
                "database": database_ready,
                "nats": nats_ready,
            }
        })),
    )
}

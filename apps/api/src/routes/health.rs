use axum::{
    extract::State,
    http::{header, StatusCode},
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

async fn live() -> impl IntoResponse {
    (
        StatusCode::OK,
        [(header::CACHE_CONTROL, "no-store")],
        Json(json!({ "status": "ok" })),
    )
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

    (
        status,
        [(header::CACHE_CONTROL, "no-store")],
        Json(json!({
            "status": if status == StatusCode::OK { "ok" } else { "error" },
            "checks": {
                "database": database_ready,
                "nats": nats_ready,
            }
        })),
    )
}

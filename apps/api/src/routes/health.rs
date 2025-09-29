use axum::{extract::State, http::StatusCode, routing::get, Router};
use sqlx::query;

use crate::state::ApiState;

pub fn health_routes() -> Router<ApiState> {
    Router::new()
        .route("/health/live", get(live))
        .route("/health/ready", get(ready))
}

async fn live() -> StatusCode {
    StatusCode::OK
}

async fn ready(State(state): State<ApiState>) -> StatusCode {
    let nats_ready = if state.nats_configured {
        match state.nats_client.as_ref() {
            Some(client) => match client.flush().await {
                Ok(_) => true,
                Err(error) => {
                    tracing::warn!(error = %error, "nats health check failed");
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
            Some(pool) => match query("SELECT 1").execute(pool).await {
                Ok(_) => true,
                Err(error) => {
                    tracing::warn!(error = %error, "database health check failed");
                    false
                }
            },
            None => false,
        }
    } else {
        true
    };

    if database_ready && nats_ready {
        StatusCode::OK
    } else {
        StatusCode::SERVICE_UNAVAILABLE
    }
}

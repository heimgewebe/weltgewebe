use axum::{extract::State, http::StatusCode, routing::get, Router};

use crate::state::ApiState;

pub fn health_routes() -> Router<ApiState> {
    Router::new()
        .route("/health/live", get(live))
        .route("/health/ready", get(ready))
}

async fn live(State(state): State<ApiState>) -> StatusCode {
    state
        .metrics
        .http_requests_total()
        .with_label_values(&["GET", "/health/live"])
        .inc();

    StatusCode::OK
}

async fn ready(State(state): State<ApiState>) -> StatusCode {
    let database_ready = match &state.db_pool {
        Some(pool) => match pool.acquire().await {
            Ok(connection) => {
                drop(connection);
                true
            }
            Err(error) => {
                tracing::warn!(error = %error, "database health check failed");
                false
            }
        },
        None => true,
    };

    let nats_ready = if database_ready {
        match &state.nats_client {
            Some(client) => match client.flush().await {
                Ok(_) => true,
                Err(error) => {
                    tracing::warn!(error = %error, "nats health check failed");
                    false
                }
            },
            None => true,
        }
    } else {
        false
    };

    state
        .metrics
        .http_requests_total()
        .with_label_values(&["GET", "/health/ready"])
        .inc();

    if database_ready && nats_ready {
        StatusCode::OK
    } else {
        StatusCode::SERVICE_UNAVAILABLE
    }
}

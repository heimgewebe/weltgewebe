use axum::{extract::State, http::StatusCode, routing::get, Router};

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
    let nats_ready = match &state.nats_client {
        Some(client) => match client.flush().await {
            Ok(_) => true,
            Err(error) => {
                tracing::warn!(error = %error, "nats health check failed");
                false
            }
        },
        None => true,
    };

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

    if database_ready && nats_ready {
        StatusCode::OK
    } else {
        StatusCode::SERVICE_UNAVAILABLE
    }
}

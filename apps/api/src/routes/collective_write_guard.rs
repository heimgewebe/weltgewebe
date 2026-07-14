use std::sync::OnceLock;

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::{IntoResponse, Response},
    Extension, Json,
};
use serde_json::Value;
use sqlx::{Postgres, Transaction};
use tokio::sync::{Mutex, MutexGuard};

use crate::{
    config::{DomainEdgeWriteSource, DomainNodeWriteSource},
    middleware::auth::AuthContext,
    state::ApiState,
};

use super::{edges, nodes};

// Stable database-wide lock identity for graph mutations that must not cross:
// creating a new edge and deleting a node together with all of its edges.
const COLLECTIVE_GRAPH_LOCK_KEY: i64 = 0x5747_434F_4C4C_4543;
static JSONL_COLLECTIVE_GRAPH_LOCK: OnceLock<Mutex<()>> = OnceLock::new();

enum CollectiveGraphGuard {
    Jsonl(MutexGuard<'static, ()>),
    Postgres(Transaction<'static, Postgres>),
}

fn jsonl_collective_graph_lock() -> &'static Mutex<()> {
    JSONL_COLLECTIVE_GRAPH_LOCK.get_or_init(|| Mutex::new(()))
}

async fn acquire_collective_graph_guard(
    state: &ApiState,
) -> Result<CollectiveGraphGuard, Response> {
    let postgres_graph = matches!(
        (
            state.config.domain_node_write_source,
            state.config.domain_edge_write_source,
        ),
        (
            DomainNodeWriteSource::Postgres,
            DomainEdgeWriteSource::Postgres,
        )
    );

    if !postgres_graph {
        return Ok(CollectiveGraphGuard::Jsonl(
            jsonl_collective_graph_lock().lock().await,
        ));
    }

    let pool = state.db_pool.as_ref().ok_or_else(|| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            "PostgreSQL pool unavailable for collective graph write",
        )
            .into_response()
    })?;
    let mut transaction = pool.begin().await.map_err(|error| {
        tracing::error!(%error, "failed to begin collective graph guard transaction");
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            "failed to acquire collective graph write guard",
        )
            .into_response()
    })?;
    sqlx::query("SELECT pg_advisory_xact_lock($1)")
        .bind(COLLECTIVE_GRAPH_LOCK_KEY)
        .execute(&mut *transaction)
        .await
        .map_err(|error| {
            tracing::error!(%error, "failed to acquire collective graph advisory lock");
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                "failed to acquire collective graph write guard",
            )
                .into_response()
        })?;

    Ok(CollectiveGraphGuard::Postgres(transaction))
}

async fn release_collective_graph_guard(guard: CollectiveGraphGuard) -> Result<(), Response> {
    match guard {
        CollectiveGraphGuard::Jsonl(_guard) => Ok(()),
        CollectiveGraphGuard::Postgres(transaction) => {
            transaction.commit().await.map_err(|error| {
                tracing::error!(%error, "failed to release collective graph advisory lock");
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "failed to release collective graph write guard",
                )
                    .into_response()
            })
        }
    }
}

pub async fn create_edge_serialized(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
    Json(payload): Json<Value>,
) -> Response {
    let guard = match acquire_collective_graph_guard(&state).await {
        Ok(guard) => guard,
        Err(response) => return response,
    };
    let response = edges::create_edge(State(state), Extension(auth), Json(payload))
        .await
        .into_response();
    match release_collective_graph_guard(guard).await {
        Ok(()) => response,
        Err(response) => response,
    }
}

pub async fn delete_node_serialized(
    State(state): State<ApiState>,
    Path(id): Path<String>,
) -> Response {
    let guard = match acquire_collective_graph_guard(&state).await {
        Ok(guard) => guard,
        Err(response) => return response,
    };
    let response = nodes::delete_node(State(state), Path(id))
        .await
        .into_response();
    match release_collective_graph_guard(guard).await {
        Ok(()) => response,
        Err(response) => response,
    }
}

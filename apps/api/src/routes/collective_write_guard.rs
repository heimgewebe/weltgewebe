use std::{future::Future, sync::OnceLock};

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
    config::{DomainEdgeWriteSource, DomainNodeWriteSource, DomainReadSource},
    middleware::auth::AuthContext,
    state::ApiState,
};

use super::{edges, nodes};

// Stable database-wide lock identity for shared node/edge mutations. Every API
// instance first queues mutations locally; PostgreSQL instances then coordinate
// across processes with the same advisory-lock identity.
const COLLECTIVE_GRAPH_LOCK_KEY: i64 = 0x5747_434F_4C4C_4543;
static LOCAL_COLLECTIVE_GRAPH_LOCK: OnceLock<Mutex<()>> = OnceLock::new();

#[derive(Clone, Copy)]
enum GraphMutationScope {
    Node,
    Edge,
    Cascade,
}

enum PersistenceLockKind {
    None,
    Jsonl,
    Postgres,
}

enum CollectiveGraphGuard {
    None,
    Local {
        _guard: MutexGuard<'static, ()>,
    },
    Postgres {
        _guard: MutexGuard<'static, ()>,
        transaction: Transaction<'static, Postgres>,
    },
}

fn local_collective_graph_lock() -> &'static Mutex<()> {
    LOCAL_COLLECTIVE_GRAPH_LOCK.get_or_init(|| Mutex::new(()))
}

fn persistence_lock_kind(state: &ApiState, scope: GraphMutationScope) -> PersistenceLockKind {
    match (
        scope,
        state.config.domain_read_source,
        state.config.domain_node_write_source,
        state.config.domain_edge_write_source,
    ) {
        (GraphMutationScope::Node, DomainReadSource::Jsonl, DomainNodeWriteSource::Jsonl, _)
        | (GraphMutationScope::Edge, DomainReadSource::Jsonl, _, DomainEdgeWriteSource::Jsonl)
        | (
            GraphMutationScope::Cascade,
            DomainReadSource::Jsonl,
            DomainNodeWriteSource::Jsonl,
            DomainEdgeWriteSource::Jsonl,
        ) => PersistenceLockKind::Jsonl,
        (
            GraphMutationScope::Node,
            DomainReadSource::Postgres,
            DomainNodeWriteSource::Postgres,
            _,
        )
        | (
            GraphMutationScope::Edge,
            DomainReadSource::Postgres,
            _,
            DomainEdgeWriteSource::Postgres,
        )
        | (
            GraphMutationScope::Cascade,
            DomainReadSource::Postgres,
            DomainNodeWriteSource::Postgres,
            DomainEdgeWriteSource::Postgres,
        ) => PersistenceLockKind::Postgres,
        // The route-level write guards return the precise 409/500 contract for
        // mixed or otherwise invalid source combinations. Do not mask it here.
        _ => PersistenceLockKind::None,
    }
}

async fn acquire_collective_graph_guard(
    state: &ApiState,
    scope: GraphMutationScope,
) -> Result<CollectiveGraphGuard, Response> {
    match persistence_lock_kind(state, scope) {
        PersistenceLockKind::None => Ok(CollectiveGraphGuard::None),
        PersistenceLockKind::Jsonl => Ok(CollectiveGraphGuard::Local {
            _guard: local_collective_graph_lock().lock().await,
        }),
        PersistenceLockKind::Postgres => {
            // Queue before borrowing a pool connection. Otherwise several local
            // waiters could occupy the whole pool while only one holds the
            // database advisory lock and the active handler needs another
            // connection for its actual mutation.
            let guard = local_collective_graph_lock().lock().await;
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
            Ok(CollectiveGraphGuard::Postgres {
                _guard: guard,
                transaction,
            })
        }
    }
}

async fn release_collective_graph_guard(guard: CollectiveGraphGuard) -> Result<(), Response> {
    match guard {
        CollectiveGraphGuard::None | CollectiveGraphGuard::Local { .. } => Ok(()),
        CollectiveGraphGuard::Postgres {
            _guard,
            transaction,
        } => transaction.commit().await.map_err(|error| {
            tracing::error!(%error, "failed to release collective graph advisory lock");
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                "failed to release collective graph write guard",
            )
                .into_response()
        }),
    }
}

async fn run_collective_graph_mutation<F>(
    state: &ApiState,
    scope: GraphMutationScope,
    mutation: F,
) -> Response
where
    F: Future<Output = Response>,
{
    let guard = match acquire_collective_graph_guard(state, scope).await {
        Ok(guard) => guard,
        Err(response) => return response,
    };
    let response = mutation.await;
    match release_collective_graph_guard(guard).await {
        Ok(()) => response,
        Err(response) => response,
    }
}

pub async fn create_node_serialized(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
    Json(payload): Json<Value>,
) -> Response {
    let mutation_state = state.clone();
    run_collective_graph_mutation(&state, GraphMutationScope::Node, async move {
        nodes::create_node(State(mutation_state), Extension(auth), Json(payload))
            .await
            .into_response()
    })
    .await
}

pub async fn patch_node_serialized(
    State(state): State<ApiState>,
    Path(id): Path<String>,
    Json(payload): Json<nodes::UpdateNode>,
) -> Response {
    let mutation_state = state.clone();
    run_collective_graph_mutation(&state, GraphMutationScope::Node, async move {
        nodes::patch_node(State(mutation_state), Path(id), Json(payload))
            .await
            .into_response()
    })
    .await
}

pub async fn replace_node_serialized(
    State(state): State<ApiState>,
    Path(id): Path<String>,
    Json(payload): Json<Value>,
) -> Response {
    let mutation_state = state.clone();
    run_collective_graph_mutation(&state, GraphMutationScope::Node, async move {
        nodes::replace_node(State(mutation_state), Path(id), Json(payload))
            .await
            .into_response()
    })
    .await
}

pub async fn delete_node_serialized(
    State(state): State<ApiState>,
    Path(id): Path<String>,
) -> Response {
    let mutation_state = state.clone();
    run_collective_graph_mutation(&state, GraphMutationScope::Cascade, async move {
        nodes::delete_node(State(mutation_state), Path(id))
            .await
            .into_response()
    })
    .await
}

pub async fn create_edge_serialized(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
    Json(payload): Json<Value>,
) -> Response {
    let mutation_state = state.clone();
    run_collective_graph_mutation(&state, GraphMutationScope::Edge, async move {
        edges::create_edge(State(mutation_state), Extension(auth), Json(payload))
            .await
            .into_response()
    })
    .await
}

pub async fn patch_edge_serialized(
    State(state): State<ApiState>,
    Path(id): Path<String>,
    Json(payload): Json<Value>,
) -> Response {
    let mutation_state = state.clone();
    run_collective_graph_mutation(&state, GraphMutationScope::Edge, async move {
        edges::patch_edge(State(mutation_state), Path(id), Json(payload))
            .await
            .into_response()
    })
    .await
}

pub async fn delete_edge_serialized(
    State(state): State<ApiState>,
    Path(id): Path<String>,
) -> Response {
    let mutation_state = state.clone();
    run_collective_graph_mutation(&state, GraphMutationScope::Edge, async move {
        edges::delete_edge(State(mutation_state), Path(id))
            .await
            .into_response()
    })
    .await
}

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
    config::{DomainNodeWriteSource, DomainReadSource},
    middleware::auth::AuthContext,
    state::ApiState,
};

use super::nodes;

// PostgreSQL node mutations are serialized per node id across API instances.
// A bounded process-local stripe queue prevents same-node waiters from occupying
// the connection pool while the first request owns the database advisory lock.
// Different node ids can proceed concurrently; rare stripe collisions only
// reduce local parallelism and never weaken correctness.
const NODE_MUTATION_LOCK_NAMESPACE: &str = "weltgewebe:node-mutation:v1";
const LOCAL_NODE_LOCK_STRIPES: usize = 64;
static LOCAL_NODE_LOCKS: OnceLock<Vec<Mutex<()>>> = OnceLock::new();

enum NodeMutationGuard {
    None,
    Postgres {
        _guard: MutexGuard<'static, ()>,
        transaction: Transaction<'static, Postgres>,
    },
}

fn local_node_locks() -> &'static [Mutex<()>] {
    LOCAL_NODE_LOCKS
        .get_or_init(|| {
            (0..LOCAL_NODE_LOCK_STRIPES)
                .map(|_| Mutex::new(()))
                .collect()
        })
        .as_slice()
}

fn node_mutation_lock_key(node_id: &str) -> i64 {
    crate::advisory_lock::stable_advisory_lock_key(NODE_MUTATION_LOCK_NAMESPACE, &[node_id])
}

fn local_node_lock_index(node_id: &str) -> usize {
    (node_mutation_lock_key(node_id) as u64 as usize) % LOCAL_NODE_LOCK_STRIPES
}

fn local_node_lock(node_id: &str) -> &'static Mutex<()> {
    &local_node_locks()[local_node_lock_index(node_id)]
}

fn uses_postgres_node_persistence(state: &ApiState) -> bool {
    state.config.domain_read_source == DomainReadSource::Postgres
        && state.config.domain_node_write_source == DomainNodeWriteSource::Postgres
}

async fn acquire_node_mutation_guard(
    state: &ApiState,
    node_id: &str,
) -> Result<NodeMutationGuard, Response> {
    // JSONL handlers already serialize their whole-file writes through
    // `state.nodes_persist`; adding another global lock would only duplicate
    // contention. PostgreSQL creates use server-generated ids and their own
    // idempotency/uniqueness transaction, so only existing-node mutations need
    // this cross-instance guard.
    if !uses_postgres_node_persistence(state) {
        return Ok(NodeMutationGuard::None);
    }

    let guard = local_node_lock(node_id).lock().await;
    let pool = state.db_pool.as_ref().ok_or_else(|| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            "PostgreSQL pool unavailable for collective node write",
        )
            .into_response()
    })?;
    let mut transaction = pool.begin().await.map_err(|error| {
        tracing::error!(%error, node_id, "failed to begin collective node guard transaction");
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            "failed to acquire collective node write guard",
        )
            .into_response()
    })?;
    // Hash in application code and call only PostgreSQL's documented bigint
    // advisory-lock API. This avoids depending on backend hash support
    // functions whose availability may differ across PostgreSQL-compatible
    // managed services.
    sqlx::query("SELECT pg_advisory_xact_lock($1::bigint)")
        .bind(node_mutation_lock_key(node_id))
        .execute(&mut *transaction)
        .await
        .map_err(|error| {
            tracing::error!(%error, node_id, "failed to acquire per-node advisory lock");
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                "failed to acquire collective node write guard",
            )
                .into_response()
        })?;

    Ok(NodeMutationGuard::Postgres {
        _guard: guard,
        transaction,
    })
}

async fn release_node_mutation_guard(guard: NodeMutationGuard) {
    match guard {
        NodeMutationGuard::None => {}
        NodeMutationGuard::Postgres {
            _guard,
            transaction,
        } => {
            if let Err(error) = transaction.commit().await {
                tracing::error!(
                    %error,
                    "failed to release per-node advisory lock after mutation response was produced"
                );
            }
        }
    }
}

async fn run_node_mutation<F>(state: &ApiState, node_id: &str, mutation: F) -> Response
where
    F: Future<Output = Response>,
{
    let guard = match acquire_node_mutation_guard(state, node_id).await {
        Ok(guard) => guard,
        Err(response) => return response,
    };
    let response = mutation.await;
    release_node_mutation_guard(guard).await;
    response
}

pub async fn create_node_serialized(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
    Json(payload): Json<Value>,
) -> Response {
    nodes::create_node(State(state), Extension(auth), Json(payload))
        .await
        .into_response()
}

pub async fn patch_node_serialized(
    State(state): State<ApiState>,
    Path(id): Path<String>,
    Json(payload): Json<nodes::UpdateNode>,
) -> Response {
    let mutation_state = state.clone();
    let mutation_id = id.clone();
    run_node_mutation(&state, &id, async move {
        nodes::patch_node(State(mutation_state), Path(mutation_id), Json(payload))
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
    let mutation_id = id.clone();
    run_node_mutation(&state, &id, async move {
        nodes::replace_node(State(mutation_state), Path(mutation_id), Json(payload))
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
    let mutation_id = id.clone();
    run_node_mutation(&state, &id, async move {
        nodes::delete_node(State(mutation_state), Path(mutation_id))
            .await
            .into_response()
    })
    .await
}

#[cfg(test)]
mod tests {
    use std::collections::HashSet;

    use super::*;

    #[test]
    fn node_lock_keys_and_stripes_are_stable_per_id_and_not_global() {
        assert_eq!(
            node_mutation_lock_key("node-stable"),
            2_204_785_427_200_031_019
        );
        assert_eq!(
            local_node_lock_index("node-stable"),
            local_node_lock_index("node-stable")
        );

        let stripes: HashSet<_> = (0..128)
            .map(|index| local_node_lock_index(&format!("node-{index}")))
            .collect();
        assert!(
            stripes.len() > 1,
            "different node ids must not all share one process-local lock"
        );
    }
}

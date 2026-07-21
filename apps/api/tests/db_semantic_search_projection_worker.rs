//! Direct disposable-PostgreSQL proof for T005's leased projection worker.
//!
//! Run with `T005_DATABASE_URL`; it never starts the API or exposes search.

use std::{
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
};

use async_trait::async_trait;
use sqlx::{postgres::PgPoolOptions, PgPool};
use weltgewebe_api::{
    search::{
        EmbeddingProvider, EmbeddingProviderError, GenerationSpec, ProcessOutcome, ProjectionWorker,
    },
    telemetry::{BuildInfo, Metrics},
};

const TEST_REVISION: &str =
    "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

fn generation_id(model_id: &str, dimension: i32) -> String {
    GenerationSpec {
        generation_id: "derive-only",
        provider: "local:ollama",
        model_id,
        model_revision: TEST_REVISION,
        runtime_identity: "ollama:test@http://127.0.0.1:11434",
        dimension,
    }
    .derived_id()
}

async fn pool() -> PgPool {
    let url = std::env::var("T005_DATABASE_URL")
        .expect("T005_DATABASE_URL must point to a direct disposable PostgreSQL database");
    assert!(
        !url.contains(":6432/"),
        "T005 must not use PgBouncer because claims require direct PostgreSQL locking"
    );
    PgPoolOptions::new()
        .max_connections(5)
        .connect(&url)
        .await
        .expect("connect T005 PostgreSQL")
}

async fn migrate(pool: &PgPool) {
    let migrations = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("migrations");
    sqlx::migrate::Migrator::new(migrations)
        .await
        .expect("load migrations")
        .run(pool)
        .await
        .expect("run migrations")
}

/// T005 workers deliberately claim globally across all generations.  These
/// ignored tests therefore require an empty T005 ledger in their dedicated
/// disposable database; otherwise a failed predecessor can be claimed here.
async fn reset_t005_projection_state(pool: &PgPool) {
    sqlx::query("DELETE FROM search_projection_jobs")
        .execute(pool)
        .await
        .expect("clear T005 jobs");
    sqlx::query("DELETE FROM search_node_projections")
        .execute(pool)
        .await
        .expect("clear T005 projections");
    sqlx::query("DELETE FROM search_index_generations")
        .execute(pool)
        .await
        .expect("clear T005 generations");
    // With no tracked generation, deleting prior test nodes cannot enqueue a
    // new claimable job.  Clear their trigger-created versions afterwards.
    sqlx::query("DELETE FROM domain_nodes WHERE id LIKE 't005-%'")
        .execute(pool)
        .await
        .expect("clear prior T005 nodes");
    sqlx::query("DELETE FROM search_node_versions")
        .execute(pool)
        .await
        .expect("clear T005 node versions");
}

struct FakeProvider {
    unavailable: AtomicBool,
}

#[async_trait]
impl EmbeddingProvider for FakeProvider {
    async fn embed(
        &self,
        _document: &str,
        dimension: usize,
    ) -> Result<Vec<f64>, EmbeddingProviderError> {
        if self.unavailable.load(Ordering::SeqCst) {
            Err(EmbeddingProviderError::Unavailable)
        } else {
            Ok(vec![0.25; dimension])
        }
    }
}

fn worker(pool: PgPool, id: &str, provider: Arc<FakeProvider>) -> ProjectionWorker {
    ProjectionWorker::new_with_provider(
        pool,
        id.to_owned(),
        Metrics::try_new(BuildInfo::collect()).expect("metrics"),
        provider,
    )
    .expect("worker")
}

#[tokio::test]
#[ignore = "requires T005_DATABASE_URL pointing to direct disposable PostgreSQL"]
async fn worker_is_revision_bound_leased_resumable_and_deletion_propagates() {
    let pool = pool().await;
    migrate(&pool).await;
    reset_t005_projection_state(&pool).await;
    let node = "t005-worker-node";
    let generation = generation_id("test", 4);
    sqlx::query("INSERT INTO domain_nodes (id,kind,title,payload) VALUES ($1,'Werkstatt','Fahrradhilfe',$2::jsonb)")
        .bind(node)
        .bind(r#"{"summary":"Reparatur","address":"must not index","search_visibility":"public"}"#)
        .execute(&pool).await.expect("insert node");
    let provider = Arc::new(FakeProvider {
        unavailable: AtomicBool::new(false),
    });
    let first = worker(pool.clone(), "t005-a", provider.clone());
    first
        .start_generation(GenerationSpec {
            generation_id: &generation,
            provider: "local:ollama",
            model_id: "test",
            model_revision: TEST_REVISION,
            runtime_identity: "ollama:test@http://127.0.0.1:11434",
            dimension: 4,
        })
        .await
        .expect("start");
    assert_eq!(
        first.claim_and_process_one().await.expect("process"),
        ProcessOutcome::Processed
    );
    let snapshot = first.status_snapshot().await.expect("projection status");
    assert_eq!(snapshot.active_generation_id, None);
    assert!(
        snapshot.last_successful_projection_at.is_some(),
        "a completed ready projection must establish freshness before activation"
    );
    let projection: (i64, String, String, String) = sqlx::query_as("SELECT source_version,status,semantic_state,searchable_text FROM search_node_projections WHERE generation_id=$1 AND node_id=$2")
        .bind(&generation).bind(node).fetch_one(&pool).await.expect("projection");
    assert_eq!(projection.0, 1);
    assert_eq!(projection.1, "active");
    assert_eq!(projection.2, "ready");
    assert!(!projection.3.contains("must not index"));

    // A stale result is terminal and cannot overwrite revision two.
    sqlx::query("UPDATE domain_nodes SET title='Neue Fahrradhilfe' WHERE id=$1")
        .bind(node)
        .execute(&pool)
        .await
        .expect("update node");
    let second = worker(pool.clone(), "t005-b", provider);
    assert_eq!(
        second
            .claim_and_process_one()
            .await
            .expect("process current"),
        ProcessOutcome::Processed
    );
    let version: i64 = sqlx::query_scalar(
        "SELECT source_version FROM search_node_projections WHERE generation_id=$1 AND node_id=$2",
    )
    .bind(&generation)
    .bind(node)
    .fetch_one(&pool)
    .await
    .expect("current projection");
    assert_eq!(version, 2);
    sqlx::query("INSERT INTO search_projection_jobs (generation_id,node_id,source_version,source_revision,operation) VALUES ($1,$2,1,'node-1','delete')")
        .bind(&generation).bind(node).execute(&pool).await.expect("stale job");
    assert_eq!(
        second.claim_and_process_one().await.expect("process stale"),
        ProcessOutcome::Stale
    );

    sqlx::query("DELETE FROM domain_nodes WHERE id=$1")
        .bind(node)
        .execute(&pool)
        .await
        .expect("delete node");
    assert_eq!(
        first
            .claim_and_process_one()
            .await
            .expect("process deletion"),
        ProcessOutcome::Deleted
    );
    let remaining: i64 =
        sqlx::query_scalar("SELECT count(*) FROM search_node_projections WHERE node_id=$1")
            .bind(node)
            .fetch_one(&pool)
            .await
            .expect("remaining projection count");
    assert_eq!(remaining, 0);
}

#[tokio::test]
#[ignore = "requires T005_DATABASE_URL pointing to direct disposable PostgreSQL"]
async fn worker_hardening_proves_races_trigger_identity_outage_and_activation() {
    let pool = pool().await;
    migrate(&pool).await;
    reset_t005_projection_state(&pool).await;
    let node = "t005-hardening-node";
    let generation = generation_id("m", 3);
    sqlx::query("INSERT INTO domain_nodes (id,kind,title,lat,lon,payload) VALUES ($1,'Werkstatt','Alt',1,2,$2::jsonb)")
        .bind(node).bind(r#"{"summary":"S","search_visibility":"public","address":"private","other":"a"}"#)
        .execute(&pool).await.expect("insert");
    let provider = Arc::new(FakeProvider {
        unavailable: AtomicBool::new(true),
    });
    let a = worker(pool.clone(), "t005-hardening-a", provider.clone());
    let b = worker(pool.clone(), "t005-hardening-b", provider.clone());
    a.start_generation(GenerationSpec {
        generation_id: &generation,
        provider: "local:ollama",
        model_id: "m",
        model_revision: TEST_REVISION,
        runtime_identity: "ollama:test@http://127.0.0.1:11434",
        dimension: 3,
    })
    .await
    .expect("start");
    // A provider outage leaves a leased item retryable; it does not alter the canonical node.
    assert_eq!(
        a.claim_and_process_one().await.expect("outage"),
        ProcessOutcome::PendingProvider
    );
    let state: String =
        sqlx::query_scalar("SELECT state FROM search_projection_jobs WHERE generation_id=$1")
            .bind(&generation)
            .fetch_one(&pool)
            .await
            .expect("retry state");
    assert_eq!(state, "retry");
    let canonical: String = sqlx::query_scalar("SELECT title FROM domain_nodes WHERE id=$1")
        .bind(node)
        .fetch_one(&pool)
        .await
        .expect("canonical row");
    assert_eq!(canonical, "Alt");
    // The same generation id is a complete immutable identity, including ranking revision.
    assert!(a
        .start_generation(GenerationSpec {
            generation_id: &generation,
            provider: "local:ollama",
            model_id: "other",
            model_revision: TEST_REVISION,
            runtime_identity: "ollama:test@http://127.0.0.1:11434",
            dimension: 3
        })
        .await
        .is_err());
    sqlx::query("UPDATE search_index_generations SET ranking_revision='different-ranking' WHERE generation_id=$1")
        .bind(&generation)
        .execute(&pool)
        .await
        .expect("simulate incompatible stored generation identity");
    assert!(a
        .start_generation(GenerationSpec {
            generation_id: &generation,
            provider: "local:ollama",
            model_id: "m",
            model_revision: TEST_REVISION,
            runtime_identity: "ollama:test@http://127.0.0.1:11434",
            dimension: 3
        })
        .await
        .is_err());
    sqlx::query("UPDATE search_index_generations SET ranking_revision='weltgewebe-hybrid-ranking-v2' WHERE generation_id=$1")
        .bind(&generation)
        .execute(&pool)
        .await
        .expect("restore test identity");
    // Incomplete/provider-pending generations cannot be atomically activated.
    assert!(
        sqlx::query("SELECT weltgewebe_activate_search_generation($1)")
            .bind(&generation)
            .execute(&pool)
            .await
            .is_err()
    );

    // An irrelevant position or unknown JSON update does not version/enqueue; title does.
    let before: i64 =
        sqlx::query_scalar("SELECT source_version FROM search_node_versions WHERE node_id=$1")
            .bind(node)
            .fetch_one(&pool)
            .await
            .expect("version");
    let jobs_before: i64 =
        sqlx::query_scalar("SELECT count(*) FROM search_projection_jobs WHERE generation_id=$1")
            .bind(&generation)
            .fetch_one(&pool)
            .await
            .expect("jobs");
    sqlx::query("UPDATE domain_nodes SET lat=3, lon=4, payload=payload || '{\"address\":\"changed\",\"other\":\"b\"}'::jsonb WHERE id=$1").bind(node).execute(&pool).await.expect("irrelevant update");
    assert_eq!(
        sqlx::query_scalar::<_, i64>(
            "SELECT source_version FROM search_node_versions WHERE node_id=$1"
        )
        .bind(node)
        .fetch_one(&pool)
        .await
        .expect("unchanged version"),
        before
    );
    assert_eq!(
        sqlx::query_scalar::<_, i64>(
            "SELECT count(*) FROM search_projection_jobs WHERE generation_id=$1"
        )
        .bind(&generation)
        .fetch_one(&pool)
        .await
        .expect("no new job"),
        jobs_before
    );

    // Make the retry immediately claimable and recover idempotently with the provider restored.
    provider.unavailable.store(false, Ordering::SeqCst);
    sqlx::query("UPDATE search_projection_jobs SET available_at=NOW() WHERE generation_id=$1 AND state='retry'").bind(&generation).execute(&pool).await.expect("release retry");
    assert_eq!(
        b.claim_and_process_one().await.expect("recovery"),
        ProcessOutcome::Processed
    );
    // Two independent instances race for one new job; SKIP LOCKED gives it to
    // exactly one claimant rather than duplicating a provider call/write.
    sqlx::query("UPDATE domain_nodes SET title='Mitte' WHERE id=$1")
        .bind(node)
        .execute(&pool)
        .await
        .expect("create one claimable job");
    let (a_claim, b_claim) = tokio::join!(a.claim_and_process_one(), b.claim_and_process_one());
    let a_claim = a_claim.expect("first claimant");
    let b_claim = b_claim.expect("second claimant");
    assert!(
        (a_claim == ProcessOutcome::Processed && b_claim == ProcessOutcome::Empty)
            || (a_claim == ProcessOutcome::Empty && b_claim == ProcessOutcome::Processed),
        "exactly one worker must claim the leased job"
    );

    // Insert old jobs after a newer canonical update: final mutating SQL fences both stale upsert and stale delete.
    sqlx::query("UPDATE domain_nodes SET title='Neu' WHERE id=$1")
        .bind(node)
        .execute(&pool)
        .await
        .expect("relevant update");
    sqlx::query("UPDATE search_projection_jobs SET state='pending', claimed_by=NULL, claim_until=NULL, available_at=NOW() WHERE generation_id=$1 AND node_id=$2 AND source_version=$3 AND operation='upsert'")
        .bind(&generation).bind(node).bind(before).execute(&pool).await.expect("requeue stale upsert");
    // The title update created the current v3 upsert before we requeued v1,
    // so take exactly that current job out of eligibility before proving v1
    // is fenced as stale. Queue ordering remains unchanged.
    sqlx::query("UPDATE search_projection_jobs SET state='stale', completed_at=NOW() WHERE generation_id=$1 AND node_id=$2 AND source_version=$3 AND operation='upsert'")
        .bind(&generation).bind(node).bind(before + 2).execute(&pool).await.expect("keep current job out of stale upsert proof");
    assert_eq!(
        a.claim_and_process_one()
            .await
            .expect("stale upsert outcome"),
        ProcessOutcome::Stale
    );
    sqlx::query("INSERT INTO search_projection_jobs (generation_id,node_id,source_version,source_revision,operation) VALUES ($1,$2,$3,$4,'delete') ON CONFLICT DO NOTHING")
        .bind(&generation).bind(node).bind(before).bind("node-1").execute(&pool).await.expect("stale delete");
    assert_eq!(
        b.claim_and_process_one()
            .await
            .expect("stale delete outcome"),
        ProcessOutcome::Stale
    );
    let projection_title: String = sqlx::query_scalar(
        "SELECT title FROM search_node_projections WHERE generation_id=$1 AND node_id=$2",
    )
    .bind(&generation)
    .bind(node)
    .fetch_one(&pool)
    .await
    .expect("stale delete did not remove projection");
    assert_eq!(projection_title, "Mitte");
}

#[tokio::test]
#[ignore = "requires T005_DATABASE_URL pointing to direct disposable PostgreSQL"]
async fn rebuild_fallback_rollback_status_and_repeat_digest_are_deterministic() {
    let pool = pool().await;
    migrate(&pool).await;
    reset_t005_projection_state(&pool).await;
    let node = "t005-rebuild-node";
    let a_id = generation_id("model-a", 2);
    let b_id = generation_id("model-b", 2);
    sqlx::query(
        "INSERT INTO domain_nodes (id,kind,title,payload) VALUES ($1,'Werkstatt','A',$2::jsonb)",
    )
    .bind(node)
    .bind(r#"{"summary":"one","search_visibility":"public"}"#)
    .execute(&pool)
    .await
    .expect("insert");
    let provider = Arc::new(FakeProvider {
        unavailable: AtomicBool::new(false),
    });
    let worker = worker(pool.clone(), "t005-rebuild", provider);
    for (id, model) in [(&a_id, "model-a"), (&b_id, "model-b")] {
        worker
            .start_generation(GenerationSpec {
                generation_id: id,
                provider: "local:ollama",
                model_id: model,
                model_revision: TEST_REVISION,
                runtime_identity: "ollama:test@http://127.0.0.1:11434",
                dimension: 2,
            })
            .await
            .expect("start generation");
        if id == &b_id {
            let snapshot = worker.status_snapshot().await.expect("building status");
            assert_eq!(
                snapshot.active_generation_id.as_deref(),
                Some(a_id.as_str())
            );
            assert_eq!(snapshot.rebuild_expected_nodes, Some(1));
            assert_eq!(snapshot.rebuild_completed_nodes, Some(0));
        }
        assert_eq!(
            worker.claim_and_process_one().await.expect("project"),
            ProcessOutcome::Processed
        );
        sqlx::query("SELECT weltgewebe_activate_search_generation($1)")
            .bind(id)
            .execute(&pool)
            .await
            .expect("activate");
    }
    let states: Vec<(String, String)> = sqlx::query_as("SELECT generation_id,state FROM search_index_generations WHERE generation_id IN ($1,$2) ORDER BY generation_id")
        .bind(&a_id).bind(&b_id).fetch_all(&pool).await.expect("states");
    assert!(states
        .iter()
        .any(|(id, state)| id == &b_id && state == "active"));
    assert!(states
        .iter()
        .any(|(id, state)| id == &a_id && state == "ready"));

    // Both the active B and rollback-ready A receive every canonical mutation.
    sqlx::query("UPDATE domain_nodes SET title='B' WHERE id=$1")
        .bind(node)
        .execute(&pool)
        .await
        .expect("update");
    assert_eq!(
        worker.claim_and_process_one().await.expect("B update"),
        ProcessOutcome::Processed
    );
    assert_eq!(
        worker.claim_and_process_one().await.expect("A update"),
        ProcessOutcome::Processed
    );

    // Rebuilding the same immutable generation after projection loss is
    // deterministic; its digest covers stable identity/content metadata only.
    let before = worker.integrity_digest(&b_id).await.expect("first digest");
    sqlx::query("DELETE FROM search_node_projections WHERE generation_id=$1")
        .bind(&b_id)
        .execute(&pool)
        .await
        .expect("drop regenerable projection");
    let requeued = sqlx::query(
        "UPDATE search_projection_jobs j \
         SET state='pending', available_at=NOW(), claimed_by=NULL, claim_until=NULL \
         FROM search_node_versions v \
         WHERE j.generation_id=$1 AND j.node_id=$2 AND j.operation='upsert' \
           AND j.node_id=v.node_id \
           AND j.source_version=v.source_version \
           AND j.source_revision=v.source_revision",
    )
    .bind(&b_id)
    .bind(node)
    .execute(&pool)
    .await
    .expect("requeue B current revision");
    assert_eq!(requeued.rows_affected(), 1, "requeue only B's current job");
    assert_eq!(
        worker.claim_and_process_one().await.expect("regenerate B"),
        ProcessOutcome::Processed
    );
    assert_eq!(
        worker.integrity_digest(&b_id).await.expect("repeat digest"),
        before
    );

    sqlx::query("DELETE FROM domain_nodes WHERE id=$1")
        .bind(node)
        .execute(&pool)
        .await
        .expect("delete");
    assert_eq!(
        worker.claim_and_process_one().await.expect("B delete"),
        ProcessOutcome::Deleted
    );
    assert_eq!(
        worker.claim_and_process_one().await.expect("A delete"),
        ProcessOutcome::Deleted
    );

    sqlx::query("SELECT weltgewebe_activate_search_generation($1)")
        .bind(&a_id)
        .execute(&pool)
        .await
        .expect("atomic rollback");
    let states: Vec<(String, String)> = sqlx::query_as("SELECT generation_id,state FROM search_index_generations WHERE generation_id IN ($1,$2) ORDER BY generation_id")
        .bind(&a_id).bind(&b_id).fetch_all(&pool).await.expect("rollback states");
    assert!(states
        .iter()
        .any(|(id, state)| id == &a_id && state == "active"));
    assert!(states
        .iter()
        .any(|(id, state)| id == &b_id && state == "ready"));
}

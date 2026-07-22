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
use tokio::{
    sync::{Barrier, Notify},
    time::{sleep, Duration},
};
use weltgewebe_api::{
    auth::role::Role,
    config::{
        AppConfig, DomainAccountWriteSource, DomainEdgeWriteSource, DomainNodeWriteSource,
        DomainReadSource,
    },
    middleware::auth::AuthContext,
    search::{
        execute_search, EmbeddingProvider, EmbeddingProviderError, GenerationSpec, ProcessOutcome,
        ProjectionWorker, SearchError, SearchQueryParams, DOCUMENT_REVISION,
        NORMALIZATION_REVISION, RANKING_REVISION,
    },
    state::ApiState,
    telemetry::{BuildInfo, Metrics},
};

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

async fn reset_search_state(pool: &PgPool) {
    // Tests in this target share one disposable database serially. Remove test
    // domain rows first (which may fire triggers), then clear all derived state.
    sqlx::query("DELETE FROM domain_nodes WHERE id LIKE 't005-%'")
        .execute(pool)
        .await
        .expect("remove prior T005 test nodes");
    sqlx::query("TRUNCATE search_projection_jobs, search_node_projections, search_node_versions, search_index_generations RESTART IDENTITY CASCADE")
        .execute(pool)
        .await
        .expect("reset T005 projection state");
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

struct BlockingProvider {
    entered: Arc<Notify>,
    release: Arc<Notify>,
}

#[async_trait]
impl EmbeddingProvider for BlockingProvider {
    async fn embed(
        &self,
        _document: &str,
        dimension: usize,
    ) -> Result<Vec<f64>, EmbeddingProviderError> {
        self.entered.notify_one();
        self.release.notified().await;
        Ok(vec![0.5; dimension])
    }
}

struct BarrierProvider {
    barrier: Arc<Barrier>,
}

#[async_trait]
impl EmbeddingProvider for BarrierProvider {
    async fn embed(
        &self,
        _document: &str,
        dimension: usize,
    ) -> Result<Vec<f64>, EmbeddingProviderError> {
        self.barrier.wait().await;
        Ok(vec![0.5; dimension])
    }
}

struct PermanentFailureProvider;

#[async_trait]
impl EmbeddingProvider for PermanentFailureProvider {
    async fn embed(
        &self,
        _document: &str,
        _dimension: usize,
    ) -> Result<Vec<f64>, EmbeddingProviderError> {
        Err(EmbeddingProviderError::InvalidVector)
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
    reset_search_state(&pool).await;
    let node = "t005-worker-node";
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
            generation_id: "t005-generation",
            provider: "local:ollama",
            model_id: "test",
            model_revision: "test",
            runtime_identity: "ollama:test@http://127.0.0.1:11434",
            dimension: 4,
        })
        .await
        .expect("start");
    assert_eq!(
        first.claim_and_process_one().await.expect("process"),
        ProcessOutcome::Processed
    );
    let projection: (i64, String, String, String) = sqlx::query_as("SELECT source_version,status,semantic_state,searchable_text FROM search_node_projections WHERE generation_id='t005-generation' AND node_id=$1")
        .bind(node).fetch_one(&pool).await.expect("projection");
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
    let version: i64 = sqlx::query_scalar("SELECT source_version FROM search_node_projections WHERE generation_id='t005-generation' AND node_id=$1")
        .bind(node).fetch_one(&pool).await.expect("current projection");
    assert_eq!(version, 2);
    sqlx::query("INSERT INTO search_projection_jobs (generation_id,node_id,source_version,source_revision,operation) VALUES ('t005-generation',$1,1,'node-1','delete')")
        .bind(node).execute(&pool).await.expect("stale job");
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
    reset_search_state(&pool).await;
    let node = "t005-hardening-node";
    let generation = "t005-hardening-generation";
    sqlx::query("INSERT INTO domain_nodes (id,kind,title,lat,lon,payload) VALUES ($1,'Werkstatt','Alt',1,2,$2::jsonb)")
        .bind(node).bind(r#"{"summary":"S","search_visibility":"public","address":"private","other":"a"}"#)
        .execute(&pool).await.expect("insert");
    let provider = Arc::new(FakeProvider {
        unavailable: AtomicBool::new(true),
    });
    let a = worker(pool.clone(), "t005-hardening-a", provider.clone());
    let b = worker(pool.clone(), "t005-hardening-b", provider.clone());
    a.start_generation(GenerationSpec {
        generation_id: generation,
        provider: "local:ollama",
        model_id: "m",
        model_revision: "r",
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
            .bind(generation)
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
            generation_id: generation,
            provider: "local:ollama",
            model_id: "other",
            model_revision: "r",
            runtime_identity: "ollama:test@http://127.0.0.1:11434",
            dimension: 3
        })
        .await
        .is_err());
    sqlx::query("UPDATE search_index_generations SET ranking_revision='different-ranking' WHERE generation_id=$1")
        .bind(generation)
        .execute(&pool)
        .await
        .expect("simulate incompatible stored generation identity");
    assert!(a
        .start_generation(GenerationSpec {
            generation_id: generation,
            provider: "local:ollama",
            model_id: "m",
            model_revision: "r",
            runtime_identity: "ollama:test@http://127.0.0.1:11434",
            dimension: 3
        })
        .await
        .is_err());
    sqlx::query("UPDATE search_index_generations SET ranking_revision='weltgewebe-hybrid-ranking-v2' WHERE generation_id=$1")
        .bind(generation)
        .execute(&pool)
        .await
        .expect("restore test identity");
    // Incomplete/provider-pending generations cannot be atomically activated.
    assert!(
        sqlx::query("SELECT weltgewebe_activate_search_generation($1)")
            .bind(generation)
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
            .bind(generation)
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
        .bind(generation)
        .fetch_one(&pool)
        .await
        .expect("no new job"),
        jobs_before
    );

    // Make the retry immediately claimable and recover idempotently with the provider restored.
    provider.unavailable.store(false, Ordering::SeqCst);
    sqlx::query("UPDATE search_projection_jobs SET available_at=NOW() WHERE generation_id=$1 AND state='retry'").bind(generation).execute(&pool).await.expect("release retry");
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
    sqlx::query("UPDATE search_projection_jobs SET state='pending', claimed_by=NULL, claim_until=NULL, available_at=TIMESTAMPTZ '1970-01-01' WHERE generation_id=$1 AND node_id=$2 AND source_version=$3 AND operation='upsert'")
        .bind(generation).bind(node).bind(before).execute(&pool).await.expect("requeue stale upsert");
    assert_eq!(
        a.claim_and_process_one()
            .await
            .expect("stale upsert outcome"),
        ProcessOutcome::Stale
    );
    sqlx::query("INSERT INTO search_projection_jobs (generation_id,node_id,source_version,source_revision,operation,available_at) VALUES ($1,$2,$3,$4,'delete',TIMESTAMPTZ '1970-01-01') ON CONFLICT DO NOTHING")
        .bind(generation).bind(node).bind(before).bind("node-1").execute(&pool).await.expect("stale delete");
    sqlx::query("UPDATE search_projection_jobs SET state='stale', completed_at=NOW() WHERE generation_id=$1 AND node_id=$2 AND source_version=$3 AND operation='upsert'")
        .bind(generation).bind(node).bind(before + 2).execute(&pool).await.expect("keep newer job out of this race proof");
    assert_eq!(
        b.claim_and_process_one()
            .await
            .expect("stale delete outcome"),
        ProcessOutcome::Stale
    );
    let projection_title: String = sqlx::query_scalar(
        "SELECT title FROM search_node_projections WHERE generation_id=$1 AND node_id=$2",
    )
    .bind(generation)
    .bind(node)
    .fetch_one(&pool)
    .await
    .expect("stale delete did not remove projection");
    assert_eq!(projection_title, "Mitte");
}

#[tokio::test]
#[ignore = "requires T005_DATABASE_URL pointing to direct disposable PostgreSQL"]
async fn provider_failures_are_bounded_fail_closed_and_explicitly_recoverable() {
    let pool = pool().await;
    migrate(&pool).await;
    reset_search_state(&pool).await;
    let node = "t005-provider-node";
    let generation = "t005-provider-generation";
    sqlx::query("INSERT INTO domain_nodes (id,kind,title,payload) VALUES ($1,'Werkstatt','Provider',$2::jsonb)")
        .bind(node)
        .bind(r#"{"search_visibility":"public"}"#)
        .execute(&pool)
        .await
        .expect("insert provider node");

    let unavailable = Arc::new(FakeProvider {
        unavailable: AtomicBool::new(true),
    });
    let retrying = worker(pool.clone(), "t005-provider-retry", unavailable.clone());
    retrying
        .start_generation(GenerationSpec {
            generation_id: generation,
            provider: "local:ollama",
            model_id: "m",
            model_revision: "r",
            runtime_identity: "ollama:test@http://127.0.0.1:11434",
            dimension: 3,
        })
        .await
        .expect("start retry generation");

    for attempt in 1..=8 {
        let outcome = retrying
            .claim_and_process_one()
            .await
            .expect("provider outage attempt");
        if attempt < 8 {
            assert_eq!(outcome, ProcessOutcome::PendingProvider);
            sqlx::query("UPDATE search_projection_jobs SET available_at=TIMESTAMPTZ '1970-01-01' WHERE generation_id=$1 AND state='retry'")
                .bind(generation)
                .execute(&pool)
                .await
                .expect("make retry claimable");
        } else {
            assert_eq!(outcome, ProcessOutcome::Failed);
        }
    }
    let exhausted: (String, i32, Option<String>) = sqlx::query_as(
        "SELECT state,attempt_count,last_error_code FROM search_projection_jobs WHERE generation_id=$1",
    )
    .bind(generation)
    .fetch_one(&pool)
    .await
    .expect("exhausted job");
    assert_eq!(exhausted.0, "failed");
    assert_eq!(exhausted.1, 8);
    assert_eq!(
        exhausted.2.as_deref(),
        Some("provider_unavailable_exhausted")
    );

    unavailable.unavailable.store(false, Ordering::SeqCst);
    retrying
        .start_generation(GenerationSpec {
            generation_id: generation,
            provider: "local:ollama",
            model_id: "m",
            model_revision: "r",
            runtime_identity: "ollama:test@http://127.0.0.1:11434",
            dimension: 3,
        })
        .await
        .expect("explicit catch-up rearm");
    assert_eq!(
        retrying
            .claim_and_process_one()
            .await
            .expect("catch-up projection"),
        ProcessOutcome::Processed
    );

    let permanent_generation = "t005-provider-permanent";
    let permanent = ProjectionWorker::new_with_provider(
        pool.clone(),
        "t005-provider-permanent-worker".to_owned(),
        Metrics::try_new(BuildInfo::collect()).expect("metrics"),
        Arc::new(PermanentFailureProvider),
    )
    .expect("permanent worker");
    permanent
        .start_generation(GenerationSpec {
            generation_id: permanent_generation,
            provider: "local:ollama",
            model_id: "m",
            model_revision: "r",
            runtime_identity: "ollama:test@http://127.0.0.1:11434",
            dimension: 3,
        })
        .await
        .expect("start permanent failure generation");
    assert_eq!(
        permanent
            .claim_and_process_one()
            .await
            .expect("permanent provider failure"),
        ProcessOutcome::Failed
    );
    let permanent_state: (String, i32, Option<String>) = sqlx::query_as(
        "SELECT state,attempt_count,last_error_code FROM search_projection_jobs WHERE generation_id=$1",
    )
    .bind(permanent_generation)
    .fetch_one(&pool)
    .await
    .expect("permanent failed job");
    assert_eq!(permanent_state.0, "failed");
    assert_eq!(permanent_state.1, 1);
    assert_eq!(
        permanent_state.2.as_deref(),
        Some("provider_invalid_vector")
    );
    permanent
        .start_generation(GenerationSpec {
            generation_id: permanent_generation,
            provider: "local:ollama",
            model_id: "m",
            model_revision: "r",
            runtime_identity: "ollama:test@http://127.0.0.1:11434",
            dimension: 3,
        })
        .await
        .expect("idempotent permanent generation restart");
    let still_failed: String =
        sqlx::query_scalar("SELECT state FROM search_projection_jobs WHERE generation_id=$1")
            .bind(permanent_generation)
            .fetch_one(&pool)
            .await
            .expect("permanent failure stays failed");
    assert_eq!(still_failed, "failed");
}

#[tokio::test]
#[ignore = "requires T005_DATABASE_URL pointing to direct disposable PostgreSQL"]
async fn rollback_candidate_stays_current_and_retired_generation_cannot_reactivate() {
    let pool = pool().await;
    migrate(&pool).await;
    reset_search_state(&pool).await;
    let node = "t005-rollback-node";
    sqlx::query(
        "INSERT INTO domain_nodes (id,kind,title,payload) VALUES ($1,'Werkstatt','A',$2::jsonb)",
    )
    .bind(node)
    .bind(r#"{"summary":"sichtbar","search_visibility":"public"}"#)
    .execute(&pool)
    .await
    .expect("insert rollback node");
    let provider = Arc::new(FakeProvider {
        unavailable: AtomicBool::new(false),
    });
    let worker = worker(pool.clone(), "t005-rollback", provider);
    let spec = |generation_id| GenerationSpec {
        generation_id,
        provider: "local:ollama",
        model_id: "m",
        model_revision: "r",
        runtime_identity: "ollama:test@http://127.0.0.1:11434",
        dimension: 3,
    };

    worker
        .start_generation(spec("t005-gen-a"))
        .await
        .expect("gen A");
    assert_eq!(
        worker.claim_and_process_one().await.expect("A project"),
        ProcessOutcome::Processed
    );
    sqlx::query("SELECT weltgewebe_activate_search_generation('t005-gen-a')")
        .execute(&pool)
        .await
        .expect("activate A");

    worker
        .start_generation(spec("t005-gen-b"))
        .await
        .expect("gen B");
    assert_eq!(
        worker.claim_and_process_one().await.expect("B project"),
        ProcessOutcome::Processed
    );
    sqlx::query("SELECT weltgewebe_activate_search_generation('t005-gen-b')")
        .execute(&pool)
        .await
        .expect("activate B");
    let states: Vec<(String, String)> = sqlx::query_as(
        "SELECT generation_id,state FROM search_index_generations WHERE generation_id IN ('t005-gen-a','t005-gen-b') ORDER BY generation_id",
    )
    .fetch_all(&pool).await.expect("A/B states");
    assert_eq!(
        states,
        vec![
            ("t005-gen-a".into(), "ready".into()),
            ("t005-gen-b".into(), "active".into())
        ]
    );

    sqlx::query("UPDATE domain_nodes SET title='Aktuell' WHERE id=$1")
        .bind(node)
        .execute(&pool)
        .await
        .expect("mutate canonical node");
    assert_eq!(
        worker
            .claim_and_process_one()
            .await
            .expect("first catch-up"),
        ProcessOutcome::Processed
    );
    assert_eq!(
        worker
            .claim_and_process_one()
            .await
            .expect("second catch-up"),
        ProcessOutcome::Processed
    );
    let versions: Vec<(String, i64)> = sqlx::query_as(
        "SELECT generation_id,source_version FROM search_node_projections WHERE node_id=$1 AND generation_id IN ('t005-gen-a','t005-gen-b') ORDER BY generation_id",
    )
    .bind(node).fetch_all(&pool).await.expect("caught-up versions");
    assert_eq!(
        versions,
        vec![("t005-gen-a".into(), 2), ("t005-gen-b".into(), 2)]
    );

    sqlx::query("UPDATE domain_nodes SET payload=jsonb_set(payload,'{search_visibility}','\"hidden\"'::jsonb) WHERE id=$1")
        .bind(node).execute(&pool).await.expect("withdraw visibility");
    assert_eq!(
        worker
            .claim_and_process_one()
            .await
            .expect("first visibility catch-up"),
        ProcessOutcome::Processed
    );
    assert_eq!(
        worker
            .claim_and_process_one()
            .await
            .expect("second visibility catch-up"),
        ProcessOutcome::Processed
    );
    let visibility: Vec<(String, String, Vec<String>)> = sqlx::query_as(
        "SELECT generation_id,status,visibility_scopes FROM search_node_projections WHERE node_id=$1 AND generation_id IN ('t005-gen-a','t005-gen-b') ORDER BY generation_id",
    )
    .bind(node).fetch_all(&pool).await.expect("visibility projections");
    assert_eq!(visibility.len(), 2);
    assert!(visibility
        .iter()
        .all(|(_, status, scopes)| status == "hidden" && scopes.is_empty()));

    sqlx::query("SELECT weltgewebe_activate_search_generation('t005-gen-a')")
        .execute(&pool)
        .await
        .expect("rollback A");
    let rolled_back: Vec<(String, String)> = sqlx::query_as(
        "SELECT generation_id,state FROM search_index_generations WHERE generation_id IN ('t005-gen-a','t005-gen-b') ORDER BY generation_id",
    )
    .fetch_all(&pool).await.expect("rollback states");
    assert_eq!(
        rolled_back,
        vec![
            ("t005-gen-a".into(), "active".into()),
            ("t005-gen-b".into(), "ready".into())
        ]
    );

    worker
        .start_generation(spec("t005-gen-c"))
        .await
        .expect("gen C");
    assert_eq!(
        worker.claim_and_process_one().await.expect("C project"),
        ProcessOutcome::Processed
    );
    sqlx::query("SELECT weltgewebe_activate_search_generation('t005-gen-c')")
        .execute(&pool)
        .await
        .expect("activate C");
    let fallback_states: Vec<(String, String)> = sqlx::query_as(
        "SELECT generation_id,state FROM search_index_generations WHERE generation_id IN ('t005-gen-a','t005-gen-b','t005-gen-c') ORDER BY generation_id",
    )
    .fetch_all(&pool)
    .await
    .expect("post-C generation states");
    assert_eq!(
        fallback_states,
        vec![
            ("t005-gen-a".into(), "ready".into()),
            ("t005-gen-b".into(), "retired".into()),
            ("t005-gen-c".into(), "active".into()),
        ]
    );
    assert!(
        sqlx::query("SELECT weltgewebe_activate_search_generation('t005-gen-b')")
            .execute(&pool)
            .await
            .is_err()
    );

    sqlx::query("DELETE FROM domain_nodes WHERE id=$1")
        .bind(node)
        .execute(&pool)
        .await
        .expect("delete canonical node");
    assert!(
        sqlx::query("SELECT weltgewebe_activate_search_generation('t005-gen-a')")
            .execute(&pool)
            .await
            .is_err(),
        "ready rollback target must not activate while delete jobs are pending"
    );
    assert_eq!(
        worker.claim_and_process_one().await.expect("delete active"),
        ProcessOutcome::Deleted
    );
    assert_eq!(
        worker.claim_and_process_one().await.expect("delete ready"),
        ProcessOutcome::Deleted
    );
    let live_rollback_projections: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM search_node_projections p JOIN search_index_generations g USING (generation_id) WHERE p.node_id=$1 AND g.state IN ('active','ready')",
    )
    .bind(node).fetch_one(&pool).await.expect("active/ready deletion count");
    assert_eq!(live_rollback_projections, 0);
    sqlx::query("SELECT weltgewebe_activate_search_generation('t005-gen-a')")
        .execute(&pool)
        .await
        .expect("rollback is safe after all delete jobs complete");
}

#[tokio::test]
#[ignore = "requires T005_DATABASE_URL pointing to direct disposable PostgreSQL"]
async fn identical_rebuilds_have_the_same_logical_integrity_digest() {
    let pool = pool().await;
    migrate(&pool).await;
    reset_search_state(&pool).await;
    let node = "t005-digest-node";
    sqlx::query("INSERT INTO domain_nodes (id,kind,title,payload) VALUES ($1,'Werkstatt','Digest',$2::jsonb)")
        .bind(node)
        .bind(r#"{"summary":"gleich","tags":["b","a"],"language":"de","search_visibility":"public"}"#)
        .execute(&pool).await.expect("insert digest node");
    let provider = Arc::new(FakeProvider {
        unavailable: AtomicBool::new(false),
    });
    let worker = worker(pool.clone(), "t005-digest", provider);
    for generation_id in ["t005-digest-a", "t005-digest-b"] {
        worker
            .start_generation(GenerationSpec {
                generation_id,
                provider: "local:ollama",
                model_id: "m",
                model_revision: "r",
                runtime_identity: "ollama:test@http://127.0.0.1:11434",
                dimension: 3,
            })
            .await
            .expect("start digest generation");
    }
    assert_eq!(
        worker.claim_and_process_one().await.expect("digest first"),
        ProcessOutcome::Processed
    );
    assert_eq!(
        worker.claim_and_process_one().await.expect("digest second"),
        ProcessOutcome::Processed
    );
    let first = worker
        .integrity_digest("t005-digest-a")
        .await
        .expect("first digest");
    let second = worker
        .integrity_digest("t005-digest-b")
        .await
        .expect("second digest");
    assert_eq!(first, second);
    assert_eq!(first.len(), 64);
}

#[tokio::test]
#[ignore = "requires T005_DATABASE_URL pointing to direct disposable PostgreSQL"]
async fn generation_start_and_activation_serialize_with_domain_mutations() {
    let pool = pool().await;
    migrate(&pool).await;
    reset_search_state(&pool).await;
    let node = "t005-generation-race-node";
    let generation = "t005-generation-race";
    sqlx::query(
        "INSERT INTO domain_nodes (id,kind,title,payload) VALUES ($1,'Werkstatt','A',$2::jsonb)",
    )
    .bind(node)
    .bind(r#"{"search_visibility":"public"}"#)
    .execute(&pool)
    .await
    .expect("insert race node");

    // Mutation reaches the trigger first and therefore holds the shared
    // generation lock until commit. Generation start must wait, then seed the
    // committed current revision rather than an older snapshot.
    let mut mutation = pool.begin().await.expect("begin pre-start mutation");
    sqlx::query("UPDATE domain_nodes SET title='B' WHERE id=$1")
        .bind(node)
        .execute(&mut *mutation)
        .await
        .expect("mutate before generation start");
    let worker = Arc::new(worker(
        pool.clone(),
        "t005-generation-race-worker",
        Arc::new(FakeProvider {
            unavailable: AtomicBool::new(false),
        }),
    ));
    let starter = worker.clone();
    let start = tokio::spawn(async move {
        starter
            .start_generation(GenerationSpec {
                generation_id: generation,
                provider: "local:ollama",
                model_id: "m",
                model_revision: "r",
                runtime_identity: "ollama:test@http://127.0.0.1:11434",
                dimension: 3,
            })
            .await
    });
    sleep(Duration::from_millis(50)).await;
    assert!(
        !start.is_finished(),
        "generation start bypassed mutation lock"
    );
    mutation.commit().await.expect("commit pre-start mutation");
    start
        .await
        .expect("start task join")
        .expect("start generation after mutation");
    let seeded_version: i64 = sqlx::query_scalar(
        "SELECT max(source_version) FROM search_projection_jobs WHERE generation_id=$1 AND node_id=$2",
    )
    .bind(generation)
    .bind(node)
    .fetch_one(&pool)
    .await
    .expect("seeded job version");
    assert_eq!(seeded_version, 2);
    assert_eq!(
        worker
            .claim_and_process_one()
            .await
            .expect("project seeded revision"),
        ProcessOutcome::Processed
    );

    // A mutation whose trigger already holds the shared lock must commit before
    // activation can take the exclusive lock. Activation then sees the pending
    // current-revision job and rejects the stale target.
    let mut before_activation = pool.begin().await.expect("begin activation mutation");
    sqlx::query("UPDATE domain_nodes SET title='C' WHERE id=$1")
        .bind(node)
        .execute(&mut *before_activation)
        .await
        .expect("mutate before activation");
    let activation_pool = pool.clone();
    let activation = tokio::spawn(async move {
        sqlx::query("SELECT weltgewebe_activate_search_generation($1)")
            .bind(generation)
            .execute(&activation_pool)
            .await
    });
    sleep(Duration::from_millis(50)).await;
    assert!(
        !activation.is_finished(),
        "activation bypassed mutation lock"
    );
    before_activation
        .commit()
        .await
        .expect("commit activation mutation");
    assert!(
        activation.await.expect("activation task join").is_err(),
        "activation must reject the newly pending revision"
    );
    assert_eq!(
        worker
            .claim_and_process_one()
            .await
            .expect("project activation revision"),
        ProcessOutcome::Processed
    );
    sqlx::query("SELECT weltgewebe_activate_search_generation($1)")
        .bind(generation)
        .execute(&pool)
        .await
        .expect("activate after catch-up");

    // The opposite ordering is explicit too: while an exclusive generation
    // operation owns the lock, a relevant mutation cannot finish its trigger.
    // Once released, the mutation proceeds and must enqueue the new revision.
    let mut generation_gate = pool.begin().await.expect("begin exclusive generation gate");
    sqlx::query("SELECT pg_advisory_xact_lock(hashtextextended('weltgewebe.search.generation.activation', 0))")
        .execute(&mut *generation_gate)
        .await
        .expect("take exclusive generation gate");
    let mutation_pool = pool.clone();
    let after_activation = tokio::spawn(async move {
        sqlx::query("UPDATE domain_nodes SET title='D' WHERE id=$1")
            .bind(node)
            .execute(&mutation_pool)
            .await
    });
    sleep(Duration::from_millis(50)).await;
    assert!(
        !after_activation.is_finished(),
        "domain mutation bypassed exclusive generation lock"
    );
    generation_gate
        .commit()
        .await
        .expect("release exclusive generation gate");
    after_activation
        .await
        .expect("post-activation mutation join")
        .expect("post-activation mutation");
    let pending_version: i64 = sqlx::query_scalar(
        "SELECT max(source_version) FROM search_projection_jobs WHERE generation_id=$1 AND node_id=$2 AND state='pending'",
    )
    .bind(generation)
    .bind(node)
    .fetch_one(&pool)
    .await
    .expect("post-activation pending version");
    assert_eq!(pending_version, 4);
}

#[tokio::test]
#[ignore = "requires T005_DATABASE_URL pointing to direct disposable PostgreSQL"]
async fn concurrent_generation_finishes_serialize_ready_transition_and_keep_counters_current() {
    let pool = pool().await;
    migrate(&pool).await;
    reset_search_state(&pool).await;
    let node = "t005-concurrent-ready-node";
    sqlx::query("INSERT INTO domain_nodes (id,kind,title,payload) VALUES ($1,'Werkstatt','Ready Race',$2::jsonb)")
        .bind(node)
        .bind(r#"{"search_visibility":"public"}"#)
        .execute(&pool)
        .await
        .expect("insert concurrent ready node");

    let barrier = Arc::new(Barrier::new(2));
    let provider = Arc::new(BarrierProvider {
        barrier: barrier.clone(),
    });
    let worker_a = Arc::new(
        ProjectionWorker::new_with_provider(
            pool.clone(),
            "t005-ready-race-a".to_owned(),
            Metrics::try_new(BuildInfo::collect()).expect("metrics a"),
            provider.clone(),
        )
        .expect("worker a"),
    );
    let worker_b = Arc::new(
        ProjectionWorker::new_with_provider(
            pool.clone(),
            "t005-ready-race-b".to_owned(),
            Metrics::try_new(BuildInfo::collect()).expect("metrics b"),
            provider,
        )
        .expect("worker b"),
    );

    for generation_id in ["t005-ready-race-gen-a", "t005-ready-race-gen-b"] {
        worker_a
            .start_generation(GenerationSpec {
                generation_id,
                provider: "local:ollama",
                model_id: "m",
                model_revision: "r",
                runtime_identity: "ollama:test@http://127.0.0.1:11434",
                dimension: 3,
            })
            .await
            .expect("start concurrent generation");
    }

    let first_worker = worker_a.clone();
    let second_worker = worker_b.clone();
    let (first, second) = tokio::join!(
        async move { first_worker.claim_and_process_one().await },
        async move { second_worker.claim_and_process_one().await }
    );
    assert_eq!(
        first.expect("first concurrent finish"),
        ProcessOutcome::Processed
    );
    assert_eq!(
        second.expect("second concurrent finish"),
        ProcessOutcome::Processed
    );

    let generations: Vec<(String, String, i64, i64)> = sqlx::query_as(
        "SELECT generation_id,state,expected_nodes,completed_nodes FROM search_index_generations WHERE generation_id IN ('t005-ready-race-gen-a','t005-ready-race-gen-b') ORDER BY generation_id",
    )
    .fetch_all(&pool)
    .await
    .expect("concurrent generation states");
    assert_eq!(generations.len(), 2);
    assert_eq!(generations.iter().filter(|row| row.1 == "ready").count(), 1);
    assert_eq!(
        generations.iter().filter(|row| row.1 == "building").count(),
        1
    );
    assert!(generations.iter().all(|row| row.2 == 1 && row.3 == 1));

    let building: String = generations
        .iter()
        .find(|row| row.1 == "building")
        .expect("one complete building generation")
        .0
        .clone();
    sqlx::query("SELECT weltgewebe_activate_search_generation($1)")
        .bind(&building)
        .execute(&pool)
        .await
        .expect("complete building generation remains directly activatable");
    let active: String = sqlx::query_scalar(
        "SELECT generation_id FROM search_index_generations WHERE state='active'",
    )
    .fetch_one(&pool)
    .await
    .expect("active generation after concurrent finish");
    assert_eq!(active, building);
}

#[tokio::test]
#[ignore = "requires T005_DATABASE_URL pointing to direct disposable PostgreSQL"]
async fn reclaimed_lease_fences_the_old_worker_before_projection_mutation() {
    let pool = pool().await;
    migrate(&pool).await;
    reset_search_state(&pool).await;
    let node = "t005-lease-fence-node";
    let generation = "t005-lease-fence-generation";
    sqlx::query("INSERT INTO domain_nodes (id,kind,title,payload) VALUES ($1,'Werkstatt','Lease',$2::jsonb)")
        .bind(node)
        .bind(r#"{"search_visibility":"public"}"#)
        .execute(&pool)
        .await
        .expect("insert lease node");

    let entered = Arc::new(Notify::new());
    let release = Arc::new(Notify::new());
    let slow = ProjectionWorker::new_with_provider(
        pool.clone(),
        "t005-lease-slow".to_owned(),
        Metrics::try_new(BuildInfo::collect()).expect("metrics"),
        Arc::new(BlockingProvider {
            entered: entered.clone(),
            release: release.clone(),
        }),
    )
    .expect("slow worker");
    slow.start_generation(GenerationSpec {
        generation_id: generation,
        provider: "local:ollama",
        model_id: "m",
        model_revision: "r",
        runtime_identity: "ollama:test@http://127.0.0.1:11434",
        dimension: 3,
    })
    .await
    .expect("start lease generation");

    let slow_task = tokio::spawn(async move { slow.claim_and_process_one().await });
    entered.notified().await;
    sqlx::query("UPDATE search_projection_jobs SET claim_until=NOW()-INTERVAL '1 second' WHERE generation_id=$1 AND state='claimed'")
        .bind(generation)
        .execute(&pool)
        .await
        .expect("expire first claim");

    let fast = worker(
        pool.clone(),
        "t005-lease-fast",
        Arc::new(FakeProvider {
            unavailable: AtomicBool::new(false),
        }),
    );
    assert_eq!(
        fast.claim_and_process_one().await.expect("reclaimed job"),
        ProcessOutcome::Processed
    );
    release.notify_one();
    assert_eq!(
        slow_task
            .await
            .expect("slow task join")
            .expect("slow result"),
        ProcessOutcome::LeaseLost
    );
    let job: (String, i32) = sqlx::query_as(
        "SELECT state,attempt_count FROM search_projection_jobs WHERE generation_id=$1",
    )
    .bind(generation)
    .fetch_one(&pool)
    .await
    .expect("lease job state");
    assert_eq!(job, ("done".into(), 2));
    let projection_count: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM search_node_projections WHERE generation_id=$1 AND node_id=$2",
    )
    .bind(generation)
    .bind(node)
    .fetch_one(&pool)
    .await
    .expect("lease projection count");
    assert_eq!(projection_count, 1);
}

#[tokio::test]
#[ignore = "requires T005_DATABASE_URL pointing to direct disposable PostgreSQL"]
async fn empty_integrity_digest_binds_generation_identity_but_not_generation_id() {
    let pool = pool().await;
    migrate(&pool).await;
    reset_search_state(&pool).await;
    let provider = Arc::new(FakeProvider {
        unavailable: AtomicBool::new(false),
    });
    let worker = worker(pool, "t005-empty-digest", provider);
    for (generation_id, revision) in [
        ("t005-empty-a", "r1"),
        ("t005-empty-b", "r2"),
        ("t005-empty-c", "r1"),
    ] {
        worker
            .start_generation(GenerationSpec {
                generation_id,
                provider: "local:ollama",
                model_id: "m",
                model_revision: revision,
                runtime_identity: "ollama:test@http://127.0.0.1:11434",
                dimension: 3,
            })
            .await
            .expect("start empty digest generation");
    }
    let first = worker
        .integrity_digest("t005-empty-a")
        .await
        .expect("digest A");
    let changed = worker
        .integrity_digest("t005-empty-b")
        .await
        .expect("digest B");
    let same = worker
        .integrity_digest("t005-empty-c")
        .await
        .expect("digest C");
    assert_eq!(first, same);
    assert_ne!(first, changed);
}

#[tokio::test]
#[ignore = "requires T005_DATABASE_URL pointing to direct disposable PostgreSQL"]
async fn invalid_projection_document_fails_terminally_without_lease_cycle() {
    let pool = pool().await;
    migrate(&pool).await;
    reset_search_state(&pool).await;
    let node = "t005-invalid-document-node";
    let generation = "t005-invalid-document-generation";
    sqlx::query(
        "INSERT INTO domain_nodes (id,kind,title,payload) VALUES ($1,'Werkstatt','   ',$2::jsonb)",
    )
    .bind(node)
    .bind(r#"{"search_visibility":"public"}"#)
    .execute(&pool)
    .await
    .expect("insert invalid projection document");
    let worker = worker(
        pool.clone(),
        "t005-invalid-document-worker",
        Arc::new(FakeProvider {
            unavailable: AtomicBool::new(false),
        }),
    );
    worker
        .start_generation(GenerationSpec {
            generation_id: generation,
            provider: "local:ollama",
            model_id: "m",
            model_revision: "r",
            runtime_identity: "ollama:test@http://127.0.0.1:11434",
            dimension: 3,
        })
        .await
        .expect("start invalid document generation");
    assert_eq!(
        worker
            .claim_and_process_one()
            .await
            .expect("process invalid document"),
        ProcessOutcome::Failed
    );
    let failed: (String, i32, Option<String>) = sqlx::query_as(
        "SELECT state,attempt_count,last_error_code FROM search_projection_jobs WHERE generation_id=$1 AND node_id=$2",
    )
    .bind(generation)
    .bind(node)
    .fetch_one(&pool)
    .await
    .expect("invalid document job state");
    assert_eq!(failed.0, "failed");
    assert_eq!(failed.1, 1);
    assert_eq!(failed.2.as_deref(), Some("document_invalid"));
    assert_eq!(
        worker
            .claim_and_process_one()
            .await
            .expect("no invalid document reclaim"),
        ProcessOutcome::Empty
    );
}

#[tokio::test]
#[ignore = "requires T005_DATABASE_URL plus explicit live Ollama identity environment"]
async fn search_backfill_binary_projects_with_live_local_provider_without_activation() {
    if std::env::var("T005_RUN_LIVE_OLLAMA_E2E").as_deref() != Ok("1") {
        return;
    }
    let pool = pool().await;
    migrate(&pool).await;
    reset_search_state(&pool).await;
    let node = "t005-backfill-e2e-node";
    let generation = "t005-backfill-e2e-generation";
    sqlx::query("INSERT INTO domain_nodes (id,kind,title,payload) VALUES ($1,'Werkstatt','Backfill E2E',$2::jsonb)")
        .bind(node)
        .bind(r#"{"summary":"lokaler Providerpfad","search_visibility":"public"}"#)
        .execute(&pool)
        .await
        .expect("insert E2E node");

    let database_url = std::env::var("T005_DATABASE_URL").expect("T005_DATABASE_URL");
    let ollama_url = std::env::var("T005_LIVE_OLLAMA_URL").expect("T005_LIVE_OLLAMA_URL");
    let model_id = std::env::var("T005_LIVE_OLLAMA_MODEL_ID").expect("model id");
    let model_revision = std::env::var("T005_LIVE_OLLAMA_MODEL_REVISION").expect("model revision");
    let runtime_identity =
        std::env::var("T005_LIVE_OLLAMA_RUNTIME_IDENTITY").expect("runtime identity");
    let dimension = std::env::var("T005_LIVE_OLLAMA_DIMENSION").expect("dimension");

    let output = std::process::Command::new(env!("CARGO_BIN_EXE_search-backfill"))
        .env("DATABASE_URL", &database_url)
        .env("WELTGEWEBE_SEARCH_GENERATION_ID", generation)
        .env("WELTGEWEBE_SEARCH_BACKFILL_MAX_JOBS", "10")
        .env("WELTGEWEBE_SEARCH_OLLAMA_URL", &ollama_url)
        .env("WELTGEWEBE_SEARCH_PROVIDER", "local:ollama")
        .env("WELTGEWEBE_SEARCH_MODEL_ID", &model_id)
        .env("WELTGEWEBE_SEARCH_MODEL_REVISION", &model_revision)
        .env("WELTGEWEBE_SEARCH_RUNTIME_IDENTITY", &runtime_identity)
        .env("WELTGEWEBE_SEARCH_DIMENSION", &dimension)
        .output()
        .expect("run search-backfill binary");
    assert!(
        output.status.success(),
        "search-backfill failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let stdout = String::from_utf8(output.stdout).expect("utf8 backfill stdout");
    assert!(stdout.contains("search backfill processed 1 jobs; generation remains unactivated"));
    assert!(!stdout.contains("Backfill E2E"));
    assert!(!stdout.contains("lokaler Providerpfad"));

    let projection: (i64, String, String) = sqlx::query_as(
        "SELECT source_version,semantic_state,status FROM search_node_projections WHERE generation_id=$1 AND node_id=$2",
    )
    .bind(generation)
    .bind(node)
    .fetch_one(&pool)
    .await
    .expect("E2E projection");
    assert_eq!(projection.0, 1);
    assert_eq!(projection.1, "ready");
    assert_eq!(projection.2, "active");
    let generation_state: String =
        sqlx::query_scalar("SELECT state FROM search_index_generations WHERE generation_id=$1")
            .bind(generation)
            .fetch_one(&pool)
            .await
            .expect("E2E generation state");
    assert_eq!(generation_state, "ready");
    let active_count: i64 =
        sqlx::query_scalar("SELECT count(*) FROM search_index_generations WHERE state='active'")
            .fetch_one(&pool)
            .await
            .expect("active generation count");
    assert_eq!(active_count, 0);
}

#[tokio::test]
async fn t006_search_api_against_postgres_projections() {
    let database_url = match std::env::var("T005_DATABASE_URL") {
        Ok(url) => url,
        Err(_) => return,
    };
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await
        .expect("connect T005 database");
    migrate(&pool).await;
    reset_search_state(&pool).await;

    let generation_spec = GenerationSpec {
        generation_id: "derived-below",
        provider: "local:ollama",
        model_id: "qwen3-embedding:4b",
        model_revision: "sha256:4b",
        runtime_identity: "ollama:test",
        dimension: 2,
    };
    let gen_id = generation_spec.derived_id();
    sqlx::query(
        "INSERT INTO search_index_generations (generation_id, provider, model_id, model_revision, runtime_identity, dimension, document_revision, normalization_revision, ranking_revision, state, activated_at) \
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'active', NOW())",
    )
    .bind(&gen_id)
    .bind(generation_spec.provider)
    .bind(generation_spec.model_id)
    .bind(generation_spec.model_revision)
    .bind(generation_spec.runtime_identity)
    .bind(generation_spec.dimension)
    .bind(DOCUMENT_REVISION)
    .bind(NORMALIZATION_REVISION)
    .bind(RANKING_REVISION)
    .execute(&pool)
    .await
    .expect("insert identity-bound active generation");

    let nodes = [
        (
            "t005-public-node",
            "Werkstatt",
            "Fahrrad Werkstatt",
            r#"{"search_visibility":"public","summary":"Reparatur"}"#,
            vec![1.0, -1.0],
        ),
        (
            "t005-public-b-node",
            "Treffpunkt",
            "Fahrrad Hilfe",
            r#"{"search_visibility":"public","summary":"Hilfe"}"#,
            vec![1.0, -1.0],
        ),
        (
            "t005-hidden-node",
            "Werkstatt",
            "Geheime Fahrrad Werkstatt",
            r#"{"search_visibility":"hidden","summary":"Geheim"}"#,
            vec![0.25, 0.25],
        ),
        (
            "t005-private-node",
            "Werkstatt",
            "Private Fahrrad Werkstatt",
            r#"{"search_visibility":"private","created_by_account_id":"owner-a","summary":"Privat"}"#,
            vec![0.25, 0.25],
        ),
        (
            "t005-stale-node",
            "Werkstatt",
            "Stale Fahrrad Werkstatt",
            r#"{"search_visibility":"public","summary":"Alt"}"#,
            vec![0.25, 0.25],
        ),
        (
            "t005-revoked-node",
            "Werkstatt",
            "Widerrufene Fahrrad Werkstatt",
            r#"{"search_visibility":"public","summary":"Widerruf"}"#,
            vec![0.25, 0.25],
        ),
        (
            "t005-deleted-node",
            "Werkstatt",
            "Geloeschte Fahrrad Werkstatt",
            r#"{"search_visibility":"public","summary":"Loeschen"}"#,
            vec![0.25, 0.25],
        ),
        (
            "t005-legacy-node",
            "Werkstatt",
            "Legacy Fahrrad Werkstatt",
            r#"{"search_visibility":"legacy","summary":"Legacy"}"#,
            vec![0.25, 0.25],
        ),
        (
            "t005-wrong-dimension-node",
            "Werkstatt",
            "Dimension Fahrrad Werkstatt",
            r#"{"search_visibility":"public","summary":"Dimension"}"#,
            vec![1.0],
        ),
    ];

    for (index, (id, kind, title, payload, embedding)) in nodes.iter().enumerate() {
        sqlx::query(
            "INSERT INTO domain_nodes (id, kind, title, lat, lon, created_at, updated_at, payload) VALUES ($1, $2, $3, 0.0, 0.0, NOW(), NOW(), $4::jsonb)",
        )
        .bind(id)
        .bind(kind)
        .bind(title)
        .bind(payload)
        .execute(&pool)
        .await
        .expect("insert T006 domain node");
        let content_sha = format!("{:064x}", index + 1);
        sqlx::query(
            "INSERT INTO search_node_projections (generation_id, node_id, source_version, source_revision, content_sha256, title, tags, searchable_text, language, kind, status, visibility_scopes, semantic_state, embedding) \
             SELECT $1, v.node_id, v.source_version, v.source_revision, $3, n.title, ARRAY[]::text[], n.title, 'de', n.kind, 'active', ARRAY['public'], 'ready', $4 \
               FROM search_node_versions v JOIN domain_nodes n ON n.id = v.node_id WHERE v.node_id = $2",
        )
        .bind(&gen_id)
        .bind(id)
        .bind(content_sha)
        .bind(embedding)
        .execute(&pool)
        .await
        .expect("insert T006 projection");
    }

    // Mutate canonical state after projection creation. The API must reject the
    // now-stale/revoked/deleted projections before lexical or semantic ranking.
    sqlx::query(
        "UPDATE domain_nodes SET title='Stale Fahrrad Werkstatt Neu' WHERE id='t005-stale-node'",
    )
    .execute(&pool)
    .await
    .expect("make projection stale");
    sqlx::query("UPDATE domain_nodes SET payload=jsonb_set(payload, '{search_visibility}', '\"revoked\"'::jsonb) WHERE id='t005-revoked-node'")
        .execute(&pool)
        .await
        .expect("revoke visibility");
    sqlx::query("DELETE FROM domain_nodes WHERE id='t005-deleted-node'")
        .execute(&pool)
        .await
        .expect("delete domain node");

    let metrics = Metrics::try_new(BuildInfo {
        version: "test",
        commit: "test",
        build_timestamp: "test",
    })
    .expect("metrics");
    let state = ApiState {
        db_pool: Some(pool.clone()),
        db_pool_configured: true,
        nats_client: None,
        nats_configured: false,
        config: AppConfig {
            fade_days: 7,
            ron_days: 84,
            anonymize_opt_in: true,
            delegation_expire_days: 28,
            max_guest_owned_nodes: 1000,
            domain_read_source: DomainReadSource::Postgres,
            domain_account_write_source: DomainAccountWriteSource::Postgres,
            domain_node_write_source: DomainNodeWriteSource::Postgres,
            domain_edge_write_source: DomainEdgeWriteSource::Postgres,
            passkey_credential_source: weltgewebe_api::config::PasskeyCredentialSource::InMemory,
            auth_public_login: false,
            auth_cookie_secure: true,
            app_base_url: None,
            auth_trusted_proxies: None,
            auth_allow_emails: None,
            auth_allow_email_domains: None,
            auth_auto_provision: false,
            auth_auto_provision_role: weltgewebe_api::config::AutoProvisionRole::Gast,
            auth_rl_ip_per_min: None,
            auth_rl_ip_per_hour: None,
            auth_rl_email_per_min: None,
            auth_rl_email_per_hour: None,
            smtp_host: None,
            smtp_port: None,
            smtp_user: None,
            smtp_pass: None,
            smtp_from: None,
            auth_log_magic_token: false,
            webauthn_rp_id: None,
            webauthn_rp_origin: None,
            webauthn_rp_name: None,
        },
        metrics,
        sessions: weltgewebe_api::auth::session::SessionBackend::new_in_memory(),
        challenges: Default::default(),
        tokens: Default::default(),
        step_up_tokens: Default::default(),
        accounts: Arc::new(tokio::sync::RwLock::new(Default::default())),
        nodes: Arc::new(tokio::sync::RwLock::new(
            weltgewebe_api::state::OrderedCache::new(),
        )),
        nodes_persist: Arc::new(tokio::sync::Mutex::new(())),
        accounts_persist: Arc::new(tokio::sync::Mutex::new(())),
        domain_projection_gate: Arc::new(tokio::sync::RwLock::new(())),
        domain_projection_version: Arc::new(std::sync::atomic::AtomicI64::new(0)),
        edges: Arc::new(tokio::sync::RwLock::new(
            weltgewebe_api::state::OrderedCache::new(),
        )),
        rate_limiter: Arc::new(weltgewebe_api::auth::rate_limit::AuthRateLimiter::new(
            &AppConfig::load().unwrap(),
        )),
        mailer: None,
        webauthn: None,
        passkey_registrations: Default::default(),
        passkey_registration_grants: Default::default(),
        passkey_authentications: Default::default(),
        passkeys: Default::default(),
    };

    let anonymous = AuthContext {
        authenticated: false,
        account_id: None,
        device_id: None,
        role: Role::Gast,
        expires_at: None,
    };
    let owner_a = AuthContext {
        authenticated: true,
        account_id: Some("owner-a".to_string()),
        device_id: None,
        role: Role::Weber,
        expires_at: None,
    };
    let owner_b = AuthContext {
        authenticated: true,
        account_id: Some("owner-b".to_string()),
        device_id: None,
        role: Role::Weber,
        expires_at: None,
    };
    let unavailable_provider = || -> Arc<dyn EmbeddingProvider> {
        Arc::new(FakeProvider {
            unavailable: AtomicBool::new(true),
        })
    };
    let available_provider = || -> Arc<dyn EmbeddingProvider> {
        Arc::new(FakeProvider {
            unavailable: AtomicBool::new(false),
        })
    };

    let public = execute_search(
        &state,
        &anonymous,
        SearchQueryParams {
            q: Some("Fahrrad Werkstatt".to_string()),
            ..Default::default()
        },
        Some(unavailable_provider()),
    )
    .await
    .expect("public lexical fallback search");
    assert_eq!(
        public.items.first().map(|node| node.id.as_str()),
        Some("t005-public-node")
    );
    assert_eq!(public.generation_id, gen_id);
    assert_eq!(public.mode, "lexical_fallback");
    assert_eq!(
        public.fallback_reason.as_deref(),
        Some("provider_unavailable")
    );

    let filtered = execute_search(
        &state,
        &anonymous,
        SearchQueryParams {
            q: Some("Fahrrad".to_string()),
            kind: Some("Werkstatt".to_string()),
            ..Default::default()
        },
        Some(unavailable_provider()),
    )
    .await
    .expect("filtered search");
    assert!(filtered.items.iter().all(|node| node.kind == "Werkstatt"));
    assert!(!filtered
        .items
        .iter()
        .any(|node| node.id == "t005-public-b-node"));

    for (forbidden_id, forbidden_title) in [
        ("t005-hidden-node", "Geheime Fahrrad Werkstatt"),
        ("t005-stale-node", "Stale Fahrrad Werkstatt"),
        ("t005-revoked-node", "Widerrufene Fahrrad Werkstatt"),
        ("t005-deleted-node", "Geloeschte Fahrrad Werkstatt"),
        ("t005-legacy-node", "Legacy Fahrrad Werkstatt"),
        ("t005-wrong-dimension-node", "Dimension Fahrrad Werkstatt"),
    ] {
        let result = execute_search(
            &state,
            &anonymous,
            SearchQueryParams {
                q: Some(forbidden_title.to_string()),
                ..Default::default()
            },
            Some(unavailable_provider()),
        )
        .await
        .expect("fail-closed lexical search");
        assert!(
            !result.items.iter().any(|node| node.id == forbidden_id),
            "{forbidden_id} must stay invisible even when other public lexical matches remain"
        );
    }

    let private_anonymous = execute_search(
        &state,
        &anonymous,
        SearchQueryParams {
            q: Some("Private Fahrrad Werkstatt".to_string()),
            ..Default::default()
        },
        Some(unavailable_provider()),
    )
    .await
    .expect("anonymous private search");
    assert!(!private_anonymous
        .items
        .iter()
        .any(|node| node.id == "t005-private-node"));

    let private_owner = execute_search(
        &state,
        &owner_a,
        SearchQueryParams {
            q: Some("Private Fahrrad Werkstatt".to_string()),
            ..Default::default()
        },
        Some(unavailable_provider()),
    )
    .await
    .expect("owner private search");
    assert!(private_owner
        .items
        .iter()
        .any(|node| node.id == "t005-private-node"));

    // Authorization changes are read from canonical domain state. Refresh only
    // the projection identity to model a completed re-projection after ownership
    // changed; the old owner must immediately lose access and the new owner gain it.
    sqlx::query("UPDATE domain_nodes SET payload=jsonb_set(payload, '{created_by_account_id}', '\"owner-b\"'::jsonb) WHERE id='t005-private-node'")
        .execute(&pool)
        .await
        .expect("change private owner");
    sqlx::query(
        "UPDATE search_node_projections p SET source_version=v.source_version, source_revision=v.source_revision \
           FROM search_node_versions v WHERE p.generation_id=$1 AND p.node_id='t005-private-node' AND v.node_id=p.node_id",
    )
    .bind(&gen_id)
    .execute(&pool)
    .await
    .expect("refresh private projection identity");

    let old_owner = execute_search(
        &state,
        &owner_a,
        SearchQueryParams {
            q: Some("Private Fahrrad Werkstatt".to_string()),
            ..Default::default()
        },
        Some(unavailable_provider()),
    )
    .await
    .expect("old owner search");
    assert!(!old_owner
        .items
        .iter()
        .any(|node| node.id == "t005-private-node"));
    let new_owner = execute_search(
        &state,
        &owner_b,
        SearchQueryParams {
            q: Some("Private Fahrrad Werkstatt".to_string()),
            ..Default::default()
        },
        Some(unavailable_provider()),
    )
    .await
    .expect("new owner search");
    assert!(new_owner
        .items
        .iter()
        .any(|node| node.id == "t005-private-node"));

    // Hidden/private candidates carry deliberately misleading public projection
    // scopes and high semantic similarity. Anonymous semantic retrieval still
    // cannot see them because canonical authorization ran before ranking.
    let semantic = execute_search(
        &state,
        &anonymous,
        SearchQueryParams {
            q: Some("voellig fremder begriff".to_string()),
            ..Default::default()
        },
        Some(available_provider()),
    )
    .await
    .expect("semantic authorization boundary");
    assert!(semantic.items.is_empty());

    let provider_contract_failure = execute_search(
        &state,
        &anonymous,
        SearchQueryParams {
            q: Some("Fahrrad Werkstatt".to_string()),
            ..Default::default()
        },
        Some(Arc::new(PermanentFailureProvider)),
    )
    .await;
    assert!(matches!(
        provider_contract_failure,
        Err(SearchError::ProviderContractError(
            EmbeddingProviderError::InvalidVector
        ))
    ));

    // Generation identity tampering is not a degradable provider outage.
    sqlx::query(
        "UPDATE search_index_generations SET runtime_identity='tampered' WHERE generation_id=$1",
    )
    .bind(&gen_id)
    .execute(&pool)
    .await
    .expect("tamper generation identity");
    let tampered = execute_search(
        &state,
        &anonymous,
        SearchQueryParams {
            q: Some("Fahrrad Werkstatt".to_string()),
            ..Default::default()
        },
        Some(unavailable_provider()),
    )
    .await;
    assert!(matches!(tampered, Err(SearchError::Unavailable)));
}

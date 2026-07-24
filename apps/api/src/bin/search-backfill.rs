//! Bounded, resumable internal T005 projection backfill.  It has no HTTP role.

use std::{env, sync::Arc};

use sqlx::{postgres::PgPoolOptions, PgPool};
use weltgewebe_api::{
    search::{
        EmbeddingProvider, GenerationSpec, OllamaEmbeddingProvider, ProcessOutcome,
        ProjectionWorker, DOCUMENT_REVISION, NORMALIZATION_REVISION, RANKING_REVISION,
    },
    telemetry::{BuildInfo, Metrics},
};

fn required(name: &str) -> anyhow::Result<String> {
    env::var(name).map_err(|_| anyhow::anyhow!("{name} is required"))
}

async fn ensure_generation_identity(
    pool: &PgPool,
    generation: &GenerationSpec<'_>,
) -> anyhow::Result<()> {
    let exact: bool = sqlx::query_scalar(
        "SELECT EXISTS ( \
            SELECT 1 FROM search_index_generations \
            WHERE generation_id=$1 AND provider=$2 AND model_id=$3 \
              AND model_revision=$4 AND runtime_identity=$5 AND dimension=$6 \
              AND document_revision=$7 AND normalization_revision=$8 \
              AND ranking_revision=$9 AND state IN ('building','ready','active') \
        )",
    )
    .bind(generation.generation_id)
    .bind(generation.provider)
    .bind(generation.model_id)
    .bind(generation.model_revision)
    .bind(generation.runtime_identity)
    .bind(generation.dimension)
    .bind(DOCUMENT_REVISION)
    .bind(NORMALIZATION_REVISION)
    .bind(RANKING_REVISION)
    .fetch_one(pool)
    .await?;
    if !exact {
        anyhow::bail!("search worker generation identity mismatch");
    }
    Ok(())
}

async fn generation_bound_pool(database_url: &str, generation_id: String) -> anyhow::Result<PgPool> {
    Ok(PgPoolOptions::new()
        .max_connections(2)
        .after_connect(move |connection, _metadata| {
            let generation_id = generation_id.clone();
            Box::pin(async move {
                sqlx::query(
                    "SELECT set_config('weltgewebe.search_generation_id',$1,false)",
                )
                .bind(generation_id)
                .execute(&mut *connection)
                .await?;
                sqlx::query("SET search_path TO pg_temp, public")
                    .execute(&mut *connection)
                    .await?;
                // A simple temporary view is automatically updatable. It shadows
                // the base queue for every unqualified worker query, including
                // SELECT ... FOR UPDATE, UPDATE ... RETURNING and lease cleanup.
                // Unlike RLS this boundary also applies when the session user is
                // a PostgreSQL superuser.
                sqlx::query(
                    "CREATE TEMP VIEW search_projection_jobs AS \
                     SELECT * FROM public.search_projection_jobs \
                     WHERE generation_id = current_setting('weltgewebe.search_generation_id')",
                )
                .execute(&mut *connection)
                .await?;
                Ok(())
            })
        })
        .connect(database_url)
        .await?)
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let database_url = required("DATABASE_URL")?;
    let generation_id = required("WELTGEWEBE_SEARCH_GENERATION_ID")?;
    let provider_name = required("WELTGEWEBE_SEARCH_PROVIDER")?;
    let model_id = required("WELTGEWEBE_SEARCH_MODEL_ID")?;
    let model_revision = required("WELTGEWEBE_SEARCH_MODEL_REVISION")?;
    let runtime_identity = required("WELTGEWEBE_SEARCH_RUNTIME_IDENTITY")?;
    let dimension: i32 = required("WELTGEWEBE_SEARCH_DIMENSION")?.parse()?;
    let generation = GenerationSpec {
        generation_id: &generation_id,
        provider: &provider_name,
        model_id: &model_id,
        model_revision: &model_revision,
        runtime_identity: &runtime_identity,
        dimension,
    };
    generation.validate()?;

    let max_jobs: usize = env::var("WELTGEWEBE_SEARCH_BACKFILL_MAX_JOBS")
        .unwrap_or_else(|_| "100".to_string())
        .parse()?;
    if max_jobs == 0 || max_jobs > 10_000 {
        anyhow::bail!("WELTGEWEBE_SEARCH_BACKFILL_MAX_JOBS must be 1..=10000");
    }

    // Generation creation needs the canonical base tables, including ON
    // CONFLICT on the real queue. Leased processing uses a separate pool whose
    // temporary view makes every queue operation generation-local.
    let control_pool = PgPoolOptions::new()
        .max_connections(2)
        .connect(&database_url)
        .await?;
    let worker_pool = generation_bound_pool(&database_url, generation_id.clone()).await?;

    let provider: Arc<dyn EmbeddingProvider> = Arc::new(
        OllamaEmbeddingProvider::new(
            &required("WELTGEWEBE_SEARCH_OLLAMA_URL")?,
            model_id.clone(),
            model_revision.clone(),
            runtime_identity.clone(),
        )
        .map_err(|error| anyhow::anyhow!("invalid local Ollama provider: {}", error.code()))?,
    );
    let generation_control = ProjectionWorker::new_with_provider(
        control_pool.clone(),
        format!("generation-control:{}:{}", generation_id, std::process::id()),
        Metrics::try_new(BuildInfo::collect())?,
        provider.clone(),
    )?;
    generation_control
        .start_generation(generation.clone())
        .await?;
    let worker = ProjectionWorker::new_with_provider(
        worker_pool,
        format!("backfill:{}:{}", generation_id, std::process::id()),
        Metrics::try_new(BuildInfo::collect())?,
        provider,
    )?;

    let mut completed = 0usize;
    while completed < max_jobs {
        // Re-read the complete stored identity before every leased mutation.
        // A changed or mismatched generation fails closed before claiming work.
        ensure_generation_identity(&control_pool, &generation).await?;
        match worker.claim_and_process_one().await? {
            ProcessOutcome::Empty => break,
            _ => completed += 1,
        }
    }
    // Deliberately no auto-activation: an operator invokes the atomic database
    // gate only after examining the bounded run's aggregate state.
    println!(
        "search backfill processed {completed} jobs for {generation_id}; generation remains unactivated"
    );
    Ok(())
}

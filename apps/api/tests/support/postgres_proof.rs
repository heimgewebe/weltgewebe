#![allow(dead_code)]

use serde::Deserialize;
use url::Url;

#[derive(Debug, Deserialize)]
struct PostgresProofContract {
    schema_version: u32,
    disposable_database_name_segments: Vec<String>,
    pgbouncer_port: u16,
}

fn contract() -> PostgresProofContract {
    let parsed: PostgresProofContract = serde_json::from_str(include_str!(
        "../../../../scripts/ci/postgres-proof-contract.json"
    ))
    .expect("postgres proof contract JSON must parse");
    assert_eq!(
        parsed.schema_version, 1,
        "unsupported postgres proof contract schema"
    );
    assert!(
        !parsed.disposable_database_name_segments.is_empty(),
        "postgres proof contract must define disposable database segments"
    );
    parsed
}

pub fn assert_disposable_database_name(name: &str) {
    let contract = contract();
    assert!(
        !name.is_empty()
            && name.chars().all(|character| {
                character.is_ascii_alphanumeric() || matches!(character, '_' | '-' | '.')
            }),
        "PostgreSQL proof refuses unsafe disposable database identifier {name:?}"
    );
    let final_segment = name
        .split(['_', '-', '.'])
        .filter(|segment| !segment.is_empty())
        .next_back();
    assert!(
        name.starts_with("weltgewebe_")
            && final_segment.is_some_and(|segment| {
                contract
                    .disposable_database_name_segments
                    .iter()
                    .any(|expected| segment == expected)
            }),
        "PostgreSQL proof refuses non-disposable database name {name:?}; expected weltgewebe_ prefix and final delimited segment from {:?}",
        contract.disposable_database_name_segments
    );
}

pub fn validated_direct_disposable_url(raw: String) -> String {
    assert_direct_disposable_database_url(&raw);
    raw
}

pub fn assert_direct_disposable_database_url(raw: &str) {
    let contract = contract();
    let url = Url::parse(raw).expect("PostgreSQL proof URL must parse");
    assert!(
        matches!(url.scheme(), "postgres" | "postgresql"),
        "PostgreSQL proof URL must use postgres/postgresql scheme"
    );
    assert!(
        url.host_str().is_some(),
        "PostgreSQL proof URL must contain a host"
    );
    assert_ne!(
        url.port().unwrap_or(5432),
        contract.pgbouncer_port,
        "PostgreSQL proof requires direct PostgreSQL, not PgBouncer"
    );
    let database = url.path().trim_start_matches('/');
    assert!(
        !database.contains('%'),
        "PostgreSQL proof database path must not contain percent-encoding"
    );
    assert_disposable_database_name(database);
}

#[cfg(test)]
mod t012_generation_boundary {
    use std::{path::PathBuf, sync::Arc};

    use async_trait::async_trait;
    use sqlx::{postgres::PgPoolOptions, PgPool};
    use weltgewebe_api::{
        search::{
            EmbeddingProvider, EmbeddingProviderError, GenerationSpec, ProcessOutcome,
            ProjectionWorker, DOCUMENT_REVISION, NORMALIZATION_REVISION, RANKING_REVISION,
        },
        telemetry::{BuildInfo, Metrics},
    };

    use super::assert_direct_disposable_database_url;

    fn runs_in_projection_worker_target() -> bool {
        module_path!().starts_with("db_semantic_search_projection_worker::")
    }

    fn database_url() -> String {
        let url = std::env::var("T005_DATABASE_URL")
            .expect("T005_DATABASE_URL must point to a direct disposable PostgreSQL database");
        assert_direct_disposable_database_url(&url);
        url
    }

    async fn pool() -> PgPool {
        PgPoolOptions::new()
            .max_connections(5)
            .connect(&database_url())
            .await
            .expect("connect T012 PostgreSQL")
    }

    async fn generation_bound_pool(generation_id: &str) -> PgPool {
        let generation_id = generation_id.to_owned();
        PgPoolOptions::new()
            .max_connections(2)
            .after_connect(move |connection, _metadata| {
                let generation_id = generation_id.clone();
                Box::pin(async move {
                    sqlx::query("SELECT set_config('weltgewebe.search_generation_id',$1,false)")
                        .bind(generation_id)
                        .execute(&mut *connection)
                        .await?;
                    sqlx::query("SET search_path TO pg_temp, public")
                        .execute(&mut *connection)
                        .await?;
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
            .connect(&database_url())
            .await
            .expect("connect generation-bound T012 PostgreSQL")
    }

    async fn migrate(pool: &PgPool) {
        let migrations = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("migrations");
        sqlx::migrate::Migrator::new(migrations)
            .await
            .expect("load migrations")
            .run(pool)
            .await
            .expect("run migrations");
    }

    async fn reset(pool: &PgPool) {
        sqlx::query("DELETE FROM domain_nodes WHERE id LIKE 't012-%'")
            .execute(pool)
            .await
            .expect("remove T012 nodes");
        sqlx::query(
            "TRUNCATE search_projection_jobs, search_node_projections, search_node_versions, search_index_generations RESTART IDENTITY CASCADE",
        )
        .execute(pool)
        .await
        .expect("reset T012 projection state");
    }

    #[derive(Default)]
    struct FakeProvider;

    #[async_trait]
    impl EmbeddingProvider for FakeProvider {
        async fn embed(
            &self,
            _document: &str,
            dimension: usize,
        ) -> Result<Vec<f64>, EmbeddingProviderError> {
            Ok(vec![0.5; dimension])
        }
    }

    fn exact_generation_spec<'a>(revision: &'a str) -> GenerationSpec<'a> {
        let draft = GenerationSpec {
            generation_id: "",
            provider: "local:ollama",
            model_id: "t012-test-model",
            model_revision: revision,
            runtime_identity: "ollama:t012@http://127.0.0.1:11434",
            dimension: 3,
        };
        let generation_id: &'static str = Box::leak(draft.derived_id().into_boxed_str());
        GenerationSpec {
            generation_id,
            ..draft
        }
    }

    fn worker(pool: PgPool, id: &str) -> ProjectionWorker {
        ProjectionWorker::new_with_provider(
            pool,
            id.to_owned(),
            Metrics::try_new(BuildInfo::collect()).expect("metrics"),
            Arc::new(FakeProvider),
        )
        .expect("worker")
    }

    #[tokio::test]
    #[ignore = "runs through the canonical direct disposable PostgreSQL proof"]
    async fn generation_binding_and_quiet_visibility_migration_are_db_proven() {
        // This support module is shared by every PostgreSQL target. Execute the
        // destructive T012 proof only in the already-canonical semantic worker
        // target; all other targets return before opening the database.
        if !runs_in_projection_worker_target() {
            return;
        }

        let unbound = pool().await;
        migrate(&unbound).await;
        reset(&unbound).await;

        sqlx::query(
            "INSERT INTO domain_nodes (id,kind,title,payload,search_visibility) VALUES ('t012-bound-node','Werkstatt','Gebundener Knoten','{}'::jsonb,'public')",
        )
        .execute(&unbound)
        .await
        .expect("insert bound node");

        let spec_a = exact_generation_spec("revision-a");
        let generation_a = spec_a.generation_id.to_owned();
        let spec_b = exact_generation_spec("revision-b");
        let generation_b = spec_b.generation_id.to_owned();
        let setup = worker(unbound.clone(), "t012-setup");
        setup
            .start_generation(spec_a)
            .await
            .expect("start generation A");
        setup
            .start_generation(spec_b)
            .await
            .expect("start generation B");

        let bound = generation_bound_pool(&generation_a).await;
        let configured: String =
            sqlx::query_scalar("SELECT current_setting('weltgewebe.search_generation_id')")
                .fetch_one(&bound)
                .await
                .expect("read session generation binding");
        assert_eq!(configured, generation_a);
        let visible_jobs: i64 = sqlx::query_scalar("SELECT count(*) FROM search_projection_jobs")
            .fetch_one(&bound)
            .await
            .expect("read generation-local queue view");
        assert_eq!(visible_jobs, 1);

        let bound_worker = worker(bound, "t012-bound-a");
        assert_eq!(
            bound_worker
                .claim_and_process_one()
                .await
                .expect("process generation A"),
            ProcessOutcome::Processed
        );
        assert_eq!(
            bound_worker
                .claim_and_process_one()
                .await
                .expect("foreign generation remains invisible"),
            ProcessOutcome::Empty
        );

        let states: Vec<(String, String)> = sqlx::query_as(
            "SELECT generation_id,state FROM search_projection_jobs WHERE node_id='t012-bound-node' ORDER BY generation_id",
        )
        .fetch_all(&unbound)
        .await
        .expect("read generation job states");
        assert_eq!(states.len(), 2);
        assert_eq!(
            states
                .iter()
                .find(|(generation, _)| generation == &generation_a)
                .map(|(_, state)| state.as_str()),
            Some("done")
        );
        assert_eq!(
            states
                .iter()
                .find(|(generation, _)| generation == &generation_b)
                .map(|(_, state)| state.as_str()),
            Some("pending")
        );
        let foreign_projection: bool = sqlx::query_scalar(
            "SELECT EXISTS (SELECT 1 FROM search_node_projections WHERE generation_id=$1 AND node_id='t012-bound-node')",
        )
        .bind(&generation_b)
        .fetch_one(&unbound)
        .await
        .expect("read foreign projection state");
        assert!(!foreign_projection);

        reset(&unbound).await;
        sqlx::raw_sql(include_str!(
            "../../migrations/20260724000002_semantic_search_projection_privacy_boundary.down.sql"
        ))
        .execute(&unbound)
        .await
        .expect("restore legacy visibility contract");

        for (id, title, payload) in [
            (
                "t012-legacy-public",
                "Legacy Public",
                r#"{"summary":"öffentlich","search_visibility":"public"}"#,
            ),
            (
                "t012-legacy-private",
                "Legacy Private",
                r#"{"summary":"privat","search_visibility":"private","created_by_account_id":"owner-a"}"#,
            ),
        ] {
            sqlx::query(
                "INSERT INTO domain_nodes (id,kind,title,payload) VALUES ($1,'Werkstatt',$2,$3::jsonb)",
            )
            .bind(id)
            .bind(title)
            .bind(payload)
            .execute(&unbound)
            .await
            .expect("insert legacy node");
        }

        let legacy_generation = "t012-legacy-generation";
        sqlx::query(
            "INSERT INTO search_index_generations (generation_id,provider,model_id,model_revision,runtime_identity,dimension,document_revision,normalization_revision,ranking_revision,state,expected_nodes,completed_nodes,activated_at) \
             VALUES ($1,'local:ollama','legacy-model','legacy-revision','ollama:legacy@http://127.0.0.1:11434',3,'node-document-v1',$2,$3,'active',2,2,clock_timestamp())",
        )
        .bind(legacy_generation)
        .bind(NORMALIZATION_REVISION)
        .bind(RANKING_REVISION)
        .execute(&unbound)
        .await
        .expect("insert active legacy generation");

        for (index, id) in ["t012-legacy-public", "t012-legacy-private"]
            .into_iter()
            .enumerate()
        {
            sqlx::query(
                "INSERT INTO search_node_projections (generation_id,node_id,source_version,source_revision,content_sha256,title,tags,searchable_text,language,kind,status,visibility_scopes,semantic_state,embedding) \
                 SELECT $1,v.node_id,v.source_version,v.source_revision,$3,n.title,'{}'::TEXT[],n.title,'de',n.kind,'active',ARRAY['public']::TEXT[],'ready',ARRAY[0.5,0.5,0.5]::DOUBLE PRECISION[] \
                 FROM search_node_versions v JOIN domain_nodes n ON n.id=v.node_id WHERE v.node_id=$2",
            )
            .bind(legacy_generation)
            .bind(id)
            .bind(format!("{:064x}", index + 1))
            .execute(&unbound)
            .await
            .expect("insert legacy projection");
        }

        let versions_before: Vec<(String, i64)> = sqlx::query_as(
            "SELECT node_id,source_version FROM search_node_versions WHERE node_id LIKE 't012-legacy-%' ORDER BY node_id",
        )
        .fetch_all(&unbound)
        .await
        .expect("read legacy versions before migration");
        let jobs_before: i64 = sqlx::query_scalar(
            "SELECT count(*) FROM search_projection_jobs WHERE generation_id=$1",
        )
        .bind(legacy_generation)
        .fetch_one(&unbound)
        .await
        .expect("read legacy jobs before migration");

        sqlx::raw_sql(include_str!(
            "../../migrations/20260724000002_semantic_search_projection_privacy_boundary.up.sql"
        ))
        .execute(&unbound)
        .await
        .expect("apply canonical visibility migration");

        let versions_after: Vec<(String, i64)> = sqlx::query_as(
            "SELECT node_id,source_version FROM search_node_versions WHERE node_id LIKE 't012-legacy-%' ORDER BY node_id",
        )
        .fetch_all(&unbound)
        .await
        .expect("read legacy versions after migration");
        assert_eq!(versions_after, versions_before);
        let jobs_after: i64 = sqlx::query_scalar(
            "SELECT count(*) FROM search_projection_jobs WHERE generation_id=$1",
        )
        .bind(legacy_generation)
        .fetch_one(&unbound)
        .await
        .expect("read legacy jobs after migration");
        assert_eq!(jobs_after, jobs_before);

        let public_projection_survives: bool = sqlx::query_scalar(
            "SELECT EXISTS (SELECT 1 FROM search_node_projections WHERE generation_id=$1 AND node_id='t012-legacy-public')",
        )
        .bind(legacy_generation)
        .fetch_one(&unbound)
        .await
        .expect("read public legacy projection");
        assert!(public_projection_survives);
        let private_projection_survives: bool = sqlx::query_scalar(
            "SELECT EXISTS (SELECT 1 FROM search_node_projections WHERE generation_id=$1 AND node_id='t012-legacy-private')",
        )
        .bind(legacy_generation)
        .fetch_one(&unbound)
        .await
        .expect("read private legacy projection");
        assert!(!private_projection_survives);

        sqlx::query(
            "UPDATE domain_nodes SET title='Legacy Public geändert' WHERE id='t012-legacy-public'",
        )
        .execute(&unbound)
        .await
        .expect("mutate post-migration legacy node");
        let legacy_job_count: i64 = sqlx::query_scalar(
            "SELECT count(*) FROM search_projection_jobs WHERE generation_id=$1",
        )
        .bind(legacy_generation)
        .fetch_one(&unbound)
        .await
        .expect("read post-migration legacy jobs");
        assert_eq!(legacy_job_count, jobs_before);

        let canonical_revision_generations: i64 = sqlx::query_scalar(
            "SELECT count(*) FROM search_index_generations WHERE document_revision=$1",
        )
        .bind(DOCUMENT_REVISION)
        .fetch_one(&unbound)
        .await
        .expect("read canonical generation count");
        assert_eq!(canonical_revision_generations, 0);
    }
}

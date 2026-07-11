pub mod auth;
pub mod config;
pub mod domain_db;
pub mod mailer;
pub mod middleware;
pub mod routes;
pub mod state;
pub mod telemetry;
pub mod utils;

#[doc(hidden)]
pub mod test_helpers;

use std::{
    collections::{hash_map::Entry, HashMap, HashSet},
    env,
    io::ErrorKind,
    net::SocketAddr,
    sync::Arc,
};

use anyhow::{anyhow, Context};
use async_nats::Client as NatsClient;
use axum::{middleware::from_fn_with_state, routing::get, Router};
use config::{
    AppConfig, DomainAccountWriteSource, DomainEdgeWriteSource, DomainNodeWriteSource,
    DomainReadSource, PasskeyCredentialSource,
};
use middleware::auth::auth_middleware;
use middleware::csrf::require_csrf;
use routes::{api_router, health::health_routes, meta::meta_routes};
use sqlx::{migrate::Migrator, postgres::PgPoolOptions, PgPool, Row};
use state::ApiState;
use telemetry::{metrics_handler, BuildInfo, Metrics, MetricsLayer};
use tokio::net::TcpListener;
use tower::ServiceBuilder;
use tower_http::request_id::{MakeRequestUuid, SetRequestIdLayer};
use tracing_subscriber::{fmt, EnvFilter};

pub async fn run() -> anyhow::Result<()> {
    // Load `.env` *before* initialising tracing so a `RUST_LOG` defined there is
    // visible to `EnvFilter::try_from_default_env()` inside `init_tracing`. The
    // load *result* must only be logged *after* the subscriber is installed —
    // otherwise these diagnostics are emitted with no subscriber and silently
    // dropped.
    let dotenv_result = dotenvy::dotenv();

    init_tracing()?;

    match &dotenv_result {
        Ok(path) => {
            tracing::debug!(?path, "loaded environment variables from .env file");
        }
        Err(dotenvy::Error::Io(io_error)) if io_error.kind() == ErrorKind::NotFound => {}
        Err(error) => {
            tracing::warn!(%error, "failed to load environment from .env file");
        }
    }

    let app_config = AppConfig::load().context("failed to load API configuration")?;

    // Install the proxy allowlist before the first request can be served, so the
    // request path resolves client IPs from the validated config rather than
    // re-reading the environment behind the config's back.
    routes::auth::init_trusted_proxies(&app_config);

    let (db_pool, db_pool_configured) = initialise_database_pool().await?;
    let (nats_client, nats_configured) = initialise_nats_client().await;

    handle_startup_migrations(db_pool_configured, db_pool.as_ref()).await?;

    // Domain write-source startup gates. Config loading already enforces that
    // every PostgreSQL write source is paired with PostgreSQL reads. Here we
    // additionally require a live pool and refuse silent fallback to JSONL.
    match app_config.domain_account_write_source {
        DomainAccountWriteSource::Postgres => {
            if db_pool.is_none() {
                return Err(anyhow!(
                    "domain_account_write_source=postgres requires DATABASE_URL and an available PostgreSQL pool; refusing to start"
                ));
            }
            tracing::info!(
                "Account-domain write source: PostgreSQL (POST /accounts, auth auto-provisioning, step-up email updates)."
            );
        }
        DomainAccountWriteSource::Jsonl => {
            tracing::info!("Account-domain write source: JSONL (default).");
        }
    }

    match app_config.domain_node_write_source {
        DomainNodeWriteSource::Postgres => {
            if db_pool.is_none() {
                return Err(anyhow!(
                    "domain_node_write_source=postgres requires DATABASE_URL and an available PostgreSQL pool; refusing to start"
                ));
            }
            tracing::info!("Node write source: PostgreSQL (POST /nodes and PATCH on a node id).");
        }
        DomainNodeWriteSource::Jsonl => {
            tracing::info!("Node write source: JSONL (default).");
        }
    }

    match app_config.domain_edge_write_source {
        DomainEdgeWriteSource::Postgres => {
            if db_pool.is_none() {
                return Err(anyhow!(
                    "domain_edge_write_source=postgres requires DATABASE_URL and an available PostgreSQL pool; refusing to start"
                ));
            }
            tracing::info!("Edge write source: PostgreSQL (POST /edges).");
        }
        DomainEdgeWriteSource::Jsonl => {
            tracing::info!("Edge write source: JSONL (default).");
        }
    }

    // AUTH-PG-002 Slice B: registered passkey credential store gate.
    //
    // Ceremony state (registration/authentication/grants) remains in-memory.
    // Only durable WebAuthn credential records switch here. PostgreSQL mode is
    // fail-closed: if explicitly selected but the pool is missing, startup
    // refuses to continue rather than silently falling back to in-memory.
    match app_config.passkey_credential_source {
        PasskeyCredentialSource::Postgres => {
            if db_pool.is_none() {
                return Err(anyhow!(
                    "passkey_credential_source=postgres requires DATABASE_URL and an available PostgreSQL pool; refusing in-memory fallback"
                ));
            }
            tracing::info!(
                "Passkey credential source: PostgreSQL (AUTH-PG-002 Slice B opt-in). \
                 WebAuthn ceremony state remains in-memory."
            );
        }
        PasskeyCredentialSource::InMemory => {
            tracing::info!("Passkey credential source: in-memory (default).");
        }
    }

    let metrics = Metrics::try_new(BuildInfo::collect())?;

    let sessions = match (db_pool_configured, db_pool.as_ref()) {
        (true, Some(pool)) => {
            tracing::info!("Session store backed by PostgreSQL database");
            crate::auth::session::SessionBackend::new(crate::auth::session_db::DbSessionStore::new(
                pool.clone(),
            ))
        }
        (true, None) => {
            return Err(anyhow!(
                "DATABASE_URL is configured but PostgreSQL pool is unavailable; refusing in-memory session fallback"
            ));
        }
        (false, _) => {
            tracing::info!("Session store in-memory (database not configured)");
            crate::auth::session::SessionBackend::new_in_memory()
        }
    };
    let challenges = crate::auth::challenges::ChallengeStore::new();
    let tokens = crate::auth::tokens::TokenStore::new();
    let step_up_tokens = crate::auth::step_up_tokens::StepUpTokenStore::new();
    let (accounts_store, nodes_cache, edges_cache) = match app_config.domain_read_source {
        DomainReadSource::Jsonl => (
            routes::accounts::load_all_accounts().await,
            routes::nodes::load_nodes().await,
            routes::edges::load_edges().await,
        ),
        DomainReadSource::Postgres => {
            let pool = db_pool.as_ref().ok_or_else(|| {
                anyhow!(
                    "domain_read_source=postgres requires DATABASE_URL and an available PostgreSQL pool"
                )
            })?;
            (
                crate::domain_db::load_accounts_from_postgres(pool).await?,
                crate::domain_db::load_nodes_from_postgres(pool).await?,
                crate::domain_db::load_edges_from_postgres(pool).await?,
            )
        }
    };
    let accounts = Arc::new(tokio::sync::RwLock::new(accounts_store));

    metrics.set_nodes_cache_count(nodes_cache.len() as i64);
    let nodes = Arc::new(tokio::sync::RwLock::new(nodes_cache));
    let nodes_persist = Arc::new(tokio::sync::Mutex::new(()));
    let accounts_persist = Arc::new(tokio::sync::Mutex::new(()));

    metrics.set_edges_cache_count(edges_cache.len() as i64);
    let edges = Arc::new(tokio::sync::RwLock::new(edges_cache));

    let rate_limiter = Arc::new(crate::auth::rate_limit::AuthRateLimiter::new(&app_config));

    // WebAuthn / Passkey support (optional — only active when WEBAUTHN_RP_ID + WEBAUTHN_RP_ORIGIN are set)
    let webauthn = match crate::auth::passkeys::build_webauthn(&app_config) {
        Ok(Some(wa)) => {
            tracing::info!("WebAuthn passkey support enabled");
            Some(wa)
        }
        Ok(None) => {
            tracing::info!("WebAuthn passkey support not configured (WEBAUTHN_RP_ID / WEBAUTHN_RP_ORIGIN unset)");
            None
        }
        Err(e) => {
            return Err(anyhow!("Failed to initialize WebAuthn: {}", e));
        }
    };
    let passkey_registrations = crate::auth::passkeys::PasskeyRegistrationStore::new();
    let passkey_registration_grants = crate::auth::passkeys::PasskeyRegistrationGrantStore::new();
    let passkey_authentications = crate::auth::passkeys::PasskeyAuthenticationStore::new();
    let passkeys = crate::auth::passkeys::PasskeyStore::new();

    let mailer = match crate::mailer::Mailer::new(&app_config) {
        Ok(mailer) => Some(Arc::new(mailer)),
        Err(error) => {
            // If Public Login is enabled AND Dev Logging is disabled, failure to init mailer is fatal.
            // (We must not run in a state where users can request login but receive nothing)
            if app_config.auth_public_login && !app_config.auth_log_magic_token {
                return Err(anyhow!(
                    "Public Login enabled without working mailer: {}",
                    error
                ));
            }

            // Otherwise (Dev mode or feature disabled), just warn.
            if app_config.smtp_host.is_some() {
                tracing::warn!(%error, "failed to initialize mailer; email sending will be disabled");
            }
            None
        }
    };

    let state = ApiState {
        db_pool,
        db_pool_configured,
        nats_client,
        nats_configured,
        config: app_config.clone(),
        metrics: metrics.clone(),
        sessions,
        challenges,
        tokens,
        step_up_tokens,
        accounts,
        nodes,
        nodes_persist,
        accounts_persist,
        edges,
        rate_limiter,
        mailer,
        webauthn,
        passkey_registrations,
        passkey_registration_grants,
        passkey_authentications,
        passkeys,
    };

    let app = Router::new()
        // Serve at root for Caddy (which strips /api prefix)
        .merge(
            api_router()
                .route_layer(from_fn_with_state(state.clone(), auth_middleware))
                .layer(axum::middleware::from_fn(require_csrf)),
        )
        // Serve at /api for direct access (e.g. apps/web fallback)
        .nest(
            "/api",
            api_router()
                .route_layer(from_fn_with_state(state.clone(), auth_middleware))
                .layer(axum::middleware::from_fn(require_csrf)),
        )
        .merge(health_routes())
        .merge(meta_routes())
        .route("/metrics", get(metrics_handler))
        .with_state(state)
        .layer(
            ServiceBuilder::new()
                .layer(SetRequestIdLayer::x_request_id(MakeRequestUuid))
                .layer(MetricsLayer::new(metrics)),
        );

    let bind_addr: SocketAddr = env::var("API_BIND")
        .unwrap_or_else(|_| "0.0.0.0:8080".to_string())
        .parse()
        .context("failed to parse API_BIND address")?;

    tracing::info!(%bind_addr, "starting API server");

    let listener = TcpListener::bind(bind_addr).await?;
    axum::serve(
        listener,
        app.into_make_service_with_connect_info::<SocketAddr>(),
    )
    .await?;

    Ok(())
}

fn init_tracing() -> anyhow::Result<()> {
    if tracing::dispatcher::has_been_set() {
        return Ok(());
    }

    let env_filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));
    fmt()
        .with_env_filter(env_filter)
        .try_init()
        .map_err(|e| anyhow!(e))
        .context("failed to initialize tracing")?;

    Ok(())
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum StartupMigrationMode {
    Run,
    VerifyApplied,
}

impl StartupMigrationMode {
    fn load() -> anyhow::Result<Self> {
        let raw = match env::var("WELTGEWEBE_API_STARTUP_MIGRATIONS") {
            Ok(value) => value,
            Err(env::VarError::NotPresent) => return Ok(Self::Run),
            Err(error) => {
                return Err(anyhow!(error)).context(
                    "failed to read WELTGEWEBE_API_STARTUP_MIGRATIONS from the environment",
                );
            }
        };

        match raw.trim().to_ascii_lowercase().as_str() {
            "" | "run" => Ok(Self::Run),
            "verify-applied" => Ok(Self::VerifyApplied),
            _ => Err(anyhow!(
                "invalid WELTGEWEBE_API_STARTUP_MIGRATIONS value {raw:?}; expected `run` or `verify-applied`"
            )),
        }
    }
}

#[derive(Debug, Clone)]
struct AppliedStartupMigration {
    success: bool,
    checksum: Vec<u8>,
}

async fn handle_startup_migrations(
    db_pool_configured: bool,
    db_pool: Option<&PgPool>,
) -> anyhow::Result<()> {
    let pool = match (db_pool_configured, db_pool) {
        (false, None) => return Ok(()),
        (true, Some(pool)) => pool,
        (true, None) => {
            return Err(anyhow!(
                "database configured but PostgreSQL pool is missing; refusing startup migration handling"
            ));
        }
        (false, Some(_)) => {
            return Err(anyhow!(
                "PostgreSQL pool is present but db_pool_configured=false; refusing ambiguous startup migration handling"
            ));
        }
    };

    let migrator = sqlx::migrate!("./migrations");

    match StartupMigrationMode::load()? {
        StartupMigrationMode::Run => {
            migrator
                .run(pool)
                .await
                .context("database migration failed")?;
        }
        StartupMigrationMode::VerifyApplied => {
            verify_startup_migrations_applied(pool, &migrator).await?;
        }
    }

    Ok(())
}

async fn verify_startup_migrations_applied(
    pool: &PgPool,
    migrator: &Migrator,
) -> anyhow::Result<()> {
    let rows = sqlx::query("SELECT version, success, checksum FROM _sqlx_migrations")
        .fetch_all(pool)
        .await
        .context(
            "WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied could not read _sqlx_migrations; refusing to start in verify-applied mode",
        )?;

    let mut applied: HashMap<i64, AppliedStartupMigration> = HashMap::new();
    for row in rows {
        let version: i64 = row
            .try_get("version")
            .context("_sqlx_migrations.version must be readable")?;
        let success: bool = row
            .try_get("success")
            .context("_sqlx_migrations.success must be readable")?;
        let checksum: Vec<u8> = row
            .try_get("checksum")
            .context("_sqlx_migrations.checksum must be readable")?;
        record_applied_startup_migration(
            &mut applied,
            version,
            AppliedStartupMigration { success, checksum },
        )?;
    }

    validate_applied_startup_migrations(&applied, migrator)?;

    tracing::info!("startup migrations verified as already applied; no migration SQL executed");
    Ok(())
}

fn record_applied_startup_migration(
    applied: &mut HashMap<i64, AppliedStartupMigration>,
    version: i64,
    migration: AppliedStartupMigration,
) -> anyhow::Result<()> {
    match applied.entry(version) {
        Entry::Vacant(slot) => {
            slot.insert(migration);
            Ok(())
        }
        Entry::Occupied(_) => Err(anyhow!(
            "duplicate startup migration version {version} in _sqlx_migrations; refusing to start in verify-applied mode"
        )),
    }
}

fn validate_applied_startup_migrations(
    applied: &HashMap<i64, AppliedStartupMigration>,
    migrator: &Migrator,
) -> anyhow::Result<()> {
    let expected_versions: HashSet<i64> = migrator
        .iter()
        .filter(|migration| !migration.migration_type.is_down_migration())
        .map(|migration| migration.version)
        .collect();

    for (version, migration) in applied {
        if !migration.success {
            return Err(anyhow!(
                "startup migration {version} is not marked successful; refusing to start in verify-applied mode"
            ));
        }

        if !expected_versions.contains(version) {
            return Err(anyhow!(
                "applied startup migration {version} is not embedded in this binary; refusing to start in verify-applied mode"
            ));
        }
    }

    for migration in migrator.iter() {
        if migration.migration_type.is_down_migration() {
            continue;
        }

        let Some(applied_migration) = applied.get(&migration.version) else {
            return Err(anyhow!(
                "pending startup migration {} ({}) under WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied; refusing to start in verify-applied mode",
                migration.version,
                migration.description
            ));
        };

        if applied_migration.checksum.as_slice() != migration.checksum.as_ref() {
            return Err(anyhow!(
                "startup migration {} ({}) checksum differs from the embedded migration; refusing to start in verify-applied mode",
                migration.version,
                migration.description
            ));
        }
    }

    Ok(())
}

/// Initialise the PostgreSQL pool from `DATABASE_URL`.
///
/// Startup contract (fail-fast). Per ADR-0007 the production auth/session and
/// domain persistence paths run against a direct PostgreSQL connection:
///
/// - `DATABASE_URL` unset → `Ok((None, false))`: PostgreSQL is not configured;
///   the API runs with in-memory sessions and JSONL domain data.
/// - `DATABASE_URL` set → PostgreSQL connectivity is **mandatory**. The pool is
///   configured and its initial connection is verified eagerly. On success
///   `Ok((Some(pool), true))`; on any failure `Err(..)` so the API refuses to
///   start rather than coming up half-wired.
///
/// Fail-fast is the only honest option here: every downstream startup step that
/// needs a configured pool — schema migrations (`sqlx::migrate!(..).run(..)?`),
/// the optional PostgreSQL domain read/write sources, and the `DbSessionStore`
/// — already aborts startup on a missing or dead pool. Tolerating a dead initial
/// connection would not yield a recoverable degraded mode; it would only defer
/// the same abort to the migration step behind a misleading warning. Runtime
/// readiness (`/health/ready`) keeps re-checking the database *after* a
/// successful start, but it cannot resurrect a process that never finished
/// booting — so the previous "readiness will keep retrying" startup message was
/// untrue and has been removed. The function therefore never returns the
/// inconsistent `(None, true)` / `(Some(dead_pool), true)` states.
async fn initialise_database_pool() -> anyhow::Result<(Option<sqlx::PgPool>, bool)> {
    let database_url = match env::var("DATABASE_URL") {
        Ok(url) => url,
        Err(_) => return Ok((None, false)),
    };

    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect_lazy(&database_url)
        .context("DATABASE_URL is set but the database pool could not be configured")?;

    // Verify connectivity now and fail fast: `DATABASE_URL` is set, so a live
    // PostgreSQL connection is a hard startup dependency (see the contract above).
    // The acquired connection is returned to the pool when this guard drops.
    let _connection = pool.acquire().await.context(
        "DATABASE_URL is set but the initial PostgreSQL connection failed; \
         refusing to start without database connectivity",
    )?;

    Ok((Some(pool), true))
}

async fn initialise_nats_client() -> (Option<NatsClient>, bool) {
    let nats_url = match env::var("NATS_URL") {
        Ok(url) => url,
        Err(_) => return (None, false),
    };

    match async_nats::connect(&nats_url).await {
        Ok(client) => (Some(client), true),
        Err(error) => {
            tracing::warn!(error = %error, "failed to connect to NATS");
            (None, true)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{
        initialise_database_pool, record_applied_startup_migration,
        validate_applied_startup_migrations, AppliedStartupMigration, StartupMigrationMode,
    };
    use crate::test_helpers::EnvGuard;
    use serial_test::serial;

    #[tokio::test]
    #[serial]
    async fn initialise_database_pool_returns_none_when_database_url_unset() {
        let _guard = EnvGuard::unset("DATABASE_URL");

        let (pool, configured) = initialise_database_pool()
            .await
            .expect("an absent DATABASE_URL must not be a startup error");

        assert!(pool.is_none(), "no pool must be built without DATABASE_URL");
        assert!(
            !configured,
            "db must report as not configured when DATABASE_URL is unset"
        );
    }

    #[tokio::test]
    #[serial]
    async fn initialise_database_pool_fails_fast_when_database_url_is_unusable() {
        // A set-but-unusable DATABASE_URL must be a hard startup error under the
        // fail-fast contract — never a silent (None, true) / (Some(dead), true)
        // degraded state, and never the old "readiness will keep retrying" lie.
        // An unparseable value fails eagerly in `connect_lazy`, so this asserts
        // the fail-fast path deterministically without a live-connection timeout.
        let _guard = EnvGuard::set("DATABASE_URL", "not a valid url");

        let error = initialise_database_pool()
            .await
            .expect_err("a set-but-unusable DATABASE_URL must abort startup");

        assert!(
            error.to_string().contains("DATABASE_URL is set"),
            "error must explain the database startup contract, got: {error}"
        );
    }

    #[test]
    #[serial]
    fn startup_migration_mode_defaults_to_run() {
        let _guard = EnvGuard::unset("WELTGEWEBE_API_STARTUP_MIGRATIONS");
        let mode = StartupMigrationMode::load().expect("default mode should load");
        assert_eq!(mode, StartupMigrationMode::Run);
    }

    #[test]
    #[serial]
    fn startup_migration_mode_accepts_verify_applied() {
        let _guard = EnvGuard::set("WELTGEWEBE_API_STARTUP_MIGRATIONS", "verify-applied");
        let mode = StartupMigrationMode::load().expect("verify-applied mode should load");
        assert_eq!(mode, StartupMigrationMode::VerifyApplied);
    }

    #[test]
    #[serial]
    fn startup_migration_mode_rejects_unknown_values() {
        let _guard = EnvGuard::set("WELTGEWEBE_API_STARTUP_MIGRATIONS", "skip");
        let error =
            StartupMigrationMode::load().expect_err("unknown migration mode must fail closed");
        assert!(
            error
                .to_string()
                .contains("expected `run` or `verify-applied`"),
            "error must name the accepted values, got: {error}"
        );
    }

    fn applied_from_migrator(
        migrator: &sqlx::migrate::Migrator,
        success: bool,
    ) -> std::collections::HashMap<i64, AppliedStartupMigration> {
        migrator
            .iter()
            .filter(|migration| !migration.migration_type.is_down_migration())
            .map(|migration| {
                (
                    migration.version,
                    AppliedStartupMigration {
                        success,
                        checksum: migration.checksum.as_ref().to_vec(),
                    },
                )
            })
            .collect()
    }

    #[test]
    fn record_applied_startup_migration_rejects_duplicate_version() {
        let mut applied = std::collections::HashMap::new();
        record_applied_startup_migration(
            &mut applied,
            1,
            AppliedStartupMigration {
                success: true,
                checksum: vec![1],
            },
        )
        .expect("first migration record should be accepted");

        let error = record_applied_startup_migration(
            &mut applied,
            1,
            AppliedStartupMigration {
                success: true,
                checksum: vec![2],
            },
        )
        .expect_err("duplicate migration version must fail closed");

        assert!(
            error
                .to_string()
                .contains("duplicate startup migration version"),
            "error must describe duplicate migration version, got: {error}"
        );
    }

    #[test]
    fn validate_applied_startup_migrations_accepts_complete_history() {
        let migrator = sqlx::migrate!("./migrations");
        let applied = applied_from_migrator(&migrator, true);

        validate_applied_startup_migrations(&applied, &migrator)
            .expect("complete applied migration history must pass");
    }

    #[test]
    fn validate_applied_startup_migrations_rejects_pending_migration() {
        let migrator = sqlx::migrate!("./migrations");
        let mut applied = applied_from_migrator(&migrator, true);
        let pending_version = migrator
            .iter()
            .find(|migration| !migration.migration_type.is_down_migration())
            .expect("embedded migrator must contain at least one up migration")
            .version;
        applied.remove(&pending_version);

        let error = validate_applied_startup_migrations(&applied, &migrator)
            .expect_err("pending migration must fail closed");

        assert!(
            error.to_string().contains("pending startup migration"),
            "error must describe pending migration, got: {error}"
        );
    }

    #[test]
    fn validate_applied_startup_migrations_rejects_checksum_mismatch() {
        let migrator = sqlx::migrate!("./migrations");
        let mut applied = applied_from_migrator(&migrator, true);
        let mismatch_version = migrator
            .iter()
            .find(|migration| !migration.migration_type.is_down_migration())
            .expect("embedded migrator must contain at least one up migration")
            .version;
        applied
            .get_mut(&mismatch_version)
            .expect("test migration should be present")
            .checksum
            .push(0);

        let error = validate_applied_startup_migrations(&applied, &migrator)
            .expect_err("checksum mismatch must fail closed");

        assert!(
            error.to_string().contains("checksum differs"),
            "error must describe checksum mismatch, got: {error}"
        );
    }

    #[test]
    fn validate_applied_startup_migrations_rejects_failed_migration() {
        let migrator = sqlx::migrate!("./migrations");
        let mut applied = applied_from_migrator(&migrator, true);
        let failed_version = migrator
            .iter()
            .find(|migration| !migration.migration_type.is_down_migration())
            .expect("embedded migrator must contain at least one up migration")
            .version;
        applied
            .get_mut(&failed_version)
            .expect("test migration should be present")
            .success = false;

        let error = validate_applied_startup_migrations(&applied, &migrator)
            .expect_err("failed migration must fail closed");

        assert!(
            error.to_string().contains("not marked successful"),
            "error must describe failed migration, got: {error}"
        );
    }

    #[test]
    fn validate_applied_startup_migrations_rejects_extra_migration() {
        let migrator = sqlx::migrate!("./migrations");
        let mut applied = applied_from_migrator(&migrator, true);
        let extra_version = migrator
            .iter()
            .filter(|migration| !migration.migration_type.is_down_migration())
            .map(|migration| migration.version)
            .max()
            .expect("embedded migrator must contain at least one up migration")
            + 1;
        applied.insert(
            extra_version,
            AppliedStartupMigration {
                success: true,
                checksum: vec![0],
            },
        );

        let error = validate_applied_startup_migrations(&applied, &migrator)
            .expect_err("extra migration must fail closed");

        assert!(
            error.to_string().contains("not embedded in this binary"),
            "error must describe extra migration, got: {error}"
        );
    }
}

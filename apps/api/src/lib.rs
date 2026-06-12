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

use std::{env, io::ErrorKind, net::SocketAddr, sync::Arc};

use anyhow::{anyhow, Context};
use async_nats::Client as NatsClient;
use axum::{middleware::from_fn_with_state, routing::get, Router};
use config::{
    AppConfig, DomainAccountWriteSource, DomainEdgeWriteSource, DomainNodeWriteSource,
    DomainReadSource,
};
use middleware::auth::auth_middleware;
use middleware::csrf::require_csrf;
use routes::{api_router, health::health_routes, meta::meta_routes};
use sqlx::postgres::PgPoolOptions;
use state::ApiState;
use telemetry::{metrics_handler, BuildInfo, Metrics, MetricsLayer};
use tokio::net::TcpListener;
use tower::ServiceBuilder;
use tower_http::request_id::{MakeRequestUuid, SetRequestIdLayer};
use tracing_subscriber::{fmt, EnvFilter};

pub async fn run() -> anyhow::Result<()> {
    let dotenv = dotenvy::dotenv();
    if let Ok(path) = &dotenv {
        tracing::debug!(?path, "loaded environment variables from .env file");
    }

    if let Err(error) = dotenv {
        match &error {
            dotenvy::Error::Io(io_error) if io_error.kind() == ErrorKind::NotFound => {}
            _ => tracing::warn!(%error, "failed to load environment from .env file"),
        }
    }
    init_tracing()?;

    let app_config = AppConfig::load().context("failed to load API configuration")?;
    let (db_pool, db_pool_configured) = initialise_database_pool().await;
    let (nats_client, nats_configured) = initialise_nats_client().await;

    if let (true, Some(pool)) = (db_pool_configured, db_pool.as_ref()) {
        sqlx::migrate!("./migrations")
            .run(pool)
            .await
            .context("database migration failed")?;
    }

    // OPT-ARC-001 Phase E-A: account-create write-path gate.
    //
    // The read/write-source coupling (PostgreSQL account-write requires the
    // PostgreSQL read source) is already enforced at config load. Here we
    // additionally require a live pool when the account-create write source is
    // PostgreSQL, and refuse to start otherwise — no silent downgrade to JSONL.
    // This gate is intentionally narrow: it implements `POST /accounts` only;
    // node writes, edge writes, step-up email persistence and WebAuthn user-id
    // writeback persistence remain unchanged and are NOT a PostgreSQL cutover.
    match app_config.domain_account_write_source {
        DomainAccountWriteSource::Postgres => {
            if db_pool.is_none() {
                return Err(anyhow!(
                    "domain_account_write_source=postgres requires DATABASE_URL and an available PostgreSQL pool; refusing to start"
                ));
            }
            tracing::info!(
                "Account-create write source: PostgreSQL (OPT-ARC-001 Phase E-A opt-in). \
                 Only POST /accounts writes to domain_accounts; node/edge/auth writes are unchanged."
            );
        }
        DomainAccountWriteSource::Jsonl => {
            tracing::info!("Account-create write source: JSONL (default).");
        }
    }

    // OPT-ARC-001 Phase E-B: node-patch write-path gate.
    //
    // The read/write-source coupling (PostgreSQL node-write requires the
    // PostgreSQL read source) is already enforced at config load. Here we
    // additionally require a live pool when the node-patch write source is
    // PostgreSQL, and refuse to start otherwise — no silent downgrade to JSONL.
    // This gate is intentionally narrow: it implements `PATCH /nodes` only;
    // account writes, edge writes, step-up email persistence and WebAuthn
    // user-id writeback persistence remain unchanged.
    match app_config.domain_node_write_source {
        DomainNodeWriteSource::Postgres => {
            if db_pool.is_none() {
                return Err(anyhow!(
                    "domain_node_write_source=postgres requires DATABASE_URL and an available PostgreSQL pool; refusing to start"
                ));
            }
            tracing::info!(
                "Node patch write source: PostgreSQL (OPT-ARC-001 Phase E-B opt-in). \
                 Only PATCH /nodes writes to domain_nodes; account/edge/auth writes are unchanged."
            );
        }
        DomainNodeWriteSource::Jsonl => {
            tracing::info!("Node patch write source: JSONL (default).");
        }
    }

    // OPT-ARC-001 Phase E-C: edge-create write-path gate.
    //
    // The read/write-source coupling (PostgreSQL edge-write requires the
    // PostgreSQL read source) is already enforced at config load. Here we
    // additionally require a live pool when the edge-create write source is
    // PostgreSQL, and refuse to start otherwise — no silent downgrade to JSONL.
    // This gate is intentionally narrow: it implements `POST /edges` only;
    // account writes, node writes, step-up email persistence and WebAuthn
    // user-id writeback persistence remain unchanged.
    match app_config.domain_edge_write_source {
        DomainEdgeWriteSource::Postgres => {
            if db_pool.is_none() {
                return Err(anyhow!(
                    "domain_edge_write_source=postgres requires DATABASE_URL and an available PostgreSQL pool; refusing to start"
                ));
            }
            tracing::info!(
                "Edge-create write source: PostgreSQL (OPT-ARC-001 Phase E-C opt-in). \
                 Only POST /edges writes to domain_edges; account/node/auth writes are unchanged."
            );
        }
        DomainEdgeWriteSource::Jsonl => {
            tracing::info!("Edge-create write source: JSONL (default).");
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

async fn initialise_database_pool() -> (Option<sqlx::PgPool>, bool) {
    let database_url = match env::var("DATABASE_URL") {
        Ok(url) => url,
        Err(_) => return (None, false),
    };

    let pool = match PgPoolOptions::new()
        .max_connections(5)
        .connect_lazy(&database_url)
    {
        Ok(pool) => pool,
        Err(error) => {
            tracing::warn!(error = %error, "failed to configure database pool");
            return (None, true);
        }
    };

    match pool.acquire().await {
        Ok(connection) => drop(connection),
        Err(error) => {
            tracing::warn!(
                error = %error,
                "database connection unavailable at startup; readiness will keep retrying",
            );
        }
    }

    (Some(pool), true)
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

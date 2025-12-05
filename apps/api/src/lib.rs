pub mod config;
pub mod middleware;
pub mod routes;
pub mod state;
pub mod telemetry;

#[doc(hidden)]
pub mod test_helpers;

use std::{env, io::ErrorKind, net::SocketAddr};

use anyhow::{anyhow, Context};
use async_nats::Client as NatsClient;
use axum::{middleware::from_fn, routing::get, Router};
use config::AppConfig;
use middleware::auth::require_auth;
use routes::{api_router, health::health_routes, meta::meta_routes};
use sqlx::postgres::PgPoolOptions;
use state::ApiState;
use telemetry::{metrics_handler, BuildInfo, Metrics, MetricsLayer};
use tokio::net::TcpListener;
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

    let metrics = Metrics::try_new(BuildInfo::collect())?;
    let state = ApiState {
        db_pool,
        db_pool_configured,
        nats_client,
        nats_configured,
        config: app_config.clone(),
        metrics: metrics.clone(),
    };

    let app = Router::new()
        // Serve at root for Caddy (which strips /api prefix)
        .merge(api_router().route_layer(from_fn(require_auth)))
        // Serve at /api for direct access (e.g. apps/web fallback)
        .nest("/api", api_router().route_layer(from_fn(require_auth)))
        .merge(health_routes())
        .merge(meta_routes())
        .route("/metrics", get(metrics_handler))
        .with_state(state)
        .layer(MetricsLayer::new(metrics));

    let bind_addr: SocketAddr = env::var("API_BIND")
        .unwrap_or_else(|_| "0.0.0.0:8080".to_string())
        .parse()
        .context("failed to parse API_BIND address")?;

    tracing::info!(%bind_addr, "starting API server");

    let listener = TcpListener::bind(bind_addr).await?;
    axum::serve(listener, app).await?;

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

mod routes;
mod state;
mod telemetry;

use std::{env, net::SocketAddr};

use anyhow::{anyhow, Context};
use async_nats::Client as NatsClient;
use axum::{routing::get, Router};
use routes::health::health_routes;
use sqlx::postgres::PgPoolOptions;
use state::ApiState;
use telemetry::{metrics_handler, BuildInfo, Metrics, MetricsLayer};
use tokio::net::TcpListener;
use tracing_subscriber::{fmt, EnvFilter};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    dotenvy::dotenv().ok();
    init_tracing()?;

    let (db_pool, db_pool_configured) = initialise_database_pool().await;
    let (nats_client, nats_configured) = initialise_nats_client().await;

    let metrics = Metrics::try_new(BuildInfo::collect())?;
    let state = ApiState {
        db_pool,
        db_pool_configured,
        nats_client,
        nats_configured,
        metrics: metrics.clone(),
    };

    let app = Router::new()
        .merge(health_routes())
        .route("/metrics", get(metrics_handler))
        .layer(MetricsLayer::new(metrics))
        .with_state(state);

    let bind_addr: SocketAddr = env::var("API_BIND")
        .unwrap_or_else(|_| "0.0.0.0:8787".to_string())
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
        .map_err(|error| anyhow!(error))?;

    Ok(())
}

async fn initialise_database_pool() -> (Option<sqlx::PgPool>, bool) {
    let database_url = match env::var("DATABASE_URL") {
        Ok(url) => url,
        Err(_) => return (None, false),
    };

    match PgPoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await
    {
        Ok(pool) => (Some(pool), true),
        Err(error) => {
            tracing::warn!(error = %error, "failed to connect to database");
            (None, true)
        }
    }
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

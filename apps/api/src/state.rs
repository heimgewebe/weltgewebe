use crate::telemetry::Metrics;
use async_nats::Client as NatsClient;
use sqlx::PgPool;

#[derive(Clone)]
pub struct ApiState {
    pub db_pool: Option<PgPool>,
    pub db_pool_configured: bool,
    pub nats_client: Option<NatsClient>,
    pub nats_configured: bool,
    pub metrics: Metrics,
}

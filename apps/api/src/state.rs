use crate::telemetry::Metrics;
use async_nats::Client as NatsClient;
use sqlx::PgPool;

#[derive(Clone)]
pub struct ApiState {
    pub db_pool: Option<PgPool>,
    pub nats_client: Option<NatsClient>,
    pub metrics: Metrics,
}

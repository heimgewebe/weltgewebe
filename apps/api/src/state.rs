use crate::{config::AppConfig, telemetry::Metrics};
use async_nats::Client as NatsClient;
use sqlx::PgPool;

// ApiState is constructed for future expansion of the API server state. It is
// currently unused by the binary, so we explicitly allow dead code here to keep
// the CI pipeline green while maintaining the transparent intent of the state
// container.
#[allow(dead_code)]
#[derive(Clone)]
pub struct ApiState {
    pub db_pool: Option<PgPool>,
    pub db_pool_configured: bool,
    pub nats_client: Option<NatsClient>,
    pub nats_configured: bool,
    pub config: AppConfig,
    pub metrics: Metrics,
}

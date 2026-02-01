use std::{collections::HashMap, sync::Arc};
use tokio::sync::RwLock;

use crate::{
    auth::{session::SessionStore, tokens::TokenStore},
    config::AppConfig,
    routes::{accounts::AccountInternal, nodes::Node},
    telemetry::Metrics,
};
use async_nats::Client as NatsClient;
use sqlx::PgPool;

#[derive(Clone)]
pub struct ApiState {
    pub db_pool: Option<PgPool>,
    pub db_pool_configured: bool,
    pub nats_client: Option<NatsClient>,
    pub nats_configured: bool,
    pub config: AppConfig,
    pub metrics: Metrics,
    pub sessions: SessionStore,
    pub tokens: TokenStore,
    pub accounts: Arc<HashMap<String, AccountInternal>>,
    pub nodes: Arc<RwLock<Vec<Node>>>,
}

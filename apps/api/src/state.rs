use std::{collections::HashMap, sync::Arc};
use tokio::sync::RwLock;

use crate::{
    auth::{rate_limit::AuthRateLimiter, session::SessionStore, tokens::TokenStore},
    config::AppConfig,
    mailer::Mailer,
    routes::{accounts::AccountInternal, edges::Edge, nodes::Node},
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
    pub accounts: Arc<RwLock<HashMap<String, AccountInternal>>>,
    pub nodes: Arc<RwLock<Vec<Node>>>,
    pub edges: Arc<RwLock<Vec<Edge>>>,
    pub rate_limiter: Arc<AuthRateLimiter>,
    pub mailer: Option<Arc<Mailer>>,
}

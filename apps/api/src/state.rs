use std::{collections::BTreeMap, sync::Arc};
use tokio::sync::{Mutex, RwLock};

use crate::{
    auth::{
        challenges::ChallengeStore, rate_limit::AuthRateLimiter, session::SessionStore,
        step_up_tokens::StepUpTokenStore, tokens::TokenStore,
    },
    config::AppConfig,
    mailer::Mailer,
    routes::{accounts::AccountInternal, edges::Edge, nodes::Node},
    telemetry::Metrics,
};
use async_nats::Client as NatsClient;
use sqlx::PgPool;
use webauthn_rs::Webauthn;

#[derive(Clone)]
pub struct ApiState {
    pub db_pool: Option<PgPool>,
    pub db_pool_configured: bool,
    pub nats_client: Option<NatsClient>,
    pub nats_configured: bool,
    pub config: AppConfig,
    pub metrics: Metrics,
    pub sessions: SessionStore,
    pub challenges: ChallengeStore,
    pub tokens: TokenStore,
    pub step_up_tokens: StepUpTokenStore,
    pub accounts: Arc<RwLock<BTreeMap<String, AccountInternal>>>,
    pub nodes: Arc<RwLock<Vec<Node>>>,
    pub nodes_persist: Arc<Mutex<()>>,
    pub edges: Arc<RwLock<Vec<Edge>>>,
    pub rate_limiter: Arc<AuthRateLimiter>,
    pub mailer: Option<Arc<Mailer>>,
    pub webauthn: Arc<Webauthn>,
}

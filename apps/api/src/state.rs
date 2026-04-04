use std::{
    collections::{BTreeMap, HashMap},
    sync::Arc,
};
use tokio::sync::{Mutex, RwLock};

use crate::{
    auth::{
        challenges::ChallengeStore, passkeys::PasskeyRegistrationStore,
        rate_limit::AuthRateLimiter, session::SessionStore, step_up_tokens::StepUpTokenStore,
        tokens::TokenStore,
    },
    config::AppConfig,
    mailer::Mailer,
    routes::{accounts::AccountInternal, edges::Edge, nodes::Node},
    telemetry::Metrics,
};

use async_nats::Client as NatsClient;

/// A cache that provides $O(1)$ lookups by ID while preserving the original
/// load/insertion order for deterministic list responses.
#[derive(Clone, Default)]
pub struct OrderedCache<T> {
    items: HashMap<String, T>,
    order: Vec<String>,
}

impl<T> OrderedCache<T> {
    pub fn new() -> Self {
        Self {
            items: HashMap::new(),
            order: Vec::new(),
        }
    }

    pub fn insert(&mut self, id: String, item: T) -> bool {
        let is_replaced = self.items.insert(id.clone(), item).is_some();
        if !is_replaced {
            self.order.push(id);
        }
        is_replaced
    }

    pub fn iter_in_order(&self) -> impl Iterator<Item = &T> {
        self.order.iter().filter_map(move |id| self.items.get(id))
    }

    pub fn get(&self, id: &str) -> Option<&T> {
        self.items.get(id)
    }

    pub fn len(&self) -> usize {
        self.items.len()
    }

    pub fn is_empty(&self) -> bool {
        self.items.is_empty()
    }
}

use sqlx::PgPool;
use webauthn_rs::prelude::Webauthn;

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
    pub nodes: Arc<RwLock<OrderedCache<Node>>>,
    pub nodes_persist: Arc<Mutex<()>>,
    pub edges: Arc<RwLock<OrderedCache<Edge>>>,
    pub rate_limiter: Arc<AuthRateLimiter>,
    pub mailer: Option<Arc<Mailer>>,
    /// WebAuthn instance, present only when passkey support is configured.
    pub webauthn: Option<Arc<Webauthn>>,
    pub passkey_registrations: PasskeyRegistrationStore,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ordered_cache_id_lookup() {
        let mut cache = OrderedCache::<String>::new();
        cache.insert("id1".to_string(), "item1".to_string());
        cache.insert("id2".to_string(), "item2".to_string());

        assert_eq!(cache.get("id1"), Some(&"item1".to_string()));
        assert_eq!(cache.get("id2"), Some(&"item2".to_string()));
        assert_eq!(cache.get("id3"), None);
    }

    #[test]
    fn test_ordered_cache_deterministic_order() {
        let mut cache = OrderedCache::<String>::new();
        cache.insert("z".to_string(), "item_z".to_string());
        cache.insert("a".to_string(), "item_a".to_string());
        cache.insert("m".to_string(), "item_m".to_string());

        let order: Vec<_> = cache.iter_in_order().collect();
        assert_eq!(
            order,
            vec![
                &"item_z".to_string(),
                &"item_a".to_string(),
                &"item_m".to_string()
            ]
        );
    }

    #[test]
    fn test_ordered_cache_duplicate_last_write_wins_and_stable_order() {
        let mut cache = OrderedCache::<String>::new();
        cache.insert("id1".to_string(), "first".to_string());
        cache.insert("id2".to_string(), "item2".to_string());
        cache.insert("id1".to_string(), "second".to_string());

        assert_eq!(cache.get("id1"), Some(&"second".to_string()));
        assert_eq!(cache.len(), 2);
        // Order must match original insertion of the unique ID
        let order: Vec<_> = cache.iter_in_order().collect();
        assert_eq!(order, vec![&"second".to_string(), &"item2".to_string()]);
    }
}

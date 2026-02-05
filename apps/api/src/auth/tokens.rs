use chrono::{DateTime, Duration, Utc};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use uuid::Uuid;

#[derive(Clone, Debug)]
pub struct TokenData {
    pub email: String,
    pub expires_at: DateTime<Utc>,
    pub used: bool,
}

#[derive(Clone, Default)]
pub struct TokenStore {
    store: Arc<RwLock<HashMap<String, TokenData>>>,
}

impl TokenStore {
    pub fn new() -> Self {
        Self {
            store: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    fn hash_token(token: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(token.as_bytes());
        // Simple salt/pepper could be added here if we had a config for it
        format!("{:x}", hasher.finalize())
    }

    pub fn create(&self, email: String) -> String {
        let token = Uuid::new_v4().to_string();
        let hash = Self::hash_token(&token);

        let now = Utc::now();
        let expires_at = now + Duration::minutes(15);

        let data = TokenData {
            email,
            expires_at,
            used: false,
        };

        let mut store = self.store.write().expect("TokenStore lock poisoned");
        // Cleanup expired tokens on every write to keep memory check in check
        store.retain(|_, v| v.expires_at > now);

        store.insert(hash, data);

        token
    }

    pub fn consume(&self, token: &str) -> Option<String> {
        let now = Utc::now();
        let hash = Self::hash_token(token);
        let mut store = self.store.write().expect("TokenStore lock poisoned");

        // Cleanup expired tokens
        store.retain(|_, v| v.expires_at > now);

        // Strict single-use: remove immediately upon lookup
        if let Some(data) = store.remove(&hash) {
            if data.used {
                // Should technically not happen if we remove on use, but good for safety
                return None;
            }
            // Double check expiry just in case retain didn't catch it (though it should have)
            if data.expires_at <= now {
                return None;
            }
            return Some(data.email);
        }
        None
    }
}

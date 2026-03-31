use chrono::{DateTime, Duration, Utc};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use uuid::Uuid;

#[derive(Clone, Debug)]
pub struct TokenData {
    pub email: String,
    pub expires_at: DateTime<Utc>,
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

    pub(crate) fn hash_token(token: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(token.as_bytes());
        // Simple salt/pepper could be added here if we had a config for it
        format!("{:x}", hasher.finalize())
    }

    /// Checks if a token exists and is valid without consuming it.
    /// Returns the associated email if valid.
    pub fn peek(&self, token: &str) -> Option<String> {
        let now = Utc::now();
        let hash = Self::hash_token(token);
        let store = self.store.read().expect("TokenStore lock poisoned");

        if let Some(data) = store.get(&hash) {
            if data.expires_at > now {
                return Some(data.email.clone());
            }
        }
        None
    }

    pub fn create(&self, email: String) -> String {
        self.create_with_expiry(email, Duration::minutes(15))
    }

    pub fn create_with_expiry(&self, email: String, duration: Duration) -> String {
        let token = Uuid::new_v4().to_string();
        let hash = Self::hash_token(&token);

        let now = Utc::now();
        let expires_at = now + duration;

        let data = TokenData { email, expires_at };

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

        // Strict single-use: remove immediately upon lookup.
        // Expired tokens were already purged by retain() above, so any
        // token still present is guaranteed to be valid.
        store.remove(&hash).map(|data| data.email)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hash_token_consistent() {
        let hash1 = TokenStore::hash_token("test-token");
        let hash2 = TokenStore::hash_token("test-token");
        assert_eq!(hash1, hash2);
    }

    #[test]
    fn hash_token_different_inputs_produce_different_hashes() {
        let hash1 = TokenStore::hash_token("token-a");
        let hash2 = TokenStore::hash_token("token-b");
        assert_ne!(hash1, hash2);
    }

    #[test]
    fn create_returns_uuid_format() {
        let store = TokenStore::new();
        let token = store.create("user@example.com".to_string());
        assert!(
            uuid::Uuid::parse_str(&token).is_ok(),
            "Token should be valid UUID"
        );
    }

    #[test]
    fn peek_returns_email_for_valid_token() {
        let store = TokenStore::new();
        let token = store.create("user@example.com".to_string());
        assert_eq!(store.peek(&token), Some("user@example.com".to_string()));
    }

    #[test]
    fn peek_returns_none_for_unknown_token() {
        let store = TokenStore::new();
        assert_eq!(store.peek("nonexistent-token"), None);
    }

    #[test]
    fn consume_returns_email_and_removes_token() {
        let store = TokenStore::new();
        let token = store.create("user@example.com".to_string());

        let first = store.consume(&token);
        assert_eq!(first, Some("user@example.com".to_string()));

        let second = store.consume(&token);
        assert_eq!(second, None);
    }

    #[test]
    fn consume_returns_none_for_unknown_token() {
        let store = TokenStore::new();
        assert_eq!(store.consume("nonexistent-token"), None);
    }

    #[test]
    fn expired_token_returns_none_for_peek_and_consume() {
        let store = TokenStore::new();
        let token =
            store.create_with_expiry("user@example.com".to_string(), Duration::milliseconds(1));

        std::thread::sleep(std::time::Duration::from_millis(50));

        assert_eq!(store.peek(&token), None);
        assert_eq!(store.consume(&token), None);
    }
}

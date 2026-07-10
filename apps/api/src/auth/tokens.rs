use crate::auth::lock::RwLockRecover;
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
    /// Maps email → most recently created raw token.
    ///
    /// Populated only when the `integration-testing` feature is enabled or in
    /// unit-test builds. Used by integration tests to retrieve the token
    /// generated inside request handlers without seeding it manually.
    /// Never compiled into production builds.
    #[cfg(any(test, feature = "integration-testing"))]
    raw_by_email: Arc<RwLock<HashMap<String, String>>>,
}

impl TokenStore {
    pub fn new() -> Self {
        Self {
            store: Arc::new(RwLock::new(HashMap::new())),
            #[cfg(any(test, feature = "integration-testing"))]
            raw_by_email: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub(crate) fn hash_token(token: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(token.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    /// Checks if a token exists and is valid without consuming it.
    /// Returns the associated email if valid.
    pub fn peek(&self, token: &str) -> Option<String> {
        let now = Utc::now();
        let hash = Self::hash_token(token);
        let store = self.store.read_recover();

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

        #[cfg(any(test, feature = "integration-testing"))]
        let email_for_capture = email.clone();

        let data = TokenData {
            email: email.clone(),
            expires_at,
        };

        let mut store = self.store.write_recover();
        // Keep the store bounded and make the newest request authoritative.
        // This is done under the same write lock as insertion, so concurrent
        // requests cannot leave two usable tokens for one normalized address.
        store.retain(|_, existing| existing.expires_at > now && existing.email != email);
        store.insert(hash, data);

        #[cfg(any(test, feature = "integration-testing"))]
        {
            let mut raw = self.raw_by_email.write_recover();
            raw.insert(email_for_capture, token.clone());
        }

        token
    }

    /// Return the most recently created raw token for the given email.
    #[cfg(any(test, feature = "integration-testing"))]
    pub fn latest_raw_for_email(&self, email: &str) -> Option<String> {
        let raw = self.raw_by_email.read_recover();
        raw.get(email).cloned()
    }

    pub fn consume(&self, token: &str) -> Option<String> {
        let now = Utc::now();
        let hash = Self::hash_token(token);
        let mut store = self.store.write_recover();
        store.retain(|_, v| v.expires_at > now);
        store.remove(&hash).map(|data| data.email)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hash_token_consistent() {
        assert_eq!(
            TokenStore::hash_token("test-token"),
            TokenStore::hash_token("test-token")
        );
    }

    #[test]
    fn hash_token_different_inputs_produce_different_hashes() {
        assert_ne!(
            TokenStore::hash_token("token-a"),
            TokenStore::hash_token("token-b")
        );
    }

    #[test]
    fn create_returns_uuid_format() {
        let store = TokenStore::new();
        let token = store.create("user@example.com".to_string());
        assert!(Uuid::parse_str(&token).is_ok());
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
        assert_eq!(store.consume(&token), Some("user@example.com".to_string()));
        assert_eq!(store.consume(&token), None);
    }

    #[test]
    fn newer_token_invalidates_previous_token_for_same_email() {
        let store = TokenStore::new();
        let first = store.create("user@example.com".to_string());
        let second = store.create("user@example.com".to_string());

        assert_eq!(store.peek(&first), None);
        assert_eq!(store.consume(&first), None);
        assert_eq!(store.consume(&second), Some("user@example.com".to_string()));
    }

    #[test]
    fn newer_token_does_not_invalidate_other_email() {
        let store = TokenStore::new();
        let first_user = store.create("first@example.com".to_string());
        let second_user = store.create("second@example.com".to_string());

        assert_eq!(
            store.consume(&first_user),
            Some("first@example.com".to_string())
        );
        assert_eq!(
            store.consume(&second_user),
            Some("second@example.com".to_string())
        );
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

#[cfg(test)]
mod poison_recovery_tests {
    use super::*;
    use std::collections::HashMap;
    use std::sync::Arc;
    use std::thread;

    fn poison_write_lock(lock: &Arc<RwLock<HashMap<String, TokenData>>>) {
        let l = Arc::clone(lock);
        let _ = thread::spawn(move || {
            let _guard = l.write().unwrap();
            panic!("intentional poison");
        })
        .join();
    }

    #[test]
    fn token_store_recovers_from_poisoned_lock() {
        let store = TokenStore::new();
        let token = store.create("user@example.com".to_string());
        poison_write_lock(&store.store);
        assert!(store.store.write().is_err());
        assert_eq!(store.peek(&token), Some("user@example.com".to_string()));
        assert_eq!(store.consume(&token), Some("user@example.com".to_string()));
        assert!(store.store.read().is_ok());
    }

    #[test]
    fn token_store_create_after_poison_issues_usable_token() {
        let store = TokenStore::new();
        poison_write_lock(&store.store);
        let token = store.create("new@example.com".to_string());
        assert_eq!(store.consume(&token), Some("new@example.com".to_string()));
    }
}

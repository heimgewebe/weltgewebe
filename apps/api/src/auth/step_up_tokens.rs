use chrono::{DateTime, Duration, Utc};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use uuid::Uuid;

#[derive(Clone, Debug)]
pub struct StepUpTokenData {
    pub challenge_id: String,
    pub account_id: String,
    pub device_id: String,
    pub expires_at: DateTime<Utc>,
}

#[derive(Clone, Default)]
pub struct StepUpTokenStore {
    store: Arc<RwLock<HashMap<String, StepUpTokenData>>>,
}

impl StepUpTokenStore {
    pub fn new() -> Self {
        Self {
            store: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub(crate) fn hash_token(token: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(token.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    pub fn peek(&self, token: &str) -> Option<StepUpTokenData> {
        let now = Utc::now();
        let hash = Self::hash_token(token);
        let store = self.store.read().expect("StepUpTokenStore lock poisoned");

        if let Some(data) = store.get(&hash) {
            if data.expires_at > now {
                return Some(data.clone());
            }
        }
        None
    }

    pub fn create(&self, challenge_id: String, account_id: String, device_id: String) -> String {
        // Step-up tokens are strictly short-lived (e.g., 5 mins)
        self.create_with_expiry(challenge_id, account_id, device_id, Duration::minutes(5))
    }

    pub fn create_with_expiry(
        &self,
        challenge_id: String,
        account_id: String,
        device_id: String,
        duration: Duration,
    ) -> String {
        let token = Uuid::new_v4().to_string();
        let hash = Self::hash_token(&token);

        let now = Utc::now();
        let expires_at = now + duration;

        let data = StepUpTokenData {
            challenge_id,
            account_id,
            device_id,
            expires_at,
        };

        let mut store = self.store.write().expect("StepUpTokenStore lock poisoned");
        store.retain(|_, v| v.expires_at > now);
        store.insert(hash, data);

        token
    }

    pub fn consume(&self, token: &str) -> Option<StepUpTokenData> {
        let now = Utc::now();
        let hash = Self::hash_token(token);
        let mut store = self.store.write().expect("StepUpTokenStore lock poisoned");

        store.retain(|_, v| v.expires_at > now);

        if let Some(data) = store.remove(&hash) {
            if data.expires_at <= now {
                return None;
            }
            return Some(data);
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hash_token_consistent() {
        let hash1 = StepUpTokenStore::hash_token("test-token");
        let hash2 = StepUpTokenStore::hash_token("test-token");
        assert_eq!(hash1, hash2);
    }

    #[test]
    fn create_returns_uuid_format() {
        let store = StepUpTokenStore::new();
        let token = store.create("c-1".to_string(), "a-1".to_string(), "d-1".to_string());
        assert!(
            uuid::Uuid::parse_str(&token).is_ok(),
            "Token should be valid UUID"
        );
    }

    #[test]
    fn peek_returns_data_for_valid_token() {
        let store = StepUpTokenStore::new();
        let token = store.create("c-1".to_string(), "a-1".to_string(), "d-1".to_string());
        let data = store.peek(&token).unwrap();
        assert_eq!(data.challenge_id, "c-1");
        assert_eq!(data.account_id, "a-1");
        assert_eq!(data.device_id, "d-1");
    }

    #[test]
    fn consume_returns_data_and_removes_token() {
        let store = StepUpTokenStore::new();
        let token = store.create("c-1".to_string(), "a-1".to_string(), "d-1".to_string());

        let first = store.consume(&token).unwrap();
        assert_eq!(first.challenge_id, "c-1");

        let second = store.consume(&token);
        assert!(second.is_none());
    }

    #[test]
    fn expired_token_returns_none() {
        let store = StepUpTokenStore::new();
        let token = store.create_with_expiry(
            "c-1".to_string(),
            "a-1".to_string(),
            "d-1".to_string(),
            Duration::milliseconds(1),
        );

        std::thread::sleep(std::time::Duration::from_millis(50));

        assert!(store.peek(&token).is_none());
        assert!(store.consume(&token).is_none());
    }
}

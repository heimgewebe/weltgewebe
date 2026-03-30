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

/// Result of an atomic [`StepUpTokenStore::consume_if_matches`] operation.
pub enum ConsumeMatchResult {
    /// Token not found or expired.
    NotFound,
    /// Token found but at least one binding (challenge_id, account_id, device_id) did not match.
    /// The token is left intact so the correct caller can still use it.
    BindingMismatch,
    /// All bindings matched; the token has been removed.
    Consumed(StepUpTokenData),
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

    pub fn consume_if_matches(
        &self,
        token: &str,
        expected_challenge_id: &str,
        expected_account_id: &str,
        expected_device_id: &str,
    ) -> ConsumeMatchResult {
        let now = Utc::now();
        let hash = Self::hash_token(token);
        let mut store = self.store.write().expect("StepUpTokenStore lock poisoned");
        store.retain(|_, v| v.expires_at > now);

        match store.get(&hash) {
            None => ConsumeMatchResult::NotFound,
            Some(data) => {
                if data.challenge_id != expected_challenge_id
                    || data.account_id != expected_account_id
                    || data.device_id != expected_device_id
                {
                    ConsumeMatchResult::BindingMismatch
                } else {
                    let data = store.remove(&hash).expect("entry was present under write lock");
                    ConsumeMatchResult::Consumed(data)
                }
            }
        }
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
    fn consume_if_matches_removes_on_full_match() {
        let store = StepUpTokenStore::new();
        let token = store.create("c-1".to_string(), "a-1".to_string(), "d-1".to_string());

        let result = store.consume_if_matches(&token, "c-1", "a-1", "d-1");
        assert!(matches!(result, ConsumeMatchResult::Consumed(_)));

        // Token must be gone after successful consume
        let result2 = store.consume_if_matches(&token, "c-1", "a-1", "d-1");
        assert!(matches!(result2, ConsumeMatchResult::NotFound));
    }

    #[test]
    fn consume_if_matches_preserves_token_on_account_mismatch() {
        let store = StepUpTokenStore::new();
        let token = store.create("c-1".to_string(), "a-1".to_string(), "d-1".to_string());

        let result = store.consume_if_matches(&token, "c-1", "wrong-account", "d-1");
        assert!(matches!(result, ConsumeMatchResult::BindingMismatch));

        // Token must still be present and consumable by the correct caller
        let result2 = store.consume_if_matches(&token, "c-1", "a-1", "d-1");
        assert!(matches!(result2, ConsumeMatchResult::Consumed(_)));
    }

    #[test]
    fn consume_if_matches_preserves_token_on_device_mismatch() {
        let store = StepUpTokenStore::new();
        let token = store.create("c-1".to_string(), "a-1".to_string(), "d-1".to_string());

        let result = store.consume_if_matches(&token, "c-1", "a-1", "wrong-device");
        assert!(matches!(result, ConsumeMatchResult::BindingMismatch));

        let result2 = store.consume_if_matches(&token, "c-1", "a-1", "d-1");
        assert!(matches!(result2, ConsumeMatchResult::Consumed(_)));
    }

    #[test]
    fn consume_if_matches_preserves_token_on_challenge_mismatch() {
        let store = StepUpTokenStore::new();
        let token = store.create("c-1".to_string(), "a-1".to_string(), "d-1".to_string());

        let result = store.consume_if_matches(&token, "wrong-challenge", "a-1", "d-1");
        assert!(matches!(result, ConsumeMatchResult::BindingMismatch));

        let result2 = store.consume_if_matches(&token, "c-1", "a-1", "d-1");
        assert!(matches!(result2, ConsumeMatchResult::Consumed(_)));
    }

    #[test]
    fn consume_if_matches_returns_not_found_for_missing_token() {
        let store = StepUpTokenStore::new();
        let result = store.consume_if_matches("no-such-token", "c-1", "a-1", "d-1");
        assert!(matches!(result, ConsumeMatchResult::NotFound));
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

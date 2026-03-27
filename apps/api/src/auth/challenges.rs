use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use uuid::Uuid;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum ChallengeIntent {
    LogoutAll,
    RemoveDevice { target_device_id: String },
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Challenge {
    pub id: String,
    pub account_id: String,
    pub device_id: String,
    pub intent: ChallengeIntent,
    pub created_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
}

impl Challenge {
    pub fn is_expired(&self) -> bool {
        Utc::now() > self.expires_at
    }
}

#[derive(Clone, Default)]
pub struct ChallengeStore {
    store: Arc<RwLock<HashMap<String, Challenge>>>,
}

impl ChallengeStore {
    pub fn new() -> Self {
        Self {
            store: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub fn cleanup_expired(&self) {
        if let Ok(mut store) = self.store.write() {
            let now = Utc::now();
            store.retain(|_, challenge| challenge.expires_at > now);
        }
    }

    pub fn create(
        &self,
        account_id: String,
        device_id: String,
        intent: ChallengeIntent,
    ) -> Challenge {
        self.cleanup_expired();

        // 1. Try to find and reuse an existing active challenge with identical context
        {
            let store = self.store.read().expect("ChallengeStore lock poisoned");
            for existing_challenge in store.values() {
                if existing_challenge.account_id == account_id
                    && existing_challenge.device_id == device_id
                    && existing_challenge.intent == intent
                    && !existing_challenge.is_expired()
                {
                    return existing_challenge.clone();
                }
            }
        }

        // 2. Fallback: create a new one if no active matching challenge exists
        let id = Uuid::new_v4().to_string();
        let now = Utc::now();
        // Step-up Challenges TTL is short-lived, typically 5 minutes
        let expires_at = now + Duration::minutes(5);

        let challenge = Challenge {
            id: id.clone(),
            account_id,
            device_id,
            intent,
            created_at: now,
            expires_at,
        };

        let mut store = self.store.write().expect("ChallengeStore lock poisoned");
        store.insert(id, challenge.clone());

        challenge
    }

    pub fn consume(&self, challenge_id: &str) -> Option<Challenge> {
        let mut store = self.store.write().expect("ChallengeStore lock poisoned");
        if let Some(challenge) = store.remove(challenge_id) {
            if !challenge.is_expired() {
                return Some(challenge);
            }
        }
        None
    }

    pub fn get(&self, challenge_id: &str) -> Option<Challenge> {
        let is_expired = {
            let store = self.store.read().expect("ChallengeStore lock poisoned");
            if let Some(challenge) = store.get(challenge_id) {
                if !challenge.is_expired() {
                    return Some(challenge.clone());
                }
                true
            } else {
                false
            }
        };

        if is_expired {
            let mut store = self.store.write().expect("ChallengeStore lock poisoned");
            store.remove(challenge_id);
        }

        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_and_get_challenge() {
        let store = ChallengeStore::new();
        let c = store.create(
            "acc-1".to_string(),
            "dev-1".to_string(),
            ChallengeIntent::LogoutAll,
        );

        let retrieved = store.get(&c.id).unwrap();
        assert_eq!(retrieved.account_id, "acc-1");
        assert_eq!(retrieved.device_id, "dev-1");
        assert_eq!(retrieved.intent, ChallengeIntent::LogoutAll);
    }

    #[test]
    fn test_consume_removes_challenge() {
        let store = ChallengeStore::new();
        let c = store.create(
            "acc-1".to_string(),
            "dev-1".to_string(),
            ChallengeIntent::LogoutAll,
        );

        let consumed = store.consume(&c.id).unwrap();
        assert_eq!(consumed.id, c.id);

        assert!(store.get(&c.id).is_none());
    }

    #[test]
    fn test_get_removes_expired_challenge() {
        let store = ChallengeStore::new();
        let c = store.create(
            "acc-1".to_string(),
            "dev-1".to_string(),
            ChallengeIntent::LogoutAll,
        );

        // Manually expire the challenge
        {
            let mut w = store.store.write().unwrap();
            let challenge = w.get_mut(&c.id).unwrap();
            challenge.expires_at = Utc::now() - Duration::minutes(10);
        }

        // Before get, it's still in the map
        assert!(store.store.read().unwrap().contains_key(&c.id));

        // get() should return None and remove it
        let retrieved = store.get(&c.id);
        assert!(retrieved.is_none());

        // After get, it should be removed from the map
        assert!(!store.store.read().unwrap().contains_key(&c.id));
    }

    #[test]
    fn test_create_reuses_active_challenge() {
        let store = ChallengeStore::new();
        let c1 = store.create(
            "acc-1".to_string(),
            "dev-1".to_string(),
            ChallengeIntent::LogoutAll,
        );

        let c2 = store.create(
            "acc-1".to_string(),
            "dev-1".to_string(),
            ChallengeIntent::LogoutAll,
        );

        assert_eq!(
            c1.id, c2.id,
            "Second call should return the exact same challenge ID"
        );
    }

    #[test]
    fn test_create_generates_new_challenge_for_different_intent() {
        let store = ChallengeStore::new();
        let c1 = store.create(
            "acc-1".to_string(),
            "dev-1".to_string(),
            ChallengeIntent::LogoutAll,
        );

        let c2 = store.create(
            "acc-1".to_string(),
            "dev-1".to_string(),
            ChallengeIntent::RemoveDevice {
                target_device_id: "dev-2".to_string(),
            },
        );

        assert_ne!(
            c1.id, c2.id,
            "Changing intent should produce a new challenge ID"
        );
    }
}

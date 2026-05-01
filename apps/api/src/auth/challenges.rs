use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use uuid::Uuid;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum ChallengeIntent {
    LogoutAll,
    RemoveDevice { target_device_id: String },
    UpdateEmail { new_email: String },
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
struct ChallengeState {
    // Maps challenge_id -> Challenge
    challenges: HashMap<String, Challenge>,
    // Maps account_id -> list of challenge_ids
    account_index: HashMap<String, Vec<String>>,
}

#[derive(Clone, Default)]
pub struct ChallengeStore {
    state: Arc<RwLock<ChallengeState>>,
}

impl ChallengeStore {
    pub fn new() -> Self {
        Self {
            state: Arc::new(RwLock::new(ChallengeState::default())),
        }
    }

    pub fn cleanup_expired(&self) {
        if let Ok(mut state) = self.state.write() {
            let now = Utc::now();

            // Keep track of expired challenge IDs to remove from the index
            let mut expired_ids = Vec::new();
            state.challenges.retain(|id, challenge| {
                let keep = challenge.expires_at > now;
                if !keep {
                    expired_ids.push((id.clone(), challenge.account_id.clone()));
                }
                keep
            });

            // Remove expired IDs from the index
            for (id, account_id) in expired_ids {
                if let Some(ids) = state.account_index.get_mut(&account_id) {
                    ids.retain(|x| x != &id);
                    if ids.is_empty() {
                        state.account_index.remove(&account_id);
                    }
                }
            }
        }
    }

    pub fn create(
        &self,
        account_id: String,
        device_id: String,
        intent: ChallengeIntent,
    ) -> Challenge {
        // Atomic block: take a single write lock to avoid race conditions
        let mut state = self.state.write().expect("ChallengeStore lock poisoned");

        let now = Utc::now();

        // 1. Try to find and reuse an existing active challenge with identical context
        // Search ONLY within challenges for this account (O(1) lookup + small scan)
        if let Some(ids) = state.account_index.get(&account_id) {
            for id in ids {
                if let Some(existing_challenge) = state.challenges.get(id) {
                    if existing_challenge.expires_at > now
                        && existing_challenge.device_id == device_id
                        && existing_challenge.intent == intent
                    {
                        return existing_challenge.clone();
                    }
                }
            }
        }

        // 2. Fallback: create a new one if no active matching challenge exists
        let id = Uuid::new_v4().to_string();
        // Step-up Challenges TTL is short-lived, typically 5 minutes
        let expires_at = now + Duration::minutes(5);

        let challenge = Challenge {
            id: id.clone(),
            account_id: account_id.clone(),
            device_id,
            intent,
            created_at: now,
            expires_at,
        };

        state.challenges.insert(id.clone(), challenge.clone());
        state.account_index.entry(account_id).or_default().push(id);

        challenge
    }

    pub fn consume(&self, challenge_id: &str) -> Option<Challenge> {
        let mut state = self.state.write().expect("ChallengeStore lock poisoned");
        if let Some(challenge) = state.challenges.remove(challenge_id) {
            // Clean up index
            if let Some(ids) = state.account_index.get_mut(&challenge.account_id) {
                ids.retain(|x| x != challenge_id);
                if ids.is_empty() {
                    state.account_index.remove(&challenge.account_id);
                }
            }

            if !challenge.is_expired() {
                return Some(challenge);
            }
        }
        None
    }

    pub fn get(&self, challenge_id: &str) -> Option<Challenge> {
        let is_expired = {
            let state = self.state.read().expect("ChallengeStore lock poisoned");
            if let Some(challenge) = state.challenges.get(challenge_id) {
                if !challenge.is_expired() {
                    return Some(challenge.clone());
                }
                true
            } else {
                false
            }
        };

        if is_expired {
            let mut state = self.state.write().expect("ChallengeStore lock poisoned");
            if let Some(challenge) = state.challenges.remove(challenge_id) {
                // Clean up index
                if let Some(ids) = state.account_index.get_mut(&challenge.account_id) {
                    ids.retain(|x| x != challenge_id);
                    if ids.is_empty() {
                        state.account_index.remove(&challenge.account_id);
                    }
                }
            }
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
            let mut w = store.state.write().unwrap();
            let challenge = w.challenges.get_mut(&c.id).unwrap();
            challenge.expires_at = Utc::now() - Duration::minutes(10);
        }

        // Before get, it's still in the map
        assert!(store.state.read().unwrap().challenges.contains_key(&c.id));

        // get() should return None and remove it
        let retrieved = store.get(&c.id);
        assert!(retrieved.is_none());

        // After get, it should be removed from the map
        assert!(!store.state.read().unwrap().challenges.contains_key(&c.id));
        // And index should be empty/removed
        assert!(store
            .state
            .read()
            .unwrap()
            .account_index
            .get("acc-1")
            .is_none_or(|ids| ids.is_empty()));
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

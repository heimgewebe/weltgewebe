use crate::auth::lock::RwLockRecover;
use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use uuid::Uuid;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, Hash)]
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

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
struct ChallengeContextKey {
    account_id: String,
    device_id: String,
    intent: ChallengeIntent,
}

#[derive(Clone, Default)]
struct ChallengeState {
    // Maps challenge_id -> Challenge
    challenges: HashMap<String, Challenge>,
    // Maps exact context -> challenge_id
    active_by_context: HashMap<ChallengeContextKey, String>,
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

    fn context_key(challenge: &Challenge) -> ChallengeContextKey {
        ChallengeContextKey {
            account_id: challenge.account_id.clone(),
            device_id: challenge.device_id.clone(),
            intent: challenge.intent.clone(),
        }
    }

    fn remove_challenge(state: &mut ChallengeState, challenge_id: &str) -> Option<Challenge> {
        let challenge = state.challenges.remove(challenge_id)?;
        let key = Self::context_key(&challenge);
        if state
            .active_by_context
            .get(&key)
            .is_none_or(|id| id == challenge_id)
        {
            state.active_by_context.remove(&key);
        }
        Some(challenge)
    }

    fn cleanup_expired_locked(state: &mut ChallengeState, now: DateTime<Utc>) {
        let expired_ids: Vec<String> = state
            .challenges
            .iter()
            .filter(|(_, challenge)| challenge.expires_at <= now)
            .map(|(id, _)| id.clone())
            .collect();

        for id in expired_ids {
            Self::remove_challenge(state, &id);
        }
    }

    pub fn cleanup_expired(&self) {
        if let Ok(mut state) = self.state.write() {
            let now = Utc::now();
            Self::cleanup_expired_locked(&mut state, now);
        }
    }

    pub fn create(
        &self,
        account_id: String,
        device_id: String,
        intent: ChallengeIntent,
    ) -> Challenge {
        // Atomic block: take a single write lock to avoid race conditions
        let mut state = self.state.write_recover();

        let now = Utc::now();

        Self::cleanup_expired_locked(&mut state, now);

        let key = ChallengeContextKey {
            account_id: account_id.clone(),
            device_id: device_id.clone(),
            intent: intent.clone(),
        };

        // 1. Try to find and reuse an existing active challenge with identical context
        if let Some(challenge_id) = state.active_by_context.get(&key) {
            if let Some(challenge) = state.challenges.get(challenge_id) {
                if challenge.expires_at > now {
                    return challenge.clone();
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
        state.active_by_context.insert(key, id);

        challenge
    }

    pub fn consume(&self, challenge_id: &str) -> Option<Challenge> {
        let mut state = self.state.write_recover();
        if let Some(challenge) = Self::remove_challenge(&mut state, challenge_id) {
            if !challenge.is_expired() {
                return Some(challenge);
            }
        }
        None
    }

    pub fn get(&self, challenge_id: &str) -> Option<Challenge> {
        let is_expired = {
            let state = self.state.read_recover();
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
            let mut state = self.state.write_recover();
            Self::remove_challenge(&mut state, challenge_id);
        }

        None
    }
}

#[cfg(test)]
mod invariants_tests {
    use super::*;

    #[test]
    fn test_create_removes_expired_challenge_from_context_index() {
        let store = ChallengeStore::new();
        let c1 = store.create(
            "acc-1".to_string(),
            "dev-1".to_string(),
            ChallengeIntent::LogoutAll,
        );

        // Manually expire c1
        {
            let mut state = store.state.write().unwrap();
            let challenge = state.challenges.get_mut(&c1.id).unwrap();
            challenge.expires_at = Utc::now() - Duration::minutes(10);
        }

        let c2 = store.create(
            "acc-1".to_string(),
            "dev-1".to_string(),
            ChallengeIntent::LogoutAll,
        );

        assert_ne!(c1.id, c2.id, "Should create a new challenge");

        let state = store.state.read().unwrap();
        assert!(
            !state.challenges.contains_key(&c1.id),
            "Old challenge should be removed"
        );
        assert!(
            state.challenges.contains_key(&c2.id),
            "New challenge should exist"
        );

        let key = ChallengeContextKey {
            account_id: "acc-1".to_string(),
            device_id: "dev-1".to_string(),
            intent: ChallengeIntent::LogoutAll,
        };
        assert_eq!(
            state.active_by_context.get(&key).unwrap(),
            &c2.id,
            "Index should point to new ID"
        );
    }

    #[test]
    fn test_consume_cleans_context_index() {
        let store = ChallengeStore::new();
        let c1 = store.create(
            "acc-1".to_string(),
            "dev-1".to_string(),
            ChallengeIntent::LogoutAll,
        );

        let consumed = store.consume(&c1.id).unwrap();
        assert_eq!(consumed.id, c1.id);

        let c2 = store.create(
            "acc-1".to_string(),
            "dev-1".to_string(),
            ChallengeIntent::LogoutAll,
        );

        assert_ne!(
            c1.id, c2.id,
            "Should create a new challenge after consumption"
        );

        let state = store.state.read().unwrap();
        let key = ChallengeContextKey {
            account_id: "acc-1".to_string(),
            device_id: "dev-1".to_string(),
            intent: ChallengeIntent::LogoutAll,
        };
        assert_eq!(
            state.active_by_context.get(&key).unwrap(),
            &c2.id,
            "Index should point to new ID and no stale index remained"
        );
    }

    #[test]
    fn test_get_expired_cleans_context_index() {
        let store = ChallengeStore::new();
        let c1 = store.create(
            "acc-1".to_string(),
            "dev-1".to_string(),
            ChallengeIntent::LogoutAll,
        );

        // Manually expire c1
        {
            let mut state = store.state.write().unwrap();
            let challenge = state.challenges.get_mut(&c1.id).unwrap();
            challenge.expires_at = Utc::now() - Duration::minutes(10);
        }

        assert!(
            store.get(&c1.id).is_none(),
            "Should return None for expired challenge"
        );

        let state = store.state.read().unwrap();
        assert!(
            !state.challenges.contains_key(&c1.id),
            "Old challenge should be removed"
        );

        let key = ChallengeContextKey {
            account_id: "acc-1".to_string(),
            device_id: "dev-1".to_string(),
            intent: ChallengeIntent::LogoutAll,
        };
        assert!(
            !state.active_by_context.contains_key(&key),
            "Context index should be cleaned up"
        );
    }

    #[test]
    fn test_create_generates_new_challenge_for_different_device() {
        let store = ChallengeStore::new();
        let c1 = store.create(
            "acc-1".to_string(),
            "dev-1".to_string(),
            ChallengeIntent::LogoutAll,
        );

        let c2 = store.create(
            "acc-1".to_string(),
            "dev-2".to_string(),
            ChallengeIntent::LogoutAll,
        );

        assert_ne!(
            c1.id, c2.id,
            "Changing device should produce a new challenge ID"
        );
    }

    #[test]
    fn test_create_generates_new_challenge_for_different_account() {
        let store = ChallengeStore::new();
        let c1 = store.create(
            "acc-1".to_string(),
            "dev-1".to_string(),
            ChallengeIntent::LogoutAll,
        );

        let c2 = store.create(
            "acc-2".to_string(),
            "dev-1".to_string(),
            ChallengeIntent::LogoutAll,
        );

        assert_ne!(
            c1.id, c2.id,
            "Changing account should produce a new challenge ID"
        );
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

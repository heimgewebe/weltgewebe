use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::{Arc, RwLock, RwLockWriteGuard};
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

    /// Rebuilds `active_by_context` from `challenges`, discarding expired entries.
    ///
    /// Called after lock-poison recovery to repair the cross-map invariant:
    /// `active_by_context[key]` must point to a valid, non-expired entry in
    /// `challenges`. First entry wins per context, consistent with `create()`'s
    /// deduplication policy.
    fn rebuild_active_by_context_locked(state: &mut ChallengeState) {
        state.active_by_context.clear();
        for (id, challenge) in state.challenges.iter() {
            if !challenge.is_expired() {
                let key = Self::context_key(challenge);
                state
                    .active_by_context
                    .entry(key)
                    .or_insert_with(|| id.clone());
            }
        }
    }

    /// Acquires the write lock, repairing the context index if the lock is poisoned.
    ///
    /// Do NOT replace this with the generic `RwLockRecover` helper — `ChallengeStore`
    /// has a `challenges` ↔ `active_by_context` cross-map invariant that a plain
    /// `into_inner()` does not restore.
    fn write_locked_repaired(&self) -> RwLockWriteGuard<'_, ChallengeState> {
        match self.state.write() {
            Ok(guard) => guard,
            Err(poisoned) => {
                tracing::warn!(
                    event = "auth.challenge_store.poison_recovered",
                    "Recovered from poisoned ChallengeStore lock; rebuilding context index"
                );
                let mut guard = poisoned.into_inner();
                Self::rebuild_active_by_context_locked(&mut guard);
                // Clear poison only after successful rebuild so future lock
                // acquisitions succeed without repeating this warning.
                self.state.clear_poison();
                guard
            }
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
        let mut state = self.write_locked_repaired();
        let now = Utc::now();
        Self::cleanup_expired_locked(&mut state, now);
    }

    pub fn create(
        &self,
        account_id: String,
        device_id: String,
        intent: ChallengeIntent,
    ) -> Challenge {
        // Atomic block: take a single write lock to avoid race conditions
        let mut state = self.write_locked_repaired();

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
        let mut state = self.write_locked_repaired();
        if let Some(challenge) = Self::remove_challenge(&mut state, challenge_id) {
            if !challenge.is_expired() {
                return Some(challenge);
            }
        }
        None
    }

    pub fn get(&self, challenge_id: &str) -> Option<Challenge> {
        let is_expired = {
            // Read path does not use `active_by_context`; plain into_inner()
            // recovery is safe. The next write will rebuild the index.
            let state = self.state.read().unwrap_or_else(|poisoned| {
                tracing::warn!(
                    event = "auth.challenge_store.poison_recovered",
                    "Recovered from poisoned ChallengeStore lock (read path); index will be rebuilt on next write"
                );
                poisoned.into_inner()
            });
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
            let mut state = self.write_locked_repaired();
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

#[cfg(test)]
mod poison_recovery_tests {
    use super::*;
    use std::sync::Arc;
    use std::thread;

    fn poison_write_lock(state: &Arc<RwLock<ChallengeState>>) {
        let s = Arc::clone(state);
        let _ = thread::spawn(move || {
            let _guard = s.write().unwrap();
            panic!("intentional poison");
        })
        .join();
    }

    #[test]
    fn write_locked_repaired_rebuilds_index_after_poison() {
        let store = ChallengeStore::new();

        // Insert a valid challenge directly so we have one entry to rebuild from.
        let challenge_id = {
            let c = store.create(
                "acc-1".to_string(),
                "dev-1".to_string(),
                ChallengeIntent::LogoutAll,
            );
            c.id.clone()
        };

        // Poison the lock while holding a write guard — simulates a panic mid-mutation.
        poison_write_lock(&store.state);
        assert!(store.state.write().is_err(), "lock should be poisoned");

        // write_locked_repaired must recover and present a consistent store.
        let c2 = store.create(
            "acc-1".to_string(),
            "dev-1".to_string(),
            ChallengeIntent::LogoutAll,
        );

        // Same context → should reuse the existing challenge (deduplication).
        assert_eq!(
            c2.id, challenge_id,
            "Recovered store should reuse the existing active challenge"
        );

        // Lock must no longer be poisoned after repair.
        assert!(
            store.state.write().is_ok(),
            "lock should be healthy after recovery"
        );

        // Index invariant: active_by_context points to the challenge.
        let key = ChallengeContextKey {
            account_id: "acc-1".to_string(),
            device_id: "dev-1".to_string(),
            intent: ChallengeIntent::LogoutAll,
        };
        let state = store.state.read().unwrap();
        assert_eq!(state.active_by_context.get(&key).unwrap(), &challenge_id);
    }

    #[test]
    fn poisoned_store_discards_expired_entries_during_rebuild() {
        let store = ChallengeStore::new();

        // Insert a challenge and manually expire it.
        let c = store.create(
            "acc-2".to_string(),
            "dev-2".to_string(),
            ChallengeIntent::LogoutAll,
        );
        {
            let mut state = store.state.write().unwrap();
            state.challenges.get_mut(&c.id).unwrap().expires_at =
                Utc::now() - Duration::minutes(10);
        }

        poison_write_lock(&store.state);

        // After recovery, creating a new challenge for the same context must
        // produce a new ID, not the expired one.
        let c2 = store.create(
            "acc-2".to_string(),
            "dev-2".to_string(),
            ChallengeIntent::LogoutAll,
        );
        assert_ne!(
            c.id, c2.id,
            "Should not reuse expired challenge after recovery"
        );

        let key = ChallengeContextKey {
            account_id: "acc-2".to_string(),
            device_id: "dev-2".to_string(),
            intent: ChallengeIntent::LogoutAll,
        };
        let state = store.state.read().unwrap();
        assert_eq!(state.active_by_context.get(&key).unwrap(), &c2.id);
    }

    #[test]
    fn consume_works_after_lock_poison() {
        let store = ChallengeStore::new();
        let c = store.create(
            "acc-3".to_string(),
            "dev-3".to_string(),
            ChallengeIntent::LogoutAll,
        );

        poison_write_lock(&store.state);

        let consumed = store.consume(&c.id);
        assert!(
            consumed.is_some(),
            "consume should succeed after lock recovery"
        );
        assert_eq!(consumed.unwrap().id, c.id);

        // Challenge must be gone and index cleaned up.
        let state = store.state.read().unwrap();
        assert!(!state.challenges.contains_key(&c.id));
        let key = ChallengeContextKey {
            account_id: "acc-3".to_string(),
            device_id: "dev-3".to_string(),
            intent: ChallengeIntent::LogoutAll,
        };
        assert!(!state.active_by_context.contains_key(&key));
    }
}

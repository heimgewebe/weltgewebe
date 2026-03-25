use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use uuid::Uuid;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Session {
    pub id: String,
    pub account_id: String,
    pub device_id: String,
    pub created_at: DateTime<Utc>,
    pub last_active: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
}

impl Session {
    pub fn is_expired(&self) -> bool {
        Utc::now() > self.expires_at
    }
}

#[derive(Clone, Default)]
pub struct SessionStore {
    store: Arc<RwLock<HashMap<String, Session>>>,
}

impl SessionStore {
    pub fn new() -> Self {
        Self {
            store: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub fn cleanup_expired(&self) {
        if let Ok(mut store) = self.store.write() {
            let now = Utc::now();
            store.retain(|_, session| session.expires_at > now);
        }
    }

    pub fn create(&self, account_id: String, existing_device_id: Option<String>) -> Session {
        self.cleanup_expired();

        let session_id = Uuid::new_v4().to_string();
        let device_id = existing_device_id.unwrap_or_else(|| Uuid::new_v4().to_string());
        let now = Utc::now();
        let expires_at = now + Duration::days(1);

        let session = Session {
            id: session_id.clone(),
            account_id,
            device_id,
            created_at: now,
            last_active: now,
            expires_at,
        };

        let mut store = self.store.write().expect("SessionStore lock poisoned");
        store.insert(session_id, session.clone());

        session
    }

    pub fn get(&self, session_id: &str) -> Option<Session> {
        let store = self.store.read().expect("SessionStore lock poisoned");
        if let Some(session) = store.get(session_id) {
            if !session.is_expired() {
                return Some(session.clone());
            }
        }
        None
    }

    pub fn delete(&self, session_id: &str) {
        let mut store = self.store.write().expect("SessionStore lock poisoned");
        store.remove(session_id);
    }

    pub fn touch(&self, session_id: &str) {
        let now = Utc::now();

        // Optimistic read first to check if update is necessary
        let needs_update = {
            let store = self.store.read().expect("SessionStore lock poisoned");
            if let Some(session) = store.get(session_id) {
                // Only update if older than 5 minutes to prevent lock contention
                now.signed_duration_since(session.last_active) > Duration::minutes(5)
            } else {
                false
            }
        };

        if needs_update {
            let mut store = self.store.write().expect("SessionStore lock poisoned");
            if let Some(session) = store.get_mut(session_id) {
                session.last_active = now;
            }
        }
    }

    pub fn list_by_account(&self, account_id: &str) -> Vec<Session> {
        let store = self.store.read().expect("SessionStore lock poisoned");
        let now = Utc::now();
        store
            .values()
            .filter(|s| s.account_id == account_id && s.expires_at > now)
            .cloned()
            .collect()
    }

    pub fn delete_by_device(&self, account_id: &str, device_id: &str) {
        let mut store = self.store.write().expect("SessionStore lock poisoned");
        store.retain(|_, s| !(s.account_id == account_id && s.device_id == device_id));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn create_produces_session_with_correct_account_id() {
        let store = SessionStore::new();
        let session = store.create("account-42".to_string(), None);
        assert_eq!(session.account_id, "account-42");
    }

    #[test]
    fn create_produces_unique_session_ids() {
        let store = SessionStore::new();
        let s1 = store.create("a".to_string(), None);
        let s2 = store.create("b".to_string(), None);
        assert_ne!(s1.id, s2.id);
    }

    #[test]
    fn create_preserves_device_id() {
        let store = SessionStore::new();
        let s1 = store.create("a".to_string(), Some("dev-123".to_string()));
        assert_eq!(s1.device_id, "dev-123");
    }

    #[test]
    fn get_returns_created_session() {
        let store = SessionStore::new();
        let session = store.create("account-1".to_string(), None);
        let retrieved = store.get(&session.id);
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().account_id, "account-1");
    }

    #[test]
    fn get_returns_none_for_unknown_id() {
        let store = SessionStore::new();
        assert!(store.get("nonexistent-id").is_none());
    }

    #[test]
    fn delete_removes_session() {
        let store = SessionStore::new();
        let session = store.create("account-1".to_string(), None);
        store.delete(&session.id);
        assert!(store.get(&session.id).is_none());
    }

    #[test]
    fn list_by_account_returns_sessions() {
        let store = SessionStore::new();
        let _ = store.create("acc-1".to_string(), None);
        let _ = store.create("acc-1".to_string(), None);
        let _ = store.create("acc-2".to_string(), None);

        let sessions = store.list_by_account("acc-1");
        assert_eq!(sessions.len(), 2);
    }

    #[test]
    fn delete_by_device_removes_correct_sessions() {
        let store = SessionStore::new();
        let _s1 = store.create("acc-1".to_string(), Some("dev-A".to_string()));
        let _s2 = store.create("acc-1".to_string(), Some("dev-A".to_string()));
        let s3 = store.create("acc-1".to_string(), Some("dev-B".to_string()));

        store.delete_by_device("acc-1", "dev-A");

        let sessions = store.list_by_account("acc-1");
        assert_eq!(sessions.len(), 1);
        assert_eq!(sessions[0].id, s3.id);
    }

    #[test]
    fn session_expires_at_is_approximately_one_day() {
        let store = SessionStore::new();
        let before = Utc::now();
        let session = store.create("account-1".to_string(), None);
        let after = Utc::now();

        let expected_min = before + Duration::days(1);
        let expected_max = after + Duration::days(1);

        assert!(session.expires_at >= expected_min);
        assert!(session.expires_at <= expected_max);
    }

    #[test]
    fn is_expired_returns_false_for_new_session() {
        let store = SessionStore::new();
        let session = store.create("account-1".to_string(), None);
        assert!(!session.is_expired());
    }
}

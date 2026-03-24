use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use uuid::Uuid;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Session {
    pub id: String,
    pub account_id: String,
    pub created_at: DateTime<Utc>,
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

    pub fn create(&self, account_id: String) -> Session {
        self.cleanup_expired();

        let session_id = Uuid::new_v4().to_string();
        let now = Utc::now();
        let expires_at = now + Duration::days(1);

        let session = Session {
            id: session_id.clone(),
            account_id,
            created_at: now,
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
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn create_produces_session_with_correct_account_id() {
        let store = SessionStore::new();
        let session = store.create("account-42".to_string());
        assert_eq!(session.account_id, "account-42");
    }

    #[test]
    fn create_produces_unique_session_ids() {
        let store = SessionStore::new();
        let s1 = store.create("a".to_string());
        let s2 = store.create("b".to_string());
        assert_ne!(s1.id, s2.id);
    }

    #[test]
    fn get_returns_created_session() {
        let store = SessionStore::new();
        let session = store.create("account-1".to_string());
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
        let session = store.create("account-1".to_string());
        store.delete(&session.id);
        assert!(store.get(&session.id).is_none());
    }

    #[test]
    fn session_expires_at_is_approximately_one_day() {
        let store = SessionStore::new();
        let before = Utc::now();
        let session = store.create("account-1".to_string());
        let after = Utc::now();

        let expected_min = before + Duration::days(1);
        let expected_max = after + Duration::days(1);

        assert!(session.expires_at >= expected_min);
        assert!(session.expires_at <= expected_max);
    }

    #[test]
    fn is_expired_returns_false_for_new_session() {
        let store = SessionStore::new();
        let session = store.create("account-1".to_string());
        assert!(!session.is_expired());
    }
}

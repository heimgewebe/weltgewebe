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

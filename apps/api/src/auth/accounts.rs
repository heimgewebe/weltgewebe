use crate::routes::accounts::AccountInternal;
use std::collections::{BTreeMap, HashMap};

#[derive(Clone, Default)]
pub struct AccountStore {
    map: BTreeMap<String, AccountInternal>,
    email_index: HashMap<String, String>,
}

impl AccountStore {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn get(&self, id: &str) -> Option<&AccountInternal> {
        self.map.get(id)
    }

    pub fn get_by_email(&self, email: &str) -> Option<&AccountInternal> {
        let id = self.email_index.get(&email.to_lowercase())?;
        self.map.get(id)
    }

    pub fn insert(&mut self, account: AccountInternal) {
        let id = account.public.id.clone();
        // Remove old email from index if it existed and is different
        if let Some(existing) = self.map.get(&id) {
            if let Some(old_email) = &existing.email {
                self.email_index.remove(&old_email.to_lowercase());
            }
        }
        if let Some(email) = &account.email {
            self.email_index.insert(email.to_lowercase(), id.clone());
        }
        self.map.insert(id, account);
    }

    pub fn iter(&self) -> std::collections::btree_map::Iter<'_, String, AccountInternal> {
        self.map.iter()
    }

    pub fn values(&self) -> std::collections::btree_map::Values<'_, String, AccountInternal> {
        self.map.values()
    }

    pub fn len(&self) -> usize {
        self.map.len()
    }

    pub fn is_empty(&self) -> bool {
        self.map.is_empty()
    }
}

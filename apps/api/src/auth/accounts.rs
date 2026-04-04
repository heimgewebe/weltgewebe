use std::collections::{BTreeMap, HashMap};
use crate::routes::accounts::AccountInternal;

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
}

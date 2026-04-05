use crate::routes::accounts::AccountInternal;
use std::collections::{BTreeMap, HashMap};

#[derive(Clone, Default)]
pub struct AccountStore {
    map: BTreeMap<String, AccountInternal>,
    email_index: HashMap<String, String>,
}

/// Normalizes an email for use as an index key. Historically this repository
/// has used `.eq_ignore_ascii_case()` for email uniqueness checks. To preserve
/// this semantic during O(1) lookups, we convert all emails to lowercase ASCII.
fn normalize_email_key(email: &str) -> String {
    email.to_ascii_lowercase()
}

impl AccountStore {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn get(&self, id: &str) -> Option<&AccountInternal> {
        self.map.get(id)
    }

    pub fn get_by_email(&self, email: &str) -> Option<&AccountInternal> {
        let id = self.email_index.get(&normalize_email_key(email))?;
        self.map.get(id)
    }

    fn recompute_email_index_for_key(&mut self, key: &str) {
        let mut candidates = Vec::new();
        for (id, acc) in self.map.iter() {
            if let Some(email) = &acc.email {
                if normalize_email_key(email) == key {
                    candidates.push(id.clone());
                }
            }
        }

        if candidates.is_empty() {
            self.email_index.remove(key);
        } else {
            candidates.sort(); // Lexicographical sort based on ID
            let owner_id = candidates[0].clone();
            if candidates.len() > 1 {
                tracing::warn!(
                    event = "account_store.duplicate_email",
                    owner_id = %owner_id,
                    count = candidates.len(),
                    "Duplicate email detected in AccountStore. The deterministically smallest ID is chosen as owner."
                );
            }
            self.email_index.insert(key.to_string(), owner_id);
        }
    }

    pub fn rebuild_email_index(&mut self) {
        self.email_index.clear();
        let mut groups: HashMap<String, Vec<String>> = HashMap::new();

        for (id, acc) in self.map.iter() {
            if let Some(email) = &acc.email {
                let key = normalize_email_key(email);
                groups.entry(key).or_default().push(id.clone());
            }
        }

        for (key, mut ids) in groups {
            ids.sort(); // Deterministically pick smallest ID
            let owner_id = ids[0].clone();

            if ids.len() > 1 {
                tracing::warn!(
                    event = "account_store.duplicate_email",
                    owner_id = %owner_id,
                    count = ids.len(),
                    "Duplicate email detected in AccountStore bulk load. The deterministically smallest ID is chosen as owner."
                );
            }
            self.email_index.insert(key, owner_id);
        }
    }

    pub fn insert_unindexed(&mut self, account: AccountInternal) {
        self.map.insert(account.public.id.clone(), account);
    }

    pub fn insert(&mut self, account: AccountInternal) {
        let id = account.public.id.clone();

        let old_key = self
            .map
            .get(&id)
            .and_then(|a| a.email.as_ref().map(|e| normalize_email_key(e)));
        let new_key = account.email.as_ref().map(|e| normalize_email_key(e));

        self.map.insert(id, account);

        if let Some(old) = &old_key {
            self.recompute_email_index_for_key(old);
        }
        if let Some(new) = &new_key {
            if old_key.as_ref() != Some(new) {
                self.recompute_email_index_for_key(new);
            }
        }
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::auth::role::Role;
    use crate::routes::accounts::AccountPublic;
    use uuid::Uuid;

    fn dummy_account(id: &str, email: Option<&str>) -> AccountInternal {
        AccountInternal {
            public: AccountPublic {
                id: id.to_string(),
                kind: "ron".to_string(),
                title: "Dummy".to_string(),
                summary: None,
                public_pos: None,
                mode: crate::routes::accounts::AccountMode::Ron,
                radius_m: 0,
                disabled: false,
                tags: vec![],
            },
            role: Role::Gast,
            email: email.map(|e| e.to_string()),
            webauthn_user_id: Uuid::new_v4(),
        }
    }

    #[test]
    fn test_insert_and_get() {
        let mut store = AccountStore::new();
        let acc = dummy_account("u1", Some("Test@Example.com"));
        store.insert(acc);

        assert!(store.get("u1").is_some());
        // Test case-insensitive ASCII normalization lookup
        assert!(store.get_by_email("test@example.com").is_some());
        assert!(store.get_by_email("TEST@EXAMPLE.COM").is_some());
    }

    #[test]
    fn test_reinsert_removes_old_email_index() {
        let mut store = AccountStore::new();
        let acc1 = dummy_account("u1", Some("old@example.com"));
        store.insert(acc1);

        // Re-insert same ID, new email
        let acc2 = dummy_account("u1", Some("new@example.com"));
        store.insert(acc2);

        // Old email should no longer point to u1
        assert!(store.get_by_email("old@example.com").is_none());
        // New email should work
        assert!(store.get_by_email("new@example.com").is_some());
    }

    #[test]
    fn test_reinsert_with_none_email_removes_index() {
        let mut store = AccountStore::new();
        let acc1 = dummy_account("u1", Some("old@example.com"));
        store.insert(acc1);

        // Re-insert same ID, no email
        let acc2 = dummy_account("u1", None);
        store.insert(acc2);

        assert!(store.get_by_email("old@example.com").is_none());
        assert!(store.get("u1").is_some());
        assert_eq!(store.get("u1").unwrap().email, None);
    }

    #[test]
    fn test_reinsert_does_not_affect_other_accounts() {
        let mut store = AccountStore::new();
        let acc1 = dummy_account("u1", Some("a@example.com"));
        let acc2 = dummy_account("u2", Some("b@example.com"));
        store.insert(acc1);
        store.insert(acc2);

        // Update u1's email to c@example.com
        let updated_acc1 = dummy_account("u1", Some("c@example.com"));
        store.insert(updated_acc1);

        // Verify u1's old email is gone
        assert!(store.get_by_email("a@example.com").is_none());
        // Verify u1's new email works
        assert_eq!(store.get_by_email("c@example.com").unwrap().public.id, "u1");
        // Verify u2 is completely unaffected
        assert_eq!(store.get_by_email("b@example.com").unwrap().public.id, "u2");
    }

    #[test]
    fn test_duplicate_email_lookup_is_deterministic_by_account_id() {
        let mut store = AccountStore::new();
        let acc1 = dummy_account("u1", Some("shared@example.com"));
        let acc2 = dummy_account("u2", Some("shared@example.com"));

        store.insert(acc1);
        store.insert(acc2);

        assert_eq!(
            store.get_by_email("shared@example.com").unwrap().public.id,
            "u1" // Deterministic fallback to lexicographically smallest ID
        );
    }

    #[test]
    fn test_duplicate_owner_falls_back_to_remaining_account_when_owner_changes_email() {
        let mut store = AccountStore::new();
        let acc1 = dummy_account("u1", Some("shared@example.com"));
        let acc2 = dummy_account("u2", Some("SHARED@example.com"));

        store.insert(acc1);
        store.insert(acc2);

        assert_eq!(
            store.get_by_email("shared@example.com").unwrap().public.id,
            "u1" // Owner is deterministically u1
        );

        // u1 changes to new@example.com
        let acc1_new = dummy_account("u1", Some("new@example.com"));
        store.insert(acc1_new);

        // shared@example.com correctly falls back to u2
        assert_eq!(
            store.get_by_email("shared@example.com").unwrap().public.id,
            "u2"
        );
        // new@example.com now points to u1
        assert_eq!(
            store.get_by_email("new@example.com").unwrap().public.id,
            "u1"
        );
    }
}

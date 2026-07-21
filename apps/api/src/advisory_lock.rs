use sha2::{Digest, Sha256};

pub(crate) const ACCOUNT_LIFECYCLE_LOCK_NAMESPACE: &str = "weltgewebe:account-lifecycle:v1";
pub(crate) const NODE_MUTATION_LOCK_NAMESPACE: &str = "weltgewebe:node-mutation:v1";

// Cross-path advisory-lock ordering contract. Account lifecycle operations take
// the account-lifecycle lock first. A fully PostgreSQL-backed node create may
// then take the new node mutation lock and holds both across node persistence
// and derived Faden projection. Guest exit likewise starts with the account
// lifecycle lock and then acquires all affected node locks in deterministic
// sorted-key order. Ordinary existing-node mutations take only the node lock
// and must never open a reverse node -> account-lifecycle dependency. The
// legacy Faden account-row guard is a fallback and must not be re-entered by
// the fully lifecycle-guarded PostgreSQL create path.
//
// This is a partial order, not a universal account -> node -> row recipe:
// same-account lifecycle competitors are already serialized by the outer
// account lock. Never introduce a path that holds a node mutation lock while
// waiting for that same account's lifecycle lock.

pub(crate) fn account_lifecycle_lock_key(account_id: &str) -> i64 {
    stable_advisory_lock_key(ACCOUNT_LIFECYCLE_LOCK_NAMESPACE, &[account_id])
}

pub(crate) fn node_mutation_lock_key(node_id: &str) -> i64 {
    stable_advisory_lock_key(NODE_MUTATION_LOCK_NAMESPACE, &[node_id])
}

/// Derive one stable 64-bit PostgreSQL advisory-lock key from application-owned
/// inputs. Length-prefixing each part avoids ambiguous concatenations, while a
/// versioned namespace keeps unrelated lock domains separate.
pub(crate) fn stable_advisory_lock_key(namespace: &str, parts: &[&str]) -> i64 {
    let mut hasher = Sha256::new();
    hasher.update(namespace.as_bytes());
    for part in parts {
        let bytes = part.as_bytes();
        hasher.update((bytes.len() as u64).to_be_bytes());
        hasher.update(bytes);
    }
    let digest = hasher.finalize();
    i64::from_be_bytes(
        digest[..8]
            .try_into()
            .expect("SHA-256 always contains at least eight bytes"),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn advisory_lock_key_is_stable_and_namespace_bound() {
        assert_eq!(
            stable_advisory_lock_key("weltgewebe:node-mutation:v1", &["node-stable"]),
            2_204_785_427_200_031_019
        );
        assert_eq!(
            stable_advisory_lock_key("weltgewebe:create-operation:v1", &["actor", "operation"],),
            7_752_333_726_211_206_192
        );
        assert_ne!(
            stable_advisory_lock_key("weltgewebe:node-mutation:v1", &["node-stable"]),
            stable_advisory_lock_key("weltgewebe:create-operation:v1", &["node-stable"])
        );
    }

    #[test]
    fn length_prefixes_keep_part_boundaries_unambiguous() {
        assert_ne!(
            stable_advisory_lock_key("test", &["ab", "c"]),
            stable_advisory_lock_key("test", &["a", "bc"])
        );
    }
}

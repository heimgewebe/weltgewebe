//! Poison-tolerant `RwLock` access for the in-memory auth stores.
//!
//! These helpers are for stores whose inner data is a flat collection of
//! independent entries (e.g. `SessionStore`, `TokenStore`, `StepUpTokenStore`).
//! A panic in one request handler while holding the write lock can leave at
//! most one half-written entry — never a structurally corrupted collection —
//! so it is safe to recover via `PoisonError::into_inner()` and clear the
//! poison flag so subsequent acquisitions succeed normally.
//!
//! Do NOT use this helper for `ChallengeStore`. It maintains a
//! `challenges` ↔ `active_by_context` cross-map invariant that a plain
//! `into_inner()` does not restore; it has its own store-specific repair
//! logic in `auth::challenges::ChallengeStore::write_locked_repaired`.

use std::sync::{RwLock, RwLockReadGuard, RwLockWriteGuard};

pub trait RwLockRecover<T: ?Sized> {
    fn read_recover(&self) -> RwLockReadGuard<'_, T>;
    fn write_recover(&self) -> RwLockWriteGuard<'_, T>;
}

impl<T: ?Sized> RwLockRecover<T> for RwLock<T> {
    fn read_recover(&self) -> RwLockReadGuard<'_, T> {
        match self.read() {
            Ok(guard) => guard,
            Err(poisoned) => {
                tracing::warn!(
                    event = "auth.lock.poison_recovered",
                    kind = "read",
                    store_type = std::any::type_name::<T>(),
                    "Recovered from poisoned auth store lock; continuing with existing data"
                );
                let guard = poisoned.into_inner();
                // Clear the poison flag so subsequent lock acquisitions succeed
                // normally and this warning does not repeat on every access.
                self.clear_poison();
                guard
            }
        }
    }

    fn write_recover(&self) -> RwLockWriteGuard<'_, T> {
        match self.write() {
            Ok(guard) => guard,
            Err(poisoned) => {
                tracing::warn!(
                    event = "auth.lock.poison_recovered",
                    kind = "write",
                    store_type = std::any::type_name::<T>(),
                    "Recovered from poisoned auth store lock; continuing with existing data"
                );
                let guard = poisoned.into_inner();
                self.clear_poison();
                guard
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use std::thread;

    fn poison<T: Send + Sync + 'static>(lock: &Arc<RwLock<T>>) {
        let lock = Arc::clone(lock);
        let _ = thread::spawn(move || {
            let _guard = lock.write().unwrap();
            panic!("intentional poison");
        })
        .join();
    }

    #[test]
    fn read_recover_returns_data_and_clears_poison() {
        let lock = Arc::new(RwLock::new(42_u32));
        poison(&lock);
        assert!(lock.read().is_err(), "lock should be poisoned");
        assert_eq!(*lock.read_recover(), 42);
        // Poison must be cleared so subsequent accesses do not warn again.
        assert!(lock.read().is_ok(), "lock should no longer be poisoned");
    }

    #[test]
    fn write_recover_allows_mutation_and_clears_poison() {
        let lock = Arc::new(RwLock::new(0_u32));
        poison(&lock);
        assert!(lock.write().is_err(), "lock should be poisoned");
        *lock.write_recover() = 7;
        assert!(lock.read().is_ok(), "lock should no longer be poisoned");
        assert_eq!(*lock.read().unwrap(), 7);
    }
}

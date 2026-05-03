//! Poison-tolerant `RwLock` access for the in-memory auth stores.
//!
//! These stores hold simple `HashMap`/`BTreeMap` collections of independent
//! entries (sessions, tokens, challenges). A panic in one request handler
//! while holding the write lock leaves at most one half-written entry — never
//! a structurally corrupted collection — so it is safe to recover from
//! poisoning instead of crashing every subsequent auth request.
//!
//! Do NOT use this pattern for stores whose inner data has cross-mutation
//! invariants that a partial write could violate.

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
                    "Recovered from poisoned auth store lock; continuing with existing data"
                );
                poisoned.into_inner()
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
                    "Recovered from poisoned auth store lock; continuing with existing data"
                );
                poisoned.into_inner()
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
    fn read_recover_returns_data_after_poisoning() {
        let lock = Arc::new(RwLock::new(42_u32));
        poison(&lock);
        assert!(lock.read().is_err(), "lock should be poisoned");
        assert_eq!(*lock.read_recover(), 42);
    }

    #[test]
    fn write_recover_allows_mutation_after_poisoning() {
        let lock = Arc::new(RwLock::new(0_u32));
        poison(&lock);
        assert!(lock.write().is_err(), "lock should be poisoned");
        *lock.write_recover() = 7;
        assert_eq!(*lock.read_recover(), 7);
    }
}

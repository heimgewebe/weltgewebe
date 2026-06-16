//! WebAuthn / Passkey support.
//!
//! Provides the server-side WebAuthn configuration and registration state
//! management. The `Webauthn` instance is built from `AppConfig` and stored
//! once in `ApiState`. In-progress passkey registrations are kept in
//! `PasskeyRegistrationStore` (in-memory, TTL-based).
//!
//! ## Design decisions
//!
//! * **`webauthn_user_id`** is a dedicated UUID per account that is
//!   NOT derived from `account_id`. This decouples the WebAuthn identity from
//!   internal account semantics and protects against future migration pain.
//!   **Persistence status:** the value is read from the account data source when
//!   present and generated fresh (lazy backfill) when absent. It is stable for
//!   the lifetime of the running process. The `register/verify` handler writes
//!   the value back into the current `AccountStore` on successful registration;
//!   cross-restart stability still requires a persistent account data source.
//! * **`rp_id` / `rp_origin`** come from `AppConfig` (env overrides supported).
//!   No hardcoded defaults — missing values cause an explicit startup error when
//!   passkeys are enabled.

use std::collections::HashMap;
use std::sync::{Arc, RwLock as StdRwLock};

use chrono::{DateTime, Duration, Utc};
use sha2::{Digest, Sha256};
use tokio::sync::RwLock as TokioRwLock;
use url::Url;
use uuid::Uuid;
use webauthn_rs::prelude::*;

use crate::{auth::lock::RwLockRecover, config::AppConfig};

/// TTL for in-progress passkey registrations (5 minutes).
const REGISTRATION_TTL_SECS: i64 = 300;

/// TTL for passkey registration grants (5 minutes — matches step-up token and registration TTL).
const REGISTRATION_GRANT_TTL_SECS: i64 = 300;

/// TTL for in-progress passkey authentications / login ceremonies (5 minutes —
/// matches the registration TTL convention).
const AUTHENTICATION_TTL_SECS: i64 = 300;

/// Hard upper bound on concurrently in-flight passkey authentications.
///
/// `auth/options` is unauthenticated and pre-session, so without a ceiling a
/// caller could grow the in-memory store without limit (the per-request rate
/// limiter is the primary bound; this is defence-in-depth). At ~5 min TTL this
/// caps steady-state memory while staying far above any legitimate concurrency.
const AUTHENTICATION_STORE_MAX_ENTRIES: usize = 10_000;

/// Error returned when inserting a passkey into [`PasskeyStore`].
#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum PasskeyStoreInsertError {
    #[error("passkey credential already exists")]
    DuplicateCredentialId,
}

/// Error returned when updating a stored passkey via
/// [`PasskeyStore::update_credential`].
#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum PasskeyStoreUpdateError {
    #[error("credential not found for account")]
    NotFound,
    #[error("credential update failed")]
    UpdateFailed,
}

/// Stored passkey together with its owning account.
#[derive(Clone, Debug)]
pub struct StoredPasskey {
    pub account_id: String,
    pub passkey: Passkey,
}

/// Langlebiger In-Memory-Store für registrierte Passkeys.
///
/// Dieser Store ist **nicht** TTL-basiert und **nicht** single-use. Er hält
/// Passkeys bis zum Prozessende und eignet sich damit als Minimalpfad für
/// Phase 4, bis eine persistente Datenquelle folgt.
///
/// ⚠️ Wichtig: Da dieser Store rein in-memory ist, gehen alle Passkeys bei
/// Prozessneustart verloren.
#[derive(Clone, Default)]
pub struct PasskeyStore {
    // We intentionally use std::sync::RwLock here because operations are
    // short, purely in-memory mutations/lookups without async-await sections
    // while the lock is held.
    store: Arc<StdRwLock<PasskeyStoreInner>>,
}

#[derive(Clone, Default)]
struct PasskeyStoreInner {
    account_passkeys: HashMap<String, Vec<Passkey>>,
    credential_index: HashMap<CredentialID, String>,
}

impl PasskeyStore {
    pub fn new() -> Self {
        Self {
            store: Arc::new(StdRwLock::new(PasskeyStoreInner::default())),
        }
    }

    /// Inserts a passkey for an account.
    ///
    /// Rejects duplicate credential IDs globally across all accounts.
    pub fn insert(
        &self,
        account_id: String,
        passkey: Passkey,
    ) -> Result<(), PasskeyStoreInsertError> {
        let mut store = self.store.write_recover();
        let credential_id = passkey.cred_id().clone();
        if store.credential_index.contains_key(&credential_id) {
            return Err(PasskeyStoreInsertError::DuplicateCredentialId);
        }
        store
            .credential_index
            .insert(credential_id, account_id.clone());
        store
            .account_passkeys
            .entry(account_id)
            .or_default()
            .push(passkey);
        Ok(())
    }

    /// Lists all passkeys owned by the given account.
    pub fn list_for_account(&self, account_id: &str) -> Vec<Passkey> {
        let store = self.store.read_recover();
        store
            .account_passkeys
            .get(account_id)
            .cloned()
            .unwrap_or_default()
    }

    /// Returns all credential IDs for passkeys owned by the given account.
    pub fn credential_ids_for_account(&self, account_id: &str) -> Vec<CredentialID> {
        let store = self.store.read_recover();
        store
            .account_passkeys
            .get(account_id)
            .map(|passkeys| {
                passkeys
                    .iter()
                    .map(|passkey| passkey.cred_id().clone())
                    .collect()
            })
            .unwrap_or_default()
    }

    /// Finds a passkey by credential ID across all accounts.
    pub fn find_by_credential_id(&self, credential_id: &CredentialID) -> Option<StoredPasskey> {
        let store = self.store.read_recover();
        let account_id = store.credential_index.get(credential_id)?;
        let passkeys = store.account_passkeys.get(account_id)?;
        let passkey = passkeys
            .iter()
            .find(|candidate| candidate.cred_id() == credential_id)?;
        Some(StoredPasskey {
            account_id: account_id.clone(),
            passkey: passkey.clone(),
        })
    }

    /// Removes a credential for an account.
    ///
    /// Returns `true` if the credential existed for the given account and was
    /// removed. Credentials of other accounts are left untouched.
    pub fn remove_for_account(&self, account_id: &str, credential_id: &CredentialID) -> bool {
        let mut store = self.store.write_recover();
        let Some(passkeys) = store.account_passkeys.get_mut(account_id) else {
            return false;
        };
        let original_len = passkeys.len();
        passkeys.retain(|candidate| candidate.cred_id() != credential_id);
        let changed = passkeys.len() != original_len;
        if passkeys.is_empty() {
            store.account_passkeys.remove(account_id);
        }
        if changed {
            store.credential_index.remove(credential_id);
        }
        changed
    }

    /// Applies a WebAuthn [`AuthenticationResult`] to the stored credential it
    /// refers to (signature counter, backup flags) per webauthn-rs semantics.
    ///
    /// `update_credential` mutates the credential in place and never changes the
    /// credential ID, so the `credential_index` stays consistent and needs no
    /// reindexing. The credential must belong to `account_id`
    /// (defence-in-depth); a missing credential or a cross-account mismatch
    /// fail-closes with [`PasskeyStoreUpdateError::NotFound`].
    ///
    /// Returns `true` if the stored credential changed, `false` if it matched
    /// but nothing changed (e.g. a synced passkey reporting a constant counter).
    ///
    /// Mutates the stored credential under the store's internal write lock.
    pub fn update_credential(
        &self,
        account_id: &str,
        auth_result: &AuthenticationResult,
    ) -> Result<bool, PasskeyStoreUpdateError> {
        let mut store = self.store.write_recover();
        let credential_id = auth_result.cred_id();

        // Verify ownership first; the immutable borrow ends before the mutable one.
        let owned_by_account = store
            .credential_index
            .get(credential_id)
            .is_some_and(|owner| owner == account_id);
        if !owned_by_account {
            return Err(PasskeyStoreUpdateError::NotFound);
        }

        let passkey = store
            .account_passkeys
            .get_mut(account_id)
            .and_then(|passkeys| {
                passkeys
                    .iter_mut()
                    .find(|candidate| candidate.cred_id() == credential_id)
            })
            .ok_or(PasskeyStoreUpdateError::NotFound)?;

        // webauthn-rs' `Passkey::update_credential` returns `Some(changed)` and
        // only yields `None` on a credential-id mismatch. We located the
        // credential by `auth_result.cred_id()`, so `None` is unreachable here;
        // surface it as a hard failure rather than silently smoothing it to
        // "no change".
        match passkey.update_credential(auth_result) {
            Some(changed) => Ok(changed),
            None => Err(PasskeyStoreUpdateError::UpdateFailed),
        }
    }
}

// ── Webauthn builder ──────────────────────────────────────────────────────

/// Errors that can occur when building the `Webauthn` instance.
#[derive(Debug, thiserror::Error)]
pub enum WebauthnConfigError {
    #[error("WEBAUTHN_RP_ID is required but not set")]
    MissingRpId,
    #[error("WEBAUTHN_RP_ORIGIN is required but not set")]
    MissingRpOrigin,
    #[error("WEBAUTHN_RP_ORIGIN is not a valid URL: {0}")]
    InvalidOriginUrl(#[from] url::ParseError),
    #[error("WebAuthn builder error: {0}")]
    Builder(#[from] WebauthnError),
}

/// Build a [`Webauthn`] instance from application configuration.
///
/// Returns `None` when passkey support is not configured (both `rp_id` and
/// `rp_origin` are absent). Returns `Err` when the configuration is
/// inconsistent or invalid.
pub fn build_webauthn(config: &AppConfig) -> Result<Option<Arc<Webauthn>>, WebauthnConfigError> {
    let (rp_id, rp_origin_str) = match (&config.webauthn_rp_id, &config.webauthn_rp_origin) {
        (Some(id), Some(origin)) => (id.as_str(), origin.as_str()),
        (None, None) => return Ok(None),
        (Some(_), None) => return Err(WebauthnConfigError::MissingRpOrigin),
        (None, Some(_)) => return Err(WebauthnConfigError::MissingRpId),
    };

    let rp_origin = Url::parse(rp_origin_str)?;
    let mut builder = WebauthnBuilder::new(rp_id, &rp_origin)?;
    if let Some(name) = config.webauthn_rp_name.as_deref() {
        builder = builder.rp_name(name);
    }
    let webauthn = builder.build()?;
    Ok(Some(Arc::new(webauthn)))
}

// ── Registration state store ──────────────────────────────────────────────

/// An in-progress passkey registration, kept until the client calls
/// `register/verify` (not yet implemented).
struct PendingRegistration {
    account_id: String,
    state: PasskeyRegistration,
    created_at: DateTime<Utc>,
}

/// In-memory store for in-progress passkey registrations.
///
/// Keyed by a random opaque ID returned to the client so it can correlate
/// the `register/options` response with the subsequent `register/verify`
/// request.
#[derive(Clone, Default)]
pub struct PasskeyRegistrationStore {
    store: Arc<TokioRwLock<HashMap<String, PendingRegistration>>>,
}

impl PasskeyRegistrationStore {
    pub fn new() -> Self {
        Self::default()
    }

    /// Store a new in-progress registration. Returns the opaque registration
    /// ID that must be sent back by the client.
    pub async fn insert(&self, account_id: String, state: PasskeyRegistration) -> String {
        let id = Uuid::new_v4().to_string();
        let pending = PendingRegistration {
            account_id,
            state,
            created_at: Utc::now(),
        };
        let mut store = self.store.write().await;
        // Opportunistic cleanup of expired entries.
        let cutoff = Utc::now() - chrono::Duration::seconds(REGISTRATION_TTL_SECS);
        store.retain(|_, v| v.created_at > cutoff);
        store.insert(id.clone(), pending);
        id
    }

    /// Consume a pending registration by ID. Returns `None` if the entry
    /// does not exist, has expired, or does not belong to the given account.
    ///
    /// A mismatched `account_id` does **not** remove the entry — the entry
    /// remains available for the correct account (non-destructive rejection).
    pub async fn consume(
        &self,
        registration_id: &str,
        account_id: &str,
    ) -> Option<PasskeyRegistration> {
        let mut store = self.store.write().await;
        let cutoff = Utc::now() - chrono::Duration::seconds(REGISTRATION_TTL_SECS);
        // Peek first so we can decide whether to consume without holding a
        // borrow across a mutable operation.
        let (is_expired, account_matches) = match store.get(registration_id) {
            None => return None,
            Some(entry) => (entry.created_at <= cutoff, entry.account_id == account_id),
        };
        if is_expired {
            // Clean up the stale entry and reject.
            store.remove(registration_id);
            return None;
        }
        if !account_matches {
            // Wrong account: leave the entry intact for the legitimate caller.
            return None;
        }
        // Valid match: single-use consume.
        store.remove(registration_id).map(|p| p.state)
    }
}

// ── Registration options ──────────────────────────────────────────────────

/// Input for generating passkey registration options.
pub struct RegistrationInput<'a> {
    pub webauthn_user_id: Uuid,
    pub user_name: &'a str,
    pub user_display_name: &'a str,
}

/// Generate `CreationChallengeResponse` (WebAuthn register options) for the
/// given user.
///
/// The returned `PasskeyRegistration` state MUST be stored server-side until
/// the client completes the ceremony via `register/verify`.
pub fn start_passkey_registration(
    webauthn: &Webauthn,
    input: &RegistrationInput<'_>,
    exclude_credentials: Option<Vec<CredentialID>>,
) -> Result<(CreationChallengeResponse, PasskeyRegistration), WebauthnError> {
    webauthn.start_passkey_registration(
        input.webauthn_user_id,
        input.user_name,
        input.user_display_name,
        exclude_credentials,
    )
}

// ── Authentication (login) options & state store ──────────────────────────

/// Begin a passkey authentication (login) ceremony.
///
/// `allow_credentials` MUST contain the passkeys the ceremony is allowed to
/// satisfy — i.e. the registered passkeys of the account identified by the
/// `auth/options` request. webauthn-rs pins `UserVerificationPolicy::Required`
/// for this ceremony. The returned [`PasskeyAuthentication`] state MUST be stored
/// server-side (single-use) until the client completes the ceremony via
/// `auth/verify`; it pairs with the `RequestChallengeResponse` and is required to
/// verify the assertion.
pub fn start_passkey_authentication(
    webauthn: &Webauthn,
    allow_credentials: &[Passkey],
) -> Result<(RequestChallengeResponse, PasskeyAuthentication), WebauthnError> {
    webauthn.start_passkey_authentication(allow_credentials)
}

/// Error returned when inserting into [`PasskeyAuthenticationStore`].
#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum PasskeyAuthenticationStoreInsertError {
    #[error("passkey authentication store is at capacity")]
    Full,
}

/// An in-progress passkey authentication, kept until the client calls
/// `auth/verify`.
struct PendingAuthentication {
    account_id: String,
    state: PasskeyAuthentication,
    created_at: DateTime<Utc>,
}

/// In-memory store for in-progress passkey authentications (login ceremonies).
///
/// Keyed by a random opaque ID returned to the client so it can correlate the
/// `auth/options` response with the subsequent `auth/verify` request.
///
/// This store is deliberately **separate** from [`PasskeyRegistrationStore`]:
/// registration state (`PasskeyRegistration`) and authentication state
/// (`PasskeyAuthentication`) are distinct WebAuthn ceremonies and must never be
/// interchangeable. Like the registration store it is in-memory, TTL-bounded
/// (5 minutes) and single-use; additionally it is capacity-bounded
/// ([`AUTHENTICATION_STORE_MAX_ENTRIES`]) as defence-in-depth against unbounded
/// growth from the unauthenticated `auth/options` endpoint.
#[derive(Clone)]
pub struct PasskeyAuthenticationStore {
    store: Arc<TokioRwLock<HashMap<String, PendingAuthentication>>>,
    max_entries: usize,
}

impl Default for PasskeyAuthenticationStore {
    fn default() -> Self {
        Self {
            store: Arc::new(TokioRwLock::new(HashMap::new())),
            max_entries: AUTHENTICATION_STORE_MAX_ENTRIES,
        }
    }
}

impl PasskeyAuthenticationStore {
    pub fn new() -> Self {
        Self::default()
    }

    /// Test-only constructor with a custom capacity, so the capacity behaviour
    /// can be exercised without inserting tens of thousands of entries.
    #[cfg(test)]
    fn with_capacity_for_test(max_entries: usize) -> Self {
        Self {
            store: Arc::new(TokioRwLock::new(HashMap::new())),
            max_entries,
        }
    }

    /// Test-only: directly insert an already-expired entry (bypassing the cap),
    /// so the expired-entry pruning path can be exercised deterministically.
    #[cfg(test)]
    async fn insert_expired_for_test(&self, account_id: String, state: PasskeyAuthentication) {
        let pending = PendingAuthentication {
            account_id,
            state,
            created_at: Utc::now() - chrono::Duration::seconds(AUTHENTICATION_TTL_SECS + 1),
        };
        self.store
            .write()
            .await
            .insert(Uuid::new_v4().to_string(), pending);
    }

    /// Store a new in-progress authentication bound to `account_id`. Returns the
    /// opaque authentication ID that must be sent back by the client, or
    /// [`PasskeyAuthenticationStoreInsertError::Full`] if the store is at
    /// capacity even after pruning expired entries.
    ///
    /// Pruning the expired entries (an `O(N)` `retain`) only runs when the store
    /// is at capacity, so the steady-state insert stays `O(1)` and does not pay
    /// for a full scan under the write lock on every call.
    pub async fn insert(
        &self,
        account_id: String,
        state: PasskeyAuthentication,
    ) -> Result<String, PasskeyAuthenticationStoreInsertError> {
        let id = Uuid::new_v4().to_string();
        let pending = PendingAuthentication {
            account_id,
            state,
            created_at: Utc::now(),
        };
        let mut store = self.store.write().await;
        if store.len() >= self.max_entries {
            // Only now pay for the expired-entry sweep; if it does not free a
            // slot, reject rather than grow without bound.
            let cutoff = Utc::now() - chrono::Duration::seconds(AUTHENTICATION_TTL_SECS);
            store.retain(|_, v| v.created_at > cutoff);
            if store.len() >= self.max_entries {
                return Err(PasskeyAuthenticationStoreInsertError::Full);
            }
        }
        store.insert(id.clone(), pending);
        Ok(id)
    }

    /// Consume a pending authentication by ID (single-use). Returns the bound
    /// `account_id` together with the WebAuthn authentication state, or `None` if
    /// the entry does not exist, has already been consumed, or has expired.
    ///
    /// Unlike registration consume there is no account binding to check here: the
    /// caller of `auth/verify` is unauthenticated and presents only the opaque
    /// authentication ID. Possession of the ID alone grants nothing — a valid
    /// assertion over the stored challenge is still required by the caller before
    /// any session is created.
    pub async fn consume(
        &self,
        authentication_id: &str,
    ) -> Option<(String, PasskeyAuthentication)> {
        // Remove-first: a single lookup that is single-use regardless of outcome.
        // An expired entry is removed and rejected just the same.
        let pending = self.store.write().await.remove(authentication_id)?;
        let cutoff = Utc::now() - chrono::Duration::seconds(AUTHENTICATION_TTL_SECS);
        if pending.created_at <= cutoff {
            return None;
        }
        Some((pending.account_id, pending.state))
    }
}

// ── Registration Grant Store ──────────────────────────────────────────────

/// Internal grant record, keyed by the SHA-256 hash of the opaque grant ID.
struct PasskeyRegistrationGrantData {
    account_id: String,
    device_id: String,
    expires_at: DateTime<Utc>,
}

/// Result of a [`PasskeyRegistrationGrantStore::consume`] operation.
pub enum ConsumeGrantResult {
    /// Grant not found or has expired.
    NotFound,
    /// Grant found but `account_id` or `device_id` did not match.
    ///
    /// The grant is left intact so the correct caller can still use it.
    BindingMismatch,
    /// All bindings matched; the grant has been removed (single-use).
    Consumed,
}

/// Short-lived, single-use, account- and device-bound grant that authorises
/// the WebAuthn creation ceremony.
///
/// A grant is created by `consume_step_up` when the
/// `BeginPasskeyRegistration` intent is validated.
/// `POST /auth/passkeys/register/options` must present and consume a valid
/// grant before `start_passkey_registration` is called.
///
/// * **In-memory** — no persistence across restarts.
/// * **TTL** — 5 minutes (matches step-up token and `REGISTRATION_TTL_SECS`).
/// * **Single-use** — the grant is removed on successful [`consume`][Self::consume].
/// * **Opaque ID** — the raw UUID is returned to the client; its SHA-256 hash
///   is stored server-side (same pattern as `StepUpTokenStore`).
#[derive(Clone, Default)]
pub struct PasskeyRegistrationGrantStore {
    store: Arc<StdRwLock<HashMap<String, PasskeyRegistrationGrantData>>>,
}

impl PasskeyRegistrationGrantStore {
    pub fn new() -> Self {
        Self::default()
    }

    fn hash_grant_id(id: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(id.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    /// Insert a new grant bound to `account_id` and `device_id`.
    ///
    /// Returns the opaque grant ID (UUID) that must be given to the client.
    pub fn insert(&self, account_id: String, device_id: String) -> String {
        self.insert_with_ttl(
            account_id,
            device_id,
            Duration::seconds(REGISTRATION_GRANT_TTL_SECS),
        )
    }

    /// Insert a grant with a custom TTL.  Exposed for testing.
    pub fn insert_with_ttl(
        &self,
        account_id: String,
        device_id: String,
        duration: Duration,
    ) -> String {
        let id = Uuid::new_v4().to_string();
        let hash = Self::hash_grant_id(&id);
        let now = Utc::now();
        let expires_at = now + duration;
        let data = PasskeyRegistrationGrantData {
            account_id,
            device_id,
            expires_at,
        };
        let mut store = self.store.write_recover();
        // Opportunistic cleanup of stale grants.
        store.retain(|_, v| v.expires_at > now);
        store.insert(hash, data);
        id
    }

    /// Consume a grant atomically.
    ///
    /// * Returns [`ConsumeGrantResult::Consumed`] and removes the grant if
    ///   `account_id` and `device_id` match and the grant has not expired.
    /// * Returns [`ConsumeGrantResult::BindingMismatch`] if the grant exists
    ///   and is not expired but the bindings do not match.  The grant is left
    ///   intact so the correct caller can still use it.
    /// * Returns [`ConsumeGrantResult::NotFound`] when the grant is absent or
    ///   has expired.
    pub fn consume(&self, grant_id: &str, account_id: &str, device_id: &str) -> ConsumeGrantResult {
        let now = Utc::now();
        let hash = Self::hash_grant_id(grant_id);
        let mut store = self.store.write_recover();
        store.retain(|_, v| v.expires_at > now);
        match store.get(&hash) {
            None => ConsumeGrantResult::NotFound,
            Some(data) => {
                if data.account_id != account_id || data.device_id != device_id {
                    ConsumeGrantResult::BindingMismatch
                } else {
                    store
                        .remove(&hash)
                        .expect("entry was present under write lock");
                    ConsumeGrantResult::Consumed
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn test_webauthn() -> Arc<Webauthn> {
        let origin = Url::parse("http://localhost:3000").unwrap();
        let builder = WebauthnBuilder::new("localhost", &origin).unwrap();
        Arc::new(builder.build().unwrap())
    }

    fn test_passkey(credential_seed: u8) -> Passkey {
        let credential_id = vec![credential_seed; 32];
        let credential_id_b64 = {
            use base64::engine::general_purpose::URL_SAFE_NO_PAD;
            use base64::Engine;
            URL_SAFE_NO_PAD.encode(credential_id)
        };
        serde_json::from_value(json!({
            "cred": {
                "cred_id": credential_id_b64,
                "cred": {
                    "type_": "ES256",
                    "key": {
                        "EC_EC2": {
                            "curve": "SECP256R1",
                            "x": vec![1_u8; 32],
                            "y": vec![2_u8; 32]
                        }
                    }
                },
                "counter": 0,
                "transports": null,
                "user_verified": false,
                "backup_eligible": false,
                "backup_state": false,
                "registration_policy": "preferred",
                "extensions": {
                    "cred_protect": "NotRequested",
                    "hmac_create_secret": "NotRequested"
                },
                "attestation": {
                    "data": "None",
                    "metadata": "None"
                },
                "attestation_format": "None"
            }
        }))
        .expect("passkey fixture must deserialize")
    }

    #[test]
    fn build_webauthn_returns_none_when_unconfigured() {
        let config = AppConfig::load_from_str(
            "fade_days: 7\nron_days: 84\nanonymize_opt_in: true\ndelegation_expire_days: 28\n",
        )
        .unwrap();
        let result = build_webauthn(&config).unwrap();
        assert!(
            result.is_none(),
            "should be None when rp_id/rp_origin unset"
        );
    }

    #[test]
    fn build_webauthn_succeeds_with_valid_config() {
        let yaml = "\
fade_days: 7\n\
ron_days: 84\n\
anonymize_opt_in: true\n\
delegation_expire_days: 28\n\
webauthn_rp_id: localhost\n\
webauthn_rp_origin: \"http://localhost:3000\"\n";
        let config = AppConfig::load_from_str(yaml).unwrap();
        let result = build_webauthn(&config).unwrap();
        assert!(result.is_some(), "should build Webauthn from valid config");
    }

    #[test]
    fn build_webauthn_fails_when_only_rp_id_set() {
        let yaml = "\
fade_days: 7\n\
ron_days: 84\n\
anonymize_opt_in: true\n\
delegation_expire_days: 28\n\
webauthn_rp_id: example.com\n";
        // Config validation should catch this, but build_webauthn also guards:
        // load_from_str runs validate(), which bails on mismatch.
        let result = AppConfig::load_from_str(yaml);
        assert!(
            result.is_err(),
            "config should reject rp_id without rp_origin"
        );
    }

    #[test]
    fn start_registration_uses_provided_webauthn_user_id() {
        let webauthn = test_webauthn();
        let user_id = Uuid::new_v4();
        let input = RegistrationInput {
            webauthn_user_id: user_id,
            user_name: "test@example.com",
            user_display_name: "Test User",
        };
        let (ccr, _reg) =
            start_passkey_registration(&webauthn, &input, None).expect("registration should start");

        // The creation challenge must reference the user we provided.
        let ccr_json = serde_json::to_value(&ccr).expect("ccr serializable");
        let public_key = ccr_json.get("publicKey").expect("publicKey present");
        let user = public_key.get("user").expect("user present");
        // WebAuthn user.id is base64url-encoded; decode and compare.
        let user_id_b64 = user
            .get("id")
            .and_then(|v| v.as_str())
            .expect("user.id present");
        let decoded = {
            use base64::engine::general_purpose::URL_SAFE_NO_PAD;
            use base64::Engine;
            URL_SAFE_NO_PAD
                .decode(user_id_b64)
                .expect("valid base64url")
        };
        assert_eq!(
            decoded,
            user_id.as_bytes().to_vec(),
            "CreationChallengeResponse must use the provided webauthn_user_id"
        );
    }

    #[test]
    fn same_account_gets_same_webauthn_user_id_across_calls() {
        let webauthn = test_webauthn();
        let stable_id = Uuid::new_v4();

        let input = RegistrationInput {
            webauthn_user_id: stable_id,
            user_name: "a@b.com",
            user_display_name: "A",
        };

        let (ccr1, _) = start_passkey_registration(&webauthn, &input, None).unwrap();
        let (ccr2, _) = start_passkey_registration(&webauthn, &input, None).unwrap();

        let id1 = extract_user_id_from_ccr(&ccr1);
        let id2 = extract_user_id_from_ccr(&ccr2);
        assert_eq!(id1, id2, "same account must yield same WebAuthn user ID");
    }

    #[tokio::test]
    async fn registration_store_insert_and_consume() {
        let store = PasskeyRegistrationStore::new();
        let webauthn = test_webauthn();
        let (_, reg) = webauthn
            .start_passkey_registration(Uuid::new_v4(), "u", "U", None)
            .unwrap();

        let reg_id = store.insert("acct-1".to_string(), reg).await;
        // Consuming with correct account succeeds.
        let consumed = store.consume(&reg_id, "acct-1").await;
        assert!(
            consumed.is_some(),
            "consume should succeed for matching account"
        );
        // Second consume fails (single-use).
        let again = store.consume(&reg_id, "acct-1").await;
        assert!(again.is_none(), "consume should fail on second attempt");
    }

    #[tokio::test]
    async fn registration_store_rejects_wrong_account() {
        let store = PasskeyRegistrationStore::new();
        let webauthn = test_webauthn();
        let (_, reg) = webauthn
            .start_passkey_registration(Uuid::new_v4(), "u", "U", None)
            .unwrap();

        let reg_id = store.insert("acct-1".to_string(), reg).await;
        let consumed = store.consume(&reg_id, "acct-wrong").await;
        assert!(
            consumed.is_none(),
            "consume must reject mismatched account_id"
        );
    }

    #[tokio::test]
    async fn registration_store_wrong_account_does_not_burn_registration() {
        let store = PasskeyRegistrationStore::new();
        let webauthn = test_webauthn();
        let (_, reg) = webauthn
            .start_passkey_registration(Uuid::new_v4(), "u", "U", None)
            .unwrap();

        let reg_id = store.insert("acct-1".to_string(), reg).await;
        // A wrong-account attempt must not remove the entry.
        let wrong = store.consume(&reg_id, "acct-wrong").await;
        assert!(wrong.is_none(), "wrong account must be rejected");
        // The entry must still be consumable by the correct account.
        let correct = store.consume(&reg_id, "acct-1").await;
        assert!(
            correct.is_some(),
            "correct account must still consume after a wrong-account attempt"
        );
    }

    #[tokio::test]
    async fn authentication_store_insert_and_consume_is_single_use() {
        let store = PasskeyAuthenticationStore::new();
        let webauthn = test_webauthn();
        // Proves a passkey is accepted by the authentication-ceremony start.
        let (_, state) = webauthn
            .start_passkey_authentication(&[test_passkey(1)])
            .expect("start_passkey_authentication should accept a credential");

        let id = store
            .insert("acct-1".to_string(), state)
            .await
            .expect("insert under capacity should succeed");

        let consumed = store.consume(&id).await;
        assert!(consumed.is_some(), "consume should succeed once");
        assert_eq!(
            consumed.unwrap().0,
            "acct-1",
            "consume must return the bound account_id"
        );

        let again = store.consume(&id).await;
        assert!(
            again.is_none(),
            "consume must fail on second attempt (single-use)"
        );
    }

    #[tokio::test]
    async fn authentication_store_unknown_id_returns_none() {
        let store = PasskeyAuthenticationStore::new();
        assert!(
            store.consume("no-such-authentication-id").await.is_none(),
            "unknown authentication id must fail-closed"
        );
    }

    fn test_authentication_state() -> PasskeyAuthentication {
        let webauthn = test_webauthn();
        let (_, state) = webauthn
            .start_passkey_authentication(&[test_passkey(1)])
            .expect("start_passkey_authentication should accept a credential");
        state
    }

    #[tokio::test]
    async fn passkey_authentication_store_rejects_insert_when_capacity_reached() {
        let store = PasskeyAuthenticationStore::with_capacity_for_test(1);

        let first = store
            .insert("acct-1".to_string(), test_authentication_state())
            .await;
        assert!(first.is_ok(), "first insert fits within capacity");

        let second = store
            .insert("acct-2".to_string(), test_authentication_state())
            .await;
        assert_eq!(
            second,
            Err(PasskeyAuthenticationStoreInsertError::Full),
            "insert beyond capacity (no expired entries to prune) must be rejected"
        );
    }

    #[tokio::test]
    async fn passkey_authentication_store_allows_insert_after_expired_entries_are_pruned() {
        let store = PasskeyAuthenticationStore::with_capacity_for_test(1);

        // Pre-fill the single slot with an already-expired entry.
        store
            .insert_expired_for_test("stale".to_string(), test_authentication_state())
            .await;

        // The store is "full" by count, but the expired entry must be pruned so
        // a fresh insert succeeds.
        let fresh = store
            .insert("acct-1".to_string(), test_authentication_state())
            .await;
        assert!(
            fresh.is_ok(),
            "insert must succeed after the expired entry is pruned"
        );
    }

    #[test]
    fn passkey_store_updates_credential_after_authentication_result() {
        let store = PasskeyStore::new();
        let passkey = test_passkey(70);
        let credential_id = passkey.cred_id().clone();
        store
            .insert("acct-a".to_string(), passkey)
            .expect("insert credential");

        // A genuine `AuthenticationResult` built via serde — no browser needed.
        let auth_result = test_authentication_result(&credential_id, 7);

        // Wrong account fail-closes and mutates nothing.
        assert_eq!(
            store.update_credential("acct-b", &auth_result),
            Err(PasskeyStoreUpdateError::NotFound),
            "cross-account update must be rejected"
        );

        // Correct account: counter advances 0 -> 7, so the credential changed.
        assert_eq!(
            store.update_credential("acct-a", &auth_result),
            Ok(true),
            "advancing the signature counter must report a change"
        );

        // Re-applying the same result is a no-op (counter already at 7).
        assert_eq!(
            store.update_credential("acct-a", &auth_result),
            Ok(false),
            "re-applying an identical result must report no change"
        );
    }

    fn test_authentication_result(
        credential_id: &CredentialID,
        counter: u32,
    ) -> AuthenticationResult {
        let cred_id_value = serde_json::to_value(credential_id).expect("credential id serializes");
        serde_json::from_value(json!({
            "cred_id": cred_id_value,
            "needs_update": true,
            "user_verified": true,
            "backup_state": false,
            "backup_eligible": false,
            "counter": counter,
            "extensions": {}
        }))
        .expect("authentication result fixture must deserialize")
    }

    #[test]
    fn passkey_store_insert_and_list_for_account() {
        let store = PasskeyStore::new();
        let passkey = test_passkey(1);
        store
            .insert("acct-1".to_string(), passkey.clone())
            .expect("insert should succeed");

        let listed = store.list_for_account("acct-1");
        assert_eq!(listed.len(), 1);
        assert_eq!(listed[0].cred_id(), passkey.cred_id());
    }

    #[test]
    fn passkey_store_rejects_duplicate_credential_id() {
        let store = PasskeyStore::new();
        let passkey = test_passkey(7);

        store
            .insert("acct-1".to_string(), passkey.clone())
            .expect("first insert should succeed");
        let duplicate = store.insert("acct-2".to_string(), passkey);

        assert_eq!(
            duplicate,
            Err(PasskeyStoreInsertError::DuplicateCredentialId),
            "duplicate credential id must be rejected"
        );
    }

    #[test]
    fn passkey_store_isolates_accounts() {
        let store = PasskeyStore::new();
        store
            .insert("acct-a".to_string(), test_passkey(10))
            .expect("insert account a");
        store
            .insert("acct-b".to_string(), test_passkey(20))
            .expect("insert account b");

        assert_eq!(store.list_for_account("acct-a").len(), 1);
        assert_eq!(store.list_for_account("acct-b").len(), 1);
        assert!(store.list_for_account("acct-c").is_empty());
    }

    #[test]
    fn passkey_store_find_and_remove_are_account_scoped() {
        let store = PasskeyStore::new();
        let a_key = test_passkey(33);
        let b_key = test_passkey(44);
        let a_cred_id = a_key.cred_id().clone();
        let b_cred_id = b_key.cred_id().clone();

        store
            .insert("acct-a".to_string(), a_key)
            .expect("insert account a");
        store
            .insert("acct-b".to_string(), b_key)
            .expect("insert account b");

        let found = store
            .find_by_credential_id(&a_cred_id)
            .expect("credential must be found");
        assert_eq!(found.account_id, "acct-a");
        assert_eq!(found.passkey.cred_id(), &a_cred_id);

        assert!(
            !store.remove_for_account("acct-b", &a_cred_id),
            "other account must not be able to remove credential"
        );
        assert!(
            store.find_by_credential_id(&a_cred_id).is_some(),
            "credential must still exist after wrong-account remove"
        );

        assert!(
            store.remove_for_account("acct-a", &a_cred_id),
            "owner account should remove credential"
        );
        assert!(
            store.find_by_credential_id(&a_cred_id).is_none(),
            "removed credential must no longer exist"
        );
        assert!(
            store.find_by_credential_id(&b_cred_id).is_some(),
            "other account credential must remain"
        );
    }
    #[test]
    fn passkey_store_allows_reinsert_after_remove() {
        let store = PasskeyStore::new();
        let passkey = test_passkey(55);
        let credential_id = passkey.cred_id().clone();

        store
            .insert("acct-a".to_string(), passkey.clone())
            .expect("first insert should succeed");

        assert!(
            store.remove_for_account("acct-a", &credential_id),
            "owner account should remove credential"
        );

        store
            .insert("acct-b".to_string(), passkey)
            .expect("removed credential id should be insertable again");

        let found = store
            .find_by_credential_id(&credential_id)
            .expect("reinserted credential should be found");

        assert_eq!(found.account_id, "acct-b");
    }

    #[test]
    fn passkey_store_remove_one_of_multiple_credentials_keeps_other_indexed() {
        let store = PasskeyStore::new();
        let first = test_passkey(61);
        let second = test_passkey(62);
        let first_id = first.cred_id().clone();
        let second_id = second.cred_id().clone();

        store
            .insert("acct-a".to_string(), first)
            .expect("insert first credential");
        store
            .insert("acct-a".to_string(), second)
            .expect("insert second credential");

        assert!(store.remove_for_account("acct-a", &first_id));

        assert!(
            store.find_by_credential_id(&first_id).is_none(),
            "removed credential must not remain indexed"
        );
        assert!(
            store.find_by_credential_id(&second_id).is_some(),
            "remaining credential must stay indexed"
        );
        assert_eq!(store.credential_ids_for_account("acct-a").len(), 1);
    }

    // ── helpers ───────────────────────────────────────────────────────────

    fn extract_user_id_from_ccr(ccr: &CreationChallengeResponse) -> Vec<u8> {
        let json = serde_json::to_value(ccr).unwrap();
        let id_str = json["publicKey"]["user"]["id"].as_str().unwrap();
        // WebAuthn user.id is base64url-encoded by webauthn-rs.
        // Decode using the standard base64url (no-pad) decoder.
        use base64::engine::general_purpose::URL_SAFE_NO_PAD;
        use base64::Engine;
        URL_SAFE_NO_PAD.decode(id_str).expect("valid base64url")
    }
}

#[cfg(test)]
mod grant_tests {
    use super::*;

    #[test]
    fn insert_and_consume_success() {
        let store = PasskeyRegistrationGrantStore::new();
        let id = store.insert("acct-1".to_string(), "dev-1".to_string());
        let result = store.consume(&id, "acct-1", "dev-1");
        assert!(
            matches!(result, ConsumeGrantResult::Consumed),
            "consume with correct bindings must succeed"
        );
    }

    #[test]
    fn single_use_second_consume_rejected() {
        let store = PasskeyRegistrationGrantStore::new();
        let id = store.insert("acct-1".to_string(), "dev-1".to_string());
        store.consume(&id, "acct-1", "dev-1");
        let result = store.consume(&id, "acct-1", "dev-1");
        assert!(
            matches!(result, ConsumeGrantResult::NotFound),
            "second consume must be rejected (single-use)"
        );
    }

    #[test]
    fn wrong_account_rejected_grant_preserved() {
        let store = PasskeyRegistrationGrantStore::new();
        let id = store.insert("acct-1".to_string(), "dev-1".to_string());
        let result = store.consume(&id, "wrong-account", "dev-1");
        assert!(
            matches!(result, ConsumeGrantResult::BindingMismatch),
            "wrong account must yield BindingMismatch"
        );
        // Grant must remain intact for the correct caller.
        let result2 = store.consume(&id, "acct-1", "dev-1");
        assert!(
            matches!(result2, ConsumeGrantResult::Consumed),
            "correct account must still consume after wrong-account attempt"
        );
    }

    #[test]
    fn wrong_device_rejected_grant_preserved() {
        let store = PasskeyRegistrationGrantStore::new();
        let id = store.insert("acct-1".to_string(), "dev-1".to_string());
        let result = store.consume(&id, "acct-1", "wrong-device");
        assert!(
            matches!(result, ConsumeGrantResult::BindingMismatch),
            "wrong device must yield BindingMismatch"
        );
        let result2 = store.consume(&id, "acct-1", "dev-1");
        assert!(
            matches!(result2, ConsumeGrantResult::Consumed),
            "correct device must still consume after wrong-device attempt"
        );
    }

    #[test]
    fn expired_grant_rejected() {
        let store = PasskeyRegistrationGrantStore::new();
        let id = store.insert_with_ttl(
            "acct-1".to_string(),
            "dev-1".to_string(),
            Duration::milliseconds(1),
        );
        std::thread::sleep(std::time::Duration::from_millis(50));
        let result = store.consume(&id, "acct-1", "dev-1");
        assert!(
            matches!(result, ConsumeGrantResult::NotFound),
            "expired grant must be rejected"
        );
    }

    #[test]
    fn missing_grant_returns_not_found() {
        let store = PasskeyRegistrationGrantStore::new();
        let result = store.consume("no-such-grant-id", "acct-1", "dev-1");
        assert!(
            matches!(result, ConsumeGrantResult::NotFound),
            "missing grant must return NotFound"
        );
    }
}

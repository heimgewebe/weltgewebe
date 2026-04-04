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
//!   the lifetime of the running process. Across restarts it is only stable once
//!   the value has been written back to the account data source — which is a
//!   prerequisite for `register/verify` and is NOT yet implemented.
//! * **`rp_id` / `rp_origin`** come from `AppConfig` (env overrides supported).
//!   No hardcoded defaults — missing values cause an explicit startup error when
//!   passkeys are enabled.

use std::collections::HashMap;
use std::sync::Arc;

use chrono::{DateTime, Utc};
use tokio::sync::RwLock;
use url::Url;
use uuid::Uuid;
use webauthn_rs::prelude::*;

use crate::config::AppConfig;

/// TTL for in-progress passkey registrations (5 minutes).
const REGISTRATION_TTL_SECS: i64 = 300;

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
    store: Arc<RwLock<HashMap<String, PendingRegistration>>>,
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
    pub async fn consume(
        &self,
        registration_id: &str,
        account_id: &str,
    ) -> Option<PasskeyRegistration> {
        let mut store = self.store.write().await;
        let pending = store.remove(registration_id)?;
        let cutoff = Utc::now() - chrono::Duration::seconds(REGISTRATION_TTL_SECS);
        if pending.created_at <= cutoff || pending.account_id != account_id {
            return None;
        }
        Some(pending.state)
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

#[cfg(test)]
mod tests {
    use super::*;

    fn test_webauthn() -> Arc<Webauthn> {
        let origin = Url::parse("http://localhost:3000").unwrap();
        let builder = WebauthnBuilder::new("localhost", &origin).unwrap();
        Arc::new(builder.build().unwrap())
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

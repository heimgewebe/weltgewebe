//! Runtime facade for registered passkey credential persistence.
//!
//! AUTH-PG-002 Slice B: chooses between the existing in-memory `PasskeyStore`
//! and the PostgreSQL-backed `DbPasskeyStore` behind an explicit config gate.
//! The short-lived WebAuthn ceremony stores remain in-memory; only registered
//! credentials are routed through this facade.

use thiserror::Error;
use uuid::Uuid;
use webauthn_rs::prelude::{AuthenticationResult, CredentialID, Passkey};

use crate::{config::PasskeyCredentialSource, state::ApiState};

use super::{
    passkeys::{PasskeyStoreInsertError, PasskeyStoreUpdateError, StoredPasskey},
    passkeys_db::{DbPasskeyStore, DbPasskeyStoreError},
};

#[derive(Debug, Error)]
pub enum PasskeyCredentialRuntimeError {
    #[error("passkey credential already exists")]
    DuplicateCredentialId,
    #[error("credential not found for account")]
    NotFound,
    #[error("credential update failed")]
    UpdateFailed,
    #[error("passkey credential backend unavailable")]
    BackendUnavailable,
    #[error("passkey credential database backend failed")]
    Database(#[source] DbPasskeyStoreError),
}

fn postgres_store(state: &ApiState) -> Result<DbPasskeyStore, PasskeyCredentialRuntimeError> {
    let pool = state
        .db_pool
        .as_ref()
        .ok_or(PasskeyCredentialRuntimeError::BackendUnavailable)?;
    Ok(DbPasskeyStore::new(pool.clone()))
}

fn map_db_error(error: DbPasskeyStoreError) -> PasskeyCredentialRuntimeError {
    match error {
        DbPasskeyStoreError::DuplicateCredentialId => {
            PasskeyCredentialRuntimeError::DuplicateCredentialId
        }
        DbPasskeyStoreError::NotFound => PasskeyCredentialRuntimeError::NotFound,
        other => PasskeyCredentialRuntimeError::Database(other),
    }
}

pub async fn insert(
    state: &ApiState,
    account_id: &str,
    webauthn_user_id: Uuid,
    passkey: Passkey,
) -> Result<(), PasskeyCredentialRuntimeError> {
    match state.config.passkey_credential_source {
        PasskeyCredentialSource::InMemory => state
            .passkeys
            .insert(account_id.to_string(), passkey)
            .map_err(|error| match error {
                PasskeyStoreInsertError::DuplicateCredentialId => {
                    PasskeyCredentialRuntimeError::DuplicateCredentialId
                }
            }),
        PasskeyCredentialSource::Postgres => postgres_store(state)?
            .insert(account_id, webauthn_user_id, &passkey)
            .await
            .map_err(map_db_error),
    }
}

pub async fn list_for_account(
    state: &ApiState,
    account_id: &str,
) -> Result<Vec<Passkey>, PasskeyCredentialRuntimeError> {
    match state.config.passkey_credential_source {
        PasskeyCredentialSource::InMemory => Ok(state.passkeys.list_for_account(account_id)),
        PasskeyCredentialSource::Postgres => postgres_store(state)?
            .list_for_account(account_id)
            .await
            .map_err(map_db_error),
    }
}

pub async fn credential_ids_for_account(
    state: &ApiState,
    account_id: &str,
) -> Result<Vec<CredentialID>, PasskeyCredentialRuntimeError> {
    match state.config.passkey_credential_source {
        PasskeyCredentialSource::InMemory => {
            Ok(state.passkeys.credential_ids_for_account(account_id))
        }
        PasskeyCredentialSource::Postgres => postgres_store(state)?
            .credential_ids_for_account(account_id)
            .await
            .map_err(map_db_error),
    }
}

pub async fn find_by_credential_id(
    state: &ApiState,
    credential_id: &CredentialID,
) -> Result<Option<StoredPasskey>, PasskeyCredentialRuntimeError> {
    match state.config.passkey_credential_source {
        PasskeyCredentialSource::InMemory => {
            Ok(state.passkeys.find_by_credential_id(credential_id))
        }
        PasskeyCredentialSource::Postgres => postgres_store(state)?
            .find_by_credential_id(credential_id)
            .await
            .map_err(map_db_error),
    }
}

pub async fn update_credential(
    state: &ApiState,
    account_id: &str,
    auth_result: &AuthenticationResult,
) -> Result<bool, PasskeyCredentialRuntimeError> {
    match state.config.passkey_credential_source {
        PasskeyCredentialSource::InMemory => state
            .passkeys
            .update_credential(account_id, auth_result)
            .map_err(|error| match error {
                PasskeyStoreUpdateError::NotFound => PasskeyCredentialRuntimeError::NotFound,
                PasskeyStoreUpdateError::UpdateFailed => {
                    PasskeyCredentialRuntimeError::UpdateFailed
                }
            }),
        PasskeyCredentialSource::Postgres => postgres_store(state)?
            .update_credential(account_id, auth_result)
            .await
            .map_err(map_db_error),
    }
}

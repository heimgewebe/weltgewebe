use axum::http::StatusCode;

use crate::{
    config::{DomainAccountWriteSource, DomainReadSource},
    state::ApiState,
};

pub(super) const DOMAIN_READ_SOURCE_READ_ONLY: &str = "DOMAIN_READ_SOURCE_READ_ONLY";
pub(super) const DOMAIN_READ_SOURCE_READ_ONLY_MESSAGE: &str =
    "Domain mutations are disabled while WELTGEWEBE_DOMAIN_READ_SOURCE=postgres is active; Phase E write-path cutover is not implemented for this endpoint.";

fn read_only_conflict() -> (StatusCode, String) {
    (
        StatusCode::CONFLICT,
        format!("{DOMAIN_READ_SOURCE_READ_ONLY}: {DOMAIN_READ_SOURCE_READ_ONLY_MESSAGE}"),
    )
}

/// Reject domain mutations that have no PostgreSQL write path implemented while
/// the PostgreSQL read source is active.
///
/// Used by node writes (and future edge writes). These remain blocked in
/// PostgreSQL read mode because writing them to JSONL would be invisible after a
/// restart, and no PostgreSQL write path exists for them yet (Phase E-A only
/// implements account-create). Account creation has its own, narrower gate —
/// see [`reject_account_create_unless_writable`].
pub(super) fn reject_if_postgres_read_source(state: &ApiState) -> Result<(), (StatusCode, String)> {
    if state.config.domain_read_source == DomainReadSource::Postgres {
        return Err(read_only_conflict());
    }

    Ok(())
}

/// Account-create write gate (OPT-ARC-001 Phase E-A).
///
/// Behaviour matrix:
/// - JSONL read + JSONL account write: allow (JSONL append path).
/// - Postgres read + Postgres account write: allow (PostgreSQL insert path).
/// - Postgres read + JSONL account write: reject — appending to JSONL under a
///   PostgreSQL read source would persist writes that vanish after a restart.
/// - JSONL read + Postgres account write: unreachable; rejected at config load
///   (`domain_account_write_source=postgres` requires `domain_read_source=postgres`).
pub(super) fn reject_account_create_unless_writable(
    state: &ApiState,
) -> Result<(), (StatusCode, String)> {
    if state.config.domain_read_source == DomainReadSource::Postgres
        && state.config.domain_account_write_source != DomainAccountWriteSource::Postgres
    {
        return Err(read_only_conflict());
    }

    Ok(())
}

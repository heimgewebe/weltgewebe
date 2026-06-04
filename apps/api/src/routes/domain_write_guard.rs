use axum::http::StatusCode;

use crate::{config::DomainReadSource, state::ApiState};

pub(super) const DOMAIN_READ_SOURCE_READ_ONLY: &str = "DOMAIN_READ_SOURCE_READ_ONLY";
pub(super) const DOMAIN_READ_SOURCE_READ_ONLY_MESSAGE: &str =
    "Domain mutations are disabled while WELTGEWEBE_DOMAIN_READ_SOURCE=postgres is active; Phase E write-path cutover is not implemented.";

pub(super) fn status_error(status: StatusCode) -> (StatusCode, String) {
    (status, status.to_string())
}

pub(super) fn reject_if_postgres_read_source(state: &ApiState) -> Result<(), (StatusCode, String)> {
    if state.config.domain_read_source == DomainReadSource::Postgres {
        return Err((
            StatusCode::CONFLICT,
            format!("{DOMAIN_READ_SOURCE_READ_ONLY}: {DOMAIN_READ_SOURCE_READ_ONLY_MESSAGE}"),
        ));
    }

    Ok(())
}

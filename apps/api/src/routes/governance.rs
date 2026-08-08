//! HTTP-Oberfläche des Antragssystems (`docs/specs/governance-antraege.md`).
//!
//! Leserechte sind öffentlich. Angemeldete Gäste dürfen den eigenen
//! Weberantrag stellen, in offenen Gesprächsräumen mitreden und den eigenen
//! Account auflösen. Formale Vetos und Stimmen bleiben Webern und
//! Administratoren vorbehalten.
//!
//! PostgreSQL ist kanonisch: ohne konfigurierten Pool antworten alle
//! Governance-Endpunkte fail-closed mit 503 — es gibt keinen JSONL- oder
//! In-Memory-Fallback. Vor jedem Read werden fällige Fristen serverseitig
//! und idempotent finalisiert (zusätzlich läuft der Sweeper in `lib.rs`).

use axum::{
    extract::{Path, State},
    http::StatusCode,
    Extension, Json,
};
use chrono::{DateTime, Utc};
#[cfg(feature = "integration-testing")]
use serde::Deserialize;
use serde::Serialize;
use serde_json::Value;
use sqlx::PgPool;

use super::webgemeindezentren::{
    ensure_webgemeindezentrum_activity_faden, repair_webgemeindezentrum_activity_faden,
};
use crate::auth::role::Role;
use crate::config::{
    DomainAccountWriteSource, DomainEdgeWriteSource, DomainNodeWriteSource, DomainReadSource,
};
use crate::governance::{
    self, CreateProposalError, GuestExitError, MessageError, ProposalMessage, ProposalStatus,
    ProposalWithCounts, Veto, VetoError, VoteChoice, VoteError, VoteWriteOutcome,
    MESSAGE_BODY_MAX_CHARS, PROPOSAL_TITLE_MAX_CHARS, SUMMARY_MAX_CHARS, VETO_REASON_MAX_CHARS,
};
use crate::middleware::auth::AuthContext;
use crate::state::ApiState;

type ApiError = (StatusCode, String);

fn record_guest_exit_session_cleanup(
    account_id: &str,
    cleanup: crate::auth::session::SessionResult<()>,
) {
    if let Err(error) = cleanup {
        tracing::warn!(
            error = %error,
            account_id,
            "guest exit committed; secondary session backend cleanup failed"
        );
    }
}

/// Fail-closed-Torwächter: Governance existiert nur mit PostgreSQL.
fn require_pool(state: &ApiState) -> Result<&PgPool, ApiError> {
    if state.config.domain_read_source != DomainReadSource::Postgres
        || state.config.domain_account_write_source != DomainAccountWriteSource::Postgres
    {
        return Err((
            StatusCode::SERVICE_UNAVAILABLE,
            "governance requires PostgreSQL as the canonical account read and write source"
                .to_string(),
        ));
    }
    state.db_pool.as_ref().ok_or((
        StatusCode::SERVICE_UNAVAILABLE,
        "governance requires a configured PostgreSQL database".to_string(),
    ))
}

fn require_guest_exit_pool(state: &ApiState) -> Result<&PgPool, ApiError> {
    if state.config.domain_read_source != DomainReadSource::Postgres
        || state.config.domain_account_write_source != DomainAccountWriteSource::Postgres
        || state.config.domain_node_write_source != DomainNodeWriteSource::Postgres
        || state.config.domain_edge_write_source != DomainEdgeWriteSource::Postgres
    {
        return Err((
            StatusCode::SERVICE_UNAVAILABLE,
            "guest exit requires PostgreSQL as the canonical account, node and edge source"
                .to_string(),
        ));
    }
    state.db_pool.as_ref().ok_or((
        StatusCode::SERVICE_UNAVAILABLE,
        "guest exit requires a configured PostgreSQL database".to_string(),
    ))
}

fn internal_error(context: &'static str) -> impl Fn(sqlx::Error) -> ApiError {
    move |error| {
        tracing::error!(error = %error, context, "governance database operation failed");
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            "governance operation failed".to_string(),
        )
    }
}

fn require_account_id(auth: &AuthContext) -> Result<String, ApiError> {
    if !auth.authenticated {
        return Err((
            StatusCode::UNAUTHORIZED,
            "authentication required".to_string(),
        ));
    }
    auth.account_id.clone().ok_or((
        StatusCode::UNAUTHORIZED,
        "authenticated account context missing".to_string(),
    ))
}

fn require_formal_governance_actor(auth: &AuthContext) -> Result<String, ApiError> {
    let account_id = require_account_id(auth)?;
    if !matches!(auth.role, Role::Weber | Role::Admin) {
        return Err((
            StatusCode::FORBIDDEN,
            "formal vetoes and votes require Weber status".to_string(),
        ));
    }
    Ok(account_id)
}

/// Anzeigename aus dem laufenden Account-Store; Fallback, falls die Projektion
/// den Account (noch) nicht kennt.
async fn account_title(state: &ApiState, account_id: &str) -> String {
    let accounts = state.accounts.read().await;
    accounts
        .get(account_id)
        .map(|account| account.public.title.clone())
        .unwrap_or_else(|| "Unbenannter Account".to_string())
}

/// Fällige Fristen serverseitig und idempotent auswerten, Beförderungen in
/// den laufenden Store spiegeln. Läuft vor jedem Governance-Read.
async fn finalize_due(state: &ApiState, pool: &PgPool) -> Result<(), ApiError> {
    let outcomes = governance::finalize_due_proposals(pool, Utc::now())
        .await
        .map_err(internal_error("finalize_due_proposals"))?;
    governance::apply_promotions_to_store(&state.accounts, &outcomes).await;
    Ok(())
}

/// Öffentliche Antragsprojektion inklusive verbleibender Frist in Sekunden.
#[derive(Debug, Serialize)]
pub struct ProposalView {
    pub id: String,
    pub kind: String,
    pub webgemeindezentrum_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub target_node_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub target_node_title: Option<String>,
    pub applicant_account_id: Option<String>,
    pub applicant_title: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub summary: Option<String>,
    pub status: ProposalStatus,
    pub created_at: DateTime<Utc>,
    pub consent_until: DateTime<Utc>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub voting_until: Option<DateTime<Utc>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub finalized_at: Option<DateTime<Utc>>,
    pub veto_count: i64,
    pub message_count: i64,
    pub yes_votes: i64,
    pub no_votes: i64,
    pub abstain_votes: i64,
    /// Verbleibende Sekunden der laufenden Phase; `None` nach Finalisierung.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub remaining_seconds: Option<i64>,
}

fn proposal_view(proposal: ProposalWithCounts, now: DateTime<Utc>) -> ProposalView {
    let remaining_seconds = match proposal.status {
        ProposalStatus::Consent => Some((proposal.consent_until - now).num_seconds().max(0)),
        ProposalStatus::Voting => proposal
            .voting_until
            .map(|until| (until - now).num_seconds().max(0)),
        ProposalStatus::Accepted | ProposalStatus::Rejected => None,
    };

    ProposalView {
        id: proposal.id,
        kind: proposal.kind,
        webgemeindezentrum_id: proposal.webgemeindezentrum_id,
        title: proposal.title,
        target_node_id: proposal.target_node_id,
        target_node_title: proposal.target_node_title,
        applicant_account_id: proposal.applicant_account_id,
        applicant_title: proposal.applicant_title,
        summary: proposal.summary,
        status: proposal.status,
        created_at: proposal.created_at,
        consent_until: proposal.consent_until,
        voting_until: proposal.voting_until,
        finalized_at: proposal.finalized_at,
        veto_count: proposal.veto_count,
        message_count: proposal.message_count,
        yes_votes: proposal.yes_votes,
        no_votes: proposal.no_votes,
        abstain_votes: proposal.abstain_votes,
        remaining_seconds,
    }
}

#[derive(Debug, Serialize)]
pub struct ProposalDetailView {
    #[serde(flatten)]
    pub proposal: ProposalView,
    pub vetoes: Vec<Veto>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub own_vote: Option<String>,
}

#[cfg(feature = "integration-testing")]
#[derive(Debug, Deserialize)]
pub struct GovernanceTestingAdvancePayload {
    pub now: DateTime<Utc>,
}

#[cfg(feature = "integration-testing")]
/// Advance one proof proposal through the genuine production finalizer at an
/// explicit test timestamp. The route exists only in integration-testing builds
/// and refuses non-proof applicants.
pub async fn governance_testing_advance_proposal(
    State(state): State<ApiState>,
    Path(id): Path<String>,
    Json(payload): Json<GovernanceTestingAdvancePayload>,
) -> Result<Json<ProposalView>, ApiError> {
    let pool = require_pool(&state)?;
    let before = governance::get_proposal(pool, &id)
        .await
        .map_err(internal_error("get_proposal"))?
        .ok_or((StatusCode::NOT_FOUND, "proposal not found".to_string()))?;
    if !before
        .applicant_account_id
        .as_deref()
        .is_some_and(|account_id| account_id.starts_with("proof-governance-"))
    {
        return Err((
            StatusCode::FORBIDDEN,
            "testing advance is restricted to governance proof accounts".to_string(),
        ));
    }

    let outcomes = governance::finalize_testing_proposal(pool, &id, payload.now)
        .await
        .map_err(internal_error("finalize_testing_proposal"))?;
    governance::apply_promotions_to_store(&state.accounts, &outcomes).await;
    let after = governance::get_proposal(pool, &id)
        .await
        .map_err(internal_error("get_proposal"))?
        .ok_or((StatusCode::NOT_FOUND, "proposal not found".to_string()))?;
    Ok(Json(proposal_view(after, payload.now)))
}

/// GET /proposals — öffentliche Liste, neueste zuerst.
pub async fn list_proposals(
    State(state): State<ApiState>,
) -> Result<Json<Vec<ProposalView>>, ApiError> {
    let pool = require_pool(&state)?;
    finalize_due(&state, pool).await?;

    let now = Utc::now();
    let proposals = governance::list_proposals(pool)
        .await
        .map_err(internal_error("list_proposals"))?;
    Ok(Json(
        proposals
            .into_iter()
            .map(|proposal| proposal_view(proposal, now))
            .collect(),
    ))
}

/// GET /proposals/{id} — öffentliche Informationsseite inkl. Vetos; für
/// angemeldete Accounts zusätzlich die eigene aktuelle Stimme.
pub async fn get_proposal(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
    Path(id): Path<String>,
) -> Result<Json<ProposalDetailView>, ApiError> {
    let pool = require_pool(&state)?;
    finalize_due(&state, pool).await?;

    let proposal = governance::get_proposal(pool, &id)
        .await
        .map_err(internal_error("get_proposal"))?
        .ok_or((StatusCode::NOT_FOUND, "proposal not found".to_string()))?;

    let vetoes = governance::list_vetoes(pool, &id)
        .await
        .map_err(internal_error("list_vetoes"))?;

    let own_vote = match (&auth.authenticated, &auth.account_id) {
        (true, Some(account_id)) => governance::get_own_vote(pool, &id, account_id)
            .await
            .map_err(internal_error("get_own_vote"))?,
        _ => None,
    };

    Ok(Json(ProposalDetailView {
        proposal: proposal_view(proposal, Utc::now()),
        vetoes,
        own_vote,
    }))
}

fn bad_request(message: &str) -> ApiError {
    (StatusCode::BAD_REQUEST, message.to_string())
}

fn optional_trimmed_text(
    value: Option<&Value>,
    field: &'static str,
    max_chars: usize,
) -> Result<Option<String>, ApiError> {
    match value {
        None => Ok(None),
        Some(Value::String(text)) => {
            let trimmed = text.trim();
            if trimmed.is_empty() {
                return Err(bad_request(&format!(
                    "{field} must not be blank when present"
                )));
            }
            if trimmed.chars().count() > max_chars {
                return Err(bad_request(&format!(
                    "{field} exceeds the maximum length of {max_chars} characters"
                )));
            }
            Ok(Some(trimmed.to_string()))
        }
        Some(_) => Err(bad_request(&format!("{field} must be a string"))),
    }
}

fn required_trimmed_text(
    value: Option<&Value>,
    field: &'static str,
    max_chars: usize,
) -> Result<String, ApiError> {
    optional_trimmed_text(value, field, max_chars)?
        .ok_or_else(|| bad_request(&format!("missing or empty field: {field}")))
}

/// POST /proposals — Weberantrag für Gäste oder Sachantrag für Weber/Admin.
/// Erlaubte Felder werden je `kind` strikt getrennt geprüft.
pub async fn create_proposal(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
    Json(payload): Json<Value>,
) -> Result<(StatusCode, Json<ProposalView>), ApiError> {
    let account_id = require_account_id(&auth)?;

    let pool = require_pool(&state)?;

    let object = payload
        .as_object()
        .ok_or_else(|| bad_request("proposal request must be a JSON object"))?;
    let kind = object
        .get("kind")
        .and_then(Value::as_str)
        .ok_or_else(|| bad_request("kind must be one of: weberantrag, sachantrag"))?;
    let allowed_fields: &[&str] = match kind {
        "weberantrag" => &["kind", "summary", "webgemeindezentrum_id"],
        "sachantrag" => &[
            "kind",
            "title",
            "summary",
            "webgemeindezentrum_id",
            "target_node_id",
        ],
        _ => return Err(bad_request("kind must be one of: weberantrag, sachantrag")),
    };
    for key in object.keys() {
        if !allowed_fields.contains(&key.as_str()) {
            return Err(bad_request(&format!("unknown field for {kind}: {key}")));
        }
    }
    let summary = optional_trimmed_text(object.get("summary"), "summary", SUMMARY_MAX_CHARS)?;
    let webgemeindezentrum_id = optional_trimmed_text(
        object.get("webgemeindezentrum_id"),
        "webgemeindezentrum_id",
        128,
    )?;

    let applicant_title = account_title(&state, &account_id).await;
    let proposal_result = match kind {
        "weberantrag" => {
            if auth.role != Role::Gast {
                return Err((
                    StatusCode::CONFLICT,
                    "account already holds Weber status".to_string(),
                ));
            }
            governance::create_weber_proposal_at_center(
                pool,
                &account_id,
                &applicant_title,
                summary.as_deref(),
                webgemeindezentrum_id.as_deref(),
                Utc::now(),
            )
            .await
        }
        "sachantrag" => {
            if !matches!(auth.role, Role::Weber | Role::Admin) {
                return Err((
                    StatusCode::FORBIDDEN,
                    "Sachantraege require Weber or administrator status".to_string(),
                ));
            }
            let title =
                required_trimmed_text(object.get("title"), "title", PROPOSAL_TITLE_MAX_CHARS)?;
            let target_node_id =
                optional_trimmed_text(object.get("target_node_id"), "target_node_id", 200)?;
            governance::create_sach_proposal_at_center(
                pool,
                &account_id,
                &applicant_title,
                &title,
                summary.as_deref(),
                webgemeindezentrum_id.as_deref(),
                target_node_id.as_deref(),
                Utc::now(),
            )
            .await
        }
        _ => unreachable!("kind was validated above"),
    };
    let proposal = proposal_result.map_err(|error| match error {
        CreateProposalError::AlreadyOpen => (
            StatusCode::CONFLICT,
            "an open proposal of this kind already exists for this account".to_string(),
        ),
        CreateProposalError::NotGuest => (
            StatusCode::CONFLICT,
            "only an active guest account may apply for Weber status".to_string(),
        ),
        CreateProposalError::NotSachApplicant => (
            StatusCode::FORBIDDEN,
            "only an active Weber or administrator may create a Sachantrag".to_string(),
        ),
        CreateProposalError::CenterUnavailable => (
            StatusCode::SERVICE_UNAVAILABLE,
            "the requested Webgemeindezentrum is not an active governance center".to_string(),
        ),
        CreateProposalError::TargetNodeNotFound => (
            StatusCode::NOT_FOUND,
            "the target node does not exist".to_string(),
        ),
        CreateProposalError::Database(error) => internal_error("create_proposal")(error),
    })?;

    if let Err((status, error)) = ensure_webgemeindezentrum_activity_faden(
        &state,
        &auth,
        &proposal.webgemeindezentrum_id,
        super::edges::FadenType::Proposal,
        &proposal.id,
    )
    .await
    {
        tracing::error!(
            event = "governance.proposal_faden_projection.failed",
            proposal_id = %proposal.id,
            center_id = %proposal.webgemeindezentrum_id,
            %status,
            %error,
            "Proposal remains durable; its derived center Faden is missing"
        );
    }

    tracing::info!(
        event = "governance.proposal.created",
        proposal_id = %proposal.id,
        kind = %proposal.kind,
        center_id = %proposal.webgemeindezentrum_id,
        "Governance proposal created"
    );

    let now = Utc::now();
    Ok((StatusCode::CREATED, Json(proposal_view(proposal, now))))
}

/// POST /proposals/{id}/veto — begründetes Veto eines angemeldeten Accounts.
/// Der eigene Weberantrag bleibt von formaler Selbstentscheidung ausgeschlossen.
pub async fn veto_proposal(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
    Path(id): Path<String>,
    Json(payload): Json<Value>,
) -> Result<(StatusCode, Json<Veto>), ApiError> {
    let account_id = require_formal_governance_actor(&auth)?;
    let pool = require_pool(&state)?;

    let object = payload
        .as_object()
        .ok_or_else(|| bad_request("veto request must be a JSON object"))?;
    for key in object.keys() {
        if key != "reason" {
            return Err(bad_request(&format!("unknown field: {key}")));
        }
    }
    let reason = required_trimmed_text(object.get("reason"), "reason", VETO_REASON_MAX_CHARS)?;

    let proposal = governance::get_proposal(pool, &id)
        .await
        .map_err(internal_error("get_proposal_for_veto"))?
        .ok_or((StatusCode::NOT_FOUND, "proposal not found".to_string()))?;
    let title = account_title(&state, &account_id).await;
    let veto = governance::add_veto(pool, &id, &account_id, &title, &reason, Utc::now())
        .await
        .map_err(|error| match error {
            VetoError::NotFound => (StatusCode::NOT_FOUND, "proposal not found".to_string()),
            VetoError::WrongPhase => (
                StatusCode::CONFLICT,
                "veto is only possible during the open consent phase".to_string(),
            ),
            VetoError::AlreadyVetoed => (
                StatusCode::CONFLICT,
                "this account already vetoed the proposal".to_string(),
            ),
            VetoError::ApplicantCannotDecide => (
                StatusCode::FORBIDDEN,
                "the applicant cannot veto the own proposal".to_string(),
            ),
            VetoError::ActorNotEligible => (
                StatusCode::FORBIDDEN,
                "formal vetoes require Weber status".to_string(),
            ),
            VetoError::ActorUnavailable => (
                StatusCode::UNAUTHORIZED,
                "veto actor account is no longer active".to_string(),
            ),
            VetoError::Database(error) => internal_error("add_veto")(error),
        })?;

    if let Err((status, error)) = ensure_webgemeindezentrum_activity_faden(
        &state,
        &auth,
        &proposal.webgemeindezentrum_id,
        super::edges::FadenType::Vote,
        &id,
    )
    .await
    {
        tracing::error!(
            event = "governance.veto_faden_projection.failed",
            proposal_id = %id,
            center_id = %proposal.webgemeindezentrum_id,
            %status,
            %error,
            "Veto remains durable; its derived center Faden is missing"
        );
    }

    tracing::info!(
        event = "governance.veto.recorded",
        proposal_id = %id,
        center_id = %proposal.webgemeindezentrum_id,
        "Veto recorded"
    );

    Ok((StatusCode::CREATED, Json(veto)))
}

/// PUT /proposals/{id}/vote — genau eine aktuelle, änderbare Stimme je
/// angemeldetem Account; der Antragsteller stimmt nicht über die eigene Aufnahme ab.
pub async fn vote_proposal(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
    Path(id): Path<String>,
    Json(payload): Json<Value>,
) -> Result<Json<Value>, ApiError> {
    let account_id = require_formal_governance_actor(&auth)?;
    let pool = require_pool(&state)?;

    let object = payload
        .as_object()
        .ok_or_else(|| bad_request("vote request must be a JSON object"))?;
    for key in object.keys() {
        if key != "choice" {
            return Err(bad_request(&format!("unknown field: {key}")));
        }
    }
    let choice: VoteChoice = object
        .get("choice")
        .cloned()
        .and_then(|value| serde_json::from_value(value).ok())
        .ok_or_else(|| bad_request("choice must be one of: ja, nein, enthaltung"))?;

    let proposal = governance::get_proposal(pool, &id)
        .await
        .map_err(internal_error("get_proposal_for_vote"))?
        .ok_or((StatusCode::NOT_FOUND, "proposal not found".to_string()))?;

    let vote_outcome = governance::upsert_vote(pool, &id, &account_id, choice, Utc::now())
        .await
        .map_err(|error| match error {
            VoteError::NotFound => (StatusCode::NOT_FOUND, "proposal not found".to_string()),
            VoteError::WrongPhase => (
                StatusCode::CONFLICT,
                "voting is only possible during the open voting phase".to_string(),
            ),
            VoteError::ApplicantCannotDecide => (
                StatusCode::FORBIDDEN,
                "the applicant cannot vote on the own proposal".to_string(),
            ),
            VoteError::ActorNotEligible => (
                StatusCode::FORBIDDEN,
                "formal votes require Weber status".to_string(),
            ),
            VoteError::ActorUnavailable => (
                StatusCode::UNAUTHORIZED,
                "vote actor account is no longer active".to_string(),
            ),
            VoteError::Database(error) => internal_error("upsert_vote")(error),
        })?;

    let projection = match vote_outcome {
        VoteWriteOutcome::Created | VoteWriteOutcome::Changed => {
            ensure_webgemeindezentrum_activity_faden(
                &state,
                &auth,
                &proposal.webgemeindezentrum_id,
                super::edges::FadenType::Vote,
                &id,
            )
            .await
        }
        VoteWriteOutcome::Unchanged => {
            repair_webgemeindezentrum_activity_faden(
                &state,
                &auth,
                &proposal.webgemeindezentrum_id,
                super::edges::FadenType::Vote,
                &id,
            )
            .await
        }
    };
    if let Err((status, error)) = projection {
        tracing::error!(
            event = "governance.vote_faden_projection.failed",
            proposal_id = %id,
            center_id = %proposal.webgemeindezentrum_id,
            %status,
            %error,
            "Vote remains durable; its derived center Faden is missing"
        );
    }

    Ok(Json(serde_json::json!({ "choice": choice.as_str() })))
}

/// GET /proposals/{id}/messages — öffentlicher Gesprächsraum (lesend).
pub async fn list_proposal_messages(
    State(state): State<ApiState>,
    Path(id): Path<String>,
) -> Result<Json<Vec<ProposalMessage>>, ApiError> {
    let pool = require_pool(&state)?;
    finalize_due(&state, pool).await?;

    // 404 für unbekannte Anträge statt einer leeren Liste.
    governance::get_proposal(pool, &id)
        .await
        .map_err(internal_error("get_proposal"))?
        .ok_or((StatusCode::NOT_FOUND, "proposal not found".to_string()))?;

    let messages = governance::list_messages(pool, &id)
        .await
        .map_err(internal_error("list_messages"))?;
    Ok(Json(messages))
}

/// POST /proposals/{id}/messages — öffentlicher Beitrag eines angemeldeten
/// Accounts während einer offenen Phase.
pub async fn post_proposal_message(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
    Path(id): Path<String>,
    Json(payload): Json<Value>,
) -> Result<(StatusCode, Json<ProposalMessage>), ApiError> {
    let pool = require_pool(&state)?;
    let account_id = require_account_id(&auth)?;

    let object = payload
        .as_object()
        .ok_or_else(|| bad_request("message request must be a JSON object"))?;
    for key in object.keys() {
        if key != "body" {
            return Err(bad_request(&format!("unknown field: {key}")));
        }
    }
    let body = required_trimmed_text(object.get("body"), "body", MESSAGE_BODY_MAX_CHARS)?;

    let proposal = governance::get_proposal(pool, &id)
        .await
        .map_err(internal_error("get_proposal_for_message"))?
        .ok_or((StatusCode::NOT_FOUND, "proposal not found".to_string()))?;
    let title = account_title(&state, &account_id).await;
    let message = governance::add_message(pool, &id, &account_id, &title, &body, Utc::now())
        .await
        .map_err(|error| match error {
            MessageError::NotFound => (StatusCode::NOT_FOUND, "proposal not found".to_string()),
            MessageError::WrongPhase => (
                StatusCode::CONFLICT,
                "the conversation is closed for finalized proposals".to_string(),
            ),
            MessageError::Database(error) => internal_error("add_message")(error),
        })?;

    if let Err((status, error)) = ensure_webgemeindezentrum_activity_faden(
        &state,
        &auth,
        &proposal.webgemeindezentrum_id,
        super::edges::FadenType::Conversation,
        &id,
    )
    .await
    {
        tracing::error!(
            event = "governance.message_faden_projection.failed",
            proposal_id = %id,
            message_id = %message.id,
            center_id = %proposal.webgemeindezentrum_id,
            %status,
            %error,
            "Proposal message remains durable; its derived center Faden is missing"
        );
    }

    Ok((StatusCode::CREATED, Json(message)))
}

/// POST /accounts/me/exit — der selbst initiierte Austritt aus dem
/// Weltgewebe. Nur Gäste dürfen diesen Sonderpfad nutzen. Er entfernt ihre
/// Authentifizierungsidentität samt eigenen Weberanträgen und Anmeldedaten aus
/// der kanonischen Datenbank, aus der Laufzeitprojektion und aus allen Sessions.
/// Gemeinschaftliche Knoten und Beiträge bleiben anonymisiert erhalten.
pub async fn exit_own_account(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
) -> Result<Json<Value>, ApiError> {
    let account_id = require_account_id(&auth)?;
    if auth.role != Role::Gast {
        return Err((
            StatusCode::CONFLICT,
            "only guest accounts can use the guest exit path".to_string(),
        ));
    }
    let pool = require_guest_exit_pool(&state)?;

    governance::delete_guest_account(pool, &account_id)
        .await
        .map_err(|error| match error {
            GuestExitError::NotEligible => (
                StatusCode::CONFLICT,
                "account is no longer an active guest".to_string(),
            ),
            GuestExitError::AmbiguousLegacyEndpoint => (
                StatusCode::CONFLICT,
                "guest exit is blocked by an ambiguous legacy relationship".to_string(),
            ),
            GuestExitError::Database(error) => internal_error("delete_guest_account")(error),
        })?;

    let session_cleanup = state.sessions.delete_all_by_account(&account_id).await;
    record_guest_exit_session_cleanup(&account_id, session_cleanup);
    // In PostgreSQL mode the projection middleware holds a read guard for the
    // whole request. Refreshing here would try to upgrade that guard to a write
    // lock and deadlock against ourselves. The next domain request observes the
    // incremented database generation and refreshes before taking its read guard.

    tracing::info!(event = "governance.guest.exited", "Guest account deleted");

    Ok(Json(serde_json::json!({ "status": "exited" })))
}

#[cfg(test)]
mod tests {
    use super::record_guest_exit_session_cleanup;
    use crate::auth::session::SessionBackendError;

    #[test]
    fn failed_secondary_session_cleanup_does_not_fail_committed_guest_exit() {
        record_guest_exit_session_cleanup(
            "guest-already-deleted",
            Err(SessionBackendError::Unavailable),
        );
    }
}

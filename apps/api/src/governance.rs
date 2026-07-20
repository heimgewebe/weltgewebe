//! Governance: allgemeines Antragssystem (vertikaler Schnitt: Weberantrag).
//!
//! PostgreSQL ist die kanonische Wahrheit für Anträge, Vetos, Stimmen und
//! Gesprächsraum-Beiträge (siehe `docs/specs/governance-antraege.md`). Ohne
//! konfigurierten Pool arbeiten die Governance-Endpunkte fail-closed; es gibt
//! keinen JSONL-Fallback für diese Tabellen.
//!
//! Fristen werden serverseitig und idempotent ausgewertet:
//! [`finalize_due_proposals`] läuft sowohl als Hintergrund-Sweeper als auch
//! lazy vor jedem Governance-Read. Jede Finalisierung ist eine einzelne
//! Datenbanktransaktion mit `SELECT ... FOR UPDATE`-Recheck, damit weder ein
//! Neustart noch konkurrierende Auswertungen doppelte oder halbe Übergänge
//! erzeugen können.
//!
//! Die sqlx-Konfiguration dieses Crates hat kein `uuid`-Feature; `UUID`-Spalten
//! werden — wie in `domain_db` und `passkeys_db` — als Text mit expliziten
//! `$n::uuid`-Casts gebunden und als `id::text` gelesen.

use std::sync::Arc;

use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use sqlx::{PgPool, Postgres, Row, Transaction};
use tokio::sync::RwLock;
use uuid::Uuid;

use crate::auth::accounts::AccountStore;
use crate::auth::role::Role;

/// Länge der offenen Konsentphase eines Weberantrags.
pub const CONSENT_PHASE_DAYS: i64 = 7;
/// Länge der Beratungs- und Abstimmungsphase nach mindestens einem Veto.
pub const VOTING_PHASE_DAYS: i64 = 7;

/// Maximale Länge der Antragsbegründung (Spiegel des DB-Checks).
pub const SUMMARY_MAX_CHARS: usize = 2000;
/// Maximale Länge einer Veto-Begründung (Spiegel des DB-Checks).
pub const VETO_REASON_MAX_CHARS: usize = 2000;
/// Maximale Länge eines Gesprächsraum-Beitrags (Spiegel des DB-Checks).
pub const MESSAGE_BODY_MAX_CHARS: usize = 4000;

/// Lebenszyklus eines Antrags. Persistiert als Kleinbuchstaben-Text.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ProposalStatus {
    /// Offene Konsentphase bis `consent_until`.
    Consent,
    /// Beratungs- und Abstimmungsphase bis `voting_until` (nach Veto).
    Voting,
    /// Final angenommen; bei Weberanträgen ist die Aufnahme vollzogen.
    Accepted,
    /// Final abgelehnt (auch Gleichstand und 0:0).
    Rejected,
}

impl ProposalStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Consent => "consent",
            Self::Voting => "voting",
            Self::Accepted => "accepted",
            Self::Rejected => "rejected",
        }
    }

    fn from_db(value: &str) -> Result<Self, sqlx::Error> {
        match value {
            "consent" => Ok(Self::Consent),
            "voting" => Ok(Self::Voting),
            "accepted" => Ok(Self::Accepted),
            "rejected" => Ok(Self::Rejected),
            other => Err(sqlx::Error::Decode(
                format!("unknown governance proposal status: {other}").into(),
            )),
        }
    }
}

/// Genau eine aktuelle, änderbare Stimme je Weber und Antrag.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum VoteChoice {
    Ja,
    Nein,
    Enthaltung,
}

impl VoteChoice {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Ja => "ja",
            Self::Nein => "nein",
            Self::Enthaltung => "enthaltung",
        }
    }
}

/// Antrag inklusive öffentlicher Zählstände (Vetos und Stimmen).
#[derive(Clone, Debug)]
pub struct ProposalWithCounts {
    pub id: String,
    pub kind: String,
    pub applicant_account_id: String,
    pub applicant_title: String,
    pub summary: Option<String>,
    pub status: ProposalStatus,
    pub created_at: DateTime<Utc>,
    pub consent_until: DateTime<Utc>,
    pub voting_until: Option<DateTime<Utc>>,
    pub finalized_at: Option<DateTime<Utc>>,
    pub veto_count: i64,
    pub yes_votes: i64,
    pub no_votes: i64,
    pub abstain_votes: i64,
}

/// Begründetes Veto eines Webers (öffentlich sichtbare Webungsaktion).
#[derive(Clone, Debug, Serialize)]
pub struct Veto {
    pub weber_account_id: String,
    pub weber_title: String,
    pub reason: String,
    pub created_at: DateTime<Utc>,
}

/// Beitrag im Gesprächsraum eines Antrags.
#[derive(Clone, Debug, Serialize)]
pub struct ProposalMessage {
    pub id: String,
    pub author_account_id: Option<String>,
    pub author_title: String,
    pub body: String,
    pub created_at: DateTime<Utc>,
}

/// Ergebnis einer Finalisierung durch [`finalize_due_proposals`].
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FinalizationOutcome {
    pub proposal_id: String,
    pub applicant_account_id: String,
    pub status: ProposalStatus,
    /// `true` genau dann, wenn diese Transaktion die bestehende Gastidentität
    /// auf die Berechtigungsrolle `weber` angehoben hat.
    pub promoted: bool,
}

#[derive(Debug, thiserror::Error)]
pub enum CreateProposalError {
    /// Der Account hat bereits einen offenen Antrag dieser Art (Doppelantrag).
    #[error("an open proposal of this kind already exists for this account")]
    AlreadyOpen,
    /// Nur eine aktive Gastidentität darf den Weberstatus beantragen.
    #[error("only an active guest account may create a Weber proposal")]
    NotGuest,
    #[error("failed to persist proposal: {0}")]
    Database(#[source] sqlx::Error),
}

#[derive(Debug, thiserror::Error)]
pub enum VetoError {
    #[error("proposal not found")]
    NotFound,
    /// Veto ist nur während der offenen Konsentphase zulässig.
    #[error("proposal is not in an open consent phase")]
    WrongPhase,
    /// Je Weber höchstens ein Veto pro Antrag.
    #[error("this weber already vetoed the proposal")]
    AlreadyVetoed,
    #[error("failed to persist veto: {0}")]
    Database(#[source] sqlx::Error),
}

#[derive(Debug, thiserror::Error)]
pub enum VoteError {
    #[error("proposal not found")]
    NotFound,
    /// Stimmen sind nur während der Beratungs- und Abstimmungsphase zulässig.
    #[error("proposal is not in an open voting phase")]
    WrongPhase,
    #[error("failed to persist vote: {0}")]
    Database(#[source] sqlx::Error),
}

#[derive(Debug, thiserror::Error)]
pub enum MessageError {
    #[error("proposal not found")]
    NotFound,
    /// Beiträge sind nur zulässig, solange der Antrag offen ist.
    #[error("proposal is no longer open for conversation")]
    WrongPhase,
    #[error("failed to persist message: {0}")]
    Database(#[source] sqlx::Error),
}

// ---------------------------------------------------------------------------
// Reine Entscheidungslogik (ohne Datenbank testbar)
// ---------------------------------------------------------------------------

/// Ergebnis der Konsentphase: ohne Veto wird nach Ablauf angenommen, mit
/// mindestens einem Veto beginnt die Beratungs- und Abstimmungsphase.
pub fn consent_phase_outcome(veto_count: i64) -> ProposalStatus {
    if veto_count == 0 {
        ProposalStatus::Accepted
    } else {
        ProposalStatus::Voting
    }
}

/// Ergebnis der Abstimmungsphase: kein Quorum; angenommen genau dann, wenn
/// Ja-Stimmen größer als Nein-Stimmen sind. Gleichstand und 0:0 sind
/// abgelehnt. Enthaltungen gehen nicht in die Zählung ein.
pub fn voting_phase_outcome(yes_votes: i64, no_votes: i64) -> ProposalStatus {
    if yes_votes > no_votes {
        ProposalStatus::Accepted
    } else {
        ProposalStatus::Rejected
    }
}

// ---------------------------------------------------------------------------
// Schreibpfade
// ---------------------------------------------------------------------------

const ONE_OPEN_PROPOSAL_INDEX: &str = "governance_proposals_one_open_per_applicant";

fn is_unique_violation(error: &sqlx::Error, constraint: &str) -> bool {
    matches!(
        error.as_database_error().and_then(|db| db.constraint()),
        Some(name) if name == constraint
    )
}

/// Lege einen neuen Weberantrag an. Die Konsentphase beginnt mit `now` und
/// endet nach [`CONSENT_PHASE_DAYS`]. Ein zweiter offener Antrag desselben
/// Accounts wird über den partiellen Unique-Index abgewiesen.
pub async fn create_weber_proposal(
    pool: &PgPool,
    applicant_account_id: &str,
    applicant_title: &str,
    summary: Option<&str>,
    now: DateTime<Utc>,
) -> Result<ProposalWithCounts, CreateProposalError> {
    let id = Uuid::new_v4().to_string();
    let consent_until = now + Duration::days(CONSENT_PHASE_DAYS);

    let mut tx = pool.begin().await.map_err(CreateProposalError::Database)?;
    let applicant_role: Option<String> = sqlx::query_scalar(
        "SELECT role FROM domain_accounts \
         WHERE id = $1 AND disabled = FALSE FOR UPDATE",
    )
    .bind(applicant_account_id)
    .fetch_optional(&mut *tx)
    .await
    .map_err(CreateProposalError::Database)?;
    if applicant_role.as_deref() != Some("gast") {
        return Err(CreateProposalError::NotGuest);
    }

    sqlx::query(
        "INSERT INTO governance_proposals \
             (id, kind, applicant_account_id, applicant_title, summary, status, \
              created_at, consent_until) \
         VALUES ($1::uuid, 'weberantrag', $2, $3, $4, 'consent', $5, $6)",
    )
    .bind(&id)
    .bind(applicant_account_id)
    .bind(applicant_title)
    .bind(summary)
    .bind(now)
    .bind(consent_until)
    .execute(&mut *tx)
    .await
    .map_err(|error| {
        if is_unique_violation(&error, ONE_OPEN_PROPOSAL_INDEX) {
            CreateProposalError::AlreadyOpen
        } else {
            CreateProposalError::Database(error)
        }
    })?;
    tx.commit().await.map_err(CreateProposalError::Database)?;

    Ok(ProposalWithCounts {
        id,
        kind: "weberantrag".to_string(),
        applicant_account_id: applicant_account_id.to_string(),
        applicant_title: applicant_title.to_string(),
        summary: summary.map(str::to_string),
        status: ProposalStatus::Consent,
        created_at: now,
        consent_until,
        voting_until: None,
        finalized_at: None,
        veto_count: 0,
        yes_votes: 0,
        no_votes: 0,
        abstain_votes: 0,
    })
}

/// Sperre den Antrag und liefere `(status, consent_until, voting_until)`.
async fn lock_proposal_phase(
    tx: &mut Transaction<'_, Postgres>,
    proposal_id: &str,
) -> Result<Option<(ProposalStatus, DateTime<Utc>, Option<DateTime<Utc>>)>, sqlx::Error> {
    let row = sqlx::query(
        "SELECT status, consent_until, voting_until \
         FROM governance_proposals WHERE id = $1::uuid FOR UPDATE",
    )
    .bind(proposal_id)
    .fetch_optional(&mut **tx)
    .await?;

    row.map(|row| {
        let status = ProposalStatus::from_db(row.try_get::<String, _>("status")?.as_str())?;
        Ok((
            status,
            row.try_get("consent_until")?,
            row.try_get("voting_until")?,
        ))
    })
    .transpose()
}

/// Lege ein begründetes Veto ein. Zulässig nur während der offenen
/// Konsentphase (`status = 'consent'` und `now < consent_until`).
pub async fn add_veto(
    pool: &PgPool,
    proposal_id: &str,
    weber_account_id: &str,
    weber_title: &str,
    reason: &str,
    now: DateTime<Utc>,
) -> Result<Veto, VetoError> {
    let mut tx = pool.begin().await.map_err(VetoError::Database)?;

    let (status, consent_until, _) = lock_proposal_phase(&mut tx, proposal_id)
        .await
        .map_err(VetoError::Database)?
        .ok_or(VetoError::NotFound)?;
    if status != ProposalStatus::Consent || now >= consent_until {
        return Err(VetoError::WrongPhase);
    }

    sqlx::query(
        "INSERT INTO governance_vetoes \
             (proposal_id, weber_account_id, weber_title, reason, created_at) \
         VALUES ($1::uuid, $2, $3, $4, $5)",
    )
    .bind(proposal_id)
    .bind(weber_account_id)
    .bind(weber_title)
    .bind(reason)
    .bind(now)
    .execute(&mut *tx)
    .await
    .map_err(|error| {
        if is_unique_violation(&error, "governance_vetoes_pkey") {
            VetoError::AlreadyVetoed
        } else {
            VetoError::Database(error)
        }
    })?;

    tx.commit().await.map_err(VetoError::Database)?;

    Ok(Veto {
        weber_account_id: weber_account_id.to_string(),
        weber_title: weber_title.to_string(),
        reason: reason.to_string(),
        created_at: now,
    })
}

/// Setze oder ändere die aktuelle Stimme eines Webers. Zulässig nur während
/// der Beratungs- und Abstimmungsphase (`status = 'voting'`, vor Fristablauf).
pub async fn upsert_vote(
    pool: &PgPool,
    proposal_id: &str,
    voter_account_id: &str,
    choice: VoteChoice,
    now: DateTime<Utc>,
) -> Result<(), VoteError> {
    let mut tx = pool.begin().await.map_err(VoteError::Database)?;

    let (status, _, voting_until) = lock_proposal_phase(&mut tx, proposal_id)
        .await
        .map_err(VoteError::Database)?
        .ok_or(VoteError::NotFound)?;
    let open_voting = status == ProposalStatus::Voting
        && voting_until.is_some_and(|voting_until| now < voting_until);
    if !open_voting {
        return Err(VoteError::WrongPhase);
    }

    sqlx::query(
        "INSERT INTO governance_votes (proposal_id, voter_account_id, choice, updated_at) \
         VALUES ($1::uuid, $2, $3, $4) \
         ON CONFLICT (proposal_id, voter_account_id) \
         DO UPDATE SET choice = EXCLUDED.choice, updated_at = EXCLUDED.updated_at",
    )
    .bind(proposal_id)
    .bind(voter_account_id)
    .bind(choice.as_str())
    .bind(now)
    .execute(&mut *tx)
    .await
    .map_err(VoteError::Database)?;

    tx.commit().await.map_err(VoteError::Database)
}

/// Ergänze einen Gesprächsraum-Beitrag. Zulässig, solange der Antrag offen ist.
pub async fn add_message(
    pool: &PgPool,
    proposal_id: &str,
    author_account_id: &str,
    author_title: &str,
    body: &str,
    now: DateTime<Utc>,
) -> Result<ProposalMessage, MessageError> {
    let mut tx = pool.begin().await.map_err(MessageError::Database)?;

    let (status, consent_until, voting_until) = lock_proposal_phase(&mut tx, proposal_id)
        .await
        .map_err(MessageError::Database)?
        .ok_or(MessageError::NotFound)?;
    let conversation_open = match status {
        ProposalStatus::Consent => now < consent_until,
        ProposalStatus::Voting => voting_until.is_some_and(|until| now < until),
        ProposalStatus::Accepted | ProposalStatus::Rejected => false,
    };
    if !conversation_open {
        return Err(MessageError::WrongPhase);
    }

    let id = Uuid::new_v4().to_string();
    sqlx::query(
        "INSERT INTO governance_messages \
             (id, proposal_id, author_account_id, author_title, body, created_at) \
         VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6)",
    )
    .bind(&id)
    .bind(proposal_id)
    .bind(author_account_id)
    .bind(author_title)
    .bind(body)
    .bind(now)
    .execute(&mut *tx)
    .await
    .map_err(MessageError::Database)?;

    tx.commit().await.map_err(MessageError::Database)?;

    Ok(ProposalMessage {
        id,
        author_account_id: Some(author_account_id.to_string()),
        author_title: author_title.to_string(),
        body: body.to_string(),
        created_at: now,
    })
}

/// Lösche ein Gastkonto aus der kanonischen PostgreSQL-Wahrheit, ohne bereits
/// gemeinschaftlich sichtbare Beiträge oder Knoten zu vernichten.
///
/// - Eigene Weberanträge und ihre abhängigen Verfahrensdaten werden entfernt.
/// - Knoten bleiben bestehen, verlieren aber die aktive Urheberbindung.
/// - Von der gelöschten Garnrolle ausgehende oder zu ihr führende Fäden werden
///   entfernt, weil ihr Account-Endpunkt nicht mehr existiert.
/// - Beiträge in fremden Anträgen behalten Text und Anzeigenamen, verlieren
///   aber die live Account-ID.
/// - Passkeys, Sessions und die Gastidentität werden atomar entfernt.
///
/// Die Rollenbedingung schützt gegen versehentliches Löschen eines Webers oder
/// Administrators.
pub async fn delete_guest_account(pool: &PgPool, account_id: &str) -> Result<(), sqlx::Error> {
    let mut tx = pool.begin().await?;

    // Lock and verify the exact active guest before touching durable traces.
    let role: Option<String> = sqlx::query_scalar(
        "SELECT role FROM domain_accounts WHERE id = $1 AND disabled = FALSE FOR UPDATE",
    )
    .bind(account_id)
    .fetch_optional(&mut *tx)
    .await?;
    if role.as_deref() != Some("gast") {
        return Err(sqlx::Error::RowNotFound);
    }

    sqlx::query(
        "UPDATE domain_nodes \
         SET payload = payload - 'created_by_account_id', updated_at = NOW() \
         WHERE payload ->> 'created_by_account_id' = $1",
    )
    .bind(account_id)
    .execute(&mut *tx)
    .await?;

    sqlx::query(
        "DELETE FROM domain_edges \
         WHERE (source_id = $1 AND payload ->> 'source_type' = 'account') \
            OR (target_id = $1 AND payload ->> 'target_type' = 'account')",
    )
    .bind(account_id)
    .execute(&mut *tx)
    .await?;

    sqlx::query(
        "UPDATE governance_messages SET author_account_id = NULL \
         WHERE author_account_id = $1",
    )
    .bind(account_id)
    .execute(&mut *tx)
    .await?;

    sqlx::query("DELETE FROM governance_proposals WHERE applicant_account_id = $1")
        .bind(account_id)
        .execute(&mut *tx)
        .await?;
    sqlx::query("DELETE FROM passkey_credentials WHERE account_id = $1")
        .bind(account_id)
        .execute(&mut *tx)
        .await?;
    sqlx::query("DELETE FROM sessions WHERE account_id = $1")
        .bind(account_id)
        .execute(&mut *tx)
        .await?;
    let deleted = sqlx::query("DELETE FROM domain_accounts WHERE id = $1 AND role = 'gast'")
        .bind(account_id)
        .execute(&mut *tx)
        .await?;
    if deleted.rows_affected() != 1 {
        return Err(sqlx::Error::RowNotFound);
    }
    tx.commit().await?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Lesepfade
// ---------------------------------------------------------------------------

const PROPOSAL_WITH_COUNTS_SELECT: &str = "SELECT p.id::text AS id, p.kind, \
        p.applicant_account_id, p.applicant_title, p.summary, p.status, \
        p.created_at, p.consent_until, p.voting_until, p.finalized_at, \
        (SELECT count(*) FROM governance_vetoes v \
            WHERE v.proposal_id = p.id) AS veto_count, \
        (SELECT count(*) FROM governance_votes gv \
            WHERE gv.proposal_id = p.id AND gv.choice = 'ja') AS yes_votes, \
        (SELECT count(*) FROM governance_votes gv \
            WHERE gv.proposal_id = p.id AND gv.choice = 'nein') AS no_votes, \
        (SELECT count(*) FROM governance_votes gv \
            WHERE gv.proposal_id = p.id AND gv.choice = 'enthaltung') AS abstain_votes \
     FROM governance_proposals p";

fn proposal_from_row(row: &sqlx::postgres::PgRow) -> Result<ProposalWithCounts, sqlx::Error> {
    Ok(ProposalWithCounts {
        id: row.try_get("id")?,
        kind: row.try_get("kind")?,
        applicant_account_id: row.try_get("applicant_account_id")?,
        applicant_title: row.try_get("applicant_title")?,
        summary: row.try_get("summary")?,
        status: ProposalStatus::from_db(row.try_get::<String, _>("status")?.as_str())?,
        created_at: row.try_get("created_at")?,
        consent_until: row.try_get("consent_until")?,
        voting_until: row.try_get("voting_until")?,
        finalized_at: row.try_get("finalized_at")?,
        veto_count: row.try_get("veto_count")?,
        yes_votes: row.try_get("yes_votes")?,
        no_votes: row.try_get("no_votes")?,
        abstain_votes: row.try_get("abstain_votes")?,
    })
}

/// Alle Anträge, neueste zuerst.
pub async fn list_proposals(pool: &PgPool) -> Result<Vec<ProposalWithCounts>, sqlx::Error> {
    let query = format!("{PROPOSAL_WITH_COUNTS_SELECT} ORDER BY p.created_at DESC, p.id");
    let rows = sqlx::query(&query).fetch_all(pool).await?;
    rows.iter().map(proposal_from_row).collect()
}

/// Ein Antrag mit Zählständen; `None`, wenn er nicht existiert.
pub async fn get_proposal(
    pool: &PgPool,
    proposal_id: &str,
) -> Result<Option<ProposalWithCounts>, sqlx::Error> {
    let query = format!("{PROPOSAL_WITH_COUNTS_SELECT} WHERE p.id = $1::uuid");
    let row = sqlx::query(&query)
        .bind(proposal_id)
        .fetch_optional(pool)
        .await?;
    row.as_ref().map(proposal_from_row).transpose()
}

/// Alle Vetos eines Antrags, älteste zuerst.
pub async fn list_vetoes(pool: &PgPool, proposal_id: &str) -> Result<Vec<Veto>, sqlx::Error> {
    let rows = sqlx::query(
        "SELECT weber_account_id, weber_title, reason, created_at \
         FROM governance_vetoes WHERE proposal_id = $1::uuid \
         ORDER BY created_at, weber_account_id",
    )
    .bind(proposal_id)
    .fetch_all(pool)
    .await?;

    rows.iter()
        .map(|row| {
            Ok(Veto {
                weber_account_id: row.try_get("weber_account_id")?,
                weber_title: row.try_get("weber_title")?,
                reason: row.try_get("reason")?,
                created_at: row.try_get("created_at")?,
            })
        })
        .collect()
}

/// Aktuelle Stimme eines Accounts für einen Antrag, falls vorhanden.
pub async fn get_own_vote(
    pool: &PgPool,
    proposal_id: &str,
    voter_account_id: &str,
) -> Result<Option<String>, sqlx::Error> {
    let row = sqlx::query(
        "SELECT choice FROM governance_votes \
         WHERE proposal_id = $1::uuid AND voter_account_id = $2",
    )
    .bind(proposal_id)
    .bind(voter_account_id)
    .fetch_optional(pool)
    .await?;
    row.map(|row| row.try_get("choice")).transpose()
}

/// Alle Beiträge des Gesprächsraums, älteste zuerst.
pub async fn list_messages(
    pool: &PgPool,
    proposal_id: &str,
) -> Result<Vec<ProposalMessage>, sqlx::Error> {
    let rows = sqlx::query(
        "SELECT id::text AS id, author_account_id, author_title, body, created_at \
         FROM governance_messages WHERE proposal_id = $1::uuid \
         ORDER BY created_at, id",
    )
    .bind(proposal_id)
    .fetch_all(pool)
    .await?;

    rows.iter()
        .map(|row| {
            Ok(ProposalMessage {
                id: row.try_get("id")?,
                author_account_id: row.try_get("author_account_id")?,
                author_title: row.try_get("author_title")?,
                body: row.try_get("body")?,
                created_at: row.try_get("created_at")?,
            })
        })
        .collect()
}

// ---------------------------------------------------------------------------
// Fristauswertung und Aufnahme
// ---------------------------------------------------------------------------

/// Finalisiere alle fälligen Anträge. Serverseitig, idempotent und
/// restart-stabil: jeder Antrag wird in einer eigenen Transaktion unter
/// `FOR UPDATE` erneut geprüft, bevor ein Übergang geschrieben wird. Eine
/// konkurrierende Auswertung sieht nach dem Lock den bereits geschriebenen
/// Zustand und überspringt den Antrag.
pub async fn finalize_due_proposals(
    pool: &PgPool,
    now: DateTime<Utc>,
) -> Result<Vec<FinalizationOutcome>, sqlx::Error> {
    let mut outcomes = Vec::new();
    loop {
        let due_ids: Vec<String> = sqlx::query(
            "SELECT id::text AS id FROM governance_proposals \
             WHERE (status = 'consent' AND consent_until <= $1) \
                OR (status = 'voting' AND voting_until <= $1) \
             ORDER BY created_at, id",
        )
        .bind(now)
        .fetch_all(pool)
        .await?
        .iter()
        .map(|row| row.try_get("id"))
        .collect::<Result<_, _>>()?;
        if due_ids.is_empty() {
            break;
        }
        let mut progressed = false;
        for proposal_id in due_ids {
            if let Some(outcome) = finalize_one(pool, &proposal_id, now).await? {
                progressed = true;
                outcomes.push(outcome);
            }
        }
        if !progressed {
            break;
        }
    }
    Ok(outcomes)
}

/// Finalisiere genau einen Antrag, falls er (noch) fällig ist.
async fn finalize_one(
    pool: &PgPool,
    proposal_id: &str,
    now: DateTime<Utc>,
) -> Result<Option<FinalizationOutcome>, sqlx::Error> {
    let mut tx = pool.begin().await?;

    let Some(row) = sqlx::query(
        "SELECT status, applicant_account_id, consent_until, voting_until \
         FROM governance_proposals WHERE id = $1::uuid FOR UPDATE",
    )
    .bind(proposal_id)
    .fetch_optional(&mut *tx)
    .await?
    else {
        return Ok(None);
    };

    let status = ProposalStatus::from_db(row.try_get::<String, _>("status")?.as_str())?;
    let applicant_account_id: String = row.try_get("applicant_account_id")?;
    let consent_until: DateTime<Utc> = row.try_get("consent_until")?;
    let voting_until: Option<DateTime<Utc>> = row.try_get("voting_until")?;

    let outcome = match status {
        ProposalStatus::Consent if consent_until <= now => {
            let veto_count: i64 = sqlx::query(
                "SELECT count(*) AS n FROM governance_vetoes WHERE proposal_id = $1::uuid",
            )
            .bind(proposal_id)
            .fetch_one(&mut *tx)
            .await?
            .try_get("n")?;

            match consent_phase_outcome(veto_count) {
                ProposalStatus::Accepted => {
                    let promoted =
                        accept_weber_proposal(&mut tx, proposal_id, &applicant_account_id, now)
                            .await?;
                    Some(FinalizationOutcome {
                        proposal_id: proposal_id.to_string(),
                        applicant_account_id,
                        status: ProposalStatus::Accepted,
                        promoted,
                    })
                }
                _ => {
                    // Mit Veto beginnt die Beratungs- und Abstimmungsphase im
                    // Anschluss an die volle Konsentphase.
                    let voting_until = consent_until + Duration::days(VOTING_PHASE_DAYS);
                    sqlx::query(
                        "UPDATE governance_proposals \
                         SET status = 'voting', voting_until = $2 WHERE id = $1::uuid",
                    )
                    .bind(proposal_id)
                    .bind(voting_until)
                    .execute(&mut *tx)
                    .await?;
                    Some(FinalizationOutcome {
                        proposal_id: proposal_id.to_string(),
                        applicant_account_id,
                        status: ProposalStatus::Voting,
                        promoted: false,
                    })
                }
            }
        }
        ProposalStatus::Voting if voting_until.is_some_and(|voting_until| voting_until <= now) => {
            let tally = sqlx::query(
                "SELECT \
                     count(*) FILTER (WHERE choice = 'ja') AS yes_votes, \
                     count(*) FILTER (WHERE choice = 'nein') AS no_votes \
                 FROM governance_votes WHERE proposal_id = $1::uuid",
            )
            .bind(proposal_id)
            .fetch_one(&mut *tx)
            .await?;
            let yes_votes: i64 = tally.try_get("yes_votes")?;
            let no_votes: i64 = tally.try_get("no_votes")?;

            match voting_phase_outcome(yes_votes, no_votes) {
                ProposalStatus::Accepted => {
                    let promoted =
                        accept_weber_proposal(&mut tx, proposal_id, &applicant_account_id, now)
                            .await?;
                    Some(FinalizationOutcome {
                        proposal_id: proposal_id.to_string(),
                        applicant_account_id,
                        status: ProposalStatus::Accepted,
                        promoted,
                    })
                }
                _ => {
                    sqlx::query(
                        "UPDATE governance_proposals \
                         SET status = 'rejected', finalized_at = $2 WHERE id = $1::uuid",
                    )
                    .bind(proposal_id)
                    .bind(now)
                    .execute(&mut *tx)
                    .await?;
                    Some(FinalizationOutcome {
                        proposal_id: proposal_id.to_string(),
                        applicant_account_id,
                        status: ProposalStatus::Rejected,
                        promoted: false,
                    })
                }
            }
        }
        // Bereits finalisiert oder noch nicht fällig: idempotenter No-op.
        _ => None,
    };

    tx.commit().await?;

    if let Some(outcome) = &outcome {
        tracing::info!(
            event = "governance.proposal.finalized",
            proposal_id = %outcome.proposal_id,
            status = outcome.status.as_str(),
            promoted = outcome.promoted,
            "Governance proposal transitioned"
        );
    }

    Ok(outcome)
}

/// Vollziehe die Aufnahme in derselben Transaktion wie den Statuswechsel:
/// Antrag wird `accepted`, und die bereits kanonisch gespeicherte Garnrolle
/// erhält `role = 'weber'`. Profil, Verortung und Identität bleiben unverändert.
/// Fehlt die Gastidentität, bricht die Transaktion fail-closed ab. Replays sind
/// No-ops (Rolle bereits `weber`), Admin-Rollen werden nie herabgestuft.
async fn accept_weber_proposal(
    tx: &mut Transaction<'_, Postgres>,
    proposal_id: &str,
    applicant_account_id: &str,
    now: DateTime<Utc>,
) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE domain_accounts \
         SET role = 'weber', disabled = FALSE, updated_at = $2 \
         WHERE id = $1 AND role = 'gast' AND disabled = FALSE",
    )
    .bind(applicant_account_id)
    .bind(now)
    .execute(&mut **tx)
    .await?;

    if result.rows_affected() == 0 {
        let role: Option<String> = sqlx::query_scalar(
            "SELECT role FROM domain_accounts WHERE id = $1 AND disabled = FALSE",
        )
        .bind(applicant_account_id)
        .fetch_optional(&mut **tx)
        .await?;
        if !matches!(role.as_deref(), Some("weber") | Some("admin")) {
            return Err(sqlx::Error::RowNotFound);
        }
    }

    sqlx::query(
        "UPDATE governance_proposals \
         SET status = 'accepted', finalized_at = $2 WHERE id = $1::uuid",
    )
    .bind(proposal_id)
    .bind(now)
    .execute(&mut **tx)
    .await?;

    Ok(result.rows_affected() > 0)
}

/// Spiegle Beförderungen in den laufenden Account-Store, damit bestehende
/// Sessions die neue Rolle ohne Neuanmeldung erhalten. Der Store ist eine
/// Laufzeitprojektion; die kanonische Wahrheit liegt bereits in PostgreSQL.
pub async fn apply_promotions_to_store(
    accounts: &Arc<RwLock<AccountStore>>,
    outcomes: &[FinalizationOutcome],
) {
    let promoted: Vec<&FinalizationOutcome> = outcomes
        .iter()
        .filter(|outcome| outcome.status == ProposalStatus::Accepted)
        .collect();
    if promoted.is_empty() {
        return;
    }

    let mut store = accounts.write().await;
    for outcome in promoted {
        if let Some(existing) = store.get(&outcome.applicant_account_id) {
            if existing.role == Role::Gast {
                let mut updated = existing.clone();
                updated.role = Role::Weber;
                store.insert(updated);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn consent_without_veto_is_accepted() {
        assert_eq!(consent_phase_outcome(0), ProposalStatus::Accepted);
    }

    #[test]
    fn consent_with_veto_moves_to_voting() {
        assert_eq!(consent_phase_outcome(1), ProposalStatus::Voting);
        assert_eq!(consent_phase_outcome(5), ProposalStatus::Voting);
    }

    #[test]
    fn voting_yes_majority_is_accepted() {
        assert_eq!(voting_phase_outcome(3, 2), ProposalStatus::Accepted);
        assert_eq!(voting_phase_outcome(1, 0), ProposalStatus::Accepted);
    }

    #[test]
    fn voting_tie_is_rejected() {
        assert_eq!(voting_phase_outcome(2, 2), ProposalStatus::Rejected);
    }

    #[test]
    fn voting_zero_zero_is_rejected() {
        assert_eq!(voting_phase_outcome(0, 0), ProposalStatus::Rejected);
    }

    #[test]
    fn voting_no_majority_is_rejected() {
        assert_eq!(voting_phase_outcome(1, 4), ProposalStatus::Rejected);
    }

    #[test]
    fn proposal_status_round_trips_through_db_strings() {
        for status in [
            ProposalStatus::Consent,
            ProposalStatus::Voting,
            ProposalStatus::Accepted,
            ProposalStatus::Rejected,
        ] {
            assert_eq!(
                ProposalStatus::from_db(status.as_str()).expect("known status must parse"),
                status
            );
        }
        assert!(ProposalStatus::from_db("garbage").is_err());
    }

    #[test]
    fn vote_choice_serializes_lowercase() {
        assert_eq!(VoteChoice::Ja.as_str(), "ja");
        assert_eq!(VoteChoice::Nein.as_str(), "nein");
        assert_eq!(VoteChoice::Enthaltung.as_str(), "enthaltung");
        let parsed: VoteChoice = serde_json::from_str("\"enthaltung\"").expect("parse");
        assert_eq!(parsed, VoteChoice::Enthaltung);
    }
}

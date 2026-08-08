//! PostgreSQL-Integrationsbeweis für den Gast-zu-Weber-Prozess.
//!
//! Run with a direct PostgreSQL connection:
//! `DATABASE_URL=postgres://... cargo test --locked --test db_governance -- --include-ignored`

mod support;

use std::{path::PathBuf, str::FromStr};

use chrono::{Duration, TimeZone, Utc};
use serial_test::serial;
use sha2::{Digest, Sha256};
use sqlx::postgres::{PgConnectOptions, PgPoolOptions};
use tokio::time::{sleep, timeout, Duration as TokioDuration};
use weltgewebe_api::governance::{
    add_message, add_veto, create_sach_proposal, create_weber_proposal, delete_guest_account,
    finalize_due_proposals, get_proposal, list_proposals, upsert_vote, CreateProposalError,
    MessageError, ProposalStatus, VetoError, VoteChoice, VoteError, VoteWriteOutcome,
};

const GUEST_A: &str = "gov-proof-guest-a";
const GUEST_B: &str = "gov-proof-guest-b";
const GUEST_C: &str = "gov-proof-guest-c";
const WEBER_A: &str = "gov-proof-weber-a";
const WEBER_B: &str = "gov-proof-weber-b";
const GUEST_NODE: &str = "gov-proof-guest-node";
const GUEST_EDGE: &str = "gov-proof-guest-edge";
const SACH_NODE: &str = "gov-proof-sach-node";
const DETACHED_PROOF_APPLICANT_TITLE: &str = "gov-proof:Gast C";

fn direct_database_url() -> String {
    let url = std::env::var("DATABASE_URL")
        .expect("DATABASE_URL must point to direct PostgreSQL to run db_governance");
    assert!(
        !url.contains(":6432"),
        "do not use PgBouncer for migration tests"
    );
    support::postgres_proof::validated_direct_disposable_url(url)
}

async fn pool() -> sqlx::PgPool {
    let options = PgConnectOptions::from_str(&direct_database_url()).expect("valid DATABASE_URL");
    let pool = PgPoolOptions::new()
        .max_connections(4)
        .connect_with(options)
        .await
        .expect("connect PostgreSQL");
    let migrations_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("migrations");
    let migrator = sqlx::migrate::Migrator::new(migrations_dir)
        .await
        .expect("load migrations");
    migrator.run(&pool).await.expect("run migrations");
    pool
}

async fn cleanup(pool: &sqlx::PgPool) {
    sqlx::query("DELETE FROM domain_edges WHERE id LIKE 'gov-proof-%'")
        .execute(pool)
        .await
        .expect("clean edges");
    sqlx::query("DELETE FROM domain_nodes WHERE id LIKE 'gov-proof-%'")
        .execute(pool)
        .await
        .expect("clean nodes");
    sqlx::query(
        "DELETE FROM governance_proposals \
         WHERE applicant_account_id LIKE 'gov-proof-%' \
            OR (applicant_account_id IS NULL AND applicant_title LIKE 'gov-proof:%')",
    )
    .execute(pool)
    .await
    .expect("clean proposals");
    sqlx::query("DELETE FROM passkey_credentials WHERE account_id LIKE 'gov-proof-%'")
        .execute(pool)
        .await
        .expect("clean passkeys");
    sqlx::query("DELETE FROM sessions WHERE account_id LIKE 'gov-proof-%'")
        .execute(pool)
        .await
        .expect("clean sessions");
    sqlx::query("DELETE FROM domain_accounts WHERE id LIKE 'gov-proof-%'")
        .execute(pool)
        .await
        .expect("clean accounts");
}

fn node_mutation_lock_key(node_id: &str) -> i64 {
    let mut hasher = Sha256::new();
    hasher.update(b"weltgewebe:node-mutation:v1");
    hasher.update((node_id.len() as u64).to_be_bytes());
    hasher.update(node_id.as_bytes());
    let digest = hasher.finalize();
    i64::from_be_bytes(digest[..8].try_into().expect("SHA-256 prefix"))
}

async fn seed_guest_node(pool: &sqlx::PgPool, account_id: &str, node_id: &str) {
    sqlx::query(
        "INSERT INTO domain_nodes \
         (id, kind, title, lat, lon, created_at, updated_at, payload) \
         VALUES ($1, 'Ort', 'Rennknoten', 53.5, 10.0, NOW(), NOW(), \
                 jsonb_build_object('created_by_account_id', $2::text))",
    )
    .bind(node_id)
    .bind(account_id)
    .execute(pool)
    .await
    .expect("seed guest node");
}

async fn seed_account(pool: &sqlx::PgPool, id: &str, role: &str) {
    sqlx::query(
        "INSERT INTO domain_accounts \
         (id, kind, title, map_state, radius_m, disabled, role, public_payload, private_payload) \
         VALUES ($1, 'garnrolle', $2, 'not_on_map', 0, FALSE, $3, '{}', '{}')",
    )
    .bind(id)
    .bind(format!("Account {id}"))
    .bind(role)
    .execute(pool)
    .await
    .expect("seed account");
}

#[tokio::test]
#[serial]
#[ignore = "requires direct PostgreSQL"]
async fn sachantraege_require_weber_allow_multiple_and_accept_without_promotion() {
    let pool = pool().await;
    cleanup(&pool).await;
    seed_account(&pool, GUEST_A, "gast").await;
    seed_account(&pool, WEBER_A, "weber").await;
    seed_guest_node(&pool, WEBER_A, SACH_NODE).await;

    let t0 = Utc.with_ymd_and_hms(2026, 8, 8, 12, 0, 0).unwrap();
    let guest_attempt =
        create_sach_proposal(&pool, GUEST_A, "Gast A", "Nicht zulässig", None, None, t0).await;
    assert!(matches!(
        guest_attempt,
        Err(CreateProposalError::NotSachApplicant)
    ));

    let first = create_sach_proposal(
        &pool,
        WEBER_A,
        "Weber A",
        "Werkstattzeiten beschließen",
        Some("Die Nutzung soll verlässlich werden."),
        Some(SACH_NODE),
        t0,
    )
    .await
    .expect("create first Sachantrag");
    let second = create_sach_proposal(
        &pool,
        WEBER_A,
        "Weber A",
        "Materialbudget beschließen",
        None,
        None,
        t0 + Duration::minutes(1),
    )
    .await
    .expect("multiple open Sachantraege are allowed");
    assert_eq!(first.target_node_id.as_deref(), Some(SACH_NODE));
    assert_eq!(first.target_node_title.as_deref(), Some("Rennknoten"));
    assert_eq!(second.kind, "sachantrag");

    let outcomes = finalize_due_proposals(&pool, t0 + Duration::days(7) + Duration::minutes(1))
        .await
        .expect("finalize Sachantraege");
    assert_eq!(outcomes.len(), 2);
    assert!(outcomes
        .iter()
        .all(|outcome| { outcome.status == ProposalStatus::Accepted && !outcome.promoted }));
    let role: String = sqlx::query_scalar("SELECT role FROM domain_accounts WHERE id = $1")
        .bind(WEBER_A)
        .fetch_one(&pool)
        .await
        .expect("read unchanged role");
    assert_eq!(role, "weber");

    sqlx::query("DELETE FROM domain_nodes WHERE id = $1")
        .bind(SACH_NODE)
        .execute(&pool)
        .await
        .expect("remove target node");
    let after_delete = get_proposal(&pool, &first.id)
        .await
        .expect("read proposal")
        .expect("proposal remains");
    assert_eq!(after_delete.target_node_id, None);
    assert_eq!(
        after_delete.target_node_title.as_deref(),
        Some("Rennknoten")
    );

    cleanup(&pool).await;
}

#[tokio::test]
#[serial]
#[ignore = "requires direct PostgreSQL"]
async fn sachantrag_uses_shared_veto_voting_majority_and_self_decision_guard() {
    let pool = pool().await;
    cleanup(&pool).await;
    seed_account(&pool, WEBER_A, "weber").await;
    seed_account(&pool, WEBER_B, "weber").await;

    let t0 = Utc.with_ymd_and_hms(2026, 8, 8, 12, 0, 0).unwrap();
    let proposal = create_sach_proposal(
        &pool,
        WEBER_A,
        "Weber A",
        "Gemeinschaftsraum öffnen",
        None,
        None,
        t0,
    )
    .await
    .expect("create Sachantrag");

    let own_veto = add_veto(
        &pool,
        &proposal.id,
        WEBER_A,
        "Weber A",
        "Eigener Einwand",
        t0 + Duration::days(1),
    )
    .await;
    assert!(matches!(own_veto, Err(VetoError::ApplicantCannotDecide)));
    add_veto(
        &pool,
        &proposal.id,
        WEBER_B,
        "Weber B",
        "Bitte ausdrücklich abstimmen",
        t0 + Duration::days(1),
    )
    .await
    .expect("foreign veto");
    finalize_due_proposals(&pool, t0 + Duration::days(7))
        .await
        .expect("open voting");

    let own_vote = upsert_vote(
        &pool,
        &proposal.id,
        WEBER_A,
        VoteChoice::Ja,
        t0 + Duration::days(8),
    )
    .await;
    assert!(matches!(own_vote, Err(VoteError::ApplicantCannotDecide)));
    upsert_vote(
        &pool,
        &proposal.id,
        WEBER_B,
        VoteChoice::Ja,
        t0 + Duration::days(8),
    )
    .await
    .expect("foreign yes vote");

    let outcomes = finalize_due_proposals(&pool, t0 + Duration::days(14))
        .await
        .expect("finalize voting");
    assert_eq!(outcomes.len(), 1);
    assert_eq!(outcomes[0].status, ProposalStatus::Accepted);
    assert!(!outcomes[0].promoted);

    cleanup(&pool).await;
}

#[tokio::test]
#[serial]
#[ignore = "requires direct PostgreSQL"]
async fn no_veto_promotes_guest_atomically_and_idempotently() {
    let pool = pool().await;
    cleanup(&pool).await;
    seed_account(&pool, GUEST_A, "gast").await;

    let t0 = Utc.with_ymd_and_hms(2026, 7, 1, 12, 0, 0).unwrap();
    let proposal = create_weber_proposal(&pool, GUEST_A, "Gast A", Some("Hallo"), t0)
        .await
        .expect("create proposal");

    let outcomes = finalize_due_proposals(&pool, t0 + Duration::days(7))
        .await
        .expect("finalize");
    assert_eq!(outcomes.len(), 1);
    assert_eq!(outcomes[0].status, ProposalStatus::Accepted);
    assert!(outcomes[0].promoted);

    let role: String = sqlx::query_scalar("SELECT role FROM domain_accounts WHERE id = $1")
        .bind(GUEST_A)
        .fetch_one(&pool)
        .await
        .expect("read role");
    assert_eq!(role, "weber");
    assert_eq!(
        get_proposal(&pool, &proposal.id)
            .await
            .expect("read proposal")
            .expect("proposal")
            .status,
        ProposalStatus::Accepted
    );

    assert!(finalize_due_proposals(&pool, t0 + Duration::days(30))
        .await
        .expect("repeat finalize")
        .is_empty());
    let rows: i64 = sqlx::query_scalar("SELECT count(*) FROM domain_accounts WHERE id = $1")
        .bind(GUEST_A)
        .fetch_one(&pool)
        .await
        .expect("count account");
    assert_eq!(rows, 1, "promotion must never create a duplicate Garnrolle");

    cleanup(&pool).await;
}

#[tokio::test]
#[serial]
#[ignore = "requires direct PostgreSQL"]
async fn veto_opens_exact_second_phase_and_yes_must_exceed_no() {
    let pool = pool().await;
    cleanup(&pool).await;
    seed_account(&pool, GUEST_A, "gast").await;
    seed_account(&pool, GUEST_B, "gast").await;
    seed_account(&pool, WEBER_A, "weber").await;
    seed_account(&pool, WEBER_B, "weber").await;

    let t0 = Utc.with_ymd_and_hms(2026, 7, 1, 12, 0, 0).unwrap();

    let forbidden = create_weber_proposal(&pool, WEBER_A, "Weber A", None, t0).await;
    assert!(matches!(forbidden, Err(CreateProposalError::NotGuest)));

    let accepted = create_weber_proposal(&pool, GUEST_A, "Gast A", None, t0)
        .await
        .expect("create accepted candidate");
    let own_veto = add_veto(
        &pool,
        &accepted.id,
        GUEST_A,
        "Gast A",
        "Eigene Aufnahme blockieren",
        t0 + Duration::days(1),
    )
    .await;
    assert!(matches!(own_veto, Err(VetoError::ActorNotEligible)));

    let guest_veto = add_veto(
        &pool,
        &accepted.id,
        GUEST_B,
        "Gast B",
        "Bitte zuerst beraten",
        t0 + Duration::days(1),
    )
    .await;
    assert!(matches!(guest_veto, Err(VetoError::ActorNotEligible)));

    add_veto(
        &pool,
        &accepted.id,
        WEBER_A,
        "Weber A",
        "Bitte zuerst beraten",
        t0 + Duration::days(1),
    )
    .await
    .expect("Weber veto on guest application");

    let duplicate_veto = add_veto(
        &pool,
        &accepted.id,
        WEBER_A,
        "Weber A",
        "Zweites Veto darf nicht als Datenbankfehler erscheinen",
        t0 + Duration::days(2),
    )
    .await;
    assert!(matches!(duplicate_veto, Err(VetoError::AlreadyVetoed)));

    let first_phase = finalize_due_proposals(&pool, t0 + Duration::days(7))
        .await
        .expect("open voting");
    assert_eq!(first_phase[0].status, ProposalStatus::Voting);
    let voting_proposal = get_proposal(&pool, &accepted.id)
        .await
        .expect("read voting proposal")
        .expect("voting proposal");
    assert_eq!(voting_proposal.voting_until, Some(t0 + Duration::days(14)));

    let own_vote = upsert_vote(
        &pool,
        &accepted.id,
        GUEST_A,
        VoteChoice::Ja,
        t0 + Duration::days(8),
    )
    .await;
    assert!(matches!(own_vote, Err(VoteError::ActorNotEligible)));

    let guest_vote = upsert_vote(
        &pool,
        &accepted.id,
        GUEST_B,
        VoteChoice::Nein,
        t0 + Duration::days(8),
    )
    .await;
    assert!(matches!(guest_vote, Err(VoteError::ActorNotEligible)));

    let initial_vote = upsert_vote(
        &pool,
        &accepted.id,
        WEBER_B,
        VoteChoice::Nein,
        t0 + Duration::days(8),
    )
    .await
    .expect("initial Weber vote");
    assert_eq!(initial_vote, VoteWriteOutcome::Created);

    let repeated_vote = upsert_vote(
        &pool,
        &accepted.id,
        WEBER_B,
        VoteChoice::Nein,
        t0 + Duration::days(9),
    )
    .await
    .expect("identical Weber vote replay");
    assert_eq!(repeated_vote, VoteWriteOutcome::Unchanged);
    let unchanged_updated_at: chrono::DateTime<Utc> = sqlx::query_scalar(
        "SELECT updated_at FROM governance_votes \
         WHERE proposal_id = $1::uuid AND voter_account_id = $2",
    )
    .bind(&accepted.id)
    .bind(WEBER_B)
    .fetch_one(&pool)
    .await
    .expect("read unchanged vote timestamp");
    assert_eq!(unchanged_updated_at, t0 + Duration::days(8));

    let changed_vote = upsert_vote(
        &pool,
        &accepted.id,
        WEBER_B,
        VoteChoice::Ja,
        t0 + Duration::days(10),
    )
    .await
    .expect("changed Weber vote");
    assert_eq!(changed_vote, VoteWriteOutcome::Changed);
    let result = finalize_due_proposals(&pool, t0 + Duration::days(14))
        .await
        .expect("final vote");
    assert_eq!(result[0].status, ProposalStatus::Accepted);

    let tied = create_weber_proposal(&pool, GUEST_B, "Gast B", None, t0)
        .await
        .expect("create tied candidate");
    add_veto(
        &pool,
        &tied.id,
        WEBER_A,
        "Weber A",
        "Abstimmung nötig",
        t0 + Duration::days(1),
    )
    .await
    .expect("veto tied");
    finalize_due_proposals(&pool, t0 + Duration::days(7))
        .await
        .expect("open tied voting");
    upsert_vote(
        &pool,
        &tied.id,
        WEBER_A,
        VoteChoice::Ja,
        t0 + Duration::days(8),
    )
    .await
    .expect("yes");
    upsert_vote(
        &pool,
        &tied.id,
        WEBER_B,
        VoteChoice::Nein,
        t0 + Duration::days(8),
    )
    .await
    .expect("no");
    let tied_result = finalize_due_proposals(&pool, t0 + Duration::days(14))
        .await
        .expect("finalize tied");
    assert_eq!(tied_result[0].status, ProposalStatus::Rejected);

    cleanup(&pool).await;
}

#[tokio::test]
#[serial]
#[ignore = "requires direct PostgreSQL"]
async fn concurrent_first_vote_for_same_account_is_serialized() {
    let pool = pool().await;
    cleanup(&pool).await;
    seed_account(&pool, GUEST_A, "gast").await;
    seed_account(&pool, WEBER_A, "weber").await;
    seed_account(&pool, WEBER_B, "weber").await;

    let t0 = Utc.with_ymd_and_hms(2026, 7, 1, 12, 0, 0).unwrap();
    let proposal = create_weber_proposal(&pool, GUEST_A, "Gast A", None, t0)
        .await
        .expect("create candidate");
    add_veto(
        &pool,
        &proposal.id,
        WEBER_A,
        "Weber A",
        "Abstimmung nötig",
        t0 + Duration::days(1),
    )
    .await
    .expect("open second phase");
    finalize_due_proposals(&pool, t0 + Duration::days(7))
        .await
        .expect("open voting");

    let first_pool = pool.clone();
    let second_pool = pool.clone();
    let first_proposal_id = proposal.id.clone();
    let second_proposal_id = proposal.id.clone();
    let first = upsert_vote(
        &first_pool,
        &first_proposal_id,
        WEBER_B,
        VoteChoice::Nein,
        t0 + Duration::days(8),
    );
    let second = upsert_vote(
        &second_pool,
        &second_proposal_id,
        WEBER_B,
        VoteChoice::Nein,
        t0 + Duration::days(9),
    );
    let (first, second) = tokio::join!(first, second);
    let first = first.expect("first concurrent vote");
    let second = second.expect("second concurrent vote");
    assert!(matches!(
        (first, second),
        (VoteWriteOutcome::Created, VoteWriteOutcome::Unchanged)
            | (VoteWriteOutcome::Unchanged, VoteWriteOutcome::Created)
    ));

    let row_count: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM governance_votes \
         WHERE proposal_id = $1::uuid AND voter_account_id = $2",
    )
    .bind(&proposal.id)
    .bind(WEBER_B)
    .fetch_one(&pool)
    .await
    .expect("count concurrent vote rows");
    assert_eq!(row_count, 1);

    let stored_choice: String = sqlx::query_scalar(
        "SELECT choice FROM governance_votes \
         WHERE proposal_id = $1::uuid AND voter_account_id = $2",
    )
    .bind(&proposal.id)
    .bind(WEBER_B)
    .fetch_one(&pool)
    .await
    .expect("read concurrent vote");
    assert_eq!(stored_choice, "nein");

    cleanup(&pool).await;
}

#[tokio::test]
#[serial]
#[ignore = "requires direct PostgreSQL"]
async fn zero_to_zero_is_rejected_and_guest_exit_removes_identity() {
    let pool = pool().await;
    cleanup(&pool).await;
    seed_account(&pool, GUEST_C, "gast").await;
    seed_account(&pool, WEBER_A, "weber").await;

    let t0 = Utc.with_ymd_and_hms(2026, 7, 1, 12, 0, 0).unwrap();
    let proposal = create_weber_proposal(&pool, GUEST_C, DETACHED_PROOF_APPLICANT_TITLE, None, t0)
        .await
        .expect("create proposal");
    add_veto(
        &pool,
        &proposal.id,
        WEBER_A,
        "Weber A",
        "Abstimmung ohne Beteiligung",
        t0 + Duration::days(1),
    )
    .await
    .expect("veto");
    let late_message = add_message(
        &pool,
        &proposal.id,
        WEBER_A,
        "Weber A",
        "Zu spät",
        t0 + Duration::days(7),
    )
    .await;
    assert!(matches!(late_message, Err(MessageError::WrongPhase)));

    let outcomes = finalize_due_proposals(&pool, t0 + Duration::days(14))
        .await
        .expect("late sweep covers both phases");
    assert_eq!(
        outcomes.last().expect("final outcome").status,
        ProposalStatus::Rejected
    );

    let second = create_weber_proposal(
        &pool,
        GUEST_C,
        "Gast C",
        Some("späterer Antrag"),
        t0 + Duration::days(15),
    )
    .await
    .expect("new proposal after rejection");

    seed_account(&pool, GUEST_B, "gast").await;
    let foreign_proposal = create_weber_proposal(
        &pool,
        GUEST_B,
        "Gast B",
        Some("fremder Antrag"),
        t0 + Duration::days(15),
    )
    .await
    .expect("create foreign proposal");
    let retained_message = add_message(
        &pool,
        &foreign_proposal.id,
        GUEST_C,
        "Gast C",
        "Dieser Beitrag bleibt erhalten.",
        t0 + Duration::days(16),
    )
    .await
    .expect("guest contribution to foreign proposal");

    let listed = list_proposals(&pool)
        .await
        .expect("list proposal projections");
    let foreign_projection = listed
        .iter()
        .find(|candidate| candidate.id == foreign_proposal.id)
        .expect("foreign proposal in list");
    assert_eq!(foreign_projection.message_count, 1);
    let empty_projection = listed
        .iter()
        .find(|candidate| candidate.id == second.id)
        .expect("empty proposal in list");
    assert_eq!(empty_projection.message_count, 0);

    sqlx::query(
        "INSERT INTO domain_nodes \
         (id, kind, title, lat, lon, created_at, updated_at, payload) \
         VALUES ($1, 'Ort', 'Gastknoten', 53.5, 10.0, $2, $2, \
                 jsonb_build_object('created_by_account_id', $3::text))",
    )
    .bind(GUEST_NODE)
    .bind(t0)
    .bind(GUEST_C)
    .execute(&pool)
    .await
    .expect("seed guest node");
    sqlx::query(
        "INSERT INTO domain_edges \
         (id, source_id, target_id, edge_kind, created_at, payload) \
         VALUES ($1, $2, $3, 'reference', $4, \
                 jsonb_build_object('source_type', 'account', 'target_type', 'node'))",
    )
    .bind(GUEST_EDGE)
    .bind(GUEST_C)
    .bind(GUEST_NODE)
    .bind(t0)
    .execute(&pool)
    .await
    .expect("seed guest edge");

    delete_guest_account(&pool, GUEST_C)
        .await
        .expect("delete guest");

    let listed_after_exit = list_proposals(&pool)
        .await
        .expect("list proposal projections after guest exit");
    let retained_projection = listed_after_exit
        .iter()
        .find(|candidate| candidate.id == foreign_proposal.id)
        .expect("foreign proposal remains in list after guest exit");
    assert_eq!(retained_projection.message_count, 1);

    let account_exists: bool =
        sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM domain_accounts WHERE id = $1)")
            .bind(GUEST_C)
            .fetch_one(&pool)
            .await
            .expect("account existence");
    let proposal_exists: bool =
        sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM governance_proposals WHERE id = $1::uuid)")
            .bind(second.id)
            .fetch_one(&pool)
            .await
            .expect("proposal existence");
    let retained_procedure: (Option<String>, String, String, bool) = sqlx::query_as(
        "SELECT applicant_account_id, applicant_title, status, finalized_at IS NOT NULL
         FROM governance_proposals WHERE id = $1::uuid",
    )
    .bind(&proposal.id)
    .fetch_one(&pool)
    .await
    .expect("retained procedural history");
    let node_creator: Option<String> = sqlx::query_scalar(
        "SELECT payload ->> 'created_by_account_id' FROM domain_nodes WHERE id = $1",
    )
    .bind(GUEST_NODE)
    .fetch_one(&pool)
    .await
    .expect("retained node creator");
    let edge_exists: bool =
        sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM domain_edges WHERE id = $1)")
            .bind(GUEST_EDGE)
            .fetch_one(&pool)
            .await
            .expect("edge existence");
    let retained_author: Option<String> =
        sqlx::query_scalar("SELECT author_account_id FROM governance_messages WHERE id = $1::uuid")
            .bind(&retained_message.id)
            .fetch_one(&pool)
            .await
            .expect("retained message author");
    let retained_body: String =
        sqlx::query_scalar("SELECT body FROM governance_messages WHERE id = $1::uuid")
            .bind(&retained_message.id)
            .fetch_one(&pool)
            .await
            .expect("retained message body");
    assert!(!account_exists);
    assert!(!proposal_exists, "empty own proposal still disappears");
    assert_eq!(
        retained_procedure.0, None,
        "procedural history loses only the live applicant binding"
    );
    assert_eq!(
        retained_procedure.1, DETACHED_PROOF_APPLICANT_TITLE,
        "applicant title snapshot survives"
    );
    assert_eq!(
        retained_procedure.2, "rejected",
        "an open applicant-less procedure cannot continue"
    );
    assert!(retained_procedure.3, "detached procedure is final");
    assert_eq!(node_creator, None, "retained node must be anonymized");
    assert!(!edge_exists, "account-bound Faden must be removed");
    assert_eq!(
        retained_author, None,
        "foreign contribution must be anonymized"
    );
    assert_eq!(retained_body, "Dieser Beitrag bleibt erhalten.");

    cleanup(&pool).await;
}

#[tokio::test]
#[serial]
#[ignore = "requires direct PostgreSQL"]
async fn guest_exit_bulk_locks_and_anonymizes_many_owned_nodes() {
    const ACCOUNT: &str = "gov-proof-bulk-exit";

    let pool = pool().await;
    cleanup(&pool).await;
    seed_account(&pool, ACCOUNT, "gast").await;
    sqlx::query(
        "INSERT INTO domain_nodes \
         (id, kind, title, lat, lon, created_at, updated_at, payload) \
         SELECT 'gov-proof-bulk-node-' || series::text, 'Ort', 'Bulk-Knoten', \
                53.5, 10.0, NOW(), NOW(), \
                jsonb_build_object('created_by_account_id', $1::text) \
         FROM generate_series(1, 64) AS series",
    )
    .bind(ACCOUNT)
    .execute(&pool)
    .await
    .expect("seed many guest nodes");

    delete_guest_account(&pool, ACCOUNT)
        .await
        .expect("bulk guest exit");

    let retained: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM domain_nodes WHERE id LIKE 'gov-proof-bulk-node-%'",
    )
    .fetch_one(&pool)
    .await
    .expect("count retained bulk nodes");
    let still_owned: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM domain_nodes \
         WHERE id LIKE 'gov-proof-bulk-node-%' \
           AND payload ->> 'created_by_account_id' = $1",
    )
    .bind(ACCOUNT)
    .fetch_one(&pool)
    .await
    .expect("count residual bulk ownership");
    assert_eq!(retained, 64, "exit retains community-visible nodes");
    assert_eq!(still_owned, 0, "every retained node must be anonymized");

    cleanup(&pool).await;
}

#[tokio::test]
#[serial]
#[ignore = "requires direct PostgreSQL"]
async fn guest_exit_waits_for_an_inflight_owned_node_mutation() {
    const ACCOUNT: &str = "gov-proof-race-mutation-first";
    const NODE: &str = "gov-proof-race-node-mutation-first";

    let pool = pool().await;
    cleanup(&pool).await;
    seed_account(&pool, ACCOUNT, "gast").await;
    seed_guest_node(&pool, ACCOUNT, NODE).await;

    let mut mutation = pool.begin().await.expect("begin mutation");
    sqlx::query("SELECT pg_advisory_xact_lock($1::bigint)")
        .bind(node_mutation_lock_key(NODE))
        .execute(&mut *mutation)
        .await
        .expect("lock node mutation");

    let exit_pool = pool.clone();
    let exit = tokio::spawn(async move { delete_guest_account(&exit_pool, ACCOUNT).await });
    sleep(TokioDuration::from_millis(150)).await;
    assert!(
        !exit.is_finished(),
        "exit must wait for the active node mutation"
    );

    sqlx::query("UPDATE domain_nodes SET title = 'Bearbeitung gewinnt' WHERE id = $1")
        .bind(NODE)
        .execute(&mut *mutation)
        .await
        .expect("finish node mutation");
    mutation.commit().await.expect("commit node mutation");

    timeout(TokioDuration::from_secs(5), exit)
        .await
        .expect("exit completes after mutation lock release")
        .expect("exit task")
        .expect("delete guest");

    let row: (String, Option<String>) = sqlx::query_as(
        "SELECT title, payload ->> 'created_by_account_id' FROM domain_nodes WHERE id = $1",
    )
    .bind(NODE)
    .fetch_one(&pool)
    .await
    .expect("read retained node");
    assert_eq!(row.0, "Bearbeitung gewinnt");
    assert_eq!(row.1, None, "exit anonymizes after the mutation commits");

    cleanup(&pool).await;
}

#[tokio::test]
#[serial]
#[ignore = "requires direct PostgreSQL"]
async fn owned_node_mutation_waits_for_guest_exit_and_then_loses_ownership() {
    const ACCOUNT: &str = "gov-proof-race-exit-first";
    const NODE: &str = "gov-proof-race-node-exit-first";
    const EDGE: &str = "gov-proof-race-edge-exit-first";

    let pool = pool().await;
    cleanup(&pool).await;
    seed_account(&pool, ACCOUNT, "gast").await;
    seed_guest_node(&pool, ACCOUNT, NODE).await;
    sqlx::query(
        "INSERT INTO domain_edges (id, source_id, target_id, edge_kind, created_at, payload) \
         VALUES ($1, $2, $3, 'reference', NOW(), \
                 jsonb_build_object('source_type', 'account', 'target_type', 'node'))",
    )
    .bind(EDGE)
    .bind(ACCOUNT)
    .bind(NODE)
    .execute(&pool)
    .await
    .expect("seed blocking edge");

    let mut edge_blocker = pool.begin().await.expect("begin edge blocker");
    sqlx::query("SELECT id FROM domain_edges WHERE id = $1 FOR UPDATE")
        .bind(EDGE)
        .execute(&mut *edge_blocker)
        .await
        .expect("lock edge so exit remains open");

    let exit_pool = pool.clone();
    let exit = tokio::spawn(async move { delete_guest_account(&exit_pool, ACCOUNT).await });

    let key = node_mutation_lock_key(NODE);
    timeout(TokioDuration::from_secs(5), async {
        loop {
            let mut probe = pool.begin().await.expect("begin advisory probe");
            let acquired: bool = sqlx::query_scalar("SELECT pg_try_advisory_xact_lock($1::bigint)")
                .bind(key)
                .fetch_one(&mut *probe)
                .await
                .expect("probe node lock");
            probe.rollback().await.expect("rollback advisory probe");
            if !acquired {
                break;
            }
            sleep(TokioDuration::from_millis(25)).await;
        }
    })
    .await
    .expect("exit acquires node lock before edge deletion");

    let mutation_pool = pool.clone();
    let mutation = tokio::spawn(async move {
        let mut tx = mutation_pool.begin().await.expect("begin late mutation");
        sqlx::query("SELECT pg_advisory_xact_lock($1::bigint)")
            .bind(key)
            .execute(&mut *tx)
            .await
            .expect("wait for node lock");
        let affected = sqlx::query(
            "UPDATE domain_nodes SET title = 'Darf nicht gewinnen' \
             WHERE id = $1 AND payload ->> 'created_by_account_id' = $2",
        )
        .bind(NODE)
        .bind(ACCOUNT)
        .execute(&mut *tx)
        .await
        .expect("attempt ownership-bound mutation")
        .rows_affected();
        tx.commit().await.expect("commit late mutation");
        affected
    });
    sleep(TokioDuration::from_millis(150)).await;
    assert!(
        !mutation.is_finished(),
        "late mutation must wait for guest exit"
    );

    edge_blocker.commit().await.expect("release exit blocker");
    timeout(TokioDuration::from_secs(5), exit)
        .await
        .expect("exit completes")
        .expect("exit task")
        .expect("delete guest");
    let affected = timeout(TokioDuration::from_secs(5), mutation)
        .await
        .expect("late mutation completes")
        .expect("mutation task");
    assert_eq!(
        affected, 0,
        "post-exit ownership check must reject mutation"
    );

    let row: (String, Option<String>) = sqlx::query_as(
        "SELECT title, payload ->> 'created_by_account_id' FROM domain_nodes WHERE id = $1",
    )
    .bind(NODE)
    .fetch_one(&pool)
    .await
    .expect("read retained node");
    assert_eq!(row.0, "Rennknoten");
    assert_eq!(row.1, None);

    cleanup(&pool).await;
}

#[tokio::test]
#[serial]
#[ignore = "requires direct PostgreSQL"]
async fn finalization_locks_account_before_proposal() {
    const ACCOUNT: &str = "gov-proof-lock-order";

    let pool = pool().await;
    cleanup(&pool).await;
    seed_account(&pool, ACCOUNT, "gast").await;
    let t0 = Utc.with_ymd_and_hms(2026, 7, 1, 12, 0, 0).unwrap();
    let proposal = create_weber_proposal(&pool, ACCOUNT, "Lock Order", None, t0)
        .await
        .expect("create proposal");

    let mut account_blocker = pool.begin().await.expect("begin account blocker");
    sqlx::query("SELECT id FROM domain_accounts WHERE id = $1 FOR UPDATE")
        .bind(ACCOUNT)
        .execute(&mut *account_blocker)
        .await
        .expect("lock account");

    let finalizer_pool = pool.clone();
    let finalizer = tokio::spawn(async move {
        finalize_due_proposals(&finalizer_pool, t0 + Duration::days(7)).await
    });
    sleep(TokioDuration::from_millis(150)).await;
    assert!(
        !finalizer.is_finished(),
        "finalizer must wait for account lock"
    );

    let mut proposal_probe = pool.begin().await.expect("begin proposal probe");
    sqlx::query("SELECT id FROM governance_proposals WHERE id = $1::uuid FOR UPDATE NOWAIT")
        .bind(&proposal.id)
        .execute(&mut *proposal_probe)
        .await
        .expect("proposal must remain unlocked while account is blocked");
    proposal_probe
        .rollback()
        .await
        .expect("rollback proposal probe");

    account_blocker
        .commit()
        .await
        .expect("release account lock");
    let outcomes = timeout(TokioDuration::from_secs(5), finalizer)
        .await
        .expect("finalizer completes")
        .expect("finalizer task")
        .expect("finalize proposal");
    assert_eq!(outcomes.len(), 1);
    assert_eq!(outcomes[0].status, ProposalStatus::Accepted);

    cleanup(&pool).await;
}

#[tokio::test]
#[serial]
#[ignore = "requires direct PostgreSQL"]
async fn guest_exit_removes_untyped_legacy_account_edges_when_unambiguous() {
    const ACCOUNT: &str = "gov-proof-legacy-untyped-edge";
    const EDGE: &str = "gov-proof-legacy-untyped-edge-id";

    let pool = pool().await;
    cleanup(&pool).await;
    seed_account(&pool, ACCOUNT, "gast").await;
    sqlx::query(
        "INSERT INTO domain_edges (id, source_id, target_id, edge_kind, created_at, payload) \
         VALUES ($1, $2, 'legacy-target', 'reference', NOW(), '{}'::jsonb)",
    )
    .bind(EDGE)
    .bind(ACCOUNT)
    .execute(&pool)
    .await
    .expect("seed untyped legacy edge");

    delete_guest_account(&pool, ACCOUNT)
        .await
        .expect("unambiguous legacy account edge must be removable");
    let edge_exists: bool =
        sqlx::query_scalar("SELECT EXISTS (SELECT 1 FROM domain_edges WHERE id = $1)")
            .bind(EDGE)
            .fetch_one(&pool)
            .await
            .expect("check legacy edge");
    assert!(!edge_exists);

    cleanup(&pool).await;
}

#[tokio::test]
#[serial]
#[ignore = "requires direct PostgreSQL"]
async fn guest_exit_fails_closed_for_ambiguous_untyped_legacy_endpoint() {
    const ACCOUNT: &str = "gov-proof-legacy-ambiguous";
    const EDGE: &str = "gov-proof-legacy-ambiguous-edge";

    let pool = pool().await;
    cleanup(&pool).await;
    seed_account(&pool, ACCOUNT, "gast").await;
    seed_guest_node(&pool, "different-creator", ACCOUNT).await;
    sqlx::query(
        "INSERT INTO domain_edges (id, source_id, target_id, edge_kind, created_at, payload) \
         VALUES ($1, $2, 'legacy-target', 'reference', NOW(), '{}'::jsonb)",
    )
    .bind(EDGE)
    .bind(ACCOUNT)
    .execute(&pool)
    .await
    .expect("seed ambiguous untyped edge");

    let error = delete_guest_account(&pool, ACCOUNT)
        .await
        .expect_err("ambiguous endpoint must fail closed");
    assert!(error
        .to_string()
        .contains("cannot classify an untyped legacy edge endpoint"));

    let account_exists: bool =
        sqlx::query_scalar("SELECT EXISTS (SELECT 1 FROM domain_accounts WHERE id = $1)")
            .bind(ACCOUNT)
            .fetch_one(&pool)
            .await
            .expect("check rollback account");
    let edge_exists: bool =
        sqlx::query_scalar("SELECT EXISTS (SELECT 1 FROM domain_edges WHERE id = $1)")
            .bind(EDGE)
            .fetch_one(&pool)
            .await
            .expect("check rollback edge");
    assert!(
        account_exists,
        "failed exit must roll back account deletion"
    );
    assert!(
        edge_exists,
        "failed exit must leave ambiguous edge untouched"
    );

    cleanup(&pool).await;
}

#[tokio::test]
#[serial]
#[ignore = "requires direct PostgreSQL"]
async fn proposal_message_locks_author_account_before_proposal() {
    const AUTHOR: &str = "gov-proof-message-lock-author";
    const APPLICANT: &str = "gov-proof-message-lock-applicant";

    let pool = pool().await;
    cleanup(&pool).await;
    seed_account(&pool, AUTHOR, "gast").await;
    seed_account(&pool, APPLICANT, "gast").await;
    let t0 = Utc.with_ymd_and_hms(2026, 7, 1, 12, 0, 0).unwrap();
    let proposal = create_weber_proposal(&pool, APPLICANT, "Applicant", None, t0)
        .await
        .expect("create proposal");

    let mut account_blocker = pool.begin().await.expect("begin author blocker");
    sqlx::query("SELECT id FROM domain_accounts WHERE id = $1 FOR UPDATE")
        .bind(AUTHOR)
        .execute(&mut *account_blocker)
        .await
        .expect("lock author account");

    let message_pool = pool.clone();
    let proposal_id = proposal.id.clone();
    let writer = tokio::spawn(async move {
        add_message(
            &message_pool,
            &proposal_id,
            AUTHOR,
            "Author",
            "Lock-order proof",
            t0 + Duration::days(1),
        )
        .await
    });
    sleep(TokioDuration::from_millis(150)).await;
    assert!(
        !writer.is_finished(),
        "message writer must wait for author account lock"
    );

    let mut proposal_probe = pool.begin().await.expect("begin proposal probe");
    sqlx::query("SELECT id FROM governance_proposals WHERE id = $1::uuid FOR UPDATE NOWAIT")
        .bind(&proposal.id)
        .execute(&mut *proposal_probe)
        .await
        .expect("proposal must remain unlocked while author account is blocked");
    proposal_probe
        .rollback()
        .await
        .expect("rollback proposal probe");

    account_blocker
        .commit()
        .await
        .expect("release author account");
    timeout(TokioDuration::from_secs(5), writer)
        .await
        .expect("message writer completes")
        .expect("message task")
        .expect("message write");

    cleanup(&pool).await;
}

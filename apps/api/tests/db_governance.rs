//! PostgreSQL-Integrationsbeweis für den Gast-zu-Weber-Prozess.
//!
//! Run with a direct PostgreSQL connection:
//! `DATABASE_URL=postgres://... cargo test --locked --test db_governance -- --include-ignored`

use std::{path::PathBuf, str::FromStr};

use chrono::{Duration, TimeZone, Utc};
use serial_test::serial;
use sqlx::postgres::{PgConnectOptions, PgPoolOptions};
use weltgewebe_api::governance::{
    add_message, add_veto, create_weber_proposal, delete_guest_account, finalize_due_proposals,
    get_proposal, upsert_vote, CreateProposalError, MessageError, ProposalStatus, VoteChoice,
};

const GUEST_A: &str = "gov-proof-guest-a";
const GUEST_B: &str = "gov-proof-guest-b";
const GUEST_C: &str = "gov-proof-guest-c";
const WEBER_A: &str = "gov-proof-weber-a";
const WEBER_B: &str = "gov-proof-weber-b";

fn direct_database_url() -> String {
    let url = std::env::var("DATABASE_URL")
        .expect("DATABASE_URL must point to direct PostgreSQL to run db_governance");
    assert!(
        !url.contains(":6432"),
        "do not use PgBouncer for migration tests"
    );
    url
}

async fn pool() -> sqlx::PgPool {
    let options = PgConnectOptions::from_str(&direct_database_url()).expect("valid DATABASE_URL");
    let pool = PgPoolOptions::new()
        .max_connections(2)
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
    sqlx::query("DELETE FROM governance_proposals WHERE applicant_account_id LIKE 'gov-proof-%'")
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

async fn seed_account(pool: &sqlx::PgPool, id: &str, role: &str) {
    sqlx::query(
        "INSERT INTO domain_accounts \
         (id, kind, title, mode, map_state, radius_m, disabled, role, public_payload, private_payload) \
         VALUES ($1, 'garnrolle', $2, 'ron', 'not_on_map', 0, FALSE, $3, '{}', '{}')",
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
    add_veto(
        &pool,
        &accepted.id,
        WEBER_A,
        "Weber A",
        "Bitte zuerst beraten",
        t0 + Duration::days(1),
    )
    .await
    .expect("veto");
    let first_phase = finalize_due_proposals(&pool, t0 + Duration::days(7))
        .await
        .expect("open voting");
    assert_eq!(first_phase[0].status, ProposalStatus::Voting);
    let voting_proposal = get_proposal(&pool, &accepted.id)
        .await
        .expect("read voting proposal")
        .expect("voting proposal");
    assert_eq!(voting_proposal.voting_until, Some(t0 + Duration::days(14)));

    upsert_vote(
        &pool,
        &accepted.id,
        WEBER_A,
        VoteChoice::Nein,
        t0 + Duration::days(8),
    )
    .await
    .expect("initial vote");
    upsert_vote(
        &pool,
        &accepted.id,
        WEBER_A,
        VoteChoice::Ja,
        t0 + Duration::days(9),
    )
    .await
    .expect("changed vote");
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
async fn zero_to_zero_is_rejected_and_guest_exit_removes_identity() {
    let pool = pool().await;
    cleanup(&pool).await;
    seed_account(&pool, GUEST_C, "gast").await;
    seed_account(&pool, WEBER_A, "weber").await;

    let t0 = Utc.with_ymd_and_hms(2026, 7, 1, 12, 0, 0).unwrap();
    let proposal = create_weber_proposal(&pool, GUEST_C, "Gast C", None, t0)
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
    delete_guest_account(&pool, GUEST_C)
        .await
        .expect("delete guest");

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
    assert!(!account_exists);
    assert!(!proposal_exists);

    cleanup(&pool).await;
}

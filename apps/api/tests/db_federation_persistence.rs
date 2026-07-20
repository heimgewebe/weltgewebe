use std::{collections::HashSet, env, sync::Arc};

use anyhow::{Context, Result};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use chrono::{DateTime, Utc};
use ed25519_dalek::{Signer, SigningKey};
use serde::Serialize;
use serde_json::{json, Value};
use sqlx::postgres::PgPoolOptions;
use uuid::Uuid;
use weltgewebe_api::federation::{
    CellIdentity, FederationEvent, FederationService, MemoryFederationRepository, PeerPolicy,
    PostgresFederationRepository, PublishRequest, ReceiveStatus,
};

#[derive(Serialize)]
struct SigningPayload<'a> {
    protocol_version: &'a str,
    schema_version: u16,
    event_id: Uuid,
    event_type: &'a str,
    origin_cell_id: &'a str,
    actor: &'a str,
    object_address: &'a str,
    object_kind: &'a str,
    object_version: i64,
    previous_version: Option<i64>,
    created_at: DateTime<Utc>,
    scope: &'a str,
    neighbourhood_targets: &'a [String],
    payload: &'a Value,
    key_id: &'a str,
}

fn resign(event: &mut FederationEvent, seed: u8) -> Result<()> {
    let bytes = serde_jcs::to_vec(&SigningPayload {
        protocol_version: &event.protocol_version,
        schema_version: event.schema_version,
        event_id: event.event_id,
        event_type: &event.event_type,
        origin_cell_id: &event.origin_cell_id,
        actor: &event.actor,
        object_address: &event.object_address,
        object_kind: &event.object_kind,
        object_version: event.object_version,
        previous_version: event.previous_version,
        created_at: event.created_at,
        scope: &event.scope,
        neighbourhood_targets: &event.neighbourhood_targets,
        payload: &event.payload,
        key_id: &event.key_id,
    })?;
    let signing_key = SigningKey::from_bytes(&[seed; 32]);
    event.signature = URL_SAFE_NO_PAD.encode(signing_key.sign(&bytes).to_bytes());
    Ok(())
}

fn identity(cell_id: &str, key_id: &str, seed: u8) -> CellIdentity {
    CellIdentity::new(
        cell_id,
        format!("https://{cell_id}.example.test"),
        key_id,
        [seed; 32],
    )
    .expect("test identity")
}

#[tokio::test]
#[ignore = "requires an isolated FEDERATION_TEST_DATABASE_URL"]
async fn postgres_repository_survives_restart_and_keeps_quarantine_separate() -> Result<()> {
    let database_url = env::var("FEDERATION_TEST_DATABASE_URL")
        .context("FEDERATION_TEST_DATABASE_URL must identify an isolated PostgreSQL database")?;
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await?;
    sqlx::migrate!("./migrations").run(&pool).await?;

    let identity_a = identity("cell-a", "key-a", 61);
    let sender = FederationService::new(
        identity("cell-a", "key-a", 61),
        Arc::new(MemoryFederationRepository::new()),
    );
    let receiver_identity = identity("cell-b", "key-b", 62);
    let receiver = FederationService::new(
        receiver_identity.clone(),
        Arc::new(PostgresFederationRepository::new(pool.clone())),
    );
    receiver
        .install_peer(PeerPolicy {
            remote_cell_id: "cell-a".to_string(),
            state: "trusted".to_string(),
            allow_neighbourhood: true,
            allowed_event_types: HashSet::from([
                "object.upserted".to_string(),
                "object.deleted".to_string(),
            ]),
            keys: vec![identity_a.peer_key()],
        })
        .await?;

    let event = sender
        .publish_local(PublishRequest {
            actor: "system:postgres-proof".to_string(),
            event_type: "object.upserted".to_string(),
            object_address: "wg://cell-a/node/durable-node".to_string(),
            object_kind: "node".to_string(),
            object_version: 1,
            previous_version: None,
            scope: "global".to_string(),
            neighbourhood_targets: vec![],
            payload: json!({"title": "Durable node"}),
        })
        .await?;
    assert_eq!(
        receiver.receive(event.clone()).await?.status,
        ReceiveStatus::Applied
    );

    // Reconstruct the service from the same database as a process-restart proof.
    drop(receiver);
    let restarted = FederationService::new(
        receiver_identity,
        Arc::new(PostgresFederationRepository::new(pool.clone())),
    );
    let persisted = restarted
        .object("wg://cell-a/node/durable-node")
        .await?
        .expect("verified remote object must survive service reconstruction");
    assert_eq!(persisted.object_version, 1);
    assert_eq!(persisted.payload["title"], "Durable node");
    assert_eq!(
        restarted.receive(event.clone()).await?.status,
        ReceiveStatus::Duplicate
    );

    let mut tampered = event;
    tampered.event_id = uuid::Uuid::new_v4();
    tampered.payload = json!({"title": "Tampered after signing"});
    let outcome = restarted.receive(tampered).await?;
    assert_eq!(outcome.status, ReceiveStatus::Quarantined);
    assert!(outcome
        .reason
        .as_deref()
        .unwrap_or_default()
        .contains("signature"));
    let quarantine = restarted.quarantined().await?;
    assert!(quarantine.is_empty());

    // Two independently signed first versions race for the same address.
    // The address-bound transaction lock must serialize the transition so
    // exactly one applies and the other is quarantined as stale.
    let race_sender_one = FederationService::new(
        identity("cell-a", "key-a", 61),
        Arc::new(MemoryFederationRepository::new()),
    );
    let race_sender_two = FederationService::new(
        identity("cell-a", "key-a", 61),
        Arc::new(MemoryFederationRepository::new()),
    );
    let race_event_one = race_sender_one
        .publish_local(PublishRequest {
            actor: "system:postgres-race-proof".to_string(),
            event_type: "object.upserted".to_string(),
            object_address: "wg://cell-a/node/race-node".to_string(),
            object_kind: "node".to_string(),
            object_version: 1,
            previous_version: None,
            scope: "global".to_string(),
            neighbourhood_targets: vec![],
            payload: json!({"winner": "one"}),
        })
        .await?;
    let race_event_two = race_sender_two
        .publish_local(PublishRequest {
            actor: "system:postgres-race-proof".to_string(),
            event_type: "object.upserted".to_string(),
            object_address: "wg://cell-a/node/race-node".to_string(),
            object_kind: "node".to_string(),
            object_version: 1,
            previous_version: None,
            scope: "global".to_string(),
            neighbourhood_targets: vec![],
            payload: json!({"winner": "two"}),
        })
        .await?;
    let (first, second) = tokio::join!(
        restarted.receive(race_event_one),
        restarted.receive(race_event_two)
    );
    let outcomes = [first?, second?];
    assert_eq!(
        outcomes
            .iter()
            .filter(|outcome| outcome.status == ReceiveStatus::Applied)
            .count(),
        1
    );
    assert_eq!(
        outcomes
            .iter()
            .filter(|outcome| outcome.status == ReceiveStatus::Quarantined)
            .count(),
        1
    );
    let quarantine = restarted.quarantined().await?;
    assert_eq!(quarantine.len(), 1);

    // Two valid envelopes with the same event id but different object locks
    // must also serialize. One receipt applies; the conflicting envelope is
    // quarantined instead of leaking a unique-constraint error as HTTP 500.
    let collision_event_one = race_sender_one
        .publish_local(PublishRequest {
            actor: "system:event-id-race-proof".to_string(),
            event_type: "object.upserted".to_string(),
            object_address: "wg://cell-a/node/event-id-race-one".to_string(),
            object_kind: "node".to_string(),
            object_version: 1,
            previous_version: None,
            scope: "global".to_string(),
            neighbourhood_targets: vec![],
            payload: json!({"winner": "one"}),
        })
        .await?;
    let mut collision_event_two = race_sender_two
        .publish_local(PublishRequest {
            actor: "system:event-id-race-proof".to_string(),
            event_type: "object.upserted".to_string(),
            object_address: "wg://cell-a/node/event-id-race-two".to_string(),
            object_kind: "node".to_string(),
            object_version: 1,
            previous_version: None,
            scope: "global".to_string(),
            neighbourhood_targets: vec![],
            payload: json!({"winner": "two"}),
        })
        .await?;
    collision_event_two.event_id = collision_event_one.event_id;
    resign(&mut collision_event_two, 61)?;
    let (first, second) = tokio::join!(
        restarted.receive(collision_event_one),
        restarted.receive(collision_event_two)
    );
    let outcomes = [first?, second?];
    assert_eq!(
        outcomes
            .iter()
            .filter(|outcome| outcome.status == ReceiveStatus::Applied)
            .count(),
        1
    );
    assert_eq!(
        outcomes
            .iter()
            .filter(|outcome| outcome.status == ReceiveStatus::Quarantined)
            .count(),
        1
    );
    assert_eq!(restarted.quarantined().await?.len(), 2);

    // Explicitly inactive means revoked for new deliveries. Rotation without
    // revocation remains possible by retaining the old verification key active.
    let mut inactive_key = identity_a.peer_key();
    inactive_key.active = false;
    restarted
        .install_peer(PeerPolicy {
            remote_cell_id: "cell-a".to_string(),
            state: "trusted".to_string(),
            allow_neighbourhood: true,
            allowed_event_types: HashSet::from([
                "object.upserted".to_string(),
                "object.deleted".to_string(),
            ]),
            keys: vec![inactive_key],
        })
        .await?;
    let revoked_sender = FederationService::new(
        identity("cell-a", "key-a", 61),
        Arc::new(MemoryFederationRepository::new()),
    );
    let revoked_event = revoked_sender
        .publish_local(PublishRequest {
            actor: "system:postgres-revocation-proof".to_string(),
            event_type: "object.upserted".to_string(),
            object_address: "wg://cell-a/node/revoked-delivery".to_string(),
            object_kind: "node".to_string(),
            object_version: 1,
            previous_version: None,
            scope: "global".to_string(),
            neighbourhood_targets: vec![],
            payload: json!({"title": "Must stay quarantined"}),
        })
        .await?;
    let revoked_outcome = restarted.receive(revoked_event).await?;
    assert_eq!(revoked_outcome.status, ReceiveStatus::Quarantined);
    assert!(revoked_outcome
        .reason
        .as_deref()
        .unwrap_or_default()
        .contains("inactive"));
    assert_eq!(restarted.quarantined().await?.len(), 3);

    sqlx::query(
        "INSERT INTO federation_quarantine \
         (event_id, origin_cell_id, reason, envelope_sha256, envelope, received_at) \
         VALUES ('ffffffff-ffff-ffff-ffff-ffffffffffff', 'cell-a', \
                 'retention-fixture', repeat('f', 64), '{}'::jsonb, \
                 NOW() - INTERVAL '31 days')",
    )
    .execute(&pool)
    .await?;
    sqlx::query(
        "INSERT INTO federation_quarantine \
         (event_id, origin_cell_id, reason, envelope_sha256, envelope) \
         SELECT ('00000000-0000-0000-0000-' || lpad(value::text, 12, '0'))::uuid, \
                'cell-a', 'capacity-fixture', \
                md5(value::text) || md5(value::text), \
                jsonb_build_object('fixture', value) \
         FROM generate_series(1, 1001) AS value",
    )
    .execute(&pool)
    .await?;
    let capacity_event = revoked_sender
        .publish_local(PublishRequest {
            actor: "system:postgres-quarantine-bound-proof".to_string(),
            event_type: "object.upserted".to_string(),
            object_address: "wg://cell-a/node/quarantine-bound".to_string(),
            object_kind: "node".to_string(),
            object_version: 1,
            previous_version: None,
            scope: "global".to_string(),
            neighbourhood_targets: vec![],
            payload: json!({"title": "Bounded"}),
        })
        .await?;
    assert_eq!(
        restarted.receive(capacity_event).await?.status,
        ReceiveStatus::Quarantined
    );
    let quarantine_count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM federation_quarantine WHERE origin_cell_id = 'cell-a'",
    )
    .fetch_one(&pool)
    .await?;
    assert_eq!(quarantine_count, 1_000);
    let expired_count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM federation_quarantine \
         WHERE origin_cell_id = 'cell-a' AND reason = 'retention-fixture'",
    )
    .fetch_one(&pool)
    .await?;
    assert_eq!(expired_count, 0);

    let local = restarted
        .publish_local(PublishRequest {
            actor: "system:postgres-proof".to_string(),
            event_type: "object.upserted".to_string(),
            object_address: "wg://cell-b/shared-room/durable-room".to_string(),
            object_kind: "shared-room".to_string(),
            object_version: 1,
            previous_version: None,
            scope: "global".to_string(),
            neighbourhood_targets: vec![],
            payload: json!({"title": "Durable room"}),
        })
        .await?;
    assert_eq!(local.object_version, 1);
    let pending = restarted.pending_outbox().await?;
    assert_eq!(pending.len(), 1);
    assert_eq!(
        pending[0].object_address,
        "wg://cell-b/shared-room/durable-room"
    );

    pool.close().await;
    Ok(())
}

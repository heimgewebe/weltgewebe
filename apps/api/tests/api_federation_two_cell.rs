use std::{collections::HashSet, sync::Arc};

use anyhow::Result;
use axum::{
    body::{self, Body},
    http::{Request, StatusCode},
    Router,
};
use serde_json::{json, Value};
use tower::ServiceExt;
use weltgewebe_api::federation::{
    router, CellIdentity, FederationEvent, FederationService, MemoryFederationRepository,
    PeerPolicy, PublishRequest, ReceiveOutcome, ReceiveStatus,
};

const UPSERTED: &str = "object.upserted";
const DELETED: &str = "object.deleted";

fn identity(cell_id: &str, seed: u8) -> CellIdentity {
    CellIdentity::new(
        cell_id,
        format!("https://{cell_id}.example.test"),
        "key-1",
        [seed; 32],
    )
    .expect("test identity")
}

fn service(cell_id: &str, seed: u8) -> FederationService {
    FederationService::new(
        identity(cell_id, seed),
        Arc::new(MemoryFederationRepository::new()),
    )
}

fn peer_policy(remote: &CellIdentity, state: &str) -> PeerPolicy {
    PeerPolicy {
        remote_cell_id: remote.descriptor().cell_id,
        state: state.to_string(),
        allow_neighbourhood: true,
        allowed_event_types: HashSet::from([UPSERTED.to_string(), DELETED.to_string()]),
        keys: vec![remote.peer_key()],
    }
}

async fn publish(
    service: &FederationService,
    address: &str,
    kind: &str,
    version: i64,
    previous_version: Option<i64>,
    payload: Value,
) -> FederationEvent {
    service
        .publish_local(PublishRequest {
            actor: "system:two-cell-proof".to_string(),
            event_type: if payload.is_null() {
                DELETED.to_string()
            } else {
                UPSERTED.to_string()
            },
            object_address: address.to_string(),
            object_kind: kind.to_string(),
            object_version: version,
            previous_version,
            scope: "global".to_string(),
            neighbourhood_targets: vec![],
            payload,
        })
        .await
        .expect("publish local event")
}

async fn deliver(app: &Router, event: &FederationEvent) -> Result<(StatusCode, ReceiveOutcome)> {
    let response = app
        .clone()
        .oneshot(
            Request::post("/federation/v1/events")
                .header("content-type", "application/json")
                .body(Body::from(serde_json::to_vec(event)?))?,
        )
        .await?;
    let status = response.status();
    let bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
    Ok((status, serde_json::from_slice(&bytes)?))
}

async fn get_object(app: &Router, encoded_address: &str) -> Result<(StatusCode, Value)> {
    let response = app
        .clone()
        .oneshot(
            Request::get(format!("/federation/v1/objects?address={encoded_address}"))
                .body(Body::empty())?,
        )
        .await?;
    let status = response.status();
    let bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
    let value = if bytes.is_empty() {
        Value::Null
    } else {
        serde_json::from_slice(&bytes)?
    };
    Ok((status, value))
}

#[tokio::test]
async fn event_endpoint_rejects_noncanonical_envelopes_as_bad_request() -> Result<()> {
    let sender = service("cell-a", 11);
    let event = publish(
        &sender,
        "wg://cell-a/node/strict-envelope",
        "node",
        1,
        None,
        json!({"title": "Strict"}),
    )
    .await;
    let app = router(service("cell-b", 22));

    let mut missing_required = serde_json::to_value(&event)?;
    missing_required
        .as_object_mut()
        .expect("event object")
        .remove("neighbourhood_targets");
    let response = app
        .clone()
        .oneshot(
            Request::post("/federation/v1/events")
                .header("content-type", "application/json")
                .body(Body::from(serde_json::to_vec(&missing_required)?))?,
        )
        .await?;
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);

    let mut unknown_field = serde_json::to_value(&event)?;
    unknown_field
        .as_object_mut()
        .expect("event object")
        .insert("unsigned_extension".to_string(), json!(true));
    let response = app
        .clone()
        .oneshot(
            Request::post("/federation/v1/events")
                .header("content-type", "application/json")
                .body(Body::from(serde_json::to_vec(&unknown_field)?))?,
        )
        .await?;
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);

    let mut noncanonical_timestamp = serde_json::to_value(&event)?;
    noncanonical_timestamp["created_at"] = json!("2026-07-20T10:00:00+02:00");
    let response = app
        .clone()
        .oneshot(
            Request::post("/federation/v1/events")
                .header("content-type", "application/json")
                .body(Body::from(serde_json::to_vec(&noncanonical_timestamp)?))?,
        )
        .await?;
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);

    let mut noncanonical_event_id = serde_json::to_value(&event)?;
    noncanonical_event_id["event_id"] =
        json!(event.event_id.hyphenated().to_string().to_ascii_uppercase());
    let response = app
        .clone()
        .oneshot(
            Request::post("/federation/v1/events")
                .header("content-type", "application/json")
                .body(Body::from(serde_json::to_vec(&noncanonical_event_id)?))?,
        )
        .await?;
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);

    let response = app
        .clone()
        .oneshot(
            Request::post("/federation/v1/events").body(Body::from(serde_json::to_vec(&event)?))?,
        )
        .await?;
    assert_eq!(response.status(), StatusCode::UNSUPPORTED_MEDIA_TYPE);

    let response = app
        .oneshot(
            Request::post("/federation/v1/events")
                .header("content-type", "application/json")
                .body(Body::from(vec![b'x'; 256 * 1024 + 1]))?,
        )
        .await?;
    assert_eq!(response.status(), StatusCode::PAYLOAD_TOO_LARGE);
    Ok(())
}

#[tokio::test]
async fn event_endpoint_accepts_valid_envelope_near_body_limit() -> Result<()> {
    let sender = service("cell-a", 11);
    let event = publish(
        &sender,
        "wg://cell-a/node/near-body-limit",
        "node",
        1,
        None,
        json!({"blob": "x".repeat(250 * 1024)}),
    )
    .await;
    let body = serde_json::to_vec(&event)?;
    assert!(body.len() > 240 * 1024);
    assert!(body.len() < 256 * 1024);

    let response = router(service("cell-b", 22))
        .oneshot(
            Request::post("/federation/v1/events")
                .header("content-type", "application/json")
                .body(Body::from(body))?,
        )
        .await?;
    assert_eq!(response.status(), StatusCode::ACCEPTED);
    Ok(())
}

#[tokio::test]
async fn api_prefixed_fallback_serves_public_federation_boundary() -> Result<()> {
    let public = router(service("cell-b", 22));
    let existing_api = Router::new().route(
        "/existing",
        axum::routing::get(|| async { StatusCode::NO_CONTENT }),
    );
    let app = Router::new()
        .nest("/api", existing_api)
        .nest("/api", public.clone())
        .merge(public);

    let existing = app
        .clone()
        .oneshot(Request::get("/api/existing").body(Body::empty())?)
        .await?;
    assert_eq!(existing.status(), StatusCode::NO_CONTENT);

    let prefixed = app
        .clone()
        .oneshot(Request::get("/api/federation/v1/cell").body(Body::empty())?)
        .await?;
    assert_eq!(prefixed.status(), StatusCode::OK);

    let direct = app
        .oneshot(Request::get("/federation/v1/cell").body(Body::empty())?)
        .await?;
    assert_eq!(direct.status(), StatusCode::OK);
    Ok(())
}

#[tokio::test]
async fn two_cells_exchange_objects_survive_partition_and_converge() -> Result<()> {
    let identity_a = identity("cell-a", 11);
    let identity_b = identity("cell-b", 22);
    let cell_a = service("cell-a", 11);
    let cell_b = service("cell-b", 22);
    cell_a
        .install_peer(peer_policy(&identity_b, "trusted"))
        .await?;
    cell_b
        .install_peer(peer_policy(&identity_a, "trusted"))
        .await?;
    let app_a = router(cell_a.clone());
    let app_b = router(cell_b.clone());

    let descriptor = app_a
        .clone()
        .oneshot(Request::get("/federation/v1/cell").body(Body::empty())?)
        .await?;
    assert_eq!(descriptor.status(), StatusCode::OK);
    let descriptor: Value =
        serde_json::from_slice(&body::to_bytes(descriptor.into_body(), usize::MAX).await?)?;
    assert_eq!(descriptor["cell_id"], "cell-a");
    assert_eq!(descriptor["active_key"]["algorithm"], "Ed25519");

    // Partition begins: both cells continue to write their own local truth.
    let a_node_v1 = publish(
        &cell_a,
        "wg://cell-a/node/community-garden",
        "node",
        1,
        None,
        json!({"title": "Community Garden", "cell": "A"}),
    )
    .await;
    let a_edge_v1 = publish(
        &cell_a,
        "wg://cell-a/edge/garden-to-room",
        "edge",
        1,
        None,
        json!({
            "from": "wg://cell-a/node/community-garden",
            "to": "wg://cell-a/shared-room/harvest-2026",
            "kind": "participates-in"
        }),
    )
    .await;
    let a_room_v1 = publish(
        &cell_a,
        "wg://cell-a/shared-room/harvest-2026",
        "shared-room",
        1,
        None,
        json!({"title": "Harvest 2026", "members": ["cell-a", "cell-b"]}),
    )
    .await;
    let b_node_v1 = publish(
        &cell_b,
        "wg://cell-b/node/tool-library",
        "node",
        1,
        None,
        json!({"title": "Tool Library", "cell": "B"}),
    )
    .await;

    assert_eq!(
        cell_a
            .object("wg://cell-a/node/community-garden")
            .await?
            .expect("cell A local node")
            .object_version,
        1
    );
    assert_eq!(
        cell_b
            .object("wg://cell-b/node/tool-library")
            .await?
            .expect("cell B local node")
            .object_version,
        1
    );
    assert!(
        cell_b
            .object("wg://cell-a/node/community-garden")
            .await?
            .is_none(),
        "partition must not invent remote state"
    );

    // Partition heals: deliver the exact signed envelopes through the public API.
    for event in [&a_node_v1, &a_edge_v1, &a_room_v1] {
        let (status, outcome) = deliver(&app_b, event).await?;
        assert_eq!(status, StatusCode::CREATED);
        assert_eq!(outcome.status, ReceiveStatus::Applied);
    }
    let (status, outcome) = deliver(&app_a, &b_node_v1).await?;
    assert_eq!(status, StatusCode::CREATED);
    assert_eq!(outcome.status, ReceiveStatus::Applied);

    let (status, projected) =
        get_object(&app_b, "wg%3A%2F%2Fcell-a%2Fnode%2Fcommunity-garden").await?;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(projected["payload"]["title"], "Community Garden");
    let (status, room) =
        get_object(&app_b, "wg%3A%2F%2Fcell-a%2Fshared-room%2Fharvest-2026").await?;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(room["object_kind"], "shared-room");
    let (status, edge) = get_object(&app_b, "wg%3A%2F%2Fcell-a%2Fedge%2Fgarden-to-room").await?;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(edge["payload"]["kind"], "participates-in");

    // At-least-once delivery is harmless.
    let (status, outcome) = deliver(&app_b, &a_node_v1).await?;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(outcome.status, ReceiveStatus::Duplicate);

    // A second partition delays version 2 without blocking either local cell.
    let a_node_v2 = publish(
        &cell_a,
        "wg://cell-a/node/community-garden",
        "node",
        2,
        Some(1),
        json!({"title": "Community Garden and Kitchen", "cell": "A"}),
    )
    .await;
    assert_eq!(
        cell_b
            .object("wg://cell-a/node/community-garden")
            .await?
            .expect("cell B retains last verified version")
            .object_version,
        1
    );
    assert_eq!(cell_a.pending_outbox().await?.len(), 4);
    assert_eq!(cell_b.pending_outbox().await?.len(), 1);

    let (status, outcome) = deliver(&app_b, &a_node_v2).await?;
    assert_eq!(status, StatusCode::CREATED);
    assert_eq!(outcome.status, ReceiveStatus::Applied);
    assert_eq!(
        cell_b
            .object("wg://cell-a/node/community-garden")
            .await?
            .expect("cell B converged")
            .object_version,
        2
    );

    // Deletion remains origin-owned and becomes a visible tombstone.
    let a_node_v3_delete = publish(
        &cell_a,
        "wg://cell-a/node/community-garden",
        "node",
        3,
        Some(2),
        Value::Null,
    )
    .await;
    let (status, outcome) = deliver(&app_b, &a_node_v3_delete).await?;
    assert_eq!(status, StatusCode::CREATED);
    assert_eq!(outcome.status, ReceiveStatus::Applied);
    assert!(
        cell_b
            .object("wg://cell-a/node/community-garden")
            .await?
            .expect("tombstone remains inspectable")
            .deleted
    );
    let (status, _) = get_object(&app_b, "wg%3A%2F%2Fcell-a%2Fnode%2Fcommunity-garden").await?;
    assert_eq!(status, StatusCode::NOT_FOUND);

    Ok(())
}

#[tokio::test]
async fn invalid_scope_version_signature_and_blocked_peer_are_quarantined() -> Result<()> {
    let identity_a = identity("cell-a", 31);
    let cell_a = service("cell-a", 31);
    let cell_b = service("cell-b", 32);
    cell_b
        .install_peer(peer_policy(&identity_a, "trusted"))
        .await?;
    let app_b = router(cell_b.clone());

    let valid = publish(
        &cell_a,
        "wg://cell-a/node/n-1",
        "node",
        1,
        None,
        json!({"title": "Valid"}),
    )
    .await;
    let (status, outcome) = deliver(&app_b, &valid).await?;
    assert_eq!(status, StatusCode::CREATED);
    assert_eq!(outcome.status, ReceiveStatus::Applied);

    let mut unsupported_schema = valid.clone();
    unsupported_schema.event_id = uuid::Uuid::new_v4();
    unsupported_schema.schema_version = 99;
    let response = app_b
        .clone()
        .oneshot(
            Request::post("/federation/v1/events")
                .header("content-type", "application/json")
                .body(Body::from(serde_json::to_vec(&unsupported_schema)?))?,
        )
        .await?;
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);

    let mut local_scope = valid.clone();
    local_scope.event_id = uuid::Uuid::new_v4();
    local_scope.scope = "local".to_string();
    let response = app_b
        .clone()
        .oneshot(
            Request::post("/federation/v1/events")
                .header("content-type", "application/json")
                .body(Body::from(serde_json::to_vec(&local_scope)?))?,
        )
        .await?;
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);

    let mut tampered = valid.clone();
    tampered.event_id = uuid::Uuid::new_v4();
    tampered.payload = json!({"title": "Tampered"});
    let (status, outcome) = deliver(&app_b, &tampered).await?;
    assert_eq!(status, StatusCode::ACCEPTED);
    assert!(outcome.reason.unwrap().contains("signature"));

    // A separately signed first version for an already known address is stale.
    let stale_signer = service("cell-a", 31);
    let stale = publish(
        &stale_signer,
        "wg://cell-a/node/n-1",
        "node",
        1,
        None,
        json!({"title": "Stale but correctly signed"}),
    )
    .await;
    let (status, outcome) = deliver(&app_b, &stale).await?;
    assert_eq!(status, StatusCode::ACCEPTED);
    assert!(outcome.reason.unwrap().contains("stale"));
    let (status, outcome) = deliver(&app_b, &stale).await?;
    assert_eq!(status, StatusCode::ACCEPTED);
    assert!(outcome.reason.unwrap().contains("stale"));

    cell_b
        .install_peer(peer_policy(&identity_a, "blocked"))
        .await?;
    let blocked_event = publish(
        &cell_a,
        "wg://cell-a/node/n-2",
        "node",
        1,
        None,
        json!({"title": "Blocked"}),
    )
    .await;
    let (status, outcome) = deliver(&app_b, &blocked_event).await?;
    assert_eq!(status, StatusCode::ACCEPTED);
    assert!(outcome.reason.unwrap().contains("blocked"));

    let quarantine = cell_b.quarantined().await?;
    assert_eq!(quarantine.len(), 2);
    assert!(quarantine
        .iter()
        .all(|entry| entry.envelope_sha256.len() == 64));

    Ok(())
}

#[tokio::test]
async fn public_receive_endpoint_limits_authenticated_peer_amplification() -> Result<()> {
    let sender_identity = identity("cell-a", 71);
    let sender = FederationService::new(
        sender_identity.clone(),
        Arc::new(MemoryFederationRepository::new()),
    );
    let receiver = service("cell-b", 72);
    receiver
        .install_peer(peer_policy(&sender_identity, "trusted"))
        .await?;
    let app = router(receiver);

    for index in 0..=120 {
        let event = publish(
            &sender,
            &format!("wg://cell-a/node/rate-{index}"),
            "node",
            1,
            None,
            json!({"index": index}),
        )
        .await;
        let response = app
            .clone()
            .oneshot(
                Request::post("/federation/v1/events")
                    .header("content-type", "application/json")
                    .body(Body::from(serde_json::to_vec(&event)?))?,
            )
            .await?;
        if index < 120 {
            assert_eq!(response.status(), StatusCode::CREATED);
        } else {
            assert_eq!(response.status(), StatusCode::TOO_MANY_REQUESTS);
            assert_eq!(
                response
                    .headers()
                    .get("retry-after")
                    .and_then(|value| value.to_str().ok()),
                Some("60")
            );
        }
    }

    Ok(())
}

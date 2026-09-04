use std::{
    collections::{HashMap, HashSet},
    env,
    net::SocketAddr,
    sync::{Arc, Mutex},
    time::{Duration as StdDuration, Instant},
};

use anyhow::{bail, Context};
use async_trait::async_trait;
use axum::{
    body::Body,
    extract::{rejection::JsonRejection, ConnectInfo, DefaultBodyLimit, Query, State},
    http::{header::RETRY_AFTER, HeaderValue, Request, StatusCode},
    middleware::{from_fn_with_state, Next},
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use chrono::{DateTime, Duration, SecondsFormat, Utc};
use ed25519_dalek::{Signature, Signer, SigningKey, VerifyingKey};
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use sqlx::{PgPool, Postgres, QueryBuilder, Row};
use tokio::sync::RwLock;
use url::Url;
use uuid::Uuid;

use crate::routes::auth::client_ip_or_peer;

pub const FEDERATION_PROTOCOL_VERSION: &str = "wg-federation/1";
pub const FEDERATION_SCHEMA_VERSION: u16 = 1;
const MAX_EVENT_BYTES: usize = 256 * 1024;
const MAX_CLOCK_SKEW_SECONDS: i64 = 300;
const EVENT_UPSERTED: &str = "object.upserted";
const EVENT_DELETED: &str = "object.deleted";
const SCOPE_NEIGHBOURHOOD: &str = "neighbourhood";
const SCOPE_GLOBAL: &str = "global";
const RATE_LIMIT_WINDOW: StdDuration = StdDuration::from_secs(60);
const RATE_LIMIT_WINDOW_SECONDS: i64 = 60;
const RECEIVE_RATE_PER_ORIGIN: u32 = 120;
const RECEIVE_RATE_PER_CLIENT: u32 = 240;
const RECEIVE_RATE_GLOBAL: u32 = 6_000;
const OBJECT_READ_RATE_PER_CLIENT: u32 = 600;
const OBJECT_READ_RATE_GLOBAL: u32 = 6_000;
const RATE_SCOPE_RECEIVE_CLIENT: &str = "receive-client";
const RATE_SCOPE_RECEIVE_GLOBAL: &str = "receive-global";
const RATE_SCOPE_RECEIVE_ORIGIN: &str = "receive-origin";
const RATE_SCOPE_OBJECT_READ_CLIENT: &str = "object-read-client";
const RATE_SCOPE_OBJECT_READ_GLOBAL: &str = "object-read-global";
const QUARANTINE_RETENTION_DAYS: i64 = 30;
const QUARANTINE_MAX_PER_ORIGIN: usize = 1_000;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CellKeyDescriptor {
    pub key_id: String,
    pub algorithm: String,
    pub public_key: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CellDescriptor {
    pub protocol_version: String,
    pub cell_id: String,
    pub public_base_url: String,
    pub active_key: CellKeyDescriptor,
    pub capabilities: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct FederationEvent {
    pub protocol_version: String,
    pub schema_version: u16,
    #[serde(deserialize_with = "deserialize_canonical_uuid")]
    pub event_id: Uuid,
    pub event_type: String,
    pub origin_cell_id: String,
    pub actor: String,
    pub object_address: String,
    pub object_kind: String,
    pub object_version: i64,
    pub previous_version: Option<i64>,
    #[serde(deserialize_with = "deserialize_canonical_utc")]
    pub created_at: DateTime<Utc>,
    pub scope: String,
    pub neighbourhood_targets: Vec<String>,
    pub payload: Value,
    pub key_id: String,
    pub signature: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct FederatedObject {
    pub object_address: String,
    pub origin_cell_id: String,
    pub object_kind: String,
    pub object_version: i64,
    pub scope: String,
    pub neighbourhood_targets: Vec<String>,
    pub payload: Value,
    pub deleted: bool,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ReceiveStatus {
    Applied,
    Duplicate,
    Rejected,
    Quarantined,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReceiveOutcome {
    pub status: ReceiveStatus,
    pub event_id: Uuid,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub object_version: Option<i64>,
}

impl ReceiveOutcome {
    fn applied(event: &FederationEvent) -> Self {
        Self {
            status: ReceiveStatus::Applied,
            event_id: event.event_id,
            reason: None,
            object_version: Some(event.object_version),
        }
    }

    fn duplicate(event: &FederationEvent) -> Self {
        Self {
            status: ReceiveStatus::Duplicate,
            event_id: event.event_id,
            reason: None,
            object_version: Some(event.object_version),
        }
    }

    fn rejected(event: &FederationEvent) -> Self {
        Self {
            status: ReceiveStatus::Rejected,
            event_id: event.event_id,
            reason: Some("event authentication rejected".to_string()),
            object_version: None,
        }
    }

    fn quarantined(event: &FederationEvent, reason: impl Into<String>) -> Self {
        Self {
            status: ReceiveStatus::Quarantined,
            event_id: event.event_id,
            reason: Some(reason.into()),
            object_version: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct QuarantinedEvent {
    pub event_id: Uuid,
    pub origin_cell_id: String,
    pub reason: String,
    pub envelope_sha256: String,
    pub received_at: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct PeerKey {
    pub key_id: String,
    pub public_key: [u8; 32],
    pub active: bool,
}

#[derive(Debug, Clone)]
pub struct PeerPolicy {
    pub remote_cell_id: String,
    pub state: String,
    pub allow_neighbourhood: bool,
    pub allowed_event_types: HashSet<String>,
    pub keys: Vec<PeerKey>,
}

#[derive(Debug, Clone)]
pub struct ResolvedPeer {
    state: String,
    allow_neighbourhood: bool,
    allowed_event_types: HashSet<String>,
    public_key: [u8; 32],
    key_active: bool,
}

#[derive(Debug, Clone)]
pub struct CellIdentity {
    cell_id: String,
    public_base_url: String,
    key_id: String,
    signing_key: SigningKey,
}

impl CellIdentity {
    pub fn new(
        cell_id: impl Into<String>,
        public_base_url: impl Into<String>,
        key_id: impl Into<String>,
        signing_key: [u8; 32],
    ) -> anyhow::Result<Self> {
        let identity = Self {
            cell_id: cell_id.into(),
            public_base_url: public_base_url.into(),
            key_id: key_id.into(),
            signing_key: SigningKey::from_bytes(&signing_key),
        };
        validate_cell_id(&identity.cell_id)?;
        validate_key_id(&identity.key_id)?;
        validate_public_base_url(&identity.public_base_url)?;
        Ok(identity)
    }

    pub fn descriptor(&self) -> CellDescriptor {
        CellDescriptor {
            protocol_version: FEDERATION_PROTOCOL_VERSION.to_string(),
            cell_id: self.cell_id.clone(),
            public_base_url: self.public_base_url.clone(),
            active_key: CellKeyDescriptor {
                key_id: self.key_id.clone(),
                algorithm: "Ed25519".to_string(),
                public_key: URL_SAFE_NO_PAD.encode(self.signing_key.verifying_key().as_bytes()),
            },
            capabilities: vec![
                "signed-events".to_string(),
                "origin-owned-objects".to_string(),
                "neighbourhood-scope".to_string(),
                "shared-rooms".to_string(),
                "quarantine".to_string(),
            ],
        }
    }

    pub fn peer_key(&self) -> PeerKey {
        PeerKey {
            key_id: self.key_id.clone(),
            public_key: *self.signing_key.verifying_key().as_bytes(),
            active: true,
        }
    }
}

#[derive(Debug, Clone)]
pub struct PublishRequest {
    pub actor: String,
    pub event_type: String,
    pub object_address: String,
    pub object_kind: String,
    pub object_version: i64,
    pub previous_version: Option<i64>,
    pub scope: String,
    pub neighbourhood_targets: Vec<String>,
    pub payload: Value,
}

#[async_trait]
pub trait FederationRepository: Send + Sync {
    async fn install_peer(&self, policy: PeerPolicy) -> anyhow::Result<()>;
    async fn resolve_peer(
        &self,
        cell_id: &str,
        key_id: &str,
    ) -> anyhow::Result<Option<ResolvedPeer>>;
    async fn check_rate_limit(
        &self,
        scope: &str,
        subject: &str,
        limit: u32,
    ) -> anyhow::Result<bool>;
    async fn quarantine(
        &self,
        event: &FederationEvent,
        reason: &str,
    ) -> anyhow::Result<ReceiveOutcome>;
    async fn accept_verified(
        &self,
        event: &FederationEvent,
        origin_rate_subject: &str,
        origin_rate_limit: u32,
    ) -> anyhow::Result<ReceiveOutcome>;
    async fn persist_local(&self, event: &FederationEvent) -> anyhow::Result<()>;
    async fn object(&self, address: &str) -> anyhow::Result<Option<FederatedObject>>;
    async fn pending_outbox(&self) -> anyhow::Result<Vec<FederationEvent>>;
    async fn quarantined(&self) -> anyhow::Result<Vec<QuarantinedEvent>>;
}

struct LocalRateState {
    window_started: Instant,
    counts: HashMap<(String, String), u32>,
}

impl Default for LocalRateState {
    fn default() -> Self {
        Self {
            window_started: Instant::now(),
            counts: HashMap::new(),
        }
    }
}

impl LocalRateState {
    fn allow(&mut self, scope: &str, subject: &str, limit: u32) -> bool {
        if limit == 0 {
            return true;
        }
        if self.window_started.elapsed() >= RATE_LIMIT_WINDOW {
            *self = Self::default();
        }
        let count = self
            .counts
            .entry((scope.to_string(), subject.to_string()))
            .or_default();
        if *count >= limit {
            return false;
        }
        *count += 1;
        true
    }
}

#[derive(Clone)]
pub struct FederationService {
    identity: Arc<CellIdentity>,
    repository: Arc<dyn FederationRepository>,
    client_rate_state: Arc<Mutex<LocalRateState>>,
}

impl FederationService {
    pub fn new(identity: CellIdentity, repository: Arc<dyn FederationRepository>) -> Self {
        Self {
            identity: Arc::new(identity),
            repository,
            client_rate_state: Arc::new(Mutex::new(LocalRateState::default())),
        }
    }

    pub fn descriptor(&self) -> CellDescriptor {
        self.identity.descriptor()
    }

    fn allow_receive_client(&self, client_ip: &str) -> bool {
        let subject = format!("{}:{client_ip}", self.identity.cell_id);
        self.client_rate_state
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .allow(RATE_SCOPE_RECEIVE_CLIENT, &subject, RECEIVE_RATE_PER_CLIENT)
    }

    async fn allow_receive_global(&self) -> anyhow::Result<bool> {
        self.repository
            .check_rate_limit(
                RATE_SCOPE_RECEIVE_GLOBAL,
                &self.identity.cell_id,
                RECEIVE_RATE_GLOBAL,
            )
            .await
    }

    fn allow_object_read_client(&self, client_ip: &str) -> bool {
        let subject = format!("{}:{client_ip}", self.identity.cell_id);
        self.client_rate_state
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .allow(
                RATE_SCOPE_OBJECT_READ_CLIENT,
                &subject,
                OBJECT_READ_RATE_PER_CLIENT,
            )
    }

    async fn allow_object_read_global(&self) -> anyhow::Result<bool> {
        self.repository
            .check_rate_limit(
                RATE_SCOPE_OBJECT_READ_GLOBAL,
                &self.identity.cell_id,
                OBJECT_READ_RATE_GLOBAL,
            )
            .await
    }

    pub async fn install_peer(&self, policy: PeerPolicy) -> anyhow::Result<()> {
        validate_cell_id(&policy.remote_cell_id)?;
        if policy.remote_cell_id == self.identity.cell_id {
            bail!("a cell cannot install itself as a federation peer");
        }
        if policy.state != "trusted" && policy.state != "blocked" {
            bail!("peer state must be trusted or blocked");
        }
        if policy.allowed_event_types.is_empty() {
            bail!("peer policy must explicitly allow at least one event type");
        }
        for event_type in &policy.allowed_event_types {
            validate_event_type(event_type)?;
        }
        if policy.keys.is_empty() {
            bail!("peer policy must contain at least one verification key");
        }
        let mut key_ids = HashSet::new();
        for key in &policy.keys {
            validate_key_id(&key.key_id)?;
            let verifying_key =
                VerifyingKey::from_bytes(&key.public_key).context("peer public key is invalid")?;
            if verifying_key.is_weak() {
                bail!("peer public key is weak");
            }
            if !key_ids.insert(key.key_id.clone()) {
                bail!("peer policy contains duplicate key id {}", key.key_id);
            }
        }
        self.repository.install_peer(policy).await
    }

    pub async fn publish_local(&self, request: PublishRequest) -> anyhow::Result<FederationEvent> {
        let mut event = FederationEvent {
            protocol_version: FEDERATION_PROTOCOL_VERSION.to_string(),
            schema_version: FEDERATION_SCHEMA_VERSION,
            event_id: Uuid::new_v4(),
            event_type: request.event_type,
            origin_cell_id: self.identity.cell_id.clone(),
            actor: request.actor,
            object_address: request.object_address,
            object_kind: request.object_kind,
            object_version: request.object_version,
            previous_version: request.previous_version,
            created_at: Utc::now(),
            scope: request.scope,
            neighbourhood_targets: request.neighbourhood_targets,
            payload: request.payload,
            key_id: self.identity.key_id.clone(),
            signature: String::new(),
        };
        validate_event_shape(&event, None, true)?;
        let signature = self.identity.signing_key.sign(&signing_bytes(&event)?);
        event.signature = URL_SAFE_NO_PAD.encode(signature.to_bytes());
        self.repository.persist_local(&event).await?;
        Ok(event)
    }

    pub async fn receive(&self, event: FederationEvent) -> anyhow::Result<ReceiveOutcome> {
        self.receive_with_size_policy(event, true).await
    }

    async fn receive_body_limited(&self, event: FederationEvent) -> anyhow::Result<ReceiveOutcome> {
        self.receive_with_size_policy(event, false).await
    }

    async fn receive_with_size_policy(
        &self,
        event: FederationEvent,
        enforce_size_limit: bool,
    ) -> anyhow::Result<ReceiveOutcome> {
        if let Err(error) =
            validate_event_shape(&event, Some(&self.identity.cell_id), enforce_size_limit)
        {
            return Err(InvalidFederationEvent(error.to_string()).into());
        }
        if event.origin_cell_id == self.identity.cell_id {
            return Ok(ReceiveOutcome::rejected(&event));
        }

        let Some(peer) = self
            .repository
            .resolve_peer(&event.origin_cell_id, &event.key_id)
            .await?
        else {
            return Ok(ReceiveOutcome::rejected(&event));
        };

        if verify_signature(&event, peer.public_key).is_err() {
            return Ok(ReceiveOutcome::rejected(&event));
        }
        let origin_rate_subject = format!("{}:{}", self.identity.cell_id, event.origin_cell_id);

        // The repository re-resolves and locks the current peer/key policy, then
        // detects exact duplicates before consuming the authenticated-origin
        // rate-limit bucket. This preserves revocation/blocking semantics while
        // preventing replayed accepted envelopes from exhausting a peer quota.
        self.repository
            .accept_verified(&event, &origin_rate_subject, RECEIVE_RATE_PER_ORIGIN)
            .await
    }

    pub async fn object(&self, address: &str) -> anyhow::Result<Option<FederatedObject>> {
        validate_object_address(address)?;
        self.repository.object(address).await
    }

    pub async fn pending_outbox(&self) -> anyhow::Result<Vec<FederationEvent>> {
        self.repository.pending_outbox().await
    }

    pub async fn quarantined(&self) -> anyhow::Result<Vec<QuarantinedEvent>> {
        self.repository.quarantined().await
    }
}

#[derive(Default)]
struct MemoryState {
    peers: HashMap<(String, String), ResolvedPeer>,
    inbox: HashMap<Uuid, String>,
    objects: HashMap<String, FederatedObject>,
    outbox: Vec<FederationEvent>,
    quarantine: Vec<QuarantinedEvent>,
}

fn push_memory_quarantine_once(
    state: &mut MemoryState,
    event: &FederationEvent,
    reason: &str,
    digest: String,
) {
    let cutoff = Utc::now() - Duration::days(QUARANTINE_RETENTION_DAYS);
    state.quarantine.retain(|entry| entry.received_at >= cutoff);
    if state.quarantine.iter().any(|entry| {
        entry.event_id == event.event_id
            && entry.envelope_sha256 == digest
            && entry.reason == reason
    }) {
        return;
    }
    state.quarantine.push(QuarantinedEvent {
        event_id: event.event_id,
        origin_cell_id: event.origin_cell_id.clone(),
        reason: reason.to_string(),
        envelope_sha256: digest,
        received_at: Utc::now(),
    });
    let origin_count = state
        .quarantine
        .iter()
        .filter(|entry| entry.origin_cell_id == event.origin_cell_id)
        .count();
    if origin_count > QUARANTINE_MAX_PER_ORIGIN {
        let oldest = state
            .quarantine
            .iter()
            .enumerate()
            .filter(|(_, entry)| entry.origin_cell_id == event.origin_cell_id)
            .min_by_key(|(_, entry)| entry.received_at)
            .map(|(index, _)| index)
            .expect("quarantine origin count is non-zero");
        state.quarantine.remove(oldest);
    }
}

#[derive(Default)]
pub struct MemoryFederationRepository {
    state: RwLock<MemoryState>,
    rate_state: Mutex<LocalRateState>,
}

impl MemoryFederationRepository {
    pub fn new() -> Self {
        Self::default()
    }
}

#[async_trait]
impl FederationRepository for MemoryFederationRepository {
    async fn install_peer(&self, policy: PeerPolicy) -> anyhow::Result<()> {
        let mut state = self.state.write().await;
        for key in &policy.keys {
            if let Some(existing) = state
                .peers
                .get(&(policy.remote_cell_id.clone(), key.key_id.clone()))
            {
                if existing.public_key != key.public_key {
                    bail!(
                        "public key for ({}, {}) is immutable",
                        policy.remote_cell_id,
                        key.key_id
                    );
                }
            }
        }
        let supplied_key_ids: HashSet<_> =
            policy.keys.iter().map(|key| key.key_id.clone()).collect();
        for ((cell_id, key_id), peer) in state.peers.iter_mut() {
            if cell_id == &policy.remote_cell_id {
                peer.state = policy.state.clone();
                peer.allow_neighbourhood = policy.allow_neighbourhood;
                peer.allowed_event_types = policy.allowed_event_types.clone();
                if !supplied_key_ids.contains(key_id) {
                    peer.key_active = false;
                }
            }
        }
        for key in policy.keys {
            state.peers.insert(
                (policy.remote_cell_id.clone(), key.key_id),
                ResolvedPeer {
                    state: policy.state.clone(),
                    allow_neighbourhood: policy.allow_neighbourhood,
                    allowed_event_types: policy.allowed_event_types.clone(),
                    public_key: key.public_key,
                    key_active: key.active,
                },
            );
        }
        Ok(())
    }

    async fn resolve_peer(
        &self,
        cell_id: &str,
        key_id: &str,
    ) -> anyhow::Result<Option<ResolvedPeer>> {
        Ok(self
            .state
            .read()
            .await
            .peers
            .get(&(cell_id.to_string(), key_id.to_string()))
            .cloned())
    }

    async fn check_rate_limit(
        &self,
        scope: &str,
        subject: &str,
        limit: u32,
    ) -> anyhow::Result<bool> {
        let mut state = self
            .rate_state
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        Ok(state.allow(scope, subject, limit))
    }

    async fn quarantine(
        &self,
        event: &FederationEvent,
        reason: &str,
    ) -> anyhow::Result<ReceiveOutcome> {
        let mut state = self.state.write().await;
        let digest = envelope_sha256(event)?;
        push_memory_quarantine_once(&mut state, event, reason, digest);
        Ok(ReceiveOutcome::quarantined(event, reason))
    }

    async fn accept_verified(
        &self,
        event: &FederationEvent,
        origin_rate_subject: &str,
        origin_rate_limit: u32,
    ) -> anyhow::Result<ReceiveOutcome> {
        // Hold the same write lock used by install_peer so a policy/key update
        // cannot commit between this final authorization check and acceptance.
        let mut state = self.state.write().await;
        let Some(peer) = state
            .peers
            .get(&(event.origin_cell_id.clone(), event.key_id.clone()))
            .cloned()
        else {
            return Ok(ReceiveOutcome::rejected(event));
        };
        if verify_signature(event, peer.public_key).is_err() {
            return Ok(ReceiveOutcome::rejected(event));
        }
        let digest = envelope_sha256(event)?;
        let policy_rejection = peer_policy_rejection(&peer, event);
        if policy_rejection.is_some() {
            let origin_allowed = {
                let mut rate_state = self
                    .rate_state
                    .lock()
                    .unwrap_or_else(|poisoned| poisoned.into_inner());
                rate_state.allow(
                    RATE_SCOPE_RECEIVE_ORIGIN,
                    origin_rate_subject,
                    origin_rate_limit,
                )
            };
            if !origin_allowed {
                return Err(ReceiveRateLimitExceeded.into());
            }
        }
        let existing_digest = if let Some(existing_digest) = state.inbox.get(&event.event_id) {
            Some(existing_digest.clone())
        } else if let Some(existing) = state
            .outbox
            .iter()
            .find(|existing| existing.event_id == event.event_id)
        {
            Some(envelope_sha256(existing)?)
        } else {
            None
        };
        if existing_digest
            .as_ref()
            .is_some_and(|existing| existing == &digest)
        {
            if let Some(reason) = policy_rejection {
                return Ok(ReceiveOutcome::quarantined(event, reason));
            }
            return Ok(ReceiveOutcome::duplicate(event));
        }
        if policy_rejection.is_none() {
            let origin_allowed = {
                let mut rate_state = self
                    .rate_state
                    .lock()
                    .unwrap_or_else(|poisoned| poisoned.into_inner());
                rate_state.allow(
                    RATE_SCOPE_RECEIVE_ORIGIN,
                    origin_rate_subject,
                    origin_rate_limit,
                )
            };
            if !origin_allowed {
                return Err(ReceiveRateLimitExceeded.into());
            }
        }
        if let Some(reason) = policy_rejection {
            push_memory_quarantine_once(&mut state, event, reason, digest);
            return Ok(ReceiveOutcome::quarantined(event, reason));
        }
        if existing_digest.is_some() {
            push_memory_quarantine_once(
                &mut state,
                event,
                "event id collision with different envelope",
                digest,
            );
            return Ok(ReceiveOutcome::quarantined(
                event,
                "event id collision with different envelope",
            ));
        }
        if let Some(reason) = transition_rejection(state.objects.get(&event.object_address), event)
        {
            push_memory_quarantine_once(&mut state, event, &reason, digest);
            return Ok(ReceiveOutcome::quarantined(event, reason));
        }
        apply_event(&mut state.objects, event);
        state.inbox.insert(event.event_id, digest);
        Ok(ReceiveOutcome::applied(event))
    }

    async fn persist_local(&self, event: &FederationEvent) -> anyhow::Result<()> {
        let mut state = self.state.write().await;
        if state.inbox.contains_key(&event.event_id)
            || state
                .outbox
                .iter()
                .any(|existing| existing.event_id == event.event_id)
        {
            bail!("local federation event id already exists");
        }
        if let Some(reason) = transition_rejection(state.objects.get(&event.object_address), event)
        {
            bail!("local federation event rejected: {reason}");
        }
        apply_event(&mut state.objects, event);
        state.outbox.push(event.clone());
        Ok(())
    }

    async fn object(&self, address: &str) -> anyhow::Result<Option<FederatedObject>> {
        Ok(self.state.read().await.objects.get(address).cloned())
    }

    async fn pending_outbox(&self) -> anyhow::Result<Vec<FederationEvent>> {
        Ok(self.state.read().await.outbox.clone())
    }

    async fn quarantined(&self) -> anyhow::Result<Vec<QuarantinedEvent>> {
        Ok(self.state.read().await.quarantine.clone())
    }
}

#[derive(Clone)]
pub struct PostgresFederationRepository {
    pool: PgPool,
}

fn delivery_policy_sha256(policy: &PeerPolicy, endpoint: &str) -> anyhow::Result<String> {
    let mut event_types: Vec<_> = policy.allowed_event_types.iter().cloned().collect();
    event_types.sort();
    let payload = serde_json::json!({
        "schema_version": 1,
        "remote_cell_id": policy.remote_cell_id,
        "state": policy.state,
        "allow_neighbourhood": policy.allow_neighbourhood,
        "allowed_event_types": event_types,
        "delivery_base_url": endpoint,
    });
    Ok(hex::encode(Sha256::digest(serde_jcs::to_vec(&payload)?)))
}

impl PostgresFederationRepository {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }

    pub(crate) async fn reconcile_delivery_endpoints(
        &self,
        bindings: &[(PeerPolicy, Option<String>)],
    ) -> anyhow::Result<()> {
        let mut normalized = Vec::with_capacity(bindings.len());
        let mut cell_ids = Vec::with_capacity(bindings.len());
        let mut unique_cell_ids = HashSet::with_capacity(bindings.len());
        let mut has_duplicate_cell_ids = false;
        for (policy, endpoint) in bindings {
            let endpoint = endpoint
                .as_deref()
                .map(crate::federation_delivery::validate_delivery_base_url)
                .transpose()?;
            let fingerprint = endpoint
                .as_deref()
                .map(|endpoint| delivery_policy_sha256(policy, endpoint))
                .transpose()?;
            normalized.push((policy.clone(), endpoint, fingerprint));
            cell_ids.push(policy.remote_cell_id.clone());
            has_duplicate_cell_ids |= !unique_cell_ids.insert(policy.remote_cell_id.clone());
        }

        let mut tx = self.pool.begin().await?;
        let rows = sqlx::query(
            "SELECT remote_cell_id, delivery_base_url, delivery_policy_sha256 \
             FROM federation_peer_relationships \
             ORDER BY remote_cell_id FOR UPDATE",
        )
        .fetch_all(&mut *tx)
        .await?;

        let mut existing_peers = HashMap::with_capacity(rows.len());
        for row in rows {
            let id: String = row.try_get("remote_cell_id")?;
            let base_url: Option<String> = row.try_get("delivery_base_url")?;
            let fingerprint: Option<String> = row.try_get("delivery_policy_sha256")?;
            existing_peers.insert(id, (base_url, fingerprint));
        }

        if let Some((policy, _, _)) = normalized
            .iter()
            .find(|(policy, _, _)| !existing_peers.contains_key(&policy.remote_cell_id))
        {
            let cell_id = &policy.remote_cell_id;
            bail!("delivery endpoint references unknown peer {cell_id}");
        }

        if has_duplicate_cell_ids {
            sqlx::query(
                "UPDATE federation_peer_relationships \
                 SET delivery_base_url = NULL, delivery_policy_sha256 = NULL, updated_at = NOW() \
                 WHERE delivery_base_url IS NOT NULL \
                   AND NOT (remote_cell_id = ANY($1::text[]))",
            )
            .bind(&cell_ids)
            .execute(&mut *tx)
            .await?;

            // Runtime configuration rejects duplicate cell IDs. Keep the historical
            // sequential last-binding-wins behavior for any other internal caller
            // instead of giving duplicate VALUES rows database-dependent semantics.
            for (policy, endpoint, fingerprint) in normalized {
                let cell_id = &policy.remote_cell_id;
                let Some((previous_endpoint, previous_fingerprint)) = existing_peers.get(cell_id)
                else {
                    unreachable!("all delivery peers were checked while locked");
                };
                if previous_endpoint == &endpoint && previous_fingerprint == &fingerprint {
                    continue;
                }
                sqlx::query(
                    "UPDATE federation_peer_relationships \
                     SET delivery_base_url = $2, delivery_policy_sha256 = $3, updated_at = NOW() \
                     WHERE remote_cell_id = $1",
                )
                .bind(cell_id)
                .bind(&endpoint)
                .bind(&fingerprint)
                .execute(&mut *tx)
                .await?;
                existing_peers.insert(cell_id.clone(), (endpoint.clone(), fingerprint.clone()));
                if endpoint.is_some() && policy.state == "trusted" {
                    crate::federation_delivery::backfill_delivery_targets(
                        &mut tx,
                        std::slice::from_ref(cell_id),
                    )
                    .await?;
                }
            }
            tx.commit().await?;
            return Ok(());
        }

        let mut updates = Vec::with_capacity(existing_peers.len());
        let mut backfill_cell_ids = Vec::with_capacity(normalized.len());
        for (policy, endpoint, fingerprint) in normalized {
            let cell_id = policy.remote_cell_id;
            let Some((previous_endpoint, previous_fingerprint)) = existing_peers.get(&cell_id)
            else {
                unreachable!("all delivery peers were checked while locked");
            };
            if previous_endpoint == &endpoint && previous_fingerprint == &fingerprint {
                continue;
            }
            if endpoint.is_some() && policy.state == "trusted" {
                backfill_cell_ids.push(cell_id.clone());
            }
            updates.push((cell_id, endpoint, fingerprint));
        }
        for (cell_id, (previous_endpoint, _)) in &existing_peers {
            if previous_endpoint.is_some() && !unique_cell_ids.contains(cell_id) {
                updates.push((cell_id.clone(), None, None));
            }
        }

        updates.sort_unstable_by(|left, right| left.0.cmp(&right.0));
        backfill_cell_ids.sort_unstable();
        if !updates.is_empty() {
            let mut query = QueryBuilder::<Postgres>::new(
                "UPDATE federation_peer_relationships AS relationship \
                 SET delivery_base_url = desired.delivery_base_url, \
                     delivery_policy_sha256 = desired.delivery_policy_sha256, \
                     updated_at = NOW() \
                 FROM (",
            );
            query.push_values(
                updates.iter(),
                |mut values, (cell_id, endpoint, fingerprint)| {
                    values
                        .push_bind(cell_id)
                        .push_bind(endpoint)
                        .push_bind(fingerprint);
                },
            );
            query.push(
                ") AS desired(remote_cell_id, delivery_base_url, delivery_policy_sha256) \
                 WHERE relationship.remote_cell_id = desired.remote_cell_id",
            );
            let result = query.build().execute(&mut *tx).await?;
            if result.rows_affected() != u64::try_from(updates.len())? {
                bail!("delivery endpoint batch update did not cover every locked peer");
            }
        }
        if !backfill_cell_ids.is_empty() {
            crate::federation_delivery::backfill_delivery_targets(&mut tx, &backfill_cell_ids)
                .await?;
        }
        tx.commit().await?;
        Ok(())
    }
}

#[async_trait]
impl FederationRepository for PostgresFederationRepository {
    async fn install_peer(&self, policy: PeerPolicy) -> anyhow::Result<()> {
        let mut tx = self.pool.begin().await?;
        let mut event_types: Vec<_> = policy.allowed_event_types.iter().cloned().collect();
        event_types.sort();
        sqlx::query(
            "INSERT INTO federation_peer_relationships \
             (remote_cell_id, state, allow_neighbourhood, allowed_event_types, updated_at) \
             VALUES ($1, $2, $3, $4, NOW()) \
             ON CONFLICT (remote_cell_id) DO UPDATE SET \
               state = EXCLUDED.state, \
               allow_neighbourhood = EXCLUDED.allow_neighbourhood, \
               allowed_event_types = EXCLUDED.allowed_event_types, \
               updated_at = NOW()",
        )
        .bind(&policy.remote_cell_id)
        .bind(&policy.state)
        .bind(policy.allow_neighbourhood)
        .bind(serde_json::to_value(event_types)?)
        .execute(&mut *tx)
        .await?;
        let supplied_key_ids: Vec<_> = policy.keys.iter().map(|key| key.key_id.clone()).collect();
        sqlx::query(
            "UPDATE federation_peer_keys SET active = FALSE, \
             retired_at = COALESCE(retired_at, NOW()) \
             WHERE remote_cell_id = $1 AND NOT (key_id = ANY($2::text[]))",
        )
        .bind(&policy.remote_cell_id)
        .bind(&supplied_key_ids)
        .execute(&mut *tx)
        .await?;
        if !policy.keys.is_empty() {
            let mut key_ids = Vec::with_capacity(policy.keys.len());
            let mut public_keys = Vec::with_capacity(policy.keys.len());
            let mut actives = Vec::with_capacity(policy.keys.len());

            for key in &policy.keys {
                key_ids.push(key.key_id.clone());
                public_keys.push(key.public_key.to_vec());
                actives.push(key.active);
            }

            let upserted_key_ids: HashSet<String> = sqlx::query_scalar(
                "INSERT INTO federation_peer_keys \
                 (remote_cell_id, key_id, public_key, active, retired_at) \
                 SELECT $1, u.key_id, u.public_key, u.active, CASE WHEN u.active THEN NULL ELSE NOW() END \
                 FROM UNNEST($2::text[], $3::bytea[], $4::boolean[]) AS u(key_id, public_key, active) \
                 ON CONFLICT (remote_cell_id, key_id) DO UPDATE SET \
                   active = EXCLUDED.active, \
                   retired_at = CASE \
                     WHEN EXCLUDED.active THEN NULL \
                     ELSE COALESCE(federation_peer_keys.retired_at, NOW()) \
                   END \
                 WHERE federation_peer_keys.public_key = EXCLUDED.public_key \
                 RETURNING key_id",
            )
            .bind(&policy.remote_cell_id)
            .bind(&key_ids)
            .bind(&public_keys)
            .bind(&actives)
            .fetch_all(&mut *tx)
            .await?
            .into_iter()
            .collect();
            if upserted_key_ids.len() != policy.keys.len() {
                let mismatched_key_id = policy
                    .keys
                    .iter()
                    .find(|key| !upserted_key_ids.contains(&key.key_id))
                    .map(|key| key.key_id.as_str())
                    .unwrap_or("<unknown>");
                bail!(
                    "public key for ({}, {}) is immutable",
                    policy.remote_cell_id,
                    mismatched_key_id
                );
            }
        }
        tx.commit().await?;
        Ok(())
    }

    async fn resolve_peer(
        &self,
        cell_id: &str,
        key_id: &str,
    ) -> anyhow::Result<Option<ResolvedPeer>> {
        let row = sqlx::query(
            "SELECT r.state, r.allow_neighbourhood, r.allowed_event_types, k.public_key, k.active \
             FROM federation_peer_relationships r \
             JOIN federation_peer_keys k ON k.remote_cell_id = r.remote_cell_id \
             WHERE r.remote_cell_id = $1 AND k.key_id = $2",
        )
        .bind(cell_id)
        .bind(key_id)
        .fetch_optional(&self.pool)
        .await?;
        let Some(row) = row else {
            return Ok(None);
        };
        let public_key: Vec<u8> = row.try_get("public_key")?;
        let public_key: [u8; 32] = public_key
            .try_into()
            .map_err(|_| anyhow::anyhow!("stored peer public key is not 32 bytes"))?;
        let event_types: Value = row.try_get("allowed_event_types")?;
        let event_types: Vec<String> = serde_json::from_value(event_types)?;
        Ok(Some(ResolvedPeer {
            state: row.try_get("state")?,
            allow_neighbourhood: row.try_get("allow_neighbourhood")?,
            allowed_event_types: event_types.into_iter().collect(),
            public_key,
            key_active: row.try_get("active")?,
        }))
    }

    async fn check_rate_limit(
        &self,
        scope: &str,
        subject: &str,
        limit: u32,
    ) -> anyhow::Result<bool> {
        increment_federation_rate_limit(&self.pool, scope, subject, limit).await
    }

    async fn quarantine(
        &self,
        event: &FederationEvent,
        reason: &str,
    ) -> anyhow::Result<ReceiveOutcome> {
        let mut tx = self.pool.begin().await?;
        let digest = envelope_sha256(event)?;
        quarantine_verified_in_tx(&mut tx, event, reason, &digest).await?;
        tx.commit().await?;
        Ok(ReceiveOutcome::quarantined(event, reason))
    }

    async fn accept_verified(
        &self,
        event: &FederationEvent,
        origin_rate_subject: &str,
        origin_rate_limit: u32,
    ) -> anyhow::Result<ReceiveOutcome> {
        let mut tx = self.pool.begin().await?;

        // Lock the current relationship and key in shared mode. Peer policy
        // updates need row-update locks, so their commit is ordered before or
        // after this acceptance transaction rather than racing through it.
        let peer_row = sqlx::query(
            "SELECT r.state, r.allow_neighbourhood, r.allowed_event_types, k.public_key, k.active \
             FROM federation_peer_relationships r \
             JOIN federation_peer_keys k ON k.remote_cell_id = r.remote_cell_id \
             WHERE r.remote_cell_id = $1 AND k.key_id = $2 \
             FOR SHARE OF r, k",
        )
        .bind(&event.origin_cell_id)
        .bind(&event.key_id)
        .fetch_optional(&mut *tx)
        .await?;
        let Some(peer_row) = peer_row else {
            tx.rollback().await?;
            return Ok(ReceiveOutcome::rejected(event));
        };
        let public_key: Vec<u8> = peer_row.try_get("public_key")?;
        let public_key: [u8; 32] = public_key
            .try_into()
            .map_err(|_| anyhow::anyhow!("stored peer public key is not 32 bytes"))?;
        let event_types: Value = peer_row.try_get("allowed_event_types")?;
        let event_types: Vec<String> = serde_json::from_value(event_types)?;
        let peer = ResolvedPeer {
            state: peer_row.try_get("state")?,
            allow_neighbourhood: peer_row.try_get("allow_neighbourhood")?,
            allowed_event_types: event_types.into_iter().collect(),
            public_key,
            key_active: peer_row.try_get("active")?,
        };
        if verify_signature(event, peer.public_key).is_err() {
            tx.rollback().await?;
            return Ok(ReceiveOutcome::rejected(event));
        }
        let digest = envelope_sha256(event)?;
        let policy_rejection = peer_policy_rejection(&peer, event);
        if policy_rejection.is_some()
            && !increment_federation_rate_limit_in_tx(
                &mut tx,
                RATE_SCOPE_RECEIVE_ORIGIN,
                origin_rate_subject,
                origin_rate_limit,
            )
            .await?
        {
            tx.rollback().await?;
            return Err(ReceiveRateLimitExceeded.into());
        }

        // A lock-free pre-read lets established exact duplicates return without
        // queueing behind the per-event advisory lock. New/colliding events are
        // re-read after taking the lock before any mutation.
        let existing_digests = event_receipt_digests_in_tx(&mut tx, event.event_id).await?;
        if !existing_digests.is_empty()
            && existing_digests
                .iter()
                .all(|existing_digest| existing_digest == &digest)
        {
            if let Some(reason) = policy_rejection {
                tx.commit().await?;
                return Ok(ReceiveOutcome::quarantined(event, reason));
            }
            tx.rollback().await?;
            return Ok(ReceiveOutcome::duplicate(event));
        }
        if policy_rejection.is_none()
            && !increment_federation_rate_limit_in_tx(
                &mut tx,
                RATE_SCOPE_RECEIVE_ORIGIN,
                origin_rate_subject,
                origin_rate_limit,
            )
            .await?
        {
            tx.rollback().await?;
            return Err(ReceiveRateLimitExceeded.into());
        }

        lock_event_receipt(&mut tx, event.event_id).await?;
        let existing_digests = event_receipt_digests_in_tx(&mut tx, event.event_id).await?;
        if !existing_digests.is_empty()
            && existing_digests
                .iter()
                .all(|existing_digest| existing_digest == &digest)
        {
            if let Some(reason) = policy_rejection {
                tx.commit().await?;
                return Ok(ReceiveOutcome::quarantined(event, reason));
            }
            tx.rollback().await?;
            return Ok(ReceiveOutcome::duplicate(event));
        }
        if let Some(reason) = policy_rejection {
            quarantine_verified_in_tx(&mut tx, event, reason, &digest).await?;
            tx.commit().await?;
            return Ok(ReceiveOutcome::quarantined(event, reason));
        }
        if !existing_digests.is_empty() {
            let reason = "event id collision with different envelope";
            quarantine_verified_in_tx(&mut tx, event, reason, &digest).await?;
            tx.commit().await?;
            return Ok(ReceiveOutcome::quarantined(event, reason));
        }

        lock_object_transition(&mut tx, &event.object_address).await?;
        let current = sqlx::query(
            "SELECT object_address, origin_cell_id, object_kind, object_version, scope, \
                    neighbourhood_targets, payload, \
                    deleted_at, updated_at \
             FROM federation_objects WHERE object_address = $1 FOR UPDATE",
        )
        .bind(&event.object_address)
        .fetch_optional(&mut *tx)
        .await?;
        let current = current.map(row_to_object).transpose()?;
        if let Some(reason) = transition_rejection(current.as_ref(), event) {
            quarantine_verified_in_tx(&mut tx, event, &reason, &digest).await?;
            tx.commit().await?;
            return Ok(ReceiveOutcome::quarantined(event, reason));
        }

        upsert_object(&mut tx, event).await?;
        reserve_event_receipt_in_tx(&mut tx, event.event_id, &digest, "inbox").await?;
        sqlx::query(
            "INSERT INTO federation_inbox \
             (event_id, origin_cell_id, object_address, object_version, event_type, \
              schema_version, scope, envelope_sha256, envelope) \
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
        )
        .bind(event.event_id)
        .bind(&event.origin_cell_id)
        .bind(&event.object_address)
        .bind(event.object_version)
        .bind(&event.event_type)
        .bind(i32::from(event.schema_version))
        .bind(&event.scope)
        .bind(digest)
        .bind(serde_json::to_value(event)?)
        .execute(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(ReceiveOutcome::applied(event))
    }

    async fn persist_local(&self, event: &FederationEvent) -> anyhow::Result<()> {
        let mut tx = self.pool.begin().await?;
        lock_event_receipt(&mut tx, event.event_id).await?;
        if !event_receipt_digests_in_tx(&mut tx, event.event_id)
            .await?
            .is_empty()
        {
            bail!("local federation event id already exists");
        }
        lock_object_transition(&mut tx, &event.object_address).await?;
        let current = sqlx::query(
            "SELECT object_address, origin_cell_id, object_kind, object_version, scope, \
                    neighbourhood_targets, payload, \
                    deleted_at, updated_at \
             FROM federation_objects WHERE object_address = $1 FOR UPDATE",
        )
        .bind(&event.object_address)
        .fetch_optional(&mut *tx)
        .await?;
        let current = current.map(row_to_object).transpose()?;
        if let Some(reason) = transition_rejection(current.as_ref(), event) {
            bail!("local federation event rejected: {reason}");
        }
        upsert_object(&mut tx, event).await?;
        let digest = envelope_sha256(event)?;
        reserve_event_receipt_in_tx(&mut tx, event.event_id, &digest, "outbox").await?;
        sqlx::query(
            "INSERT INTO federation_outbox \
             (event_id, object_address, object_version, envelope_sha256, envelope) \
             VALUES ($1, $2, $3, $4, $5)",
        )
        .bind(event.event_id)
        .bind(&event.object_address)
        .bind(event.object_version)
        .bind(digest)
        .bind(serde_json::to_value(event)?)
        .execute(&mut *tx)
        .await?;
        crate::federation_delivery::enqueue_delivery_targets(&mut tx, event).await?;
        tx.commit().await?;
        Ok(())
    }

    async fn object(&self, address: &str) -> anyhow::Result<Option<FederatedObject>> {
        sqlx::query(
            "SELECT object_address, origin_cell_id, object_kind, object_version, scope, \
                    neighbourhood_targets, payload, \
                    deleted_at, updated_at \
             FROM federation_objects WHERE object_address = $1",
        )
        .bind(address)
        .fetch_optional(&self.pool)
        .await?
        .map(row_to_object)
        .transpose()
    }

    async fn pending_outbox(&self) -> anyhow::Result<Vec<FederationEvent>> {
        let rows =
            sqlx::query("SELECT envelope FROM federation_outbox ORDER BY created_at, event_id")
                .fetch_all(&self.pool)
                .await?;
        rows.into_iter()
            .map(|row| {
                let value: Value = row.try_get("envelope")?;
                Ok(serde_json::from_value(value)?)
            })
            .collect()
    }

    async fn quarantined(&self) -> anyhow::Result<Vec<QuarantinedEvent>> {
        let rows = sqlx::query(
            "SELECT event_id, origin_cell_id, reason, envelope_sha256, received_at \
             FROM federation_quarantine ORDER BY received_at, id",
        )
        .fetch_all(&self.pool)
        .await?;
        rows.into_iter()
            .map(|row| {
                Ok(QuarantinedEvent {
                    event_id: row.try_get("event_id")?,
                    origin_cell_id: row.try_get("origin_cell_id")?,
                    reason: row.try_get("reason")?,
                    envelope_sha256: row.try_get("envelope_sha256")?,
                    received_at: row.try_get("received_at")?,
                })
            })
            .collect()
    }
}

async fn increment_federation_rate_limit(
    pool: &PgPool,
    scope: &str,
    subject: &str,
    limit: u32,
) -> anyhow::Result<bool> {
    if limit == 0 {
        return Ok(true);
    }
    let count: i64 = sqlx::query_scalar(
        "WITH database_window AS (\
           SELECT floor(extract(epoch FROM clock_timestamp()) / $3)::bigint * $3 AS window_start\
         ) \
         INSERT INTO federation_rate_limit_counters \
         (scope, subject, window_start, window_seconds, request_count, expires_at) \
         SELECT $1, $2, window_start, $3, 1, to_timestamp(window_start + $3 + 60) \
         FROM database_window \
         ON CONFLICT (scope, subject, window_start, window_seconds) \
         DO UPDATE SET request_count = federation_rate_limit_counters.request_count + 1 \
         RETURNING request_count",
    )
    .bind(scope)
    .bind(subject)
    .bind(i32::try_from(RATE_LIMIT_WINDOW_SECONDS)?)
    .fetch_one(pool)
    .await?;
    if count == 1 {
        sqlx::query("DELETE FROM federation_rate_limit_counters WHERE expires_at <= NOW()")
            .execute(pool)
            .await?;
    }
    Ok(count <= i64::from(limit))
}

async fn increment_federation_rate_limit_in_tx(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    scope: &str,
    subject: &str,
    limit: u32,
) -> anyhow::Result<bool> {
    if limit == 0 {
        return Ok(true);
    }
    let count: i64 = sqlx::query_scalar(
        "WITH database_window AS (\
           SELECT floor(extract(epoch FROM clock_timestamp()) / $3)::bigint * $3 AS window_start\
         ) \
         INSERT INTO federation_rate_limit_counters \
         (scope, subject, window_start, window_seconds, request_count, expires_at) \
         SELECT $1, $2, window_start, $3, 1, to_timestamp(window_start + $3 + 60) \
         FROM database_window \
         ON CONFLICT (scope, subject, window_start, window_seconds) \
         DO UPDATE SET request_count = federation_rate_limit_counters.request_count + 1 \
         RETURNING request_count",
    )
    .bind(scope)
    .bind(subject)
    .bind(i32::try_from(RATE_LIMIT_WINDOW_SECONDS)?)
    .fetch_one(&mut **tx)
    .await?;
    if count == 1 {
        sqlx::query("DELETE FROM federation_rate_limit_counters WHERE expires_at <= NOW()")
            .execute(&mut **tx)
            .await?;
    }
    Ok(count <= i64::from(limit))
}

async fn event_receipt_digests_in_tx(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    event_id: Uuid,
) -> anyhow::Result<Vec<String>> {
    Ok(sqlx::query_scalar(
        "SELECT envelope_sha256 FROM federation_event_receipts WHERE event_id = $1",
    )
    .bind(event_id)
    .fetch_all(&mut **tx)
    .await?)
}

async fn reserve_event_receipt_in_tx(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    event_id: Uuid,
    digest: &str,
    direction: &str,
) -> anyhow::Result<()> {
    sqlx::query(
        "INSERT INTO federation_event_receipts \
         (event_id, envelope_sha256, direction, recorded_at) \
         VALUES ($1, $2, $3, clock_timestamp())",
    )
    .bind(event_id)
    .bind(digest)
    .bind(direction)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

async fn quarantine_verified_in_tx(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    event: &FederationEvent,
    reason: &str,
    digest: &str,
) -> anyhow::Result<()> {
    sqlx::query(
        "SELECT pg_advisory_xact_lock(\
         hashtextextended('federation-quarantine:' || $1::text, 0))",
    )
    .bind(&event.origin_cell_id)
    .execute(&mut **tx)
    .await?;
    sqlx::query(
        "DELETE FROM federation_quarantine \
         WHERE origin_cell_id = $1 \
           AND received_at < NOW() - make_interval(days => $2)",
    )
    .bind(&event.origin_cell_id)
    .bind(i32::try_from(QUARANTINE_RETENTION_DAYS)?)
    .execute(&mut **tx)
    .await?;
    sqlx::query(
        "INSERT INTO federation_quarantine \
         (event_id, origin_cell_id, reason, envelope_sha256, envelope) \
         VALUES ($1, $2, $3, $4, $5) \
         ON CONFLICT (event_id, envelope_sha256, reason) DO NOTHING",
    )
    .bind(event.event_id)
    .bind(&event.origin_cell_id)
    .bind(reason)
    .bind(digest)
    .bind(serde_json::to_value(event)?)
    .execute(&mut **tx)
    .await?;
    sqlx::query(
        "DELETE FROM federation_quarantine WHERE id IN (\
           SELECT id FROM federation_quarantine \
           WHERE origin_cell_id = $1 \
           ORDER BY received_at DESC, id DESC OFFSET $2\
         )",
    )
    .bind(&event.origin_cell_id)
    .bind(i64::try_from(QUARANTINE_MAX_PER_ORIGIN)?)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

async fn lock_event_receipt(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    event_id: Uuid,
) -> anyhow::Result<()> {
    sqlx::query(
        "SELECT pg_advisory_xact_lock(hashtextextended('federation-event:' || $1::text, 0))",
    )
    .bind(event_id)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

async fn lock_object_transition(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    object_address: &str,
) -> anyhow::Result<()> {
    sqlx::query("SELECT pg_advisory_xact_lock(hashtextextended($1::text, 0))")
        .bind(object_address)
        .execute(&mut **tx)
        .await?;
    Ok(())
}

async fn upsert_object(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    event: &FederationEvent,
) -> anyhow::Result<()> {
    let deleted = event.event_type == EVENT_DELETED;
    let neighbourhood_targets = canonical_neighbourhood_targets(event);
    sqlx::query(
        "INSERT INTO federation_objects \
         (object_address, origin_cell_id, object_kind, object_version, scope, \
          neighbourhood_targets, payload, deleted_at, updated_at) \
         VALUES ($1, $2, $3, $4, $5, $6, $7, CASE WHEN $8 THEN NOW() ELSE NULL END, NOW()) \
         ON CONFLICT (object_address) DO UPDATE SET \
           object_version = EXCLUDED.object_version, \
           payload = EXCLUDED.payload, \
           deleted_at = EXCLUDED.deleted_at, \
           updated_at = NOW()",
    )
    .bind(&event.object_address)
    .bind(&event.origin_cell_id)
    .bind(&event.object_kind)
    .bind(event.object_version)
    .bind(&event.scope)
    .bind(serde_json::to_value(neighbourhood_targets)?)
    .bind(&event.payload)
    .bind(deleted)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

fn row_to_object(row: sqlx::postgres::PgRow) -> anyhow::Result<FederatedObject> {
    let deleted_at: Option<DateTime<Utc>> = row.try_get("deleted_at")?;
    Ok(FederatedObject {
        object_address: row.try_get("object_address")?,
        origin_cell_id: row.try_get("origin_cell_id")?,
        object_kind: row.try_get("object_kind")?,
        object_version: row.try_get("object_version")?,
        scope: row.try_get("scope")?,
        neighbourhood_targets: serde_json::from_value(row.try_get("neighbourhood_targets")?)?,
        payload: row.try_get("payload")?,
        deleted: deleted_at.is_some(),
        updated_at: row.try_get("updated_at")?,
    })
}

fn transition_rejection(
    current: Option<&FederatedObject>,
    event: &FederationEvent,
) -> Option<String> {
    match current {
        None if event.object_version != 1 || event.previous_version.is_some() => {
            Some("first observed object version must be 1 without previous_version".to_string())
        }
        None => None,
        Some(current) if current.origin_cell_id != event.origin_cell_id => {
            Some("origin cell cannot change".to_string())
        }
        Some(current) if current.object_kind != event.object_kind => {
            Some("object kind cannot change".to_string())
        }
        Some(current) if current.scope != event.scope => {
            Some("object scope cannot change".to_string())
        }
        Some(current)
            if current.neighbourhood_targets != canonical_neighbourhood_targets(event) =>
        {
            Some("object neighbourhood audience cannot change".to_string())
        }
        Some(current) if event.object_version <= current.object_version => {
            Some("object version is stale or replayed".to_string())
        }
        Some(current)
            if event.object_version != current.object_version + 1
                || event.previous_version != Some(current.object_version) =>
        {
            Some("object version gap or previous_version mismatch".to_string())
        }
        Some(_) => None,
    }
}

fn apply_event(objects: &mut HashMap<String, FederatedObject>, event: &FederationEvent) {
    objects.insert(
        event.object_address.clone(),
        FederatedObject {
            object_address: event.object_address.clone(),
            origin_cell_id: event.origin_cell_id.clone(),
            object_kind: event.object_kind.clone(),
            object_version: event.object_version,
            scope: event.scope.clone(),
            neighbourhood_targets: canonical_neighbourhood_targets(event),
            payload: event.payload.clone(),
            deleted: event.event_type == EVENT_DELETED,
            updated_at: Utc::now(),
        },
    );
}

fn canonical_neighbourhood_targets(event: &FederationEvent) -> Vec<String> {
    let mut targets = event.neighbourhood_targets.clone();
    targets.sort();
    targets.dedup();
    targets
}

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

fn deserialize_canonical_uuid<'de, D>(deserializer: D) -> Result<Uuid, D::Error>
where
    D: Deserializer<'de>,
{
    let raw = String::deserialize(deserializer)?;
    let parsed = Uuid::parse_str(&raw).map_err(serde::de::Error::custom)?;
    let canonical = parsed.hyphenated().to_string();
    if raw != canonical {
        return Err(serde::de::Error::custom(
            "event_id must use lowercase hyphenated UUID form",
        ));
    }
    Ok(parsed)
}

fn deserialize_canonical_utc<'de, D>(deserializer: D) -> Result<DateTime<Utc>, D::Error>
where
    D: Deserializer<'de>,
{
    let raw = String::deserialize(deserializer)?;
    let parsed = DateTime::parse_from_rfc3339(&raw)
        .map_err(serde::de::Error::custom)?
        .with_timezone(&Utc);
    let canonical = parsed.to_rfc3339_opts(SecondsFormat::AutoSi, true);
    if raw != canonical {
        return Err(serde::de::Error::custom(
            "created_at must use canonical UTC RFC3339 form",
        ));
    }
    Ok(parsed)
}

// Signature domain: every wire field except `signature`, canonically encoded with JCS.
// This is intentionally distinct from `envelope_sha256`, which identifies the exact
// signed envelope including the signature for replay/collision bookkeeping.
fn signing_bytes(event: &FederationEvent) -> anyhow::Result<Vec<u8>> {
    Ok(serde_jcs::to_vec(&SigningPayload {
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
    })?)
}

// Envelope identity: hash the complete signed envelope, including `signature`.
pub(crate) fn envelope_sha256(event: &FederationEvent) -> anyhow::Result<String> {
    let bytes = serde_jcs::to_vec(event)?;
    Ok(hex::encode(Sha256::digest(bytes)))
}

fn verify_signature(event: &FederationEvent, public_key: [u8; 32]) -> anyhow::Result<()> {
    let signature = URL_SAFE_NO_PAD
        .decode(&event.signature)
        .context("signature is not valid base64url")?;
    let signature = Signature::from_slice(&signature).context("signature must be 64 bytes")?;
    let verifying_key =
        VerifyingKey::from_bytes(&public_key).context("peer public key is invalid")?;
    verifying_key
        .verify_strict(&signing_bytes(event)?, &signature)
        .context("event signature verification failed")
}

fn peer_policy_rejection(peer: &ResolvedPeer, event: &FederationEvent) -> Option<&'static str> {
    if peer.state == "blocked" {
        return Some("peer is blocked");
    }
    if !peer.key_active {
        return Some("peer key is inactive");
    }
    if !peer.allowed_event_types.contains(&event.event_type) {
        return Some("event type is not allowed for this peer");
    }
    if event.scope == SCOPE_NEIGHBOURHOOD && !peer.allow_neighbourhood {
        return Some("neighbourhood scope is not allowed for this peer");
    }
    None
}

fn validate_event_shape(
    event: &FederationEvent,
    receiver_cell_id: Option<&str>,
    enforce_size_limit: bool,
) -> anyhow::Result<()> {
    if event.protocol_version != FEDERATION_PROTOCOL_VERSION {
        bail!("unsupported protocol version");
    }
    if event.schema_version != FEDERATION_SCHEMA_VERSION {
        bail!("unsupported schema version");
    }
    validate_event_type(&event.event_type)?;
    validate_cell_id(&event.origin_cell_id)?;
    validate_key_id(&event.key_id)?;
    validate_actor(&event.actor)?;
    let (address_cell, address_kind) = validate_object_address(&event.object_address)?;
    if address_cell != event.origin_cell_id {
        bail!("object address origin does not match event origin");
    }
    if address_kind != event.object_kind {
        bail!("object address kind does not match event object_kind");
    }
    if event.object_version <= 0 {
        bail!("object_version must be positive");
    }
    if event.object_version == 1 {
        if event.previous_version.is_some() {
            bail!("version 1 must not declare previous_version");
        }
    } else if event.previous_version != Some(event.object_version - 1) {
        bail!("previous_version must equal object_version - 1");
    }
    if event.created_at > Utc::now() + Duration::seconds(MAX_CLOCK_SKEW_SECONDS) {
        bail!("event creation time is too far in the future");
    }
    if enforce_size_limit && serde_json::to_vec(event)?.len() > MAX_EVENT_BYTES {
        bail!("event exceeds maximum envelope size");
    }
    match event.scope.as_str() {
        SCOPE_GLOBAL => {
            if !event.neighbourhood_targets.is_empty() {
                bail!("global events must not declare neighbourhood targets");
            }
        }
        SCOPE_NEIGHBOURHOOD => {
            if event.neighbourhood_targets.is_empty() {
                bail!("neighbourhood events need explicit target cells");
            }
            let mut unique = HashSet::new();
            for target in &event.neighbourhood_targets {
                validate_cell_id(target)?;
                if !unique.insert(target) {
                    bail!("neighbourhood target cells must be unique");
                }
            }
            if let Some(receiver) = receiver_cell_id {
                if !event
                    .neighbourhood_targets
                    .iter()
                    .any(|target| target == receiver)
                {
                    bail!("receiver cell is not included in neighbourhood targets");
                }
            }
        }
        "private" | "local" => bail!("private or local events are not externally federable"),
        _ => bail!("unsupported event scope"),
    }
    match event.event_type.as_str() {
        EVENT_UPSERTED if !event.payload.is_object() => {
            bail!("upsert events require an object payload")
        }
        EVENT_DELETED if !event.payload.is_null() => bail!("delete events require a null payload"),
        _ => {}
    }
    Ok(())
}

fn validate_event_type(value: &str) -> anyhow::Result<()> {
    if value != EVENT_UPSERTED && value != EVENT_DELETED {
        bail!("unsupported event type");
    }
    Ok(())
}

fn validate_actor(value: &str) -> anyhow::Result<()> {
    if value.is_empty() || value.chars().count() > 128 || value.chars().any(char::is_control) {
        bail!("actor must be a non-empty control-free string of at most 128 characters");
    }
    Ok(())
}

fn validate_cell_id(value: &str) -> anyhow::Result<()> {
    if !(3..=64).contains(&value.len())
        || !value.bytes().all(|byte| {
            byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'.' || byte == b'-'
        })
        || !value
            .as_bytes()
            .first()
            .is_some_and(u8::is_ascii_alphanumeric)
        || !value
            .as_bytes()
            .last()
            .is_some_and(u8::is_ascii_alphanumeric)
    {
        bail!("cell id must be 3-64 lowercase DNS-like characters");
    }
    Ok(())
}

fn validate_key_id(value: &str) -> anyhow::Result<()> {
    if !(1..=64).contains(&value.len())
        || !value.bytes().all(|byte| {
            byte.is_ascii_alphanumeric() || byte == b'.' || byte == b'-' || byte == b'_'
        })
    {
        bail!("key id contains unsupported characters");
    }
    Ok(())
}

fn validate_object_address(value: &str) -> anyhow::Result<(String, String)> {
    let rest = value
        .strip_prefix("wg://")
        .ok_or_else(|| anyhow::anyhow!("object address must use wg://"))?;
    let parts: Vec<_> = rest.split('/').collect();
    if parts.len() != 3 {
        bail!("object address must be wg://<cell>/<kind>/<id>");
    }
    validate_cell_id(parts[0])?;
    if !matches!(parts[1], "node" | "edge" | "shared-room") {
        bail!("object address kind is unsupported");
    }
    if parts[2].is_empty()
        || parts[2].len() > 128
        || !parts[2].bytes().all(|byte| {
            byte.is_ascii_alphanumeric()
                || byte == b'.'
                || byte == b'-'
                || byte == b'_'
                || byte == b'~'
        })
    {
        bail!("object address id contains unsupported characters");
    }
    Ok((parts[0].to_string(), parts[1].to_string()))
}

fn validate_public_base_url(value: &str) -> anyhow::Result<()> {
    let url = Url::parse(value).context("public federation base URL is invalid")?;
    if url.scheme() != "https" {
        bail!("public federation base URL must use https");
    }
    if url.host_str().is_none() || url.username() != "" || url.password().is_some() {
        bail!("public federation base URL must contain a host and no credentials");
    }
    if url.query().is_some() || url.fragment().is_some() {
        bail!("public federation base URL must not contain query or fragment");
    }
    Ok(())
}

#[derive(Debug, Deserialize)]
struct ObjectQuery {
    address: String,
}

async fn cell_descriptor(State(service): State<FederationService>) -> Json<CellDescriptor> {
    Json(service.descriptor())
}

#[derive(Debug)]
struct InvalidFederationEvent(String);

impl std::fmt::Display for InvalidFederationEvent {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(&self.0)
    }
}

impl std::error::Error for InvalidFederationEvent {}

#[derive(Debug)]
struct ReceiveRateLimitExceeded;

impl std::fmt::Display for ReceiveRateLimitExceeded {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str("federation receive rate limit exceeded")
    }
}

impl std::error::Error for ReceiveRateLimitExceeded {}

async fn receive_rate_limit_guard(
    State(service): State<FederationService>,
    request: Request<Body>,
    next: Next,
) -> Result<Response, ApiError> {
    if let Some(connect_info) = request.extensions().get::<ConnectInfo<SocketAddr>>() {
        let client_ip = client_ip_or_peer(connect_info.0, request.headers(), "federation-receive");
        if !service.allow_receive_client(&client_ip.to_string()) {
            return Err(ApiError::too_many_requests(
                "federation client receive rate limit exceeded",
            ));
        }
    }
    if !service
        .allow_receive_global()
        .await
        .map_err(ApiError::internal)?
    {
        return Err(ApiError::too_many_requests(
            "federation receive circuit breaker exceeded",
        ));
    }
    Ok(next.run(request).await)
}

async fn object_read_rate_limit_guard(
    State(service): State<FederationService>,
    request: Request<Body>,
    next: Next,
) -> Result<Response, ApiError> {
    if let Some(connect_info) = request.extensions().get::<ConnectInfo<SocketAddr>>() {
        let client_ip =
            client_ip_or_peer(connect_info.0, request.headers(), "federation-object-read");
        if !service.allow_object_read_client(&client_ip.to_string()) {
            return Err(ApiError::too_many_requests(
                "federation client object read rate limit exceeded",
            ));
        }
    }
    if !service
        .allow_object_read_global()
        .await
        .map_err(ApiError::internal)?
    {
        return Err(ApiError::too_many_requests(
            "federation object read circuit breaker exceeded",
        ));
    }
    Ok(next.run(request).await)
}

async fn receive_event(
    State(service): State<FederationService>,
    payload: Result<Json<FederationEvent>, JsonRejection>,
) -> Result<(StatusCode, Json<ReceiveOutcome>), ApiError> {
    let Json(event) = payload.map_err(|rejection| match rejection.status() {
        StatusCode::UNSUPPORTED_MEDIA_TYPE => ApiError::unsupported_media_type(),
        StatusCode::PAYLOAD_TOO_LARGE => ApiError::payload_too_large(),
        _ => ApiError::bad_request("invalid federation event envelope"),
    })?;
    let outcome = match service.receive_body_limited(event).await {
        Ok(outcome) => outcome,
        Err(error) if error.downcast_ref::<InvalidFederationEvent>().is_some() => {
            return Err(ApiError::bad_request("invalid federation event"));
        }
        Err(error) if error.downcast_ref::<ReceiveRateLimitExceeded>().is_some() => {
            return Err(ApiError::too_many_requests(
                "federation receive rate limit exceeded",
            ));
        }
        Err(error) => return Err(ApiError::internal(error)),
    };
    let status = match outcome.status {
        ReceiveStatus::Applied => StatusCode::CREATED,
        ReceiveStatus::Duplicate => StatusCode::OK,
        ReceiveStatus::Rejected => StatusCode::ACCEPTED,
        ReceiveStatus::Quarantined => StatusCode::ACCEPTED,
    };
    Ok((status, Json(outcome)))
}

async fn resolve_object(
    State(service): State<FederationService>,
    Query(query): Query<ObjectQuery>,
) -> Result<Json<FederatedObject>, ApiError> {
    let object = service
        .object(&query.address)
        .await
        .map_err(ApiError::bad_request)?
        .filter(|object| object.scope == SCOPE_GLOBAL && !object.deleted)
        .ok_or_else(|| ApiError::not_found("federated object not found"))?;
    Ok(Json(object))
}

#[derive(Debug)]
struct ApiError {
    status: StatusCode,
    message: String,
}

impl ApiError {
    fn bad_request(error: impl std::fmt::Display) -> Self {
        Self {
            status: StatusCode::BAD_REQUEST,
            message: error.to_string(),
        }
    }

    fn unsupported_media_type() -> Self {
        Self {
            status: StatusCode::UNSUPPORTED_MEDIA_TYPE,
            message: "federation event content type must be application/json".to_string(),
        }
    }

    fn payload_too_large() -> Self {
        Self {
            status: StatusCode::PAYLOAD_TOO_LARGE,
            message: "federation event envelope exceeds the size limit".to_string(),
        }
    }

    fn not_found(message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::NOT_FOUND,
            message: message.into(),
        }
    }

    fn too_many_requests(message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::TOO_MANY_REQUESTS,
            message: message.into(),
        }
    }

    fn internal(error: impl std::fmt::Display) -> Self {
        tracing::error!(error = %error, "federation request failed");
        Self {
            status: StatusCode::INTERNAL_SERVER_ERROR,
            message: "federation request failed".to_string(),
        }
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let mut response = (
            self.status,
            Json(serde_json::json!({ "error": self.message })),
        )
            .into_response();
        if self.status == StatusCode::TOO_MANY_REQUESTS {
            response
                .headers_mut()
                .insert(RETRY_AFTER, HeaderValue::from_static("60"));
        }
        response
    }
}

pub fn router(service: FederationService) -> Router {
    Router::new()
        .route("/federation/v1/cell", get(cell_descriptor))
        .route(
            "/federation/v1/events",
            post(receive_event).route_layer(from_fn_with_state(
                service.clone(),
                receive_rate_limit_guard,
            )),
        )
        .route(
            "/federation/v1/objects",
            get(resolve_object).route_layer(from_fn_with_state(
                service.clone(),
                object_read_rate_limit_guard,
            )),
        )
        .layer(DefaultBodyLimit::max(MAX_EVENT_BYTES))
        .with_state(service)
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct PeerBootstrap {
    cell_id: String,
    state: String,
    #[serde(default)]
    allow_neighbourhood: bool,
    allowed_event_types: Vec<String>,
    keys: Vec<PeerKeyBootstrap>,
    #[serde(default)]
    delivery_base_url: Option<String>,
}

struct PeerRuntimeConfig {
    policy: PeerPolicy,
    delivery_base_url: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct PeerKeyBootstrap {
    key_id: String,
    public_key: String,
    #[serde(default = "default_true")]
    active: bool,
}

fn default_true() -> bool {
    true
}

fn peer_configs_from_json(raw: &str) -> anyhow::Result<Vec<PeerRuntimeConfig>> {
    let peers: Vec<PeerBootstrap> =
        serde_json::from_str(raw).context("FEDERATION_PEERS_JSON is invalid")?;
    let mut cell_ids = HashSet::new();
    if let Some(duplicate) = peers
        .iter()
        .find(|peer| !cell_ids.insert(peer.cell_id.clone()))
    {
        bail!(
            "FEDERATION_PEERS_JSON contains duplicate cell_id {}",
            duplicate.cell_id
        );
    }
    peers
        .into_iter()
        .map(|peer| {
            let keys = peer
                .keys
                .into_iter()
                .map(|key| {
                    let decoded = URL_SAFE_NO_PAD
                        .decode(&key.public_key)
                        .context("peer public key is not valid base64url")?;
                    let public_key: [u8; 32] = decoded
                        .try_into()
                        .map_err(|_| anyhow::anyhow!("peer public key must be 32 bytes"))?;
                    Ok(PeerKey {
                        key_id: key.key_id,
                        public_key,
                        active: key.active,
                    })
                })
                .collect::<anyhow::Result<Vec<_>>>()?;
            let delivery_base_url = peer
                .delivery_base_url
                .as_deref()
                .map(crate::federation_delivery::validate_delivery_base_url)
                .transpose()?;
            Ok(PeerRuntimeConfig {
                policy: PeerPolicy {
                    remote_cell_id: peer.cell_id,
                    state: peer.state,
                    allow_neighbourhood: peer.allow_neighbourhood,
                    allowed_event_types: peer.allowed_event_types.into_iter().collect(),
                    keys,
                },
                delivery_base_url,
            })
        })
        .collect()
}

#[cfg(test)]
fn peer_policies_from_json(raw: &str) -> anyhow::Result<Vec<PeerPolicy>> {
    Ok(peer_configs_from_json(raw)?
        .into_iter()
        .map(|config| config.policy)
        .collect())
}

pub async fn runtime_router(pool: Option<PgPool>) -> anyhow::Result<Router> {
    let delivery_config = crate::federation_delivery::DeliveryWorkerConfig::from_env()?;
    let Some(identity) = identity_from_env()? else {
        if delivery_config.is_some() {
            bail!(
                "federation delivery requires a complete federation cell identity; \
                 refusing a worker without FEDERATION_CELL_ID and signing configuration"
            );
        }
        return Ok(Router::new());
    };
    let pool = pool.ok_or_else(|| {
        anyhow::anyhow!(
            "federation is configured but DATABASE_URL is unavailable; refusing ephemeral fallback"
        )
    })?;
    let repository = Arc::new(PostgresFederationRepository::new(pool.clone()));
    let service = FederationService::new(identity, repository.clone());

    let peer_configs = match env::var("FEDERATION_PEERS_JSON") {
        Ok(raw) if !raw.trim().is_empty() => peer_configs_from_json(&raw)?,
        Ok(_) | Err(env::VarError::NotPresent) => Vec::new(),
        Err(error) => return Err(error.into()),
    };
    for config in &peer_configs {
        service.install_peer(config.policy.clone()).await?;
    }
    let delivery_bindings: Vec<_> = peer_configs
        .iter()
        .map(|config| (config.policy.clone(), config.delivery_base_url.clone()))
        .collect();
    repository
        .reconcile_delivery_endpoints(&delivery_bindings)
        .await?;

    if let Some(config) = delivery_config {
        let target_count = delivery_bindings
            .iter()
            .filter(|(_, endpoint)| endpoint.is_some())
            .count();
        if target_count == 0 {
            bail!(
                "FEDERATION_DELIVERY_ENABLED=true requires at least one peer with delivery_base_url"
            );
        }
        drop(crate::federation_delivery::start(pool, config)?);
        tracing::info!(target_count, "durable federation delivery worker enabled");
    } else if delivery_bindings
        .iter()
        .any(|(_, endpoint)| endpoint.is_some())
    {
        tracing::warn!(
            "federation delivery endpoints are configured but FEDERATION_DELIVERY_ENABLED is false"
        );
    }

    tracing::info!(
        cell_id = %service.descriptor().cell_id,
        "public federation HTTP boundary enabled"
    );
    Ok(router(service))
}

fn require_explicit_federation_proxy_trust(value: Option<&str>) -> anyhow::Result<()> {
    if value
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .is_none()
    {
        bail!(
            "federation activation requires an explicit AUTH_TRUSTED_PROXIES decision; \
             set it to trusted proxy IPs/CIDRs or to `none` for direct exposure"
        );
    }
    Ok(())
}

fn identity_from_env() -> anyhow::Result<Option<CellIdentity>> {
    let values = [
        env::var("FEDERATION_CELL_ID").ok(),
        env::var("FEDERATION_PUBLIC_BASE_URL").ok(),
        env::var("FEDERATION_KEY_ID").ok(),
        env::var("FEDERATION_SIGNING_KEY_B64").ok(),
    ];
    if values.iter().all(Option::is_none) {
        return Ok(None);
    }
    let [Some(cell_id), Some(public_base_url), Some(key_id), Some(signing_key)] = values else {
        bail!(
            "federation activation requires FEDERATION_CELL_ID, FEDERATION_PUBLIC_BASE_URL, \
             FEDERATION_KEY_ID and FEDERATION_SIGNING_KEY_B64 together"
        );
    };
    let trusted_proxies = env::var("AUTH_TRUSTED_PROXIES").ok();
    require_explicit_federation_proxy_trust(trusted_proxies.as_deref())?;
    let decoded = URL_SAFE_NO_PAD
        .decode(signing_key.trim())
        .context("FEDERATION_SIGNING_KEY_B64 is not valid base64url")?;
    let signing_key: [u8; 32] = decoded
        .try_into()
        .map_err(|_| anyhow::anyhow!("FEDERATION_SIGNING_KEY_B64 must decode to 32 bytes"))?;
    Ok(Some(CellIdentity::new(
        cell_id.trim(),
        public_base_url.trim(),
        key_id.trim(),
        signing_key,
    )?))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_helpers::EnvGuard;
    use serial_test::serial;

    fn identity(cell_id: &str, seed: u8) -> CellIdentity {
        CellIdentity::new(
            cell_id,
            format!("https://{cell_id}.example.test"),
            "key-1",
            [seed; 32],
        )
        .expect("test identity")
    }

    #[test]
    #[serial]
    fn federation_prefilter_groups_ambiguous_xff_under_proxy_peer() {
        let _guard = EnvGuard::set("AUTH_TRUSTED_PROXIES", "127.0.0.1");
        let peer: SocketAddr = "127.0.0.1:8080".parse().unwrap();
        let mut headers = axum::http::HeaderMap::new();
        headers.insert(
            "X-Forwarded-For",
            "203.0.113.7, 198.51.100.9".parse().unwrap(),
        );
        let client_ip = client_ip_or_peer(peer, &headers, "federation-receive-test");
        assert_eq!(client_ip, peer.ip());

        let service = FederationService::new(
            identity("cell-a", 1),
            Arc::new(MemoryFederationRepository::new()),
        );
        for _ in 0..RECEIVE_RATE_PER_CLIENT {
            assert!(service.allow_receive_client(&client_ip.to_string()));
        }
        assert!(!service.allow_receive_client(&client_ip.to_string()));
    }

    #[test]
    fn rfc8785_interoperability_vector_is_stable() {
        let mut event = FederationEvent {
            protocol_version: FEDERATION_PROTOCOL_VERSION.to_string(),
            schema_version: FEDERATION_SCHEMA_VERSION,
            event_id: Uuid::parse_str("018f7b1a-4bb5-7cc3-a1b2-334455667788").unwrap(),
            event_type: EVENT_UPSERTED.to_string(),
            origin_cell_id: "cell-a.example".to_string(),
            actor: "account:public-weber-42".to_string(),
            object_address: "wg://cell-a.example/shared-room/harvest-2026".to_string(),
            object_kind: "shared-room".to_string(),
            object_version: 1,
            previous_version: None,
            created_at: DateTime::parse_from_rfc3339("2026-07-20T08:00:00Z")
                .unwrap()
                .with_timezone(&Utc),
            scope: SCOPE_NEIGHBOURHOOD.to_string(),
            neighbourhood_targets: vec!["cell-b.example".to_string()],
            payload: serde_json::json!({
                "title": "Harvest 2026",
                "members": ["cell-a.example", "cell-b.example"],
                "details": {"unicode": "Gewebe ☀", "count": 2}
            }),
            key_id: "key-2026-07".to_string(),
            signature: String::new(),
        };
        let bytes = signing_bytes(&event).unwrap();
        let key = SigningKey::from_bytes(&[7; 32]);
        event.signature = URL_SAFE_NO_PAD.encode(key.sign(&bytes).to_bytes());
        assert_eq!(
            hex::encode(Sha256::digest(&bytes)),
            "d0e9fde82180c8e1585f2a3654807853d0b84b8b5dc78ffc741366591b592fb6"
        );
        assert_eq!(
            URL_SAFE_NO_PAD.encode(key.verifying_key().as_bytes()),
            "6kpsY-KcUgq-9VB7Ey7F-ZVHdq6-vnuSQh7qaRRG0iw"
        );
        assert_eq!(
            event.signature,
            "K1oizQlxat51Gqo8kd-vXpbBut7L2wq6eAqaue7d09gd7feuZ8bR1JDx7jSomACnbwjo5kS0nd0WGavP2pNHDQ"
        );
        verify_signature(&event, *key.verifying_key().as_bytes()).unwrap();

        let signing_domain = signing_bytes(&event).unwrap();
        let envelope_digest = envelope_sha256(&event).unwrap();
        let mut signature_variant = event.clone();
        signature_variant.signature.push('A');
        assert_eq!(signing_bytes(&signature_variant).unwrap(), signing_domain);
        assert_ne!(
            envelope_sha256(&signature_variant).unwrap(),
            envelope_digest
        );
    }

    #[tokio::test]
    async fn historical_peer_key_remains_valid_after_rotation() {
        let old_identity =
            CellIdentity::new("cell-a", "https://cell-a.example.test", "key-old", [3; 32]).unwrap();
        let new_identity =
            CellIdentity::new("cell-a", "https://cell-a.example.test", "key-new", [4; 32]).unwrap();
        let receiver = FederationService::new(
            identity("cell-b", 5),
            Arc::new(MemoryFederationRepository::new()),
        );
        let old_peer_key = old_identity.peer_key();
        receiver
            .install_peer(PeerPolicy {
                remote_cell_id: "cell-a".to_string(),
                state: "trusted".to_string(),
                allow_neighbourhood: true,
                allowed_event_types: [EVENT_UPSERTED.to_string()].into_iter().collect(),
                keys: vec![old_peer_key.clone()],
            })
            .await
            .unwrap();
        let old_sender =
            FederationService::new(old_identity, Arc::new(MemoryFederationRepository::new()));
        let old_event = old_sender
            .publish_local(PublishRequest {
                actor: "system:key-rotation-test".to_string(),
                event_type: EVENT_UPSERTED.to_string(),
                object_address: "wg://cell-a/node/signed-before-rotation".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: SCOPE_GLOBAL.to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"title": "Old key"}),
            })
            .await
            .unwrap();

        receiver
            .install_peer(PeerPolicy {
                remote_cell_id: "cell-a".to_string(),
                state: "trusted".to_string(),
                allow_neighbourhood: true,
                allowed_event_types: [EVENT_UPSERTED.to_string()].into_iter().collect(),
                keys: vec![old_peer_key, new_identity.peer_key()],
            })
            .await
            .unwrap();
        assert_eq!(
            receiver.receive(old_event).await.unwrap().status,
            ReceiveStatus::Applied
        );

        let new_sender =
            FederationService::new(new_identity, Arc::new(MemoryFederationRepository::new()));
        let new_event = new_sender
            .publish_local(PublishRequest {
                actor: "system:key-rotation-test".to_string(),
                event_type: EVENT_UPSERTED.to_string(),
                object_address: "wg://cell-a/node/signed-after-rotation".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: SCOPE_GLOBAL.to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"title": "New key"}),
            })
            .await
            .unwrap();
        assert_eq!(
            receiver.receive(new_event).await.unwrap().status,
            ReceiveStatus::Applied
        );
    }

    #[tokio::test]
    async fn omitted_peer_key_is_retired_fail_closed() {
        let old_identity =
            CellIdentity::new("cell-a", "https://cell-a.example.test", "key-old", [8; 32]).unwrap();
        let new_identity =
            CellIdentity::new("cell-a", "https://cell-a.example.test", "key-new", [9; 32]).unwrap();
        let receiver = FederationService::new(
            identity("cell-b", 10),
            Arc::new(MemoryFederationRepository::new()),
        );
        receiver
            .install_peer(PeerPolicy {
                remote_cell_id: "cell-a".to_string(),
                state: "trusted".to_string(),
                allow_neighbourhood: true,
                allowed_event_types: [EVENT_UPSERTED.to_string()].into_iter().collect(),
                keys: vec![old_identity.peer_key()],
            })
            .await
            .unwrap();
        let old_sender =
            FederationService::new(old_identity, Arc::new(MemoryFederationRepository::new()));
        receiver
            .install_peer(PeerPolicy {
                remote_cell_id: "cell-a".to_string(),
                state: "trusted".to_string(),
                allow_neighbourhood: true,
                allowed_event_types: [EVENT_UPSERTED.to_string()].into_iter().collect(),
                keys: vec![new_identity.peer_key()],
            })
            .await
            .unwrap();
        let event = old_sender
            .publish_local(PublishRequest {
                actor: "system:omitted-key-test".to_string(),
                event_type: EVENT_UPSERTED.to_string(),
                object_address: "wg://cell-a/node/retired-key".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: SCOPE_GLOBAL.to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"title": "Retired"}),
            })
            .await
            .unwrap();
        let outcome = receiver.receive(event).await.unwrap();
        assert_eq!(outcome.status, ReceiveStatus::Quarantined);
        assert!(outcome.reason.unwrap().contains("inactive"));
    }

    #[tokio::test]
    async fn inactive_peer_key_is_rejected() {
        let sender_identity = identity("cell-a", 6);
        let mut inactive_key = sender_identity.peer_key();
        inactive_key.active = false;
        let receiver = FederationService::new(
            identity("cell-b", 7),
            Arc::new(MemoryFederationRepository::new()),
        );
        receiver
            .install_peer(PeerPolicy {
                remote_cell_id: "cell-a".to_string(),
                state: "trusted".to_string(),
                allow_neighbourhood: true,
                allowed_event_types: [EVENT_UPSERTED.to_string()].into_iter().collect(),
                keys: vec![inactive_key],
            })
            .await
            .unwrap();
        let sender =
            FederationService::new(sender_identity, Arc::new(MemoryFederationRepository::new()));
        let event = sender
            .publish_local(PublishRequest {
                actor: "system:key-revocation-test".to_string(),
                event_type: EVENT_UPSERTED.to_string(),
                object_address: "wg://cell-a/node/revoked-key".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: SCOPE_GLOBAL.to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"title": "Must not apply"}),
            })
            .await
            .unwrap();

        let outcome = receiver.receive(event).await.unwrap();
        assert_eq!(outcome.status, ReceiveStatus::Quarantined);
        assert!(outcome.reason.unwrap().contains("inactive"));
    }

    #[tokio::test]
    async fn memory_repository_enforces_one_event_id_namespace_across_inbox_and_outbox() {
        let sender_identity = identity("cell-a", 1);
        let receiver_repo = Arc::new(MemoryFederationRepository::new());
        let receiver = FederationService::new(identity("cell-b", 2), receiver_repo.clone());
        receiver
            .install_peer(PeerPolicy {
                remote_cell_id: "cell-a".to_string(),
                state: "trusted".to_string(),
                allow_neighbourhood: true,
                allowed_event_types: [EVENT_UPSERTED.to_string()].into_iter().collect(),
                keys: vec![sender_identity.peer_key()],
            })
            .await
            .unwrap();
        let local = receiver
            .publish_local(PublishRequest {
                actor: "system:event-id-namespace-test".to_string(),
                event_type: EVENT_UPSERTED.to_string(),
                object_address: "wg://cell-b/node/local-first".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: SCOPE_GLOBAL.to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"title": "Local first"}),
            })
            .await
            .unwrap();
        let sender = FederationService::new(
            sender_identity.clone(),
            Arc::new(MemoryFederationRepository::new()),
        );
        let mut inbound_collision = sender
            .publish_local(PublishRequest {
                actor: "system:event-id-namespace-test".to_string(),
                event_type: EVENT_UPSERTED.to_string(),
                object_address: "wg://cell-a/node/remote-collision".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: SCOPE_GLOBAL.to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"title": "Remote collision"}),
            })
            .await
            .unwrap();
        inbound_collision.event_id = local.event_id;
        let signing_key = SigningKey::from_bytes(&[1; 32]);
        inbound_collision.signature = URL_SAFE_NO_PAD.encode(
            signing_key
                .sign(&signing_bytes(&inbound_collision).unwrap())
                .to_bytes(),
        );
        let collision = receiver.receive(inbound_collision).await.unwrap();
        assert_eq!(collision.status, ReceiveStatus::Quarantined);
        assert_eq!(
            collision.reason.as_deref(),
            Some("event id collision with different envelope")
        );

        let second_repo = Arc::new(MemoryFederationRepository::new());
        let second_receiver = FederationService::new(identity("cell-b", 2), second_repo.clone());
        second_receiver
            .install_peer(PeerPolicy {
                remote_cell_id: "cell-a".to_string(),
                state: "trusted".to_string(),
                allow_neighbourhood: true,
                allowed_event_types: [EVENT_UPSERTED.to_string()].into_iter().collect(),
                keys: vec![sender_identity.peer_key()],
            })
            .await
            .unwrap();
        let inbound_first = sender
            .publish_local(PublishRequest {
                actor: "system:event-id-namespace-test".to_string(),
                event_type: EVENT_UPSERTED.to_string(),
                object_address: "wg://cell-a/node/remote-first".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: SCOPE_GLOBAL.to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"title": "Remote first"}),
            })
            .await
            .unwrap();
        assert_eq!(
            second_receiver
                .receive(inbound_first.clone())
                .await
                .unwrap()
                .status,
            ReceiveStatus::Applied
        );
        let mut local_conflict = inbound_first;
        local_conflict.origin_cell_id = "cell-b".to_string();
        local_conflict.object_address = "wg://cell-b/node/local-conflict".to_string();
        local_conflict.key_id = "key-1".to_string();
        local_conflict.signature.clear();
        let error = second_repo
            .persist_local(&local_conflict)
            .await
            .unwrap_err();
        assert!(error
            .to_string()
            .contains("local federation event id already exists"));
    }

    #[tokio::test]
    async fn tampered_event_is_rejected_without_quarantine() {
        let a = identity("cell-a", 1);
        let b_repo = Arc::new(MemoryFederationRepository::new());
        let b = FederationService::new(identity("cell-b", 2), b_repo);
        b.install_peer(PeerPolicy {
            remote_cell_id: "cell-a".to_string(),
            state: "trusted".to_string(),
            allow_neighbourhood: true,
            allowed_event_types: [EVENT_UPSERTED.to_string()].into_iter().collect(),
            keys: vec![a.peer_key()],
        })
        .await
        .unwrap();
        let a = FederationService::new(a, Arc::new(MemoryFederationRepository::new()));
        let mut event = a
            .publish_local(PublishRequest {
                actor: "system:test".to_string(),
                event_type: EVENT_UPSERTED.to_string(),
                object_address: "wg://cell-a/node/n-1".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: SCOPE_GLOBAL.to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"title": "Original"}),
            })
            .await
            .unwrap();
        event.payload = serde_json::json!({"title": "Manipulated"});
        let outcome = b.receive(event).await.unwrap();
        assert_eq!(outcome.status, ReceiveStatus::Rejected);
        assert_eq!(
            outcome.reason.as_deref(),
            Some("event authentication rejected")
        );
        assert!(b.quarantined().await.unwrap().is_empty());
    }

    #[tokio::test]
    async fn exact_authenticated_duplicates_do_not_consume_origin_rate_limit() {
        let sender_identity = identity("cell-a", 41);
        let sender = FederationService::new(
            sender_identity.clone(),
            Arc::new(MemoryFederationRepository::new()),
        );
        let receiver = FederationService::new(
            identity("cell-b", 42),
            Arc::new(MemoryFederationRepository::new()),
        );
        receiver
            .install_peer(PeerPolicy {
                remote_cell_id: "cell-a".to_string(),
                state: "trusted".to_string(),
                allow_neighbourhood: true,
                allowed_event_types: [EVENT_UPSERTED.to_string()].into_iter().collect(),
                keys: vec![sender_identity.peer_key()],
            })
            .await
            .unwrap();
        let first = sender
            .publish_local(PublishRequest {
                actor: "system:duplicate-rate-test".to_string(),
                event_type: EVENT_UPSERTED.to_string(),
                object_address: "wg://cell-a/node/first".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: SCOPE_GLOBAL.to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"value": 1}),
            })
            .await
            .unwrap();
        assert_eq!(
            receiver.receive(first.clone()).await.unwrap().status,
            ReceiveStatus::Applied
        );
        for _ in 0..=RECEIVE_RATE_PER_ORIGIN {
            assert_eq!(
                receiver.receive(first.clone()).await.unwrap().status,
                ReceiveStatus::Duplicate
            );
        }
        let second = sender
            .publish_local(PublishRequest {
                actor: "system:duplicate-rate-test".to_string(),
                event_type: EVENT_UPSERTED.to_string(),
                object_address: "wg://cell-a/node/second".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: SCOPE_GLOBAL.to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"value": 2}),
            })
            .await
            .unwrap();
        assert_eq!(
            receiver.receive(second).await.unwrap().status,
            ReceiveStatus::Applied
        );

        receiver
            .install_peer(PeerPolicy {
                remote_cell_id: "cell-a".to_string(),
                state: "blocked".to_string(),
                allow_neighbourhood: true,
                allowed_event_types: [EVENT_UPSERTED.to_string()].into_iter().collect(),
                keys: vec![sender_identity.peer_key()],
            })
            .await
            .unwrap();
        let blocked_replay = receiver.receive(first).await.unwrap();
        assert_eq!(blocked_replay.status, ReceiveStatus::Quarantined);
        assert!(blocked_replay
            .reason
            .as_deref()
            .unwrap_or_default()
            .contains("blocked"));
    }

    #[tokio::test]
    async fn weak_peer_key_is_rejected_before_install() {
        let service = FederationService::new(
            identity("cell-b", 50),
            Arc::new(MemoryFederationRepository::new()),
        );
        let mut weak_public_key = [0_u8; 32];
        weak_public_key[0] = 1;
        let error = service
            .install_peer(PeerPolicy {
                remote_cell_id: "cell-a".to_string(),
                state: "trusted".to_string(),
                allow_neighbourhood: true,
                allowed_event_types: [EVENT_UPSERTED.to_string()].into_iter().collect(),
                keys: vec![PeerKey {
                    key_id: "weak-key".to_string(),
                    public_key: weak_public_key,
                    active: true,
                }],
            })
            .await
            .unwrap_err();
        assert!(error.to_string().contains("weak"));
    }

    #[tokio::test]
    async fn strict_verification_rejects_weak_key_universal_signature() {
        let sender = FederationService::new(
            identity("cell-a", 49),
            Arc::new(MemoryFederationRepository::new()),
        );
        let mut event = sender
            .publish_local(PublishRequest {
                actor: "system:weak-key-test".to_string(),
                event_type: EVENT_UPSERTED.to_string(),
                object_address: "wg://cell-a/node/weak-key-signature".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: SCOPE_GLOBAL.to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"title": "Must not verify"}),
            })
            .await
            .unwrap();
        let mut weak_public_key = [0_u8; 32];
        weak_public_key[0] = 1;
        let mut universal_signature = [0_u8; 64];
        universal_signature[0] = 1;
        event.signature = URL_SAFE_NO_PAD.encode(universal_signature);

        let error = verify_signature(&event, weak_public_key).unwrap_err();
        assert!(error
            .to_string()
            .contains("event signature verification failed"));
    }

    #[tokio::test]
    async fn peer_key_bytes_are_immutable_and_failed_reinstall_rolls_back() {
        let repository = Arc::new(MemoryFederationRepository::new());
        let service = FederationService::new(identity("cell-b", 51), repository.clone());
        let original = identity("cell-a", 52).peer_key();
        service
            .install_peer(PeerPolicy {
                remote_cell_id: "cell-a".to_string(),
                state: "trusted".to_string(),
                allow_neighbourhood: true,
                allowed_event_types: [EVENT_UPSERTED.to_string()].into_iter().collect(),
                keys: vec![original.clone()],
            })
            .await
            .unwrap();
        let mut replacement = original.clone();
        replacement.public_key = *SigningKey::from_bytes(&[53; 32]).verifying_key().as_bytes();
        let error = service
            .install_peer(PeerPolicy {
                remote_cell_id: "cell-a".to_string(),
                state: "blocked".to_string(),
                allow_neighbourhood: false,
                allowed_event_types: [EVENT_DELETED.to_string()].into_iter().collect(),
                keys: vec![replacement],
            })
            .await
            .unwrap_err();
        assert!(error.to_string().contains("immutable"));
        let resolved = repository
            .resolve_peer("cell-a", &original.key_id)
            .await
            .unwrap()
            .unwrap();
        assert_eq!(resolved.public_key, original.public_key);
        assert_eq!(resolved.state, "trusted");
        assert!(resolved.allow_neighbourhood);
    }

    #[test]
    fn object_scope_and_canonical_neighbourhood_audience_are_immutable() {
        let mut event = FederationEvent {
            protocol_version: FEDERATION_PROTOCOL_VERSION.to_string(),
            schema_version: FEDERATION_SCHEMA_VERSION,
            event_id: Uuid::new_v4(),
            event_type: EVENT_UPSERTED.to_string(),
            origin_cell_id: "cell-a".to_string(),
            actor: "system:scope-test".to_string(),
            object_address: "wg://cell-a/node/audience".to_string(),
            object_kind: "node".to_string(),
            object_version: 2,
            previous_version: Some(1),
            created_at: Utc::now(),
            scope: SCOPE_NEIGHBOURHOOD.to_string(),
            neighbourhood_targets: vec!["cell-c".to_string(), "cell-b".to_string()],
            payload: serde_json::json!({}),
            key_id: "key-1".to_string(),
            signature: String::new(),
        };
        let current = FederatedObject {
            object_address: event.object_address.clone(),
            origin_cell_id: event.origin_cell_id.clone(),
            object_kind: event.object_kind.clone(),
            object_version: 1,
            scope: SCOPE_NEIGHBOURHOOD.to_string(),
            neighbourhood_targets: vec!["cell-b".to_string(), "cell-c".to_string()],
            payload: serde_json::json!({}),
            deleted: false,
            updated_at: Utc::now(),
        };
        assert_eq!(transition_rejection(Some(&current), &event), None);
        event.neighbourhood_targets = vec!["cell-b".to_string(), "cell-d".to_string()];
        assert_eq!(
            transition_rejection(Some(&current), &event).as_deref(),
            Some("object neighbourhood audience cannot change")
        );
        event.scope = SCOPE_GLOBAL.to_string();
        event.neighbourhood_targets.clear();
        assert_eq!(
            transition_rejection(Some(&current), &event).as_deref(),
            Some("object scope cannot change")
        );
    }

    #[test]
    fn actor_limit_counts_unicode_characters_like_json_schema() {
        assert!(validate_actor(&"é".repeat(128)).is_ok());
        assert!(validate_actor(&"é".repeat(129)).is_err());
    }

    #[test]
    fn federation_activation_requires_explicit_proxy_trust_decision() {
        assert!(require_explicit_federation_proxy_trust(None).is_err());
        assert!(require_explicit_federation_proxy_trust(Some("   ")).is_err());
        assert!(require_explicit_federation_proxy_trust(Some("none")).is_ok());
        assert!(require_explicit_federation_proxy_trust(Some("127.0.0.1")).is_ok());
    }

    #[tokio::test]
    async fn new_authenticated_policy_rejections_consume_origin_rate_limit() {
        let sender_identity = identity("cell-a", 71);
        let sender = FederationService::new(
            sender_identity.clone(),
            Arc::new(MemoryFederationRepository::new()),
        );
        let receiver = FederationService::new(
            identity("cell-b", 72),
            Arc::new(MemoryFederationRepository::new()),
        );
        receiver
            .install_peer(PeerPolicy {
                remote_cell_id: "cell-a".to_string(),
                state: "blocked".to_string(),
                allow_neighbourhood: true,
                allowed_event_types: [EVENT_UPSERTED.to_string()].into_iter().collect(),
                keys: vec![sender_identity.peer_key()],
            })
            .await
            .unwrap();

        for index in 0..RECEIVE_RATE_PER_ORIGIN {
            let event = sender
                .publish_local(PublishRequest {
                    actor: "system:blocked-origin-rate-proof".to_string(),
                    event_type: EVENT_UPSERTED.to_string(),
                    object_address: format!("wg://cell-a/node/blocked-rate-{index}"),
                    object_kind: "node".to_string(),
                    object_version: 1,
                    previous_version: None,
                    scope: SCOPE_GLOBAL.to_string(),
                    neighbourhood_targets: vec![],
                    payload: serde_json::json!({"index": index}),
                })
                .await
                .unwrap();
            assert_eq!(
                receiver.receive(event).await.unwrap().status,
                ReceiveStatus::Quarantined
            );
        }

        let overflow = sender
            .publish_local(PublishRequest {
                actor: "system:blocked-origin-rate-proof".to_string(),
                event_type: EVENT_UPSERTED.to_string(),
                object_address: "wg://cell-a/node/blocked-rate-overflow".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: SCOPE_GLOBAL.to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"overflow": true}),
            })
            .await
            .unwrap();
        assert!(receiver
            .receive(overflow)
            .await
            .unwrap_err()
            .downcast_ref::<ReceiveRateLimitExceeded>()
            .is_some());
    }

    #[tokio::test]
    async fn policy_rejected_replays_of_previously_applied_event_are_rate_limited() {
        let sender_identity = identity("cell-a", 81);
        let sender = FederationService::new(
            sender_identity.clone(),
            Arc::new(MemoryFederationRepository::new()),
        );
        let repository = Arc::new(MemoryFederationRepository::new());
        let receiver = FederationService::new(identity("cell-b", 82), repository.clone());
        receiver
            .install_peer(PeerPolicy {
                remote_cell_id: "cell-a".to_string(),
                state: "trusted".to_string(),
                allow_neighbourhood: true,
                allowed_event_types: [EVENT_UPSERTED.to_string()].into_iter().collect(),
                keys: vec![sender_identity.peer_key()],
            })
            .await
            .unwrap();
        let event = sender
            .publish_local(PublishRequest {
                actor: "system:blocked-replay-rate-proof".to_string(),
                event_type: EVENT_UPSERTED.to_string(),
                object_address: "wg://cell-a/node/blocked-replay-rate-proof".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: SCOPE_GLOBAL.to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"proof": true}),
            })
            .await
            .unwrap();
        assert_eq!(
            receiver.receive(event.clone()).await.unwrap().status,
            ReceiveStatus::Applied
        );
        receiver
            .install_peer(PeerPolicy {
                remote_cell_id: "cell-a".to_string(),
                state: "blocked".to_string(),
                allow_neighbourhood: true,
                allowed_event_types: [EVENT_UPSERTED.to_string()].into_iter().collect(),
                keys: vec![sender_identity.peer_key()],
            })
            .await
            .unwrap();

        for _ in 1..RECEIVE_RATE_PER_ORIGIN {
            assert_eq!(
                receiver.receive(event.clone()).await.unwrap().status,
                ReceiveStatus::Quarantined
            );
        }
        assert!(repository.quarantined().await.unwrap().is_empty());
        assert!(receiver
            .receive(event)
            .await
            .unwrap_err()
            .downcast_ref::<ReceiveRateLimitExceeded>()
            .is_some());
    }

    #[test]
    fn peer_bootstrap_requires_state_and_rejects_duplicate_cells() {
        let key = URL_SAFE_NO_PAD.encode([7; 32]);
        let missing_state = format!(
            r#"[{{"cell_id":"cell-a","allowed_event_types":["object.upserted"],"keys":[{{"key_id":"key-1","public_key":"{key}"}}]}}]"#
        );
        assert!(peer_policies_from_json(&missing_state).is_err());
        let duplicate = format!(
            r#"[{{"cell_id":"cell-a","state":"trusted","allowed_event_types":["object.upserted"],"keys":[{{"key_id":"key-1","public_key":"{key}"}}]}},{{"cell_id":"cell-a","state":"blocked","allowed_event_types":["object.upserted"],"keys":[{{"key_id":"key-2","public_key":"{key}"}}]}}]"#
        );
        let error = peer_policies_from_json(&duplicate).unwrap_err();
        assert!(error.to_string().contains("duplicate cell_id cell-a"));
    }

    #[test]
    fn peer_bootstrap_validates_optional_delivery_endpoint() {
        let key = URL_SAFE_NO_PAD.encode([9; 32]);
        let valid = format!(
            r#"[{{"cell_id":"cell-a","state":"trusted","allowed_event_types":["object.upserted"],"keys":[{{"key_id":"key-1","public_key":"{key}"}}],"delivery_base_url":"https://cell-a.example.test/edge/"}}]"#
        );
        let configs = peer_configs_from_json(&valid).unwrap();
        assert_eq!(configs.len(), 1);
        assert_eq!(
            configs[0].delivery_base_url.as_deref(),
            Some("https://cell-a.example.test/edge")
        );

        let insecure = valid.replace(
            "https://cell-a.example.test/edge/",
            "http://cell-a.example.test",
        );
        assert!(peer_configs_from_json(&insecure).is_err());
    }
}

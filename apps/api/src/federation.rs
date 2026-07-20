use std::{
    collections::{HashMap, HashSet},
    env,
    sync::{Arc, Mutex},
    time::{Duration as StdDuration, Instant},
};

use anyhow::{bail, Context};
use async_trait::async_trait;
use axum::{
    extract::{rejection::JsonRejection, DefaultBodyLimit, Query, State},
    http::{header::RETRY_AFTER, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use chrono::{DateTime, Duration, SecondsFormat, Utc};
use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use sqlx::{PgPool, Row};
use tokio::sync::RwLock;
use url::Url;
use uuid::Uuid;

pub const FEDERATION_PROTOCOL_VERSION: &str = "wg-federation/1";
pub const FEDERATION_SCHEMA_VERSION: u16 = 1;
const MAX_EVENT_BYTES: usize = 256 * 1024;
const MAX_CLOCK_SKEW_SECONDS: i64 = 300;
const EVENT_UPSERTED: &str = "object.upserted";
const EVENT_DELETED: &str = "object.deleted";
const SCOPE_NEIGHBOURHOOD: &str = "neighbourhood";
const SCOPE_GLOBAL: &str = "global";
const RECEIVE_RATE_WINDOW: StdDuration = StdDuration::from_secs(60);
const RECEIVE_RATE_PER_ORIGIN: u32 = 120;
const RECEIVE_RATE_GLOBAL: u32 = 600;
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
    pub payload: Value,
    pub deleted: bool,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ReceiveStatus {
    Applied,
    Duplicate,
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
    async fn quarantine(
        &self,
        event: &FederationEvent,
        reason: &str,
    ) -> anyhow::Result<ReceiveOutcome>;
    async fn accept_verified(&self, event: &FederationEvent) -> anyhow::Result<ReceiveOutcome>;
    async fn persist_local(&self, event: &FederationEvent) -> anyhow::Result<()>;
    async fn object(&self, address: &str) -> anyhow::Result<Option<FederatedObject>>;
    async fn pending_outbox(&self) -> anyhow::Result<Vec<FederationEvent>>;
    async fn quarantined(&self) -> anyhow::Result<Vec<QuarantinedEvent>>;
}

struct ReceiveRateState {
    window_started: Instant,
    global_count: u32,
    per_origin: HashMap<String, u32>,
}

impl Default for ReceiveRateState {
    fn default() -> Self {
        Self {
            window_started: Instant::now(),
            global_count: 0,
            per_origin: HashMap::new(),
        }
    }
}

#[derive(Clone)]
pub struct FederationService {
    identity: Arc<CellIdentity>,
    repository: Arc<dyn FederationRepository>,
    receive_rate_state: Arc<Mutex<ReceiveRateState>>,
}

impl FederationService {
    pub fn new(identity: CellIdentity, repository: Arc<dyn FederationRepository>) -> Self {
        Self {
            identity: Arc::new(identity),
            repository,
            receive_rate_state: Arc::new(Mutex::new(ReceiveRateState::default())),
        }
    }

    pub fn descriptor(&self) -> CellDescriptor {
        self.identity.descriptor()
    }

    fn allow_receive_global(&self) -> bool {
        let mut state = self
            .receive_rate_state
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        if state.window_started.elapsed() >= RECEIVE_RATE_WINDOW {
            *state = ReceiveRateState::default();
        }
        if state.global_count >= RECEIVE_RATE_GLOBAL {
            return false;
        }
        state.global_count += 1;
        true
    }

    fn allow_authenticated_origin(&self, origin_cell_id: &str) -> bool {
        let mut state = self
            .receive_rate_state
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        if state.window_started.elapsed() >= RECEIVE_RATE_WINDOW {
            *state = ReceiveRateState::default();
        }
        let origin_count = state
            .per_origin
            .entry(origin_cell_id.to_string())
            .or_default();
        if *origin_count >= RECEIVE_RATE_PER_ORIGIN {
            return false;
        }
        *origin_count += 1;
        true
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
            return Ok(ReceiveOutcome::quarantined(
                &event,
                "loopback event from local cell",
            ));
        }

        let Some(peer) = self
            .repository
            .resolve_peer(&event.origin_cell_id, &event.key_id)
            .await?
        else {
            return Ok(ReceiveOutcome::quarantined(&event, "unknown cell or key"));
        };

        if let Err(error) = verify_signature(&event, peer.public_key) {
            return Ok(ReceiveOutcome::quarantined(&event, error.to_string()));
        }
        if !self.allow_authenticated_origin(&event.origin_cell_id) {
            return Err(ReceiveRateLimitExceeded.into());
        }

        // The repository re-resolves and locks the current peer/key policy before
        // object mutation. This closes the revocation/blocking TOCTOU window
        // between the optimistic signature check above and durable acceptance.
        self.repository.accept_verified(&event).await
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

    async fn accept_verified(&self, event: &FederationEvent) -> anyhow::Result<ReceiveOutcome> {
        // Hold the same write lock used by install_peer so a policy/key update
        // cannot commit between this final authorization check and acceptance.
        let mut state = self.state.write().await;
        let Some(peer) = state
            .peers
            .get(&(event.origin_cell_id.clone(), event.key_id.clone()))
            .cloned()
        else {
            return Ok(ReceiveOutcome::quarantined(event, "unknown cell or key"));
        };
        if verify_signature(event, peer.public_key).is_err() {
            return Ok(ReceiveOutcome::quarantined(
                event,
                "event signature no longer verifies against current peer key",
            ));
        }
        let digest = envelope_sha256(event)?;
        if let Some(reason) = peer_policy_rejection(&peer, event) {
            push_memory_quarantine_once(&mut state, event, reason, digest);
            return Ok(ReceiveOutcome::quarantined(event, reason));
        }
        if let Some(existing_digest) = state.inbox.get(&event.event_id) {
            if existing_digest == &digest {
                return Ok(ReceiveOutcome::duplicate(event));
            }
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

impl PostgresFederationRepository {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
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
        for key in policy.keys {
            sqlx::query(
                "INSERT INTO federation_peer_keys \
                 (remote_cell_id, key_id, public_key, active, retired_at) \
                 VALUES ($1, $2, $3, $4, CASE WHEN $4 THEN NULL ELSE NOW() END) \
                 ON CONFLICT (remote_cell_id, key_id) DO UPDATE SET \
                   public_key = EXCLUDED.public_key, \
                   active = EXCLUDED.active, \
                   retired_at = CASE \
                     WHEN EXCLUDED.active THEN NULL \
                     ELSE COALESCE(federation_peer_keys.retired_at, NOW()) \
                   END",
            )
            .bind(&policy.remote_cell_id)
            .bind(&key.key_id)
            .bind(key.public_key.as_slice())
            .bind(key.active)
            .execute(&mut *tx)
            .await?;
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

    async fn accept_verified(&self, event: &FederationEvent) -> anyhow::Result<ReceiveOutcome> {
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
            return Ok(ReceiveOutcome::quarantined(event, "unknown cell or key"));
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
            return Ok(ReceiveOutcome::quarantined(
                event,
                "event signature no longer verifies against current peer key",
            ));
        }
        let digest = envelope_sha256(event)?;
        if let Some(reason) = peer_policy_rejection(&peer, event) {
            quarantine_verified_in_tx(&mut tx, event, reason, &digest).await?;
            tx.commit().await?;
            return Ok(ReceiveOutcome::quarantined(event, reason));
        }

        lock_event_receipt(&mut tx, event.event_id).await?;
        lock_object_transition(&mut tx, &event.object_address).await?;
        let existing = sqlx::query(
            "SELECT envelope_sha256 FROM federation_inbox WHERE event_id = $1 FOR UPDATE",
        )
        .bind(event.event_id)
        .fetch_optional(&mut *tx)
        .await?;
        if let Some(existing) = existing {
            let existing_digest: String = existing.try_get("envelope_sha256")?;
            if existing_digest == digest {
                tx.rollback().await?;
                return Ok(ReceiveOutcome::duplicate(event));
            }
            let reason = "event id collision with different envelope";
            quarantine_verified_in_tx(&mut tx, event, reason, &digest).await?;
            tx.commit().await?;
            return Ok(ReceiveOutcome::quarantined(event, reason));
        }

        let current = sqlx::query(
            "SELECT object_address, origin_cell_id, object_kind, object_version, scope, payload, \
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
        lock_object_transition(&mut tx, &event.object_address).await?;
        let current = sqlx::query(
            "SELECT object_address, origin_cell_id, object_kind, object_version, scope, payload, \
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
        sqlx::query(
            "INSERT INTO federation_outbox \
             (event_id, object_address, object_version, envelope_sha256, envelope) \
             VALUES ($1, $2, $3, $4, $5)",
        )
        .bind(event.event_id)
        .bind(&event.object_address)
        .bind(event.object_version)
        .bind(envelope_sha256(event)?)
        .bind(serde_json::to_value(event)?)
        .execute(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(())
    }

    async fn object(&self, address: &str) -> anyhow::Result<Option<FederatedObject>> {
        sqlx::query(
            "SELECT object_address, origin_cell_id, object_kind, object_version, scope, payload, \
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
    sqlx::query(
        "INSERT INTO federation_objects \
         (object_address, origin_cell_id, object_kind, object_version, scope, payload, deleted_at, updated_at) \
         VALUES ($1, $2, $3, $4, $5, $6, CASE WHEN $7 THEN NOW() ELSE NULL END, NOW()) \
         ON CONFLICT (object_address) DO UPDATE SET \
           origin_cell_id = EXCLUDED.origin_cell_id, \
           object_kind = EXCLUDED.object_kind, \
           object_version = EXCLUDED.object_version, \
           scope = EXCLUDED.scope, \
           payload = EXCLUDED.payload, \
           deleted_at = EXCLUDED.deleted_at, \
           updated_at = NOW()",
    )
    .bind(&event.object_address)
    .bind(&event.origin_cell_id)
    .bind(&event.object_kind)
    .bind(event.object_version)
    .bind(&event.scope)
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
            payload: event.payload.clone(),
            deleted: event.event_type == EVENT_DELETED,
            updated_at: Utc::now(),
        },
    );
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
fn envelope_sha256(event: &FederationEvent) -> anyhow::Result<String> {
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
        .verify(&signing_bytes(event)?, &signature)
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
    if value.is_empty() || value.len() > 128 || value.chars().any(char::is_control) {
        bail!("actor must be a non-empty control-free string of at most 128 bytes");
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

async fn receive_event(
    State(service): State<FederationService>,
    payload: Result<Json<FederationEvent>, JsonRejection>,
) -> Result<(StatusCode, Json<ReceiveOutcome>), ApiError> {
    let Json(event) = payload.map_err(|rejection| match rejection.status() {
        StatusCode::UNSUPPORTED_MEDIA_TYPE => ApiError::unsupported_media_type(),
        StatusCode::PAYLOAD_TOO_LARGE => ApiError::payload_too_large(),
        _ => ApiError::bad_request("invalid federation event envelope"),
    })?;
    if !service.allow_receive_global() {
        return Err(ApiError::too_many_requests());
    }
    let outcome = match service.receive_body_limited(event).await {
        Ok(outcome) => outcome,
        Err(error) if error.downcast_ref::<InvalidFederationEvent>().is_some() => {
            return Err(ApiError::bad_request("invalid federation event"));
        }
        Err(error) if error.downcast_ref::<ReceiveRateLimitExceeded>().is_some() => {
            return Err(ApiError::too_many_requests());
        }
        Err(error) => return Err(ApiError::internal(error)),
    };
    let status = match outcome.status {
        ReceiveStatus::Applied => StatusCode::CREATED,
        ReceiveStatus::Duplicate => StatusCode::OK,
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

    fn too_many_requests() -> Self {
        Self {
            status: StatusCode::TOO_MANY_REQUESTS,
            message: "federation receive rate limit exceeded".to_string(),
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
        .route("/federation/v1/events", post(receive_event))
        .route("/federation/v1/objects", get(resolve_object))
        .layer(DefaultBodyLimit::max(MAX_EVENT_BYTES))
        .with_state(service)
}

#[derive(Debug, Deserialize)]
struct PeerBootstrap {
    cell_id: String,
    #[serde(default = "trusted_state")]
    state: String,
    #[serde(default)]
    allow_neighbourhood: bool,
    allowed_event_types: Vec<String>,
    keys: Vec<PeerKeyBootstrap>,
}

#[derive(Debug, Deserialize)]
struct PeerKeyBootstrap {
    key_id: String,
    public_key: String,
    #[serde(default = "default_true")]
    active: bool,
}

fn trusted_state() -> String {
    "trusted".to_string()
}

fn default_true() -> bool {
    true
}

pub async fn runtime_router(pool: Option<PgPool>) -> anyhow::Result<Router> {
    let Some(identity) = identity_from_env()? else {
        return Ok(Router::new());
    };
    let pool = pool.ok_or_else(|| {
        anyhow::anyhow!(
            "federation is configured but DATABASE_URL is unavailable; refusing ephemeral fallback"
        )
    })?;
    let repository = Arc::new(PostgresFederationRepository::new(pool));
    let service = FederationService::new(identity, repository);
    if let Ok(raw) = env::var("FEDERATION_PEERS_JSON") {
        if !raw.trim().is_empty() {
            let peers: Vec<PeerBootstrap> =
                serde_json::from_str(&raw).context("FEDERATION_PEERS_JSON is invalid")?;
            for peer in peers {
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
                service
                    .install_peer(PeerPolicy {
                        remote_cell_id: peer.cell_id,
                        state: peer.state,
                        allow_neighbourhood: peer.allow_neighbourhood,
                        allowed_event_types: peer.allowed_event_types.into_iter().collect(),
                        keys,
                    })
                    .await?;
            }
        }
    }
    tracing::info!(
        cell_id = %service.descriptor().cell_id,
        "public federation HTTP boundary enabled"
    );
    Ok(router(service))
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
    async fn tampered_event_is_quarantined() {
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
        assert_eq!(outcome.status, ReceiveStatus::Quarantined);
        assert!(outcome.reason.unwrap().contains("signature"));
    }
}

use std::{env, sync::Arc, time::Duration};

use anyhow::{bail, Context};
use async_trait::async_trait;
use futures_util::StreamExt;
use reqwest::{redirect::Policy, Client};
use serde_json::Value;
use sqlx::{PgPool, Row};
use tokio::{task::JoinHandle, time::MissedTickBehavior};
use url::Url;
use uuid::Uuid;

use crate::federation::{FederationEvent, ReceiveOutcome, ReceiveStatus};

pub const DELIVERY_ENABLED_ENV: &str = "FEDERATION_DELIVERY_ENABLED";
pub const DELIVERY_POLL_SECONDS_ENV: &str = "FEDERATION_DELIVERY_POLL_SECONDS";
pub const DELIVERY_REQUEST_TIMEOUT_SECONDS_ENV: &str =
    "FEDERATION_DELIVERY_REQUEST_TIMEOUT_SECONDS";
pub const DELIVERY_BATCH_SIZE_ENV: &str = "FEDERATION_DELIVERY_BATCH_SIZE";
pub const DELIVERY_MAX_ATTEMPTS_ENV: &str = "FEDERATION_DELIVERY_MAX_ATTEMPTS";

const DEFAULT_POLL_SECONDS: u64 = 5;
const DEFAULT_REQUEST_TIMEOUT_SECONDS: u64 = 10;
const DEFAULT_BATCH_SIZE: usize = 20;
const DEFAULT_MAX_ATTEMPTS: u32 = 8;
const DELIVERY_LEASE_GRACE_SECONDS: u64 = 30;
const MAX_RESPONSE_BYTES: usize = 64 * 1024;
const MAX_BACKOFF_SECONDS: u64 = 300;

#[derive(Clone, Debug)]
pub struct DeliveryWorkerConfig {
    pub poll_interval: Duration,
    pub request_timeout: Duration,
    pub batch_size: usize,
    pub max_attempts: u32,
}

impl DeliveryWorkerConfig {
    pub fn from_env() -> anyhow::Result<Option<Self>> {
        let enabled = match env::var(DELIVERY_ENABLED_ENV) {
            Ok(value) => parse_bool(DELIVERY_ENABLED_ENV, &value)?,
            Err(env::VarError::NotPresent) => false,
            Err(error) => return Err(error.into()),
        };
        if !enabled {
            return Ok(None);
        }
        Ok(Some(Self {
            poll_interval: Duration::from_secs(parse_bounded_u64(
                DELIVERY_POLL_SECONDS_ENV,
                DEFAULT_POLL_SECONDS,
                1,
                60,
            )?),
            request_timeout: Duration::from_secs(parse_bounded_u64(
                DELIVERY_REQUEST_TIMEOUT_SECONDS_ENV,
                DEFAULT_REQUEST_TIMEOUT_SECONDS,
                1,
                30,
            )?),
            batch_size: usize::try_from(parse_bounded_u64(
                DELIVERY_BATCH_SIZE_ENV,
                u64::try_from(DEFAULT_BATCH_SIZE)?,
                1,
                100,
            )?)?,
            max_attempts: u32::try_from(parse_bounded_u64(
                DELIVERY_MAX_ATTEMPTS_ENV,
                u64::from(DEFAULT_MAX_ATTEMPTS),
                1,
                20,
            )?)?,
        }))
    }
}

fn parse_bool(name: &str, raw: &str) -> anyhow::Result<bool> {
    match raw.trim() {
        "true" => Ok(true),
        "false" => Ok(false),
        _ => bail!("{name} must be exactly true or false"),
    }
}

fn parse_bounded_u64(name: &str, default: u64, minimum: u64, maximum: u64) -> anyhow::Result<u64> {
    let raw = match env::var(name) {
        Ok(value) => value,
        Err(env::VarError::NotPresent) => return Ok(default),
        Err(error) => return Err(error.into()),
    };
    let value: u64 = raw
        .trim()
        .parse()
        .with_context(|| format!("{name} must be an integer"))?;
    if !(minimum..=maximum).contains(&value) {
        bail!("{name} must be between {minimum} and {maximum}");
    }
    Ok(value)
}

pub fn validate_delivery_base_url(raw: &str) -> anyhow::Result<String> {
    let value = raw.trim();
    let url = Url::parse(value).context("federation delivery base URL is invalid")?;
    if url.scheme() != "https" {
        bail!("federation delivery base URL must use https");
    }
    if url.host_str().is_none() || !url.username().is_empty() || url.password().is_some() {
        bail!("federation delivery base URL must contain a host and no credentials");
    }
    if !matches!(url.host(), Some(url::Host::Domain(_))) {
        bail!("federation delivery base URL must use a DNS host, not an IP literal");
    }
    if url.query().is_some() || url.fragment().is_some() {
        bail!("federation delivery base URL must not contain query or fragment");
    }
    Ok(value.trim_end_matches('/').to_string())
}

fn event_endpoint(base_url: &str) -> anyhow::Result<Url> {
    let base_url = validate_delivery_base_url(base_url)?;
    Url::parse(&format!("{base_url}/federation/v1/events"))
        .context("federation delivery event URL is invalid")
}

#[derive(Debug)]
pub struct DeliveryHttpResponse {
    pub status: u16,
    pub retry_after_seconds: Option<u64>,
    pub body: Vec<u8>,
}

#[derive(Debug)]
pub struct DeliveryTransportError {
    pub class: &'static str,
}

#[async_trait]
pub trait DeliveryTransport: Send + Sync {
    async fn post_event(
        &self,
        base_url: &str,
        event: &FederationEvent,
    ) -> Result<DeliveryHttpResponse, DeliveryTransportError>;
}

struct ReqwestDeliveryTransport {
    client: Client,
}

impl ReqwestDeliveryTransport {
    fn new(timeout: Duration) -> anyhow::Result<Self> {
        Ok(Self {
            client: Client::builder()
                .connect_timeout(Duration::from_secs(3).min(timeout))
                .timeout(timeout)
                .redirect(Policy::none())
                .user_agent("weltgewebe-federation-delivery/1")
                .build()?,
        })
    }
}

#[async_trait]
impl DeliveryTransport for ReqwestDeliveryTransport {
    async fn post_event(
        &self,
        base_url: &str,
        event: &FederationEvent,
    ) -> Result<DeliveryHttpResponse, DeliveryTransportError> {
        let endpoint = event_endpoint(base_url).map_err(|_| DeliveryTransportError {
            class: "invalid-delivery-endpoint",
        })?;
        let response = self
            .client
            .post(endpoint)
            .json(event)
            .send()
            .await
            .map_err(|error| DeliveryTransportError {
                class: if error.is_timeout() {
                    "request-timeout"
                } else if error.is_connect() {
                    "connect-failed"
                } else {
                    "request-failed"
                },
            })?;
        let status = response.status().as_u16();
        let retry_after_seconds = response
            .headers()
            .get(reqwest::header::RETRY_AFTER)
            .and_then(|value| value.to_str().ok())
            .and_then(|value| value.parse::<u64>().ok())
            .map(|value| value.min(MAX_BACKOFF_SECONDS));
        let mut body = Vec::new();
        let mut stream = response.bytes_stream();
        while let Some(chunk) = stream.next().await {
            let chunk = chunk.map_err(|_| DeliveryTransportError {
                class: "response-read-failed",
            })?;
            if body.len().saturating_add(chunk.len()) > MAX_RESPONSE_BYTES {
                return Err(DeliveryTransportError {
                    class: "response-too-large",
                });
            }
            body.extend_from_slice(&chunk);
        }
        Ok(DeliveryHttpResponse {
            status,
            retry_after_seconds,
            body,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum DeliveryDecision {
    Delivered {
        http_status: u16,
    },
    Retry {
        http_status: Option<u16>,
        error_class: &'static str,
        retry_after_seconds: Option<u64>,
    },
    Dead {
        http_status: Option<u16>,
        error_class: &'static str,
    },
}

fn classify_response(
    response: DeliveryHttpResponse,
    expected_event_id: Uuid,
    expected_object_version: i64,
) -> DeliveryDecision {
    if response.status == 429 || response.status >= 500 {
        return DeliveryDecision::Retry {
            http_status: Some(response.status),
            error_class: if response.status == 429 {
                "remote-rate-limited"
            } else {
                "remote-server-error"
            },
            retry_after_seconds: response.retry_after_seconds,
        };
    }
    if (200..300).contains(&response.status) {
        let outcome: ReceiveOutcome = match serde_json::from_slice(&response.body) {
            Ok(outcome) => outcome,
            Err(_) => {
                return DeliveryDecision::Dead {
                    http_status: Some(response.status),
                    error_class: "invalid-success-response",
                }
            }
        };
        if outcome.event_id != expected_event_id {
            return DeliveryDecision::Dead {
                http_status: Some(response.status),
                error_class: "response-event-mismatch",
            };
        }
        return match outcome.status {
            ReceiveStatus::Applied | ReceiveStatus::Duplicate
                if outcome.object_version == Some(expected_object_version) =>
            {
                DeliveryDecision::Delivered {
                    http_status: response.status,
                }
            }
            ReceiveStatus::Applied | ReceiveStatus::Duplicate => DeliveryDecision::Dead {
                http_status: Some(response.status),
                error_class: "response-version-mismatch",
            },
            ReceiveStatus::Rejected => DeliveryDecision::Retry {
                http_status: Some(response.status),
                error_class: "remote-rejected",
                retry_after_seconds: response.retry_after_seconds,
            },
            ReceiveStatus::Quarantined => DeliveryDecision::Retry {
                http_status: Some(response.status),
                error_class: "remote-quarantined",
                retry_after_seconds: response.retry_after_seconds,
            },
        };
    }
    DeliveryDecision::Dead {
        http_status: Some(response.status),
        error_class: "remote-client-or-protocol-error",
    }
}

fn retry_delay_seconds(event_id: Uuid, attempt_count: u32) -> u64 {
    let exponent = attempt_count.saturating_sub(1).min(6);
    let base = 5_u64.saturating_mul(1_u64 << exponent);
    let jitter = u64::from(event_id.as_bytes()[15] % 5);
    base.saturating_add(jitter).min(MAX_BACKOFF_SECONDS)
}

fn effective_retry_delay_seconds(
    event_id: Uuid,
    attempt_count: u32,
    retry_after_seconds: Option<u64>,
) -> u64 {
    let computed = retry_delay_seconds(event_id, attempt_count);
    retry_after_seconds
        .map(|remote| remote.max(computed))
        .unwrap_or(computed)
        .min(MAX_BACKOFF_SECONDS)
}

#[derive(Debug)]
struct DeliveryClaim {
    event_id: Uuid,
    target_cell_id: String,
    attempt_count: u32,
    lease_owner: Uuid,
}

pub fn start(pool: PgPool, config: DeliveryWorkerConfig) -> anyhow::Result<JoinHandle<()>> {
    let transport = Arc::new(ReqwestDeliveryTransport::new(config.request_timeout)?);
    Ok(tokio::spawn(run_worker(pool, config, transport)))
}

async fn run_worker(
    pool: PgPool,
    config: DeliveryWorkerConfig,
    transport: Arc<dyn DeliveryTransport>,
) {
    let worker_id = Uuid::new_v4();
    let mut ticker = tokio::time::interval(config.poll_interval);
    ticker.set_missed_tick_behavior(MissedTickBehavior::Delay);
    loop {
        ticker.tick().await;
        match run_delivery_batch(&pool, &config, transport.as_ref(), worker_id).await {
            Ok(delivered) if delivered > 0 => {
                tracing::debug!(worker_id = %worker_id, processed = delivered, "federation delivery batch processed");
            }
            Ok(_) => {}
            Err(error) => {
                tracing::warn!(worker_id = %worker_id, %error, "federation delivery batch failed");
            }
        }
    }
}

pub async fn run_delivery_batch(
    pool: &PgPool,
    config: &DeliveryWorkerConfig,
    transport: &dyn DeliveryTransport,
    worker_id: Uuid,
) -> anyhow::Result<usize> {
    expire_exhausted_deliveries(pool, config.max_attempts).await?;
    let lease_seconds = delivery_lease_seconds(config)?;
    let mut processed = 0;
    for _ in 0..config.batch_size {
        let Some(claim) = claim_due_delivery(pool, worker_id, lease_seconds).await? else {
            break;
        };
        execute_claim(pool, config, transport, claim).await?;
        processed += 1;
    }
    Ok(processed)
}

fn delivery_lease_seconds(config: &DeliveryWorkerConfig) -> anyhow::Result<i64> {
    let seconds = config
        .request_timeout
        .as_secs()
        .saturating_add(DELIVERY_LEASE_GRACE_SECONDS);
    Ok(i64::try_from(seconds)?)
}

async fn expire_exhausted_deliveries(pool: &PgPool, max_attempts: u32) -> anyhow::Result<()> {
    sqlx::query(
        "UPDATE federation_delivery_attempts \
         SET state = 'dead', next_attempt_at = NOW(), \
             lease_owner = NULL, lease_expires_at = NULL, \
             last_error_class = 'delivery-attempts-exhausted', updated_at = NOW() \
         WHERE attempt_count >= $1 \
           AND ( \
             state IN ('pending', 'retry') \
             OR (state = 'in_flight' AND lease_expires_at <= NOW()) \
           )",
    )
    .bind(i32::try_from(max_attempts)?)
    .execute(pool)
    .await?;
    Ok(())
}

pub(crate) async fn enqueue_delivery_targets(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    event: &FederationEvent,
) -> anyhow::Result<()> {
    sqlx::query(
        "INSERT INTO federation_delivery_attempts (event_id, target_cell_id) \
         SELECT $1, relationship.remote_cell_id \
         FROM federation_peer_relationships AS relationship \
         WHERE relationship.state = 'trusted' \
           AND relationship.delivery_base_url IS NOT NULL \
           AND ( \
             $2 = 'global' \
             OR ( \
               $2 = 'neighbourhood' \
               AND relationship.allow_neighbourhood \
               AND relationship.remote_cell_id = ANY($3::text[]) \
             ) \
           ) \
         ON CONFLICT (event_id, target_cell_id) DO NOTHING",
    )
    .bind(event.event_id)
    .bind(&event.scope)
    .bind(&event.neighbourhood_targets)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

pub(crate) async fn backfill_delivery_targets(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    target_cell_ids: &[String],
) -> anyhow::Result<()> {
    if target_cell_ids.is_empty() {
        return Ok(());
    }
    sqlx::query(
        "INSERT INTO federation_delivery_attempts (event_id, target_cell_id) \
         SELECT outbox.event_id, relationship.remote_cell_id \
         FROM federation_outbox AS outbox \
         JOIN federation_peer_relationships AS relationship \
           ON relationship.remote_cell_id = ANY($1::text[]) \
          AND relationship.state = 'trusted' \
          AND relationship.delivery_base_url IS NOT NULL \
          AND ( \
            outbox.envelope ->> 'scope' = 'global' \
            OR ( \
              outbox.envelope ->> 'scope' = 'neighbourhood' \
              AND relationship.allow_neighbourhood \
              AND (outbox.envelope -> 'neighbourhood_targets') ? relationship.remote_cell_id \
            ) \
          ) \
         ON CONFLICT (event_id, target_cell_id) DO UPDATE SET \
           state = 'pending', \
           attempt_count = 0, \
           next_attempt_at = NOW(), \
           lease_owner = NULL, \
           lease_expires_at = NULL, \
           last_http_status = NULL, \
           last_error_class = NULL, \
           delivered_at = NULL, \
           updated_at = NOW() \
         WHERE federation_delivery_attempts.state = 'dead' \
           AND federation_delivery_attempts.last_error_class IN ( \
             'peer-not-trusted', \
             'event-type-not-allowed', \
             'neighbourhood-target-not-allowed', \
             'scope-not-deliverable', \
             'delivery-endpoint-missing', \
             'delivery-endpoint-invalid', \
             'remote-rejected', \
             'remote-quarantined', \
             'delivery-attempts-exhausted' \
           )",
    )
    .bind(target_cell_ids)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

async fn claim_due_delivery(
    pool: &PgPool,
    worker_id: Uuid,
    lease_seconds: i64,
) -> anyhow::Result<Option<DeliveryClaim>> {
    let row = sqlx::query(
        "WITH candidate AS ( \
           SELECT delivery.event_id, delivery.target_cell_id \
           FROM federation_delivery_attempts AS delivery \
           JOIN federation_outbox AS outbox USING (event_id) \
           WHERE ( \
             (delivery.state IN ('pending', 'retry') AND delivery.next_attempt_at <= NOW()) \
             OR (delivery.state = 'in_flight' AND delivery.lease_expires_at <= NOW()) \
           ) \
             AND NOT EXISTS ( \
               SELECT 1 \
               FROM federation_delivery_attempts AS predecessor \
               JOIN federation_outbox AS predecessor_outbox \
                 ON predecessor_outbox.event_id = predecessor.event_id \
               WHERE predecessor.target_cell_id = delivery.target_cell_id \
                 AND predecessor_outbox.object_address = outbox.object_address \
                 AND predecessor_outbox.object_version < outbox.object_version \
                 AND predecessor.state <> 'delivered' \
             ) \
           ORDER BY delivery.next_attempt_at, outbox.created_at, delivery.event_id, delivery.target_cell_id \
           FOR UPDATE OF delivery SKIP LOCKED \
           LIMIT 1 \
         ) \
         UPDATE federation_delivery_attempts AS delivery \
         SET state = 'in_flight', \
             attempt_count = delivery.attempt_count + 1, \
             lease_owner = $1, \
             lease_expires_at = NOW() + ($2 * INTERVAL '1 second'), \
             updated_at = NOW() \
         FROM candidate \
         WHERE delivery.event_id = candidate.event_id \
           AND delivery.target_cell_id = candidate.target_cell_id \
         RETURNING delivery.event_id, delivery.target_cell_id, delivery.attempt_count",
    )
    .bind(worker_id)
    .bind(lease_seconds)
    .fetch_optional(pool)
    .await?;
    let Some(row) = row else {
        return Ok(None);
    };
    let attempt_count: i32 = row.try_get("attempt_count")?;
    Ok(Some(DeliveryClaim {
        event_id: row.try_get("event_id")?,
        target_cell_id: row.try_get("target_cell_id")?,
        attempt_count: u32::try_from(attempt_count)?,
        lease_owner: worker_id,
    }))
}

struct DeliveryContext {
    event: FederationEvent,
    peer_state: String,
    allow_neighbourhood: bool,
    allowed_event_types: Vec<String>,
    delivery_base_url: Option<String>,
}

async fn load_delivery_context(
    pool: &PgPool,
    claim: &DeliveryClaim,
) -> anyhow::Result<Option<DeliveryContext>> {
    let row = sqlx::query(
        "SELECT delivery.state AS delivery_state, delivery.lease_owner, \
                outbox.envelope, outbox.envelope_sha256, relationship.state AS peer_state, \
                relationship.allow_neighbourhood, relationship.allowed_event_types, \
                relationship.delivery_base_url \
         FROM federation_delivery_attempts AS delivery \
         JOIN federation_outbox AS outbox USING (event_id) \
         JOIN federation_peer_relationships AS relationship \
           ON relationship.remote_cell_id = delivery.target_cell_id \
         WHERE delivery.event_id = $1 AND delivery.target_cell_id = $2",
    )
    .bind(claim.event_id)
    .bind(&claim.target_cell_id)
    .fetch_optional(pool)
    .await?;
    let Some(row) = row else {
        return Ok(None);
    };
    let delivery_state: String = row.try_get("delivery_state")?;
    let lease_owner: Option<Uuid> = row.try_get("lease_owner")?;
    if delivery_state != "in_flight" || lease_owner != Some(claim.lease_owner) {
        return Ok(None);
    }
    let envelope: Value = row.try_get("envelope")?;
    let event: FederationEvent = match serde_json::from_value(envelope) {
        Ok(event) => event,
        Err(error) => {
            tracing::error!(event_id = %claim.event_id, %error, "invalid federation outbox envelope");
            mark_dead(pool, claim, None, "invalid-outbox-envelope").await?;
            return Ok(None);
        }
    };
    let stored_envelope_sha256: String = row.try_get("envelope_sha256")?;
    let observed_envelope_sha256 = crate::federation::envelope_sha256(&event)?;
    if stored_envelope_sha256 != observed_envelope_sha256 {
        tracing::error!(
            event_id = %claim.event_id,
            stored_envelope_sha256,
            observed_envelope_sha256,
            "federation outbox envelope digest mismatch"
        );
        mark_dead(pool, claim, None, "outbox-envelope-digest-mismatch").await?;
        return Ok(None);
    }
    let allowed_event_types: Value = row.try_get("allowed_event_types")?;
    let allowed_event_types: Vec<String> = match serde_json::from_value(allowed_event_types) {
        Ok(event_types) => event_types,
        Err(error) => {
            tracing::error!(target_cell_id = %claim.target_cell_id, %error, "invalid federation peer policy");
            mark_dead(pool, claim, None, "invalid-peer-policy").await?;
            return Ok(None);
        }
    };
    Ok(Some(DeliveryContext {
        event,
        peer_state: row.try_get("peer_state")?,
        allow_neighbourhood: row.try_get("allow_neighbourhood")?,
        allowed_event_types,
        delivery_base_url: row.try_get("delivery_base_url")?,
    }))
}

async fn execute_claim(
    pool: &PgPool,
    config: &DeliveryWorkerConfig,
    transport: &dyn DeliveryTransport,
    claim: DeliveryClaim,
) -> anyhow::Result<()> {
    let Some(context) = load_delivery_context(pool, &claim).await? else {
        return Ok(());
    };
    let policy_error = delivery_policy_error(
        &context.event,
        &claim.target_cell_id,
        &context.peer_state,
        context.allow_neighbourhood,
        &context.allowed_event_types,
        context.delivery_base_url.as_deref(),
    );
    if let Some(error_class) = policy_error {
        mark_dead(pool, &claim, None, error_class).await?;
        return Ok(());
    }
    let base_url = context
        .delivery_base_url
        .as_deref()
        .expect("validated delivery base URL");
    let decision = match transport.post_event(base_url, &context.event).await {
        Ok(response) => classify_response(
            response,
            context.event.event_id,
            context.event.object_version,
        ),
        Err(error) => DeliveryDecision::Retry {
            http_status: None,
            error_class: error.class,
            retry_after_seconds: None,
        },
    };
    let decision = match decision {
        DeliveryDecision::Retry {
            http_status,
            error_class,
            ..
        } if claim.attempt_count >= config.max_attempts => DeliveryDecision::Dead {
            http_status,
            error_class: match error_class {
                "remote-rejected" => "remote-rejected",
                "remote-quarantined" => "remote-quarantined",
                _ => "delivery-attempts-exhausted",
            },
        },
        other => other,
    };
    finalize_decision(pool, &claim, decision).await
}

async fn finalize_decision(
    pool: &PgPool,
    claim: &DeliveryClaim,
    decision: DeliveryDecision,
) -> anyhow::Result<()> {
    match decision {
        DeliveryDecision::Delivered { http_status } => {
            sqlx::query(
                "UPDATE federation_delivery_attempts \
                 SET state = 'delivered', delivered_at = NOW(), next_attempt_at = NOW(), \
                     lease_owner = NULL, lease_expires_at = NULL, \
                     last_http_status = $4, last_error_class = NULL, updated_at = NOW() \
                 WHERE event_id = $1 AND target_cell_id = $2 \
                   AND state = 'in_flight' AND lease_owner = $3",
            )
            .bind(claim.event_id)
            .bind(&claim.target_cell_id)
            .bind(claim.lease_owner)
            .bind(i32::from(http_status))
            .execute(pool)
            .await?;
        }
        DeliveryDecision::Retry {
            http_status,
            error_class,
            retry_after_seconds,
        } => {
            let delay = effective_retry_delay_seconds(
                claim.event_id,
                claim.attempt_count,
                retry_after_seconds,
            );
            sqlx::query(
                "UPDATE federation_delivery_attempts \
                 SET state = 'retry', \
                     next_attempt_at = NOW() + ($4 * INTERVAL '1 second'), \
                     lease_owner = NULL, lease_expires_at = NULL, \
                     last_http_status = $5, last_error_class = $6, updated_at = NOW() \
                 WHERE event_id = $1 AND target_cell_id = $2 \
                   AND state = 'in_flight' AND lease_owner = $3",
            )
            .bind(claim.event_id)
            .bind(&claim.target_cell_id)
            .bind(claim.lease_owner)
            .bind(i64::try_from(delay)?)
            .bind(http_status.map(i32::from))
            .bind(error_class)
            .execute(pool)
            .await?;
        }
        DeliveryDecision::Dead {
            http_status,
            error_class,
        } => {
            mark_dead(pool, claim, http_status, error_class).await?;
        }
    }
    Ok(())
}

fn delivery_policy_error(
    event: &FederationEvent,
    target_cell_id: &str,
    peer_state: &str,
    allow_neighbourhood: bool,
    allowed_event_types: &[String],
    delivery_base_url: Option<&str>,
) -> Option<&'static str> {
    if event.origin_cell_id == target_cell_id {
        return Some("self-delivery-forbidden");
    }
    if peer_state != "trusted" {
        return Some("peer-not-trusted");
    }
    if !allowed_event_types
        .iter()
        .any(|value| value == &event.event_type)
    {
        return Some("event-type-not-allowed");
    }
    match event.scope.as_str() {
        "global" => {}
        "neighbourhood"
            if allow_neighbourhood
                && event
                    .neighbourhood_targets
                    .iter()
                    .any(|value| value == target_cell_id) => {}
        "neighbourhood" => return Some("neighbourhood-target-not-allowed"),
        _ => return Some("scope-not-deliverable"),
    }
    let Some(delivery_base_url) = delivery_base_url else {
        return Some("delivery-endpoint-missing");
    };
    if validate_delivery_base_url(delivery_base_url).is_err() {
        return Some("delivery-endpoint-invalid");
    }
    None
}

async fn mark_dead(
    pool: &PgPool,
    claim: &DeliveryClaim,
    http_status: Option<u16>,
    error_class: &str,
) -> anyhow::Result<()> {
    sqlx::query(
        "UPDATE federation_delivery_attempts \
         SET state = 'dead', next_attempt_at = NOW(), \
             lease_owner = NULL, lease_expires_at = NULL, \
             last_http_status = $4, last_error_class = $5, updated_at = NOW() \
         WHERE event_id = $1 AND target_cell_id = $2 \
           AND state = 'in_flight' AND lease_owner = $3",
    )
    .bind(claim.event_id)
    .bind(&claim.target_cell_id)
    .bind(claim.lease_owner)
    .bind(http_status.map(i32::from))
    .bind(error_class)
    .execute(pool)
    .await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{collections::HashSet, sync::Arc};

    use sqlx::postgres::PgPoolOptions;

    use crate::federation::{
        FederationEvent, FederationRepository, FederationService, MemoryFederationRepository,
        PeerPolicy, PostgresFederationRepository, PublishRequest,
    };
    use crate::test_helpers::EnvGuard;
    use serial_test::serial;

    #[test]
    fn delivery_url_is_https_and_credential_free() {
        assert_eq!(
            validate_delivery_base_url("https://cell.example/edge/").unwrap(),
            "https://cell.example/edge"
        );
        assert!(validate_delivery_base_url("http://cell.example").is_err());
        assert!(validate_delivery_base_url("https://user@cell.example").is_err());
        assert!(validate_delivery_base_url("https://cell.example?token=x").is_err());
        assert!(validate_delivery_base_url("https://127.0.0.1").is_err());
        assert!(validate_delivery_base_url("https://[::1]").is_err());
    }

    #[test]
    fn response_classification_is_fail_closed() {
        let applied = ReceiveOutcome {
            status: ReceiveStatus::Applied,
            event_id: Uuid::nil(),
            reason: None,
            object_version: Some(1),
        };
        assert_eq!(
            classify_response(
                DeliveryHttpResponse {
                    status: 201,
                    retry_after_seconds: None,
                    body: serde_json::to_vec(&applied).unwrap(),
                },
                Uuid::nil(),
                1,
            ),
            DeliveryDecision::Delivered { http_status: 201 }
        );
        assert!(matches!(
            classify_response(
                DeliveryHttpResponse {
                    status: 202,
                    retry_after_seconds: None,
                    body: b"{}".to_vec(),
                },
                Uuid::nil(),
                1,
            ),
            DeliveryDecision::Dead { .. }
        ));
        assert!(matches!(
            classify_response(
                DeliveryHttpResponse {
                    status: 503,
                    retry_after_seconds: None,
                    body: Vec::new(),
                },
                Uuid::nil(),
                1,
            ),
            DeliveryDecision::Retry { .. }
        ));
        assert!(matches!(
            classify_response(
                DeliveryHttpResponse {
                    status: 201,
                    retry_after_seconds: None,
                    body: serde_json::to_vec(&ReceiveOutcome {
                        status: ReceiveStatus::Applied,
                        event_id: Uuid::new_v4(),
                        reason: None,
                        object_version: Some(1),
                    })
                    .unwrap(),
                },
                Uuid::nil(),
                1,
            ),
            DeliveryDecision::Dead {
                error_class: "response-event-mismatch",
                ..
            }
        ));
        assert!(matches!(
            classify_response(
                DeliveryHttpResponse {
                    status: 201,
                    retry_after_seconds: None,
                    body: serde_json::to_vec(&ReceiveOutcome {
                        status: ReceiveStatus::Applied,
                        event_id: Uuid::nil(),
                        reason: None,
                        object_version: Some(2),
                    })
                    .unwrap(),
                },
                Uuid::nil(),
                1,
            ),
            DeliveryDecision::Dead {
                error_class: "response-version-mismatch",
                ..
            }
        ));
    }

    #[test]
    fn retry_after_cannot_shorten_local_backoff() {
        let event_id = Uuid::nil();
        let local = retry_delay_seconds(event_id, 2);
        assert_eq!(effective_retry_delay_seconds(event_id, 2, Some(0)), local);
        assert_eq!(effective_retry_delay_seconds(event_id, 2, Some(1)), local);
        assert_eq!(
            effective_retry_delay_seconds(event_id, 2, Some(local + 7)),
            local + 7
        );
    }

    #[test]
    fn delivery_lease_exceeds_request_timeout() {
        let config = DeliveryWorkerConfig {
            poll_interval: Duration::from_secs(1),
            request_timeout: Duration::from_secs(30),
            batch_size: 1,
            max_attempts: 3,
        };
        assert!(delivery_lease_seconds(&config).unwrap() > 30);
    }

    #[test]
    #[serial]
    fn delivery_config_is_explicit_and_bounded() {
        let _enabled = EnvGuard::set(DELIVERY_ENABLED_ENV, "true");
        let _poll = EnvGuard::set(DELIVERY_POLL_SECONDS_ENV, "2");
        let _timeout = EnvGuard::set(DELIVERY_REQUEST_TIMEOUT_SECONDS_ENV, "4");
        let _batch = EnvGuard::set(DELIVERY_BATCH_SIZE_ENV, "7");
        let _attempts = EnvGuard::set(DELIVERY_MAX_ATTEMPTS_ENV, "6");
        let config = DeliveryWorkerConfig::from_env().unwrap().unwrap();
        assert_eq!(config.poll_interval, Duration::from_secs(2));
        assert_eq!(config.request_timeout, Duration::from_secs(4));
        assert_eq!(config.batch_size, 7);
        assert_eq!(config.max_attempts, 6);
    }

    struct ReceiverTransport {
        receiver: crate::federation::FederationService,
        calls: std::sync::atomic::AtomicUsize,
        fail_first: bool,
        delay: Duration,
    }

    impl ReceiverTransport {
        fn new(receiver: crate::federation::FederationService, fail_first: bool) -> Self {
            Self {
                receiver,
                calls: std::sync::atomic::AtomicUsize::new(0),
                fail_first,
                delay: Duration::ZERO,
            }
        }

        fn with_delay(mut self, delay: Duration) -> Self {
            self.delay = delay;
            self
        }

        fn calls(&self) -> usize {
            self.calls.load(std::sync::atomic::Ordering::SeqCst)
        }
    }

    #[async_trait]
    impl DeliveryTransport for ReceiverTransport {
        async fn post_event(
            &self,
            _base_url: &str,
            event: &FederationEvent,
        ) -> Result<DeliveryHttpResponse, DeliveryTransportError> {
            let call = self.calls.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            if self.fail_first && call == 0 {
                return Err(DeliveryTransportError {
                    class: "simulated-transient-failure",
                });
            }
            if !self.delay.is_zero() {
                tokio::time::sleep(self.delay).await;
            }
            let outcome =
                self.receiver
                    .receive(event.clone())
                    .await
                    .map_err(|_| DeliveryTransportError {
                        class: "test-receiver-failed",
                    })?;
            Ok(DeliveryHttpResponse {
                status: match outcome.status {
                    ReceiveStatus::Applied => 201,
                    _ => 200,
                },
                retry_after_seconds: None,
                body: serde_json::to_vec(&outcome).map_err(|_| DeliveryTransportError {
                    class: "test-response-serialization-failed",
                })?,
            })
        }
    }

    struct GateTransport {
        receiver: crate::federation::FederationService,
        calls: std::sync::atomic::AtomicUsize,
        entered: tokio::sync::Notify,
        release: tokio::sync::Notify,
    }

    impl GateTransport {
        fn new(receiver: crate::federation::FederationService) -> Self {
            Self {
                receiver,
                calls: std::sync::atomic::AtomicUsize::new(0),
                entered: tokio::sync::Notify::new(),
                release: tokio::sync::Notify::new(),
            }
        }

        fn calls(&self) -> usize {
            self.calls.load(std::sync::atomic::Ordering::SeqCst)
        }
    }

    #[async_trait]
    impl DeliveryTransport for GateTransport {
        async fn post_event(
            &self,
            _base_url: &str,
            event: &FederationEvent,
        ) -> Result<DeliveryHttpResponse, DeliveryTransportError> {
            self.calls.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            self.entered.notify_one();
            self.release.notified().await;
            let outcome =
                self.receiver
                    .receive(event.clone())
                    .await
                    .map_err(|_| DeliveryTransportError {
                        class: "test-receiver-failed",
                    })?;
            Ok(DeliveryHttpResponse {
                status: match outcome.status {
                    ReceiveStatus::Applied => 201,
                    _ => 200,
                },
                retry_after_seconds: None,
                body: serde_json::to_vec(&outcome).map_err(|_| DeliveryTransportError {
                    class: "test-response-serialization-failed",
                })?,
            })
        }
    }

    fn test_identity(cell_id: &str, key_id: &str, seed: u8) -> crate::federation::CellIdentity {
        crate::federation::CellIdentity::new(
            cell_id,
            format!("https://{cell_id}.example.test"),
            key_id,
            [seed; 32],
        )
        .expect("test identity")
    }

    fn delivery_test_config() -> DeliveryWorkerConfig {
        DeliveryWorkerConfig {
            poll_interval: Duration::from_secs(1),
            request_timeout: Duration::from_secs(2),
            batch_size: 1,
            max_attempts: 3,
        }
    }

    async fn isolated_delivery_pool() -> anyhow::Result<PgPool> {
        let database_url = env::var("FEDERATION_TEST_DATABASE_URL")
            .context("FEDERATION_TEST_DATABASE_URL must identify an isolated database")?;
        let pool = PgPoolOptions::new()
            .max_connections(8)
            .connect(&database_url)
            .await?;
        sqlx::migrate!("./migrations").run(&pool).await?;
        sqlx::query(
            "TRUNCATE federation_delivery_attempts, federation_event_receipts, \
             federation_quarantine, federation_inbox, federation_outbox, federation_objects, \
             federation_peer_keys, federation_peer_relationships RESTART IDENTITY CASCADE",
        )
        .execute(&pool)
        .await?;
        Ok(pool)
    }

    fn delivery_peer_policy(cell_id: &str, state: &str, seed: u8) -> PeerPolicy {
        PeerPolicy {
            remote_cell_id: cell_id.to_string(),
            state: state.to_string(),
            allow_neighbourhood: true,
            allowed_event_types: HashSet::from(["object.upserted".to_string()]),
            keys: vec![test_identity(cell_id, &format!("key-{cell_id}"), seed).peer_key()],
        }
    }

    async fn postgres_sender(
        pool: &PgPool,
        peers: &[PeerPolicy],
    ) -> anyhow::Result<(Arc<PostgresFederationRepository>, FederationService)> {
        let repository = Arc::new(PostgresFederationRepository::new(pool.clone()));
        let sender =
            FederationService::new(test_identity("cell-a", "key-a", 90), repository.clone());
        for peer in peers {
            sender.install_peer(peer.clone()).await?;
        }
        Ok((repository, sender))
    }

    async fn publish_global(
        sender: &FederationService,
        object_suffix: &str,
    ) -> anyhow::Result<FederationEvent> {
        sender
            .publish_local(PublishRequest {
                actor: "system:reconcile-batch-proof".to_string(),
                event_type: "object.upserted".to_string(),
                object_address: format!("wg://cell-a/node/{object_suffix}"),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: "global".to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"proof": object_suffix}),
            })
            .await
    }

    type RelationshipSnapshot = (String, Option<String>, Option<String>, String);

    async fn relationship_snapshot(pool: &PgPool) -> anyhow::Result<Vec<RelationshipSnapshot>> {
        Ok(sqlx::query_as(
            "SELECT remote_cell_id, delivery_base_url, delivery_policy_sha256, updated_at::text \
             FROM federation_peer_relationships ORDER BY remote_cell_id",
        )
        .fetch_all(pool)
        .await?)
    }

    type AttemptSnapshot = (
        String,
        i32,
        String,
        Option<Uuid>,
        Option<String>,
        Option<i32>,
        Option<String>,
        Option<String>,
        String,
    );

    async fn attempt_snapshot(
        pool: &PgPool,
        event_id: Uuid,
        target_cell_id: &str,
    ) -> anyhow::Result<AttemptSnapshot> {
        Ok(sqlx::query_as(
            "SELECT state, attempt_count, next_attempt_at::text, lease_owner, \
                    lease_expires_at::text, last_http_status, last_error_class, \
                    delivered_at::text, updated_at::text \
             FROM federation_delivery_attempts \
             WHERE event_id = $1 AND target_cell_id = $2",
        )
        .bind(event_id)
        .bind(target_cell_id)
        .fetch_one(pool)
        .await?)
    }

    #[tokio::test]
    #[ignore = "requires an isolated FEDERATION_TEST_DATABASE_URL"]
    #[serial]
    async fn postgres_reconcile_noop_preserves_timestamps_and_delivery_state() -> anyhow::Result<()>
    {
        let pool = isolated_delivery_pool().await?;
        let peer = delivery_peer_policy("cell-b", "trusted", 91);
        let (repository, sender) = postgres_sender(&pool, std::slice::from_ref(&peer)).await?;
        let binding = (
            peer.clone(),
            Some("https://cell-b.example.test/edge".to_string()),
        );
        repository
            .reconcile_delivery_endpoints(std::slice::from_ref(&binding))
            .await?;
        let event = publish_global(&sender, "reconcile-noop").await?;
        sqlx::query(
            "UPDATE federation_delivery_attempts \
             SET state = 'dead', attempt_count = 4, \
                 next_attempt_at = TIMESTAMPTZ '2001-01-01 00:00:00+00', \
                 last_http_status = 202, last_error_class = 'remote-quarantined', \
                 updated_at = TIMESTAMPTZ '2001-01-02 00:00:00+00' \
             WHERE event_id = $1 AND target_cell_id = 'cell-b'",
        )
        .bind(event.event_id)
        .execute(&pool)
        .await?;
        let relationships_before = relationship_snapshot(&pool).await?;
        let attempt_before = attempt_snapshot(&pool, event.event_id, "cell-b").await?;

        let equivalent_binding = (
            peer,
            Some("  https://cell-b.example.test/edge/  ".to_string()),
        );
        repository
            .reconcile_delivery_endpoints(std::slice::from_ref(&equivalent_binding))
            .await?;

        assert_eq!(relationship_snapshot(&pool).await?, relationships_before);
        assert_eq!(
            attempt_snapshot(&pool, event.event_id, "cell-b").await?,
            attempt_before
        );
        Ok(())
    }

    #[tokio::test]
    #[ignore = "requires an isolated FEDERATION_TEST_DATABASE_URL"]
    #[serial]
    async fn postgres_reconcile_updates_and_backfills_multiple_changed_peers() -> anyhow::Result<()>
    {
        let pool = isolated_delivery_pool().await?;
        let cell_b = delivery_peer_policy("cell-b", "trusted", 91);
        let cell_c = delivery_peer_policy("cell-c", "trusted", 92);
        let (repository, sender) =
            postgres_sender(&pool, &[cell_b.clone(), cell_c.clone()]).await?;
        let event = publish_global(&sender, "reconcile-multiple").await?;

        repository
            .reconcile_delivery_endpoints(&[
                (
                    cell_c,
                    Some("https://cell-c.example.test/edge/".to_string()),
                ),
                (cell_b, Some("https://cell-b.example.test".to_string())),
            ])
            .await?;

        let relationships: Vec<(String, Option<String>, bool)> = sqlx::query_as(
            "SELECT remote_cell_id, delivery_base_url, delivery_policy_sha256 IS NOT NULL \
             FROM federation_peer_relationships ORDER BY remote_cell_id",
        )
        .fetch_all(&pool)
        .await?;
        assert_eq!(
            relationships,
            vec![
                (
                    "cell-b".to_string(),
                    Some("https://cell-b.example.test".to_string()),
                    true,
                ),
                (
                    "cell-c".to_string(),
                    Some("https://cell-c.example.test/edge".to_string()),
                    true,
                ),
            ]
        );
        let targets: Vec<String> = sqlx::query_scalar(
            "SELECT target_cell_id FROM federation_delivery_attempts \
             WHERE event_id = $1 ORDER BY target_cell_id",
        )
        .bind(event.event_id)
        .fetch_all(&pool)
        .await?;
        assert_eq!(targets, vec!["cell-b".to_string(), "cell-c".to_string()]);
        Ok(())
    }

    #[tokio::test]
    #[ignore = "requires an isolated FEDERATION_TEST_DATABASE_URL"]
    #[serial]
    async fn postgres_reconcile_validates_before_mutation_and_rolls_back_unknown_peer(
    ) -> anyhow::Result<()> {
        let pool = isolated_delivery_pool().await?;
        let cell_b = delivery_peer_policy("cell-b", "trusted", 91);
        let cell_c = delivery_peer_policy("cell-c", "trusted", 92);
        let (repository, _) = postgres_sender(&pool, &[cell_b.clone(), cell_c.clone()]).await?;
        repository
            .reconcile_delivery_endpoints(&[
                (
                    cell_b.clone(),
                    Some("https://cell-b.example.test/original".to_string()),
                ),
                (
                    cell_c.clone(),
                    Some("https://cell-c.example.test/original".to_string()),
                ),
            ])
            .await?;
        let before = relationship_snapshot(&pool).await?;

        let validation_error = repository
            .reconcile_delivery_endpoints(&[
                (
                    cell_b.clone(),
                    Some("https://cell-b.example.test/changed".to_string()),
                ),
                (
                    cell_c.clone(),
                    Some("http://cell-c.example.test".to_string()),
                ),
            ])
            .await
            .unwrap_err();
        assert!(validation_error.to_string().contains("must use https"));
        assert_eq!(relationship_snapshot(&pool).await?, before);

        let unknown = delivery_peer_policy("cell-unknown", "trusted", 93);
        let unknown_error = repository
            .reconcile_delivery_endpoints(&[
                (
                    cell_b,
                    Some("https://cell-b.example.test/changed".to_string()),
                ),
                (
                    unknown,
                    Some("https://cell-unknown.example.test".to_string()),
                ),
            ])
            .await
            .unwrap_err();
        assert!(unknown_error
            .to_string()
            .contains("delivery endpoint references unknown peer cell-unknown"));
        assert_eq!(relationship_snapshot(&pool).await?, before);
        Ok(())
    }

    #[tokio::test]
    #[ignore = "requires an isolated FEDERATION_TEST_DATABASE_URL"]
    #[serial]
    async fn postgres_reconcile_backfills_trusted_but_not_blocked_peer() -> anyhow::Result<()> {
        let pool = isolated_delivery_pool().await?;
        let trusted = delivery_peer_policy("cell-b", "trusted", 91);
        let blocked = delivery_peer_policy("cell-c", "blocked", 92);
        let (repository, sender) =
            postgres_sender(&pool, &[trusted.clone(), blocked.clone()]).await?;
        let event = publish_global(&sender, "reconcile-trust-filter").await?;

        repository
            .reconcile_delivery_endpoints(&[
                (trusted, Some("https://cell-b.example.test".to_string())),
                (blocked, Some("https://cell-c.example.test".to_string())),
            ])
            .await?;

        let endpoints: Vec<(String, Option<String>)> = sqlx::query_as(
            "SELECT remote_cell_id, delivery_base_url \
             FROM federation_peer_relationships ORDER BY remote_cell_id",
        )
        .fetch_all(&pool)
        .await?;
        assert_eq!(
            endpoints,
            vec![
                (
                    "cell-b".to_string(),
                    Some("https://cell-b.example.test".to_string()),
                ),
                (
                    "cell-c".to_string(),
                    Some("https://cell-c.example.test".to_string()),
                ),
            ]
        );
        let targets: Vec<String> = sqlx::query_scalar(
            "SELECT target_cell_id FROM federation_delivery_attempts WHERE event_id = $1",
        )
        .bind(event.event_id)
        .fetch_all(&pool)
        .await?;
        assert_eq!(targets, vec!["cell-b".to_string()]);
        Ok(())
    }

    #[tokio::test]
    #[ignore = "requires an isolated FEDERATION_TEST_DATABASE_URL"]
    #[serial]
    async fn postgres_batch_backfill_preserves_existing_delivery_state_semantics(
    ) -> anyhow::Result<()> {
        let pool = isolated_delivery_pool().await?;
        let peer = delivery_peer_policy("cell-b", "trusted", 91);
        let (repository, sender) = postgres_sender(&pool, std::slice::from_ref(&peer)).await?;
        repository
            .reconcile_delivery_endpoints(&[(
                peer.clone(),
                Some("https://cell-b.example.test/original".to_string()),
            )])
            .await?;
        let recoverable = publish_global(&sender, "reconcile-recoverable").await?;
        let permanent = publish_global(&sender, "reconcile-permanent").await?;
        let delivered = publish_global(&sender, "reconcile-delivered").await?;
        sqlx::query(
            "UPDATE federation_delivery_attempts \
             SET state = 'dead', attempt_count = 7, \
                 next_attempt_at = TIMESTAMPTZ '2002-01-01 00:00:00+00', \
                 last_http_status = 202, last_error_class = 'remote-quarantined', \
                 updated_at = TIMESTAMPTZ '2002-01-02 00:00:00+00' \
             WHERE event_id = $1 AND target_cell_id = 'cell-b'",
        )
        .bind(recoverable.event_id)
        .execute(&pool)
        .await?;
        sqlx::query(
            "UPDATE federation_delivery_attempts \
             SET state = 'dead', attempt_count = 5, \
                 next_attempt_at = TIMESTAMPTZ '2003-01-01 00:00:00+00', \
                 last_http_status = 400, last_error_class = 'outbox-envelope-invalid', \
                 updated_at = TIMESTAMPTZ '2003-01-02 00:00:00+00' \
             WHERE event_id = $1 AND target_cell_id = 'cell-b'",
        )
        .bind(permanent.event_id)
        .execute(&pool)
        .await?;
        sqlx::query(
            "UPDATE federation_delivery_attempts \
             SET state = 'delivered', attempt_count = 1, \
                 next_attempt_at = TIMESTAMPTZ '2004-01-01 00:00:00+00', \
                 last_http_status = 201, last_error_class = NULL, \
                 delivered_at = TIMESTAMPTZ '2004-01-02 00:00:00+00', \
                 updated_at = TIMESTAMPTZ '2004-01-03 00:00:00+00' \
             WHERE event_id = $1 AND target_cell_id = 'cell-b'",
        )
        .bind(delivered.event_id)
        .execute(&pool)
        .await?;
        let permanent_before = attempt_snapshot(&pool, permanent.event_id, "cell-b").await?;
        let delivered_before = attempt_snapshot(&pool, delivered.event_id, "cell-b").await?;

        repository
            .reconcile_delivery_endpoints(&[(
                peer,
                Some("https://cell-b.example.test/changed".to_string()),
            )])
            .await?;

        let reactivated = attempt_snapshot(&pool, recoverable.event_id, "cell-b").await?;
        assert_eq!(reactivated.0, "pending");
        assert_eq!(reactivated.1, 0);
        assert_eq!(reactivated.3, None);
        assert_eq!(reactivated.4, None);
        assert_eq!(reactivated.5, None);
        assert_eq!(reactivated.6, None);
        assert_eq!(reactivated.7, None);
        assert_eq!(
            attempt_snapshot(&pool, permanent.event_id, "cell-b").await?,
            permanent_before
        );
        assert_eq!(
            attempt_snapshot(&pool, delivered.event_id, "cell-b").await?,
            delivered_before
        );
        Ok(())
    }

    #[tokio::test]
    #[ignore = "requires an isolated FEDERATION_TEST_DATABASE_URL"]
    #[serial]
    async fn postgres_reconcile_preserves_sequential_duplicate_binding_semantics(
    ) -> anyhow::Result<()> {
        let pool = isolated_delivery_pool().await?;
        let peer = delivery_peer_policy("cell-b", "trusted", 91);
        let (repository, sender) = postgres_sender(&pool, std::slice::from_ref(&peer)).await?;
        let event = publish_global(&sender, "reconcile-duplicate-fallback").await?;

        repository
            .reconcile_delivery_endpoints(&[
                (
                    peer.clone(),
                    Some("https://cell-b.example.test/transient".to_string()),
                ),
                (peer, None),
            ])
            .await?;

        let endpoint: Option<String> = sqlx::query_scalar(
            "SELECT delivery_base_url FROM federation_peer_relationships \
             WHERE remote_cell_id = 'cell-b'",
        )
        .fetch_one(&pool)
        .await?;
        assert_eq!(endpoint, None);
        let targets: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM federation_delivery_attempts \
             WHERE event_id = $1 AND target_cell_id = 'cell-b'",
        )
        .bind(event.event_id)
        .fetch_one(&pool)
        .await?;
        assert_eq!(targets, 1);
        Ok(())
    }

    #[tokio::test]
    #[ignore = "requires an isolated FEDERATION_TEST_DATABASE_URL"]
    #[serial]
    async fn postgres_delivery_retries_and_is_multi_instance_safe() -> anyhow::Result<()> {
        let database_url = env::var("FEDERATION_TEST_DATABASE_URL")
            .context("FEDERATION_TEST_DATABASE_URL must identify an isolated database")?;
        let pool = PgPoolOptions::new()
            .max_connections(8)
            .connect(&database_url)
            .await?;
        sqlx::migrate!("./migrations").run(&pool).await?;
        sqlx::query(
            "TRUNCATE federation_delivery_attempts, federation_event_receipts, \
             federation_quarantine, federation_inbox, federation_outbox, federation_objects, \
             federation_peer_keys, federation_peer_relationships RESTART IDENTITY CASCADE",
        )
        .execute(&pool)
        .await?;

        let sender_identity = test_identity("cell-a", "key-a", 91);
        let receiver_identity = test_identity("cell-b", "key-b", 92);
        let sender_repository = Arc::new(PostgresFederationRepository::new(pool.clone()));
        let sender = FederationService::new(sender_identity.clone(), sender_repository.clone());
        let sender_peer_policy = PeerPolicy {
            remote_cell_id: "cell-b".to_string(),
            state: "trusted".to_string(),
            allow_neighbourhood: true,
            allowed_event_types: HashSet::from(["object.upserted".to_string()]),
            keys: vec![receiver_identity.peer_key()],
        };
        sender.install_peer(sender_peer_policy.clone()).await?;
        let receiver_repository = Arc::new(MemoryFederationRepository::new());
        let receiver = FederationService::new(receiver_identity, receiver_repository.clone());
        let receiver_peer_policy = PeerPolicy {
            remote_cell_id: "cell-a".to_string(),
            state: "trusted".to_string(),
            allow_neighbourhood: true,
            allowed_event_types: HashSet::from(["object.upserted".to_string()]),
            keys: vec![sender_identity.peer_key()],
        };
        receiver.install_peer(receiver_peer_policy.clone()).await?;

        let first = sender
            .publish_local(PublishRequest {
                actor: "system:delivery-proof".to_string(),
                event_type: "object.upserted".to_string(),
                object_address: "wg://cell-a/node/automatic-delivery".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: "global".to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"name": "automatic delivery"}),
            })
            .await?;
        let target_count: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM federation_delivery_attempts WHERE event_id = $1",
        )
        .bind(first.event_id)
        .fetch_one(&pool)
        .await?;
        assert_eq!(target_count, 0);
        sender_repository
            .reconcile_delivery_endpoints(&[(
                sender_peer_policy.clone(),
                Some("https://cell-b.example.test".to_string()),
            )])
            .await?;
        let target_count: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM federation_delivery_attempts WHERE event_id = $1",
        )
        .bind(first.event_id)
        .fetch_one(&pool)
        .await?;
        assert_eq!(target_count, 1);

        let retry_transport = ReceiverTransport::new(receiver.clone(), true);
        let config = delivery_test_config();
        assert_eq!(
            run_delivery_batch(&pool, &config, &retry_transport, Uuid::new_v4()).await?,
            1
        );
        let first_state: (String, i32, Option<String>) = sqlx::query_as(
            "SELECT state, attempt_count, last_error_class \
             FROM federation_delivery_attempts WHERE event_id = $1 AND target_cell_id = $2",
        )
        .bind(first.event_id)
        .bind("cell-b")
        .fetch_one(&pool)
        .await?;
        assert_eq!(first_state.0, "retry");
        assert_eq!(first_state.1, 1);
        assert_eq!(
            first_state.2.as_deref(),
            Some("simulated-transient-failure")
        );
        sqlx::query(
            "UPDATE federation_delivery_attempts SET next_attempt_at = NOW() \
             WHERE event_id = $1 AND target_cell_id = $2",
        )
        .bind(first.event_id)
        .bind("cell-b")
        .execute(&pool)
        .await?;
        assert_eq!(
            run_delivery_batch(&pool, &config, &retry_transport, Uuid::new_v4()).await?,
            1
        );
        let first_state: (String, i32) = sqlx::query_as(
            "SELECT state, attempt_count FROM federation_delivery_attempts \
             WHERE event_id = $1 AND target_cell_id = $2",
        )
        .bind(first.event_id)
        .bind("cell-b")
        .fetch_one(&pool)
        .await?;
        assert_eq!(first_state, ("delivered".to_string(), 2));
        assert_eq!(retry_transport.calls(), 2);
        assert!(receiver
            .object("wg://cell-a/node/automatic-delivery")
            .await?
            .is_some());

        let revocation_event = sender
            .publish_local(PublishRequest {
                actor: "system:delivery-revocation-proof".to_string(),
                event_type: "object.upserted".to_string(),
                object_address: "wg://cell-a/node/revocation-liveness".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: "global".to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"state": "in-flight"}),
            })
            .await?;
        let gate_transport = Arc::new(GateTransport::new(receiver.clone()));
        let worker_pool = pool.clone();
        let worker_config = config.clone();
        let worker_transport = gate_transport.clone();
        let in_flight_worker = tokio::spawn(async move {
            run_delivery_batch(
                &worker_pool,
                &worker_config,
                worker_transport.as_ref(),
                Uuid::new_v4(),
            )
            .await
        });
        tokio::time::timeout(Duration::from_secs(2), gate_transport.entered.notified()).await?;
        let mut revoked_policy = sender_peer_policy.clone();
        revoked_policy.state = "blocked".to_string();
        tokio::time::timeout(Duration::from_secs(2), async {
            sender.install_peer(revoked_policy.clone()).await?;
            sender_repository
                .reconcile_delivery_endpoints(&[(
                    revoked_policy,
                    Some("https://cell-b.example.test".to_string()),
                )])
                .await?;
            Ok::<(), anyhow::Error>(())
        })
        .await??;
        gate_transport.release.notify_one();
        assert_eq!(in_flight_worker.await??, 1);
        assert_eq!(gate_transport.calls(), 1);
        let revocation_state: String = sqlx::query_scalar(
            "SELECT state FROM federation_delivery_attempts \
             WHERE event_id = $1 AND target_cell_id = $2",
        )
        .bind(revocation_event.event_id)
        .bind("cell-b")
        .fetch_one(&pool)
        .await?;
        assert_eq!(revocation_state, "delivered");
        sender.install_peer(sender_peer_policy.clone()).await?;
        sender_repository
            .reconcile_delivery_endpoints(&[(
                sender_peer_policy.clone(),
                Some("https://cell-b.example.test".to_string()),
            )])
            .await?;

        let policy_pending = sender
            .publish_local(PublishRequest {
                actor: "system:delivery-policy-proof".to_string(),
                event_type: "object.upserted".to_string(),
                object_address: "wg://cell-a/node/policy-reactivation".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: "global".to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"state": "created-before-block"}),
            })
            .await?;
        let pending_targets: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM federation_delivery_attempts WHERE event_id = $1",
        )
        .bind(policy_pending.event_id)
        .fetch_one(&pool)
        .await?;
        assert_eq!(pending_targets, 1);

        let mut blocked_policy = sender_peer_policy.clone();
        blocked_policy.state = "blocked".to_string();
        sender.install_peer(blocked_policy.clone()).await?;
        sender_repository
            .reconcile_delivery_endpoints(&[(
                blocked_policy,
                Some("https://cell-b.example.test".to_string()),
            )])
            .await?;
        assert_eq!(
            run_delivery_batch(&pool, &config, &retry_transport, Uuid::new_v4()).await?,
            1
        );
        let blocked_state: (String, Option<String>) = sqlx::query_as(
            "SELECT state, last_error_class FROM federation_delivery_attempts              WHERE event_id = $1 AND target_cell_id = $2",
        )
        .bind(policy_pending.event_id)
        .bind("cell-b")
        .fetch_one(&pool)
        .await?;
        assert_eq!(
            blocked_state,
            ("dead".to_string(), Some("peer-not-trusted".to_string()))
        );
        assert!(receiver
            .object("wg://cell-a/node/policy-reactivation")
            .await?
            .is_none());
        assert_eq!(retry_transport.calls(), 2);

        sender.install_peer(sender_peer_policy.clone()).await?;
        sender_repository
            .reconcile_delivery_endpoints(&[(
                sender_peer_policy.clone(),
                Some("https://cell-b.example.test".to_string()),
            )])
            .await?;
        let reactivated_state: (String, i32, Option<String>) = sqlx::query_as(
            "SELECT state, attempt_count, last_error_class              FROM federation_delivery_attempts WHERE event_id = $1 AND target_cell_id = $2",
        )
        .bind(policy_pending.event_id)
        .bind("cell-b")
        .fetch_one(&pool)
        .await?;
        assert_eq!(reactivated_state, ("pending".to_string(), 0, None));
        assert_eq!(
            run_delivery_batch(&pool, &config, &retry_transport, Uuid::new_v4()).await?,
            1
        );
        assert_eq!(retry_transport.calls(), 3);
        assert!(receiver
            .object("wg://cell-a/node/policy-reactivation")
            .await?
            .is_some());

        let second = sender
            .publish_local(PublishRequest {
                actor: "system:delivery-proof".to_string(),
                event_type: "object.upserted".to_string(),
                object_address: "wg://cell-a/node/multi-instance-delivery".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: "global".to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"name": "multi instance"}),
            })
            .await?;
        let concurrent_transport = Arc::new(ReceiverTransport::new(receiver.clone(), false));
        let worker_one = run_delivery_batch(
            &pool,
            &config,
            concurrent_transport.as_ref(),
            Uuid::new_v4(),
        );
        let worker_two = run_delivery_batch(
            &pool,
            &config,
            concurrent_transport.as_ref(),
            Uuid::new_v4(),
        );
        let (one, two) = tokio::join!(worker_one, worker_two);
        assert_eq!(one? + two?, 1);
        assert_eq!(concurrent_transport.calls(), 1);
        let second_state: (String, i32) = sqlx::query_as(
            "SELECT state, attempt_count FROM federation_delivery_attempts \
             WHERE event_id = $1 AND target_cell_id = $2",
        )
        .bind(second.event_id)
        .bind("cell-b")
        .fetch_one(&pool)
        .await?;
        assert_eq!(second_state, ("delivered".to_string(), 1));
        assert!(receiver_repository
            .object("wg://cell-a/node/multi-instance-delivery")
            .await?
            .is_some());
        assert_eq!(
            run_delivery_batch(
                &pool,
                &config,
                concurrent_transport.as_ref(),
                Uuid::new_v4()
            )
            .await?,
            0
        );

        let rejected_event = sender
            .publish_local(PublishRequest {
                actor: "system:delivery-rejection-proof".to_string(),
                event_type: "object.upserted".to_string(),
                object_address: "wg://cell-a/node/rejection-recovery".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: "global".to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"state": "awaiting receiver trust"}),
            })
            .await?;
        let mut blocked_receiver_policy = receiver_peer_policy.clone();
        blocked_receiver_policy.state = "blocked".to_string();
        receiver.install_peer(blocked_receiver_policy).await?;
        let rejection_transport = ReceiverTransport::new(receiver.clone(), false);
        let rejection_config = DeliveryWorkerConfig {
            max_attempts: 2,
            ..config.clone()
        };
        assert_eq!(
            run_delivery_batch(
                &pool,
                &rejection_config,
                &rejection_transport,
                Uuid::new_v4(),
            )
            .await?,
            1
        );
        sqlx::query(
            "UPDATE federation_delivery_attempts SET next_attempt_at = NOW() \
             WHERE event_id = $1 AND target_cell_id = $2",
        )
        .bind(rejected_event.event_id)
        .bind("cell-b")
        .execute(&pool)
        .await?;
        assert_eq!(
            run_delivery_batch(
                &pool,
                &rejection_config,
                &rejection_transport,
                Uuid::new_v4(),
            )
            .await?,
            1
        );
        let rejected_state: (String, Option<String>) = sqlx::query_as(
            "SELECT state, last_error_class FROM federation_delivery_attempts \
             WHERE event_id = $1 AND target_cell_id = $2",
        )
        .bind(rejected_event.event_id)
        .bind("cell-b")
        .fetch_one(&pool)
        .await?;
        assert_eq!(
            rejected_state,
            ("dead".to_string(), Some("remote-quarantined".to_string()))
        );
        receiver.install_peer(receiver_peer_policy.clone()).await?;
        sender_repository
            .reconcile_delivery_endpoints(&[(
                sender_peer_policy.clone(),
                Some("https://cell-b.example.test/recovered".to_string()),
            )])
            .await?;
        assert_eq!(
            run_delivery_batch(&pool, &config, &rejection_transport, Uuid::new_v4()).await?,
            1
        );
        assert!(receiver
            .object("wg://cell-a/node/rejection-recovery")
            .await?
            .is_some());

        let tampered_event = sender
            .publish_local(PublishRequest {
                actor: "system:delivery-digest-proof".to_string(),
                event_type: "object.upserted".to_string(),
                object_address: "wg://cell-a/node/outbox-digest".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: "global".to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"state": "original"}),
            })
            .await?;
        sqlx::query(
            "UPDATE federation_outbox \
             SET envelope = jsonb_set(envelope, '{payload,state}', to_jsonb('tampered'::text)) \
             WHERE event_id = $1",
        )
        .bind(tampered_event.event_id)
        .execute(&pool)
        .await?;
        let calls_before_tamper = rejection_transport.calls();
        assert_eq!(
            run_delivery_batch(&pool, &config, &rejection_transport, Uuid::new_v4()).await?,
            1
        );
        assert_eq!(rejection_transport.calls(), calls_before_tamper);
        let tampered_state: (String, Option<String>) = sqlx::query_as(
            "SELECT state, last_error_class FROM federation_delivery_attempts \
             WHERE event_id = $1 AND target_cell_id = $2",
        )
        .bind(tampered_event.event_id)
        .bind("cell-b")
        .fetch_one(&pool)
        .await?;
        assert_eq!(
            tampered_state,
            (
                "dead".to_string(),
                Some("outbox-envelope-digest-mismatch".to_string())
            )
        );

        let version_one = sender
            .publish_local(PublishRequest {
                actor: "system:delivery-order-proof".to_string(),
                event_type: "object.upserted".to_string(),
                object_address: "wg://cell-a/node/version-order".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: "global".to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"version": 1}),
            })
            .await?;
        let version_two = sender
            .publish_local(PublishRequest {
                actor: "system:delivery-order-proof".to_string(),
                event_type: "object.upserted".to_string(),
                object_address: "wg://cell-a/node/version-order".to_string(),
                object_kind: "node".to_string(),
                object_version: 2,
                previous_version: Some(1),
                scope: "global".to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"version": 2}),
            })
            .await?;
        let ordered_transport = Arc::new(
            ReceiverTransport::new(receiver.clone(), false).with_delay(Duration::from_millis(100)),
        );
        let order_worker_one =
            run_delivery_batch(&pool, &config, ordered_transport.as_ref(), Uuid::new_v4());
        let order_worker_two =
            run_delivery_batch(&pool, &config, ordered_transport.as_ref(), Uuid::new_v4());
        let (one, two) = tokio::join!(order_worker_one, order_worker_two);
        assert_eq!(one? + two?, 1);
        assert_eq!(ordered_transport.calls(), 1);
        let states: Vec<(Uuid, String)> = sqlx::query_as(
            "SELECT event_id, state FROM federation_delivery_attempts \
             WHERE event_id = ANY($1::uuid[]) ORDER BY event_id",
        )
        .bind(vec![version_one.event_id, version_two.event_id])
        .fetch_all(&pool)
        .await?;
        assert_eq!(
            states
                .iter()
                .find(|(event_id, _)| *event_id == version_one.event_id)
                .map(|(_, state)| state.as_str()),
            Some("delivered")
        );
        assert_eq!(
            states
                .iter()
                .find(|(event_id, _)| *event_id == version_two.event_id)
                .map(|(_, state)| state.as_str()),
            Some("pending")
        );
        assert_eq!(
            run_delivery_batch(&pool, &config, ordered_transport.as_ref(), Uuid::new_v4(),).await?,
            1
        );
        assert_eq!(ordered_transport.calls(), 2);
        let remote = receiver
            .object("wg://cell-a/node/version-order")
            .await?
            .expect("versioned object delivered");
        assert_eq!(remote.object_version, 2);

        let gap_v1 = sender
            .publish_local(PublishRequest {
                actor: "system:delivery-gap-proof".to_string(),
                event_type: "object.upserted".to_string(),
                object_address: "wg://cell-a/node/event-type-gap".to_string(),
                object_kind: "node".to_string(),
                object_version: 1,
                previous_version: None,
                scope: "global".to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"version": 1}),
            })
            .await?;
        let gap_v2 = sender
            .publish_local(PublishRequest {
                actor: "system:delivery-gap-proof".to_string(),
                event_type: "object.deleted".to_string(),
                object_address: "wg://cell-a/node/event-type-gap".to_string(),
                object_kind: "node".to_string(),
                object_version: 2,
                previous_version: Some(1),
                scope: "global".to_string(),
                neighbourhood_targets: vec![],
                payload: Value::Null,
            })
            .await?;
        let gap_v3 = sender
            .publish_local(PublishRequest {
                actor: "system:delivery-gap-proof".to_string(),
                event_type: "object.upserted".to_string(),
                object_address: "wg://cell-a/node/event-type-gap".to_string(),
                object_kind: "node".to_string(),
                object_version: 3,
                previous_version: Some(2),
                scope: "global".to_string(),
                neighbourhood_targets: vec![],
                payload: serde_json::json!({"version": 3}),
            })
            .await?;
        let gap_transport = ReceiverTransport::new(receiver.clone(), false);
        assert_eq!(
            run_delivery_batch(&pool, &config, &gap_transport, Uuid::new_v4()).await?,
            1
        );
        assert_eq!(
            run_delivery_batch(&pool, &config, &gap_transport, Uuid::new_v4()).await?,
            1
        );
        let gap_states: Vec<(Uuid, String, Option<String>)> = sqlx::query_as(
            "SELECT event_id, state, last_error_class \
             FROM federation_delivery_attempts \
             WHERE event_id = ANY($1::uuid[])",
        )
        .bind(vec![gap_v1.event_id, gap_v2.event_id, gap_v3.event_id])
        .fetch_all(&pool)
        .await?;
        assert_eq!(
            gap_states
                .iter()
                .find(|(event_id, _, _)| *event_id == gap_v2.event_id)
                .map(|(_, state, error)| (state.as_str(), error.as_deref())),
            Some(("dead", Some("event-type-not-allowed")))
        );
        assert_eq!(
            gap_states
                .iter()
                .find(|(event_id, _, _)| *event_id == gap_v3.event_id)
                .map(|(_, state, _)| state.as_str()),
            Some("pending")
        );

        let mut expanded_sender_policy = sender_peer_policy.clone();
        expanded_sender_policy
            .allowed_event_types
            .insert("object.deleted".to_string());
        let mut expanded_receiver_policy = receiver_peer_policy.clone();
        expanded_receiver_policy
            .allowed_event_types
            .insert("object.deleted".to_string());
        receiver.install_peer(expanded_receiver_policy).await?;
        sender.install_peer(expanded_sender_policy.clone()).await?;
        sender_repository
            .reconcile_delivery_endpoints(&[(
                expanded_sender_policy,
                Some("https://cell-b.example.test".to_string()),
            )])
            .await?;
        assert_eq!(
            run_delivery_batch(&pool, &config, &gap_transport, Uuid::new_v4()).await?,
            1
        );
        assert_eq!(
            run_delivery_batch(&pool, &config, &gap_transport, Uuid::new_v4()).await?,
            1
        );
        let gap_remote = receiver
            .object("wg://cell-a/node/event-type-gap")
            .await?
            .expect("event-type gap recovered");
        assert_eq!(gap_remote.object_version, 3);

        Ok(())
    }
}

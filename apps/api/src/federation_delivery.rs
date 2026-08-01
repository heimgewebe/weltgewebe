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
const DELIVERY_LEASE_SECONDS: i64 = 30;
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
            ReceiveStatus::Rejected => DeliveryDecision::Dead {
                http_status: Some(response.status),
                error_class: "remote-rejected",
            },
            ReceiveStatus::Quarantined => DeliveryDecision::Dead {
                http_status: Some(response.status),
                error_class: "remote-quarantined",
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
    let mut processed = 0;
    for _ in 0..config.batch_size {
        let Some(claim) = claim_due_delivery(pool, worker_id).await? else {
            break;
        };
        execute_claim(pool, config, transport, claim).await?;
        processed += 1;
    }
    Ok(processed)
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
           AND relationship.allowed_event_types ? $2 \
           AND ( \
             $3 = 'global' \
             OR ( \
               $3 = 'neighbourhood' \
               AND relationship.allow_neighbourhood \
               AND relationship.remote_cell_id = ANY($4::text[]) \
             ) \
           ) \
         ON CONFLICT (event_id, target_cell_id) DO NOTHING",
    )
    .bind(event.event_id)
    .bind(&event.event_type)
    .bind(&event.scope)
    .bind(&event.neighbourhood_targets)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

pub(crate) async fn backfill_delivery_target(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    target_cell_id: &str,
) -> anyhow::Result<()> {
    sqlx::query(
        "INSERT INTO federation_delivery_attempts (event_id, target_cell_id) \
         SELECT outbox.event_id, relationship.remote_cell_id \
         FROM federation_outbox AS outbox \
         JOIN federation_peer_relationships AS relationship \
           ON relationship.remote_cell_id = $1 \
          AND relationship.state = 'trusted' \
          AND relationship.delivery_base_url IS NOT NULL \
          AND relationship.allowed_event_types ? (outbox.envelope ->> 'event_type') \
          AND ( \
            outbox.envelope ->> 'scope' = 'global' \
            OR ( \
              outbox.envelope ->> 'scope' = 'neighbourhood' \
              AND relationship.allow_neighbourhood \
              AND (outbox.envelope -> 'neighbourhood_targets') ? relationship.remote_cell_id \
            ) \
          ) \
         ON CONFLICT (event_id, target_cell_id) DO UPDATE SET
           state = 'pending',
           attempt_count = 0,
           next_attempt_at = NOW(),
           lease_owner = NULL,
           lease_expires_at = NULL,
           last_http_status = NULL,
           last_error_class = NULL,
           delivered_at = NULL,
           updated_at = NOW()
         WHERE federation_delivery_attempts.state = 'dead'
           AND federation_delivery_attempts.last_error_class IN (
             'peer-not-trusted',
             'event-type-not-allowed',
             'neighbourhood-target-not-allowed',
             'scope-not-deliverable',
             'delivery-endpoint-missing',
             'delivery-endpoint-invalid'
           )",
    )
    .bind(target_cell_id)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

async fn claim_due_delivery(
    pool: &PgPool,
    worker_id: Uuid,
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
    .bind(DELIVERY_LEASE_SECONDS)
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

async fn execute_claim(
    pool: &PgPool,
    config: &DeliveryWorkerConfig,
    transport: &dyn DeliveryTransport,
    claim: DeliveryClaim,
) -> anyhow::Result<()> {
    let mut tx = pool.begin().await?;
    let row = sqlx::query(
        "SELECT delivery.state AS delivery_state, delivery.lease_owner, \
                outbox.envelope, relationship.state AS peer_state, \
                relationship.allow_neighbourhood, relationship.allowed_event_types, \
                relationship.delivery_base_url \
         FROM federation_delivery_attempts AS delivery \
         JOIN federation_outbox AS outbox USING (event_id) \
         JOIN federation_peer_relationships AS relationship \
           ON relationship.remote_cell_id = delivery.target_cell_id \
         WHERE delivery.event_id = $1 AND delivery.target_cell_id = $2 \
         FOR UPDATE OF delivery FOR SHARE OF relationship",
    )
    .bind(claim.event_id)
    .bind(&claim.target_cell_id)
    .fetch_optional(&mut *tx)
    .await?;
    let Some(row) = row else {
        tx.rollback().await?;
        return Ok(());
    };
    let delivery_state: String = row.try_get("delivery_state")?;
    let lease_owner: Option<Uuid> = row.try_get("lease_owner")?;
    if delivery_state != "in_flight" || lease_owner != Some(claim.lease_owner) {
        tx.rollback().await?;
        return Ok(());
    }
    let envelope: Value = row.try_get("envelope")?;
    let event: FederationEvent = serde_json::from_value(envelope)?;
    let peer_state: String = row.try_get("peer_state")?;
    let allow_neighbourhood: bool = row.try_get("allow_neighbourhood")?;
    let allowed_event_types: Value = row.try_get("allowed_event_types")?;
    let allowed_event_types: Vec<String> = serde_json::from_value(allowed_event_types)?;
    let delivery_base_url: Option<String> = row.try_get("delivery_base_url")?;

    let policy_error = delivery_policy_error(
        &event,
        &claim.target_cell_id,
        &peer_state,
        allow_neighbourhood,
        &allowed_event_types,
        delivery_base_url.as_deref(),
    );
    if let Some(error_class) = policy_error {
        mark_dead(&mut tx, &claim, None, error_class).await?;
        tx.commit().await?;
        return Ok(());
    }
    let base_url = delivery_base_url.expect("validated delivery base URL");
    let decision = match transport.post_event(&base_url, &event).await {
        Ok(response) => classify_response(response, event.event_id, event.object_version),
        Err(error) => DeliveryDecision::Retry {
            http_status: None,
            error_class: error.class,
            retry_after_seconds: None,
        },
    };
    let decision = match decision {
        DeliveryDecision::Retry { http_status, .. }
            if claim.attempt_count >= config.max_attempts =>
        {
            DeliveryDecision::Dead {
                http_status,
                error_class: "delivery-attempts-exhausted",
            }
        }
        other => other,
    };
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
            .execute(&mut *tx)
            .await?;
        }
        DeliveryDecision::Retry {
            http_status,
            error_class,
            retry_after_seconds,
        } => {
            let delay = retry_after_seconds
                .unwrap_or_else(|| retry_delay_seconds(claim.event_id, claim.attempt_count))
                .min(MAX_BACKOFF_SECONDS);
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
            .execute(&mut *tx)
            .await?;
        }
        DeliveryDecision::Dead {
            http_status,
            error_class,
        } => {
            mark_dead(&mut tx, &claim, http_status, error_class).await?;
        }
    }
    tx.commit().await?;
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
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
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
    .execute(&mut **tx)
    .await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
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

    #[tokio::test]
    #[ignore = "requires an isolated FEDERATION_TEST_DATABASE_URL"]
    async fn postgres_delivery_retries_and_is_multi_instance_safe() -> anyhow::Result<()> {
        use std::{collections::HashSet, sync::Arc};

        use sqlx::postgres::PgPoolOptions;

        use crate::federation::{
            FederationRepository, FederationService, MemoryFederationRepository, PeerPolicy,
            PostgresFederationRepository, PublishRequest,
        };

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
        receiver
            .install_peer(PeerPolicy {
                remote_cell_id: "cell-a".to_string(),
                state: "trusted".to_string(),
                allow_neighbourhood: true,
                allowed_event_types: HashSet::from(["object.upserted".to_string()]),
                keys: vec![sender_identity.peer_key()],
            })
            .await?;

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

        Ok(())
    }
}

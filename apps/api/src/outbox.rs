use std::{future::Future, time::Duration};

use anyhow::Context;
use async_nats::{
    jetstream::{
        self,
        consumer::{self, PullConsumer},
        stream,
    },
    Client, HeaderMap,
};
use chrono::{DateTime, Utc};
use futures_util::StreamExt;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sqlx::PgPool;

use crate::{
    config::{
        AppConfig, DomainAccountWriteSource, DomainEdgeWriteSource, DomainNodeWriteSource,
        DomainReadSource,
    },
    telemetry::{DomainEventWorker, Metrics},
};

pub(crate) const STREAM_NAME: &str = "WELTGEWEBE_DOMAIN";
pub(crate) const STREAM_SUBJECT: &str = "weltgewebe.domain.>";
pub(crate) const CONSUMER_NAME: &str = "weltgewebe-api-domain-receipts-v1";
pub(crate) const CONSUMER_LEDGER_NAME: &str = "weltgewebe-api-domain-receipts-v1";
const CLAIM_BATCH_SIZE: i64 = 32;
const CLAIM_LEASE_SECONDS: i32 = 30;
const MAX_ATTEMPTS: i32 = 10;

#[derive(Debug, Clone, sqlx::FromRow)]
pub struct OutboxEvent {
    pub id: i64,
    pub aggregate_type: String,
    pub aggregate_id: String,
    pub event_type: String,
    pub payload: Value,
    pub created_at: DateTime<Utc>,
    pub attempt_count: i32,
}

#[derive(Debug, Clone, Copy, sqlx::FromRow)]
pub struct EventChainDbSnapshot {
    pub pending: i64,
    pub retrying: i64,
    pub quarantined: i64,
    pub oldest_pending_age_seconds: i64,
    pub receipts_missing: i64,
    pub oldest_missing_receipt_age_seconds: i64,
}

#[derive(Debug, Serialize, Deserialize)]
struct PublishedDomainEvent {
    schema_version: u8,
    event_id: i64,
    aggregate_type: String,
    aggregate_id: String,
    event_type: String,
    payload: Value,
    created_at: DateTime<Utc>,
}

fn expected_stream_config() -> stream::Config {
    stream::Config {
        name: STREAM_NAME.to_string(),
        description: Some(
            "Transactional Weltgewebe domain events emitted from PostgreSQL".to_string(),
        ),
        subjects: vec![STREAM_SUBJECT.to_string()],
        max_age: Duration::from_secs(30 * 24 * 60 * 60),
        duplicate_window: Duration::from_secs(2 * 60),
        ..Default::default()
    }
}

fn expected_consumer_config() -> consumer::pull::Config {
    consumer::pull::Config {
        durable_name: Some(CONSUMER_NAME.to_string()),
        filter_subject: STREAM_SUBJECT.to_string(),
        ack_policy: consumer::AckPolicy::Explicit,
        ..Default::default()
    }
}

pub(crate) fn validate_stream_contract(config: &stream::Config) -> anyhow::Result<()> {
    anyhow::ensure!(
        config.name == STREAM_NAME,
        "domain JetStream has name {:?}, expected {STREAM_NAME:?}",
        config.name
    );
    anyhow::ensure!(
        config.subjects == [STREAM_SUBJECT],
        "domain JetStream subjects are {:?}, expected only {STREAM_SUBJECT:?}",
        config.subjects
    );
    anyhow::ensure!(
        config.max_age == Duration::from_secs(30 * 24 * 60 * 60),
        "domain JetStream max_age is {:?}, expected 30 days",
        config.max_age
    );
    anyhow::ensure!(
        config.duplicate_window == Duration::from_secs(2 * 60),
        "domain JetStream duplicate_window is {:?}, expected 120 seconds",
        config.duplicate_window
    );
    Ok(())
}

fn validate_consumer_config(
    stream_name: &str,
    consumer_name: &str,
    config: &consumer::Config,
) -> anyhow::Result<()> {
    anyhow::ensure!(
        stream_name == STREAM_NAME,
        "domain receipt consumer is attached to {:?}, expected {STREAM_NAME:?}",
        stream_name
    );
    anyhow::ensure!(
        consumer_name == CONSUMER_NAME,
        "domain receipt consumer has name {:?}, expected {CONSUMER_NAME:?}",
        consumer_name
    );
    anyhow::ensure!(
        config.durable_name.as_deref() == Some(CONSUMER_NAME),
        "domain receipt consumer is not the expected durable consumer"
    );
    anyhow::ensure!(
        config.deliver_subject.is_none(),
        "domain receipt consumer must remain pull-based"
    );
    anyhow::ensure!(
        config.filter_subject == STREAM_SUBJECT,
        "domain receipt consumer filter is {:?}, expected {STREAM_SUBJECT:?}",
        config.filter_subject
    );
    anyhow::ensure!(
        config.ack_policy == consumer::AckPolicy::Explicit,
        "domain receipt consumer must use explicit acknowledgements"
    );
    Ok(())
}

pub(crate) fn validate_consumer_contract(info: &consumer::Info) -> anyhow::Result<()> {
    validate_consumer_config(&info.stream_name, &info.name, &info.config)
}

pub fn event_chain_required(config: &AppConfig) -> bool {
    config.domain_read_source == DomainReadSource::Postgres
        || config.domain_account_write_source == DomainAccountWriteSource::Postgres
        || config.domain_node_write_source == DomainNodeWriteSource::Postgres
        || config.domain_edge_write_source == DomainEdgeWriteSource::Postgres
}

pub async fn ensure_stream(client: Client) -> anyhow::Result<(jetstream::Context, stream::Stream)> {
    let context = jetstream::new(client);
    let mut stream = context
        .get_or_create_stream(expected_stream_config())
        .await
        .context("failed to get or create Weltgewebe domain JetStream")?;
    let info = stream
        .info()
        .await
        .context("failed to inspect Weltgewebe domain JetStream")?;
    validate_stream_contract(&info.config)?;
    Ok((context, stream))
}

pub async fn verify_jetstream_contract(client: &Client) -> anyhow::Result<()> {
    let context = jetstream::new(client.clone());
    let mut stream = context
        .get_stream(STREAM_NAME)
        .await
        .context("expected Weltgewebe domain JetStream is missing")?;
    let stream_info = stream
        .info()
        .await
        .context("failed to inspect Weltgewebe domain JetStream")?;
    validate_stream_contract(&stream_info.config)?;
    let consumer_info = stream
        .consumer_info(CONSUMER_NAME)
        .await
        .context("expected durable domain receipt consumer is missing")?;
    validate_consumer_contract(&consumer_info)
}

pub async fn load_event_chain_db_snapshot(pool: &PgPool) -> anyhow::Result<EventChainDbSnapshot> {
    sqlx::query_as::<_, EventChainDbSnapshot>(
        "SELECT \
            COUNT(*) FILTER (WHERE event.published_at IS NULL AND event.quarantined_at IS NULL)::BIGINT AS pending, \
            COUNT(*) FILTER (WHERE event.published_at IS NULL AND event.quarantined_at IS NULL AND event.attempt_count > 0)::BIGINT AS retrying, \
            COUNT(*) FILTER (WHERE event.published_at IS NULL AND event.quarantined_at IS NOT NULL)::BIGINT AS quarantined, \
            COALESCE(FLOOR(EXTRACT(EPOCH FROM (NOW() - MIN(event.created_at) FILTER (WHERE event.published_at IS NULL AND event.quarantined_at IS NULL)))), 0)::BIGINT AS oldest_pending_age_seconds, \
            COUNT(*) FILTER (WHERE event.published_at IS NOT NULL AND receipt.event_id IS NULL)::BIGINT AS receipts_missing, \
            COALESCE(FLOOR(EXTRACT(EPOCH FROM (NOW() - MIN(event.published_at) FILTER (WHERE event.published_at IS NOT NULL AND receipt.event_id IS NULL)))), 0)::BIGINT AS oldest_missing_receipt_age_seconds \
         FROM domain_outbox event \
         LEFT JOIN domain_event_consumptions receipt \
           ON receipt.consumer_name = $1 AND receipt.event_id = event.id",
    )
    .bind(CONSUMER_LEDGER_NAME)
    .fetch_one(pool)
    .await
    .context("failed to inspect transactional domain event chain")
}

pub async fn claim_pending(pool: &PgPool, limit: i64) -> anyhow::Result<Vec<OutboxEvent>> {
    sqlx::query_as::<_, OutboxEvent>(
        "WITH picked AS (\
             SELECT id FROM domain_outbox \
             WHERE published_at IS NULL \
               AND quarantined_at IS NULL \
               AND available_at <= NOW() \
             ORDER BY available_at ASC, id ASC \
             FOR UPDATE SKIP LOCKED \
             LIMIT $1\
         ) \
         UPDATE domain_outbox AS event \
            SET attempt_count = event.attempt_count + 1, \
                available_at = NOW() + make_interval(secs => $2) \
           FROM picked \
          WHERE event.id = picked.id \
         RETURNING event.id, event.aggregate_type, event.aggregate_id, \
                   event.event_type, event.payload, event.created_at, event.attempt_count",
    )
    .bind(limit)
    .bind(CLAIM_LEASE_SECONDS)
    .fetch_all(pool)
    .await
    .context("failed to claim domain outbox events")
}

pub async fn mark_published(pool: &PgPool, event_id: i64) -> anyhow::Result<()> {
    sqlx::query(
        "UPDATE domain_outbox \
            SET published_at = NOW(), last_error = NULL \
          WHERE id = $1 AND published_at IS NULL AND quarantined_at IS NULL",
    )
    .bind(event_id)
    .execute(pool)
    .await
    .context("failed to mark domain outbox event published")?;
    Ok(())
}

pub async fn mark_failed(
    pool: &PgPool,
    event_id: i64,
    attempt_count: i32,
    error: &str,
) -> anyhow::Result<bool> {
    let error: String = error.chars().take(2_000).collect();
    if attempt_count >= MAX_ATTEMPTS {
        sqlx::query(
            "UPDATE domain_outbox \
                SET quarantined_at = NOW(), last_error = $2 \
              WHERE id = $1 AND published_at IS NULL",
        )
        .bind(event_id)
        .bind(&error)
        .execute(pool)
        .await
        .context("failed to quarantine domain outbox event")?;
        return Ok(true);
    }

    let exponent = u32::try_from(attempt_count.clamp(1, 8)).unwrap_or(8);
    let base_delay_seconds = (2_i32.pow(exponent) * 2).min(300);
    // Deterministic per-event jitter prevents many failed events from becoming
    // eligible in the same second while keeping retry timing testable.
    let jitter_seconds = i32::try_from(event_id.rem_euclid(11)).unwrap_or(0);
    let delay_seconds = (base_delay_seconds + jitter_seconds).min(300);
    sqlx::query(
        "UPDATE domain_outbox \
            SET available_at = NOW() + make_interval(secs => $2), last_error = $3 \
          WHERE id = $1 AND published_at IS NULL AND quarantined_at IS NULL",
    )
    .bind(event_id)
    .bind(delay_seconds)
    .bind(&error)
    .execute(pool)
    .await
    .context("failed to reschedule domain outbox event")?;
    Ok(false)
}

/// Requeue one explicitly quarantined event for a controlled operator retry.
/// Published events are never reopened, and non-quarantined events are left unchanged.
pub async fn requeue_quarantined(pool: &PgPool, event_id: i64) -> anyhow::Result<bool> {
    let result = sqlx::query(
        "UPDATE domain_outbox \
            SET quarantined_at = NULL, attempt_count = 0, available_at = NOW(), last_error = NULL \
          WHERE id = $1 AND published_at IS NULL AND quarantined_at IS NOT NULL",
    )
    .bind(event_id)
    .execute(pool)
    .await
    .context("failed to requeue quarantined domain outbox event")?;
    Ok(result.rows_affected() == 1)
}

pub async fn record_consumed_once(
    pool: &PgPool,
    consumer_name: &str,
    event_id: i64,
) -> anyhow::Result<bool> {
    let result = sqlx::query(
        "INSERT INTO domain_event_consumptions (consumer_name, event_id) \
         VALUES ($1, $2) ON CONFLICT DO NOTHING",
    )
    .bind(consumer_name)
    .bind(event_id)
    .execute(pool)
    .await
    .context("failed to record domain event consumption")?;
    Ok(result.rows_affected() == 1)
}

async fn publish_event(context: &jetstream::Context, event: &OutboxEvent) -> anyhow::Result<()> {
    let envelope = PublishedDomainEvent {
        schema_version: 1,
        event_id: event.id,
        aggregate_type: event.aggregate_type.clone(),
        aggregate_id: event.aggregate_id.clone(),
        event_type: event.event_type.clone(),
        payload: event.payload.clone(),
        created_at: event.created_at,
    };
    let subject = format!("weltgewebe.{}", event.event_type);
    let mut headers = HeaderMap::new();
    headers.insert("Nats-Msg-Id", format!("domain-outbox-{}", event.id));
    context
        .publish_with_headers(subject, headers, serde_json::to_vec(&envelope)?.into())
        .await
        .context("failed to send domain outbox event to JetStream")?
        .await
        .context("JetStream did not acknowledge domain outbox event")?;
    Ok(())
}

async fn relay_loop(pool: PgPool, context: jetstream::Context) {
    loop {
        match claim_pending(&pool, CLAIM_BATCH_SIZE).await {
            Ok(events) if events.is_empty() => {
                tokio::time::sleep(Duration::from_millis(250)).await;
            }
            Ok(events) => {
                for event in events {
                    match publish_event(&context, &event).await {
                        Ok(()) => {
                            if let Err(error) = mark_published(&pool, event.id).await {
                                tracing::error!(
                                    event_id = event.id,
                                    error = %error,
                                    "Published domain event could not be marked complete"
                                );
                            }
                        }
                        Err(error) => {
                            match mark_failed(
                                &pool,
                                event.id,
                                event.attempt_count,
                                &error.to_string(),
                            )
                            .await
                            {
                                Ok(true) => tracing::error!(
                                    event_id = event.id,
                                    attempts = event.attempt_count,
                                    error = %error,
                                    "Domain outbox event quarantined"
                                ),
                                Ok(false) => tracing::warn!(
                                    event_id = event.id,
                                    attempts = event.attempt_count,
                                    error = %error,
                                    "Domain outbox publish failed; retry scheduled"
                                ),
                                Err(mark_error) => tracing::error!(
                                    event_id = event.id,
                                    error = %error,
                                    mark_error = %mark_error,
                                    "Domain outbox publish and failure recording both failed"
                                ),
                            }
                        }
                    }
                }
            }
            Err(error) => {
                tracing::error!(error = %error, "Domain outbox claim failed");
                tokio::time::sleep(Duration::from_secs(1)).await;
            }
        }
    }
}

async fn receipt_consumer_loop(pool: PgPool, consumer: PullConsumer) {
    loop {
        let mut messages = match consumer.messages().await {
            Ok(messages) => messages,
            Err(error) => {
                tracing::error!(error = %error, "Domain receipt consumer could not fetch messages");
                tokio::time::sleep(Duration::from_secs(1)).await;
                continue;
            }
        };
        while let Some(message) = messages.next().await {
            let message = match message {
                Ok(message) => message,
                Err(error) => {
                    tracing::warn!(error = %error, "Domain receipt consumer message error");
                    break;
                }
            };
            let envelope: PublishedDomainEvent = match serde_json::from_slice(&message.payload) {
                Ok(envelope) => envelope,
                Err(error) => {
                    tracing::error!(error = %error, "Malformed internal domain event discarded");
                    if let Err(ack_error) = message.ack().await {
                        tracing::warn!(error = %ack_error, "Malformed domain event ack failed");
                    }
                    continue;
                }
            };
            match record_consumed_once(&pool, CONSUMER_LEDGER_NAME, envelope.event_id).await {
                Ok(first_delivery) => {
                    tracing::debug!(
                        event_id = envelope.event_id,
                        first_delivery,
                        "Domain event consumption receipt recorded"
                    );
                    if let Err(error) = message.ack().await {
                        tracing::warn!(event_id = envelope.event_id, error = %error, "Domain event ack failed");
                    }
                }
                Err(error) => {
                    tracing::error!(
                        event_id = envelope.event_id,
                        error = %error,
                        "Domain event consumption receipt failed; leaving message unacked"
                    );
                }
            }
        }
    }
}

fn spawn_essential_worker<F>(
    metrics: Metrics,
    worker: DomainEventWorker,
    future: F,
) -> tokio::task::AbortHandle
where
    F: Future<Output = ()> + Send + 'static,
{
    metrics.set_domain_event_worker_up(worker, true);
    let worker_handle = tokio::spawn(future);
    let abort_handle = worker_handle.abort_handle();
    tokio::spawn(async move {
        let outcome = worker_handle.await;
        metrics.set_domain_event_worker_up(worker, false);
        match outcome {
            Ok(()) => tracing::error!(?worker, "Essential domain event worker exited"),
            Err(error) => {
                tracing::error!(?worker, %error, "Essential domain event worker stopped unexpectedly")
            }
        }
    });
    abort_handle
}

pub async fn start(pool: PgPool, client: Client, metrics: Metrics) -> anyhow::Result<()> {
    let (context, stream) = ensure_stream(client).await?;
    let consumer: PullConsumer = stream
        .get_or_create_consumer(CONSUMER_NAME, expected_consumer_config())
        .await
        .context("failed to get or create domain receipt consumer")?;
    let consumer_info = stream
        .consumer_info(CONSUMER_NAME)
        .await
        .context("failed to inspect domain receipt consumer")?;
    validate_consumer_contract(&consumer_info)?;

    spawn_essential_worker(
        metrics.clone(),
        DomainEventWorker::Relay,
        relay_loop(pool.clone(), context),
    );
    spawn_essential_worker(
        metrics,
        DomainEventWorker::ReceiptConsumer,
        receipt_consumer_loop(pool, consumer),
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::{future::pending, time::Duration};

    use super::*;
    use crate::telemetry::BuildInfo;

    fn metrics() -> Metrics {
        Metrics::try_new(BuildInfo {
            version: "outbox-test",
            commit: "outbox-test",
            build_timestamp: "outbox-test",
        })
        .expect("metrics")
    }

    #[test]
    fn jetstream_contract_rejects_subject_and_durable_consumer_drift() {
        let stream = expected_stream_config();
        validate_stream_contract(&stream).expect("expected stream contract");
        let mut wrong_stream = stream.clone();
        wrong_stream.subjects = vec!["unrelated.>".to_string()];
        assert!(validate_stream_contract(&wrong_stream).is_err());
        let mut extra_subject = stream.clone();
        extra_subject.subjects.push("unrelated.>".to_string());
        assert!(validate_stream_contract(&extra_subject).is_err());
        let mut wrong_retention = stream.clone();
        wrong_retention.max_age = Duration::from_secs(60);
        assert!(validate_stream_contract(&wrong_retention).is_err());
        let mut wrong_deduplication = stream;
        wrong_deduplication.duplicate_window = Duration::from_secs(30);
        assert!(validate_stream_contract(&wrong_deduplication).is_err());

        let consumer = consumer::Config {
            durable_name: Some(CONSUMER_NAME.to_string()),
            filter_subject: STREAM_SUBJECT.to_string(),
            ack_policy: consumer::AckPolicy::Explicit,
            ..Default::default()
        };
        validate_consumer_config(STREAM_NAME, CONSUMER_NAME, &consumer)
            .expect("expected durable receipt consumer contract");
        let mut ephemeral = consumer;
        ephemeral.durable_name = None;
        assert!(validate_consumer_config(STREAM_NAME, CONSUMER_NAME, &ephemeral).is_err());
    }

    #[tokio::test]
    async fn essential_worker_abort_is_reflected_by_shared_liveness() {
        let metrics = metrics();
        let abort =
            spawn_essential_worker(metrics.clone(), DomainEventWorker::Relay, pending::<()>());
        assert!(metrics.domain_event_worker_is_up(DomainEventWorker::Relay));

        abort.abort();
        tokio::time::timeout(Duration::from_secs(1), async {
            while metrics.domain_event_worker_is_up(DomainEventWorker::Relay) {
                tokio::task::yield_now().await;
            }
        })
        .await
        .expect("supervisor must expose an aborted essential worker");
    }
}

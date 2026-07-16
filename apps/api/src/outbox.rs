use std::time::Duration;

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

const STREAM_NAME: &str = "WELTGEWEBE_DOMAIN";
const STREAM_SUBJECT: &str = "weltgewebe.domain.>";
const CONSUMER_NAME: &str = "weltgewebe-api-domain-receipts-v1";
const CONSUMER_LEDGER_NAME: &str = "weltgewebe-api-domain-receipts-v1";
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

pub async fn ensure_stream(client: Client) -> anyhow::Result<(jetstream::Context, stream::Stream)> {
    let context = jetstream::new(client);
    let stream = context
        .get_or_create_stream(stream::Config {
            name: STREAM_NAME.to_string(),
            description: Some(
                "Transactional Weltgewebe domain events emitted from PostgreSQL".to_string(),
            ),
            subjects: vec![STREAM_SUBJECT.to_string()],
            max_age: Duration::from_secs(30 * 24 * 60 * 60),
            duplicate_window: Duration::from_secs(2 * 60),
            ..Default::default()
        })
        .await
        .context("failed to get or create Weltgewebe domain JetStream")?;
    Ok((context, stream))
}

pub async fn claim_pending(pool: &PgPool, limit: i64) -> anyhow::Result<Vec<OutboxEvent>> {
    sqlx::query_as::<_, OutboxEvent>(
        "WITH picked AS (\
             SELECT id FROM domain_outbox \
             WHERE published_at IS NULL \
               AND quarantined_at IS NULL \
               AND available_at <= NOW() \
             ORDER BY id ASC \
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
    let delay_seconds = (2_i32.pow(exponent) * 2).min(300);
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

pub async fn start(pool: PgPool, client: Client) -> anyhow::Result<()> {
    let (context, stream) = ensure_stream(client).await?;
    let consumer: PullConsumer = stream
        .get_or_create_consumer(
            CONSUMER_NAME,
            consumer::pull::Config {
                durable_name: Some(CONSUMER_NAME.to_string()),
                filter_subject: STREAM_SUBJECT.to_string(),
                ack_policy: consumer::AckPolicy::Explicit,
                ..Default::default()
            },
        )
        .await
        .context("failed to get or create domain receipt consumer")?;

    tokio::spawn(relay_loop(pool.clone(), context));
    tokio::spawn(receipt_consumer_loop(pool, consumer));
    Ok(())
}

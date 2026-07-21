//! T005's internal, PostgreSQL-backed search projection worker.
//!
//! It deliberately has no HTTP surface.  Domain rows remain canonical; this
//! module only claims leased work and writes a regenerable projection.

use std::{sync::Arc, time::Duration};

use anyhow::Context;
use async_trait::async_trait;
use serde_json::Value;
use sha2::{Digest, Sha256};
use sqlx::{PgPool, Row};
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    net::TcpStream,
    time::timeout,
};
use unicode_normalization::UnicodeNormalization;

use crate::telemetry::Metrics;

pub const DOCUMENT_REVISION: &str = "node-document-v1";
pub const NORMALIZATION_REVISION: &str = "weltgewebe-search-normalization-v1";
pub const RANKING_REVISION: &str = "weltgewebe-hybrid-ranking-v2";
const CLAIM_SECONDS: i32 = 30;
const OLLAMA_RESPONSE_LIMIT: usize = 1_048_576;
// Leave a small, bounded allowance for HTTP headers and chunk framing while
// keeping the decoded provider body at the contract limit.
const OLLAMA_RAW_RESPONSE_LIMIT: usize = OLLAMA_RESPONSE_LIMIT + 16_384;
const OLLAMA_TIMEOUT: Duration = Duration::from_secs(10);

#[derive(Clone, Debug)]
pub struct GenerationSpec<'a> {
    pub generation_id: &'a str,
    pub provider: &'a str,
    pub model_id: &'a str,
    pub model_revision: &'a str,
    pub runtime_identity: &'a str,
    pub dimension: i32,
}

impl GenerationSpec<'_> {
    pub fn derived_id(&self) -> String {
        // Byte-compatible with hybrid_ranking_core.py's sorted compact JSON.
        let payload = serde_json::json!({
            "model": {
                "provider": self.provider,
                "model_id": self.model_id,
                "model_revision": self.model_revision,
                "runtime_id": self.runtime_identity,
                "dimensions": self.dimension,
            },
            "document_revision": DOCUMENT_REVISION,
            "normalization_revision": NORMALIZATION_REVISION,
            "ranking_revision": RANKING_REVISION,
        });
        let bytes = serde_jcs::to_vec(&payload)
            .expect("generation identity payload contains only JCS-compatible values");
        format!("search-gen-{}", hex::encode(Sha256::digest(bytes)))
    }

    fn is_valid_model_revision(&self) -> bool {
        is_canonical_sha256(self.model_revision)
    }
}

fn is_canonical_sha256(value: &str) -> bool {
    value.len() == "sha256:".len() + 64
        && value.starts_with("sha256:")
        && value["sha256:".len()..]
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ProcessOutcome {
    Processed,
    Stale,
    PendingProvider,
    Failed,
    Deleted,
    Empty,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProjectionStatusSnapshot {
    pub pending_jobs: i64,
    pub claimed_jobs: i64,
    pub retry_jobs: i64,
    pub done_jobs: i64,
    pub stale_jobs: i64,
    pub failed_jobs: i64,
    pub active_generation_id: Option<String>,
    pub active_generation_identity: Option<String>,
    pub rebuild_expected_nodes: Option<i64>,
    pub rebuild_completed_nodes: Option<i64>,
    pub last_successful_projection_at: Option<chrono::DateTime<chrono::Utc>>,
}

#[derive(Debug, thiserror::Error)]
pub enum EmbeddingProviderError {
    #[error("embedding provider unavailable")]
    Unavailable,
    #[error("embedding provider identity mismatch")]
    IdentityMismatch,
    #[error("embedding provider returned malformed data")]
    MalformedResponse,
    #[error("embedding provider returned wrong dimension")]
    WrongDimension,
    #[error("embedding provider returned invalid vector")]
    InvalidVector,
    #[error("embedding provider is unsupported")]
    Unsupported,
    #[error("embedding provider failed")]
    Failed,
}

impl EmbeddingProviderError {
    pub fn code(&self) -> &'static str {
        match self {
            Self::Unavailable => "provider_unavailable",
            Self::IdentityMismatch => "provider_identity_mismatch",
            Self::MalformedResponse => "provider_malformed_response",
            Self::WrongDimension => "provider_wrong_dimension",
            Self::InvalidVector => "provider_invalid_vector",
            Self::Unsupported => "provider_unsupported",
            Self::Failed => "provider_failed",
        }
    }
}

/// Private boundary for T005's worker. Implementations must not log the
/// document or vector; the worker records only bounded outcome labels.
#[async_trait]
pub trait EmbeddingProvider: Send + Sync {
    async fn embed(
        &self,
        document: &str,
        dimension: usize,
    ) -> Result<Vec<f64>, EmbeddingProviderError>;
}

/// T004-compatible local Ollama boundary.  It accepts only a literal loopback
/// HTTP origin and checks the model/runtime identity on both sides of embedding.
pub struct OllamaEmbeddingProvider {
    base_url: url::Url,
    model_id: String,
    model_revision: String,
    runtime_identity: String,
}

impl OllamaEmbeddingProvider {
    pub fn new(
        base_url: &str,
        model_id: String,
        model_revision: String,
        runtime_identity: String,
    ) -> Result<Self, EmbeddingProviderError> {
        let base_url =
            url::Url::parse(base_url).map_err(|_| EmbeddingProviderError::Unsupported)?;
        let loopback = matches!(base_url.host_str(), Some("127.0.0.1") | Some("::1"));
        if base_url.scheme() != "http"
            || !loopback
            || base_url.username() != ""
            || base_url.password().is_some()
            || base_url.query().is_some()
            || base_url.fragment().is_some()
            || base_url.path() != "/"
        {
            return Err(EmbeddingProviderError::Unsupported);
        }
        Ok(Self {
            base_url,
            model_id,
            model_revision,
            runtime_identity,
        })
    }

    async fn object(
        &self,
        path: &str,
        body: Option<Value>,
    ) -> Result<Value, EmbeddingProviderError> {
        let host = self
            .base_url
            .host_str()
            .ok_or(EmbeddingProviderError::Unsupported)?;
        let port = self
            .base_url
            .port_or_known_default()
            .ok_or(EmbeddingProviderError::Unsupported)?;
        let payload = body
            .map(|body| serde_json::to_vec(&body).map_err(|_| EmbeddingProviderError::Failed))
            .transpose()?;
        let request = match &payload {
            Some(payload) => format!("POST /{path} HTTP/1.1\r\nHost: {host}:{port}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n", payload.len()).into_bytes(),
            None => format!("GET /{path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n").into_bytes(),
        };
        let mut stream = timeout(OLLAMA_TIMEOUT, TcpStream::connect((host, port)))
            .await
            .map_err(|_| EmbeddingProviderError::Unavailable)?
            .map_err(|_| EmbeddingProviderError::Unavailable)?;
        timeout(OLLAMA_TIMEOUT, async {
            stream.write_all(&request).await?;
            if let Some(payload) = &payload {
                stream.write_all(payload).await?;
            }
            Ok::<(), std::io::Error>(())
        })
        .await
        .map_err(|_| EmbeddingProviderError::Unavailable)?
        .map_err(|_| EmbeddingProviderError::Unavailable)?;
        let mut bytes = Vec::new();
        timeout(OLLAMA_TIMEOUT, async {
            let mut part = [0_u8; 8192];
            loop {
                let read = stream.read(&mut part).await?;
                if read == 0 {
                    break;
                }
                if bytes.len() + read > OLLAMA_RAW_RESPONSE_LIMIT {
                    return Err(std::io::Error::other("response too large"));
                }
                bytes.extend_from_slice(&part[..read]);
            }
            Ok::<(), std::io::Error>(())
        })
        .await
        .map_err(|_| EmbeddingProviderError::Unavailable)?
        .map_err(|_| EmbeddingProviderError::MalformedResponse)?;
        let split = bytes
            .windows(4)
            .position(|window| window == b"\r\n\r\n")
            .ok_or(EmbeddingProviderError::MalformedResponse)?;
        let header = std::str::from_utf8(&bytes[..split])
            .map_err(|_| EmbeddingProviderError::MalformedResponse)?;
        let mut status_parts = header.lines().next().unwrap_or_default().split_whitespace();
        let protocol = status_parts
            .next()
            .ok_or(EmbeddingProviderError::MalformedResponse)?;
        if protocol != "HTTP/1.1" && protocol != "HTTP/1.0" {
            return Err(EmbeddingProviderError::MalformedResponse);
        }
        let status = status_parts
            .next()
            .ok_or(EmbeddingProviderError::MalformedResponse)?
            .parse::<u16>()
            .map_err(|_| EmbeddingProviderError::MalformedResponse)?;
        if (300..400).contains(&status) {
            // There is deliberately no redirect policy at this loopback-only
            // boundary: following one could silently leave loopback.
            return Err(EmbeddingProviderError::MalformedResponse);
        }
        if (500..600).contains(&status) {
            return Err(EmbeddingProviderError::Unavailable);
        }
        if !(200..300).contains(&status) {
            return Err(EmbeddingProviderError::Failed);
        }
        let mut content_length = None;
        let mut transfer_encoding = None;
        for line in header.lines().skip(1) {
            let (name, value) = line
                .split_once(':')
                .ok_or(EmbeddingProviderError::MalformedResponse)?;
            if name.eq_ignore_ascii_case("transfer-encoding") {
                if transfer_encoding.is_some() || !value.trim().eq_ignore_ascii_case("chunked") {
                    return Err(EmbeddingProviderError::MalformedResponse);
                }
                transfer_encoding = Some(());
            }
            if name.eq_ignore_ascii_case("content-length") {
                if content_length.is_some() {
                    return Err(EmbeddingProviderError::MalformedResponse);
                }
                let value = value.trim();
                if value.is_empty() || !value.bytes().all(|byte| byte.is_ascii_digit()) {
                    return Err(EmbeddingProviderError::MalformedResponse);
                }
                content_length = Some(
                    value
                        .parse::<usize>()
                        .map_err(|_| EmbeddingProviderError::MalformedResponse)?,
                );
            }
        }
        let framed_body = &bytes[split + 4..];
        let body = match (content_length, transfer_encoding) {
            (Some(_), Some(_)) | (None, None) => {
                return Err(EmbeddingProviderError::MalformedResponse)
            }
            (Some(content_length), None) => {
                if content_length > OLLAMA_RESPONSE_LIMIT || framed_body.len() != content_length {
                    return Err(EmbeddingProviderError::MalformedResponse);
                }
                framed_body.to_vec()
            }
            (None, Some(())) => decode_ollama_chunked_body(framed_body)?,
        };
        serde_json::from_slice(&body).map_err(|_| EmbeddingProviderError::MalformedResponse)
    }

    async fn verify_identity(&self) -> Result<(), EmbeddingProviderError> {
        let tags = self.object("api/tags", None).await?;
        let digest = tags
            .get("models")
            .and_then(Value::as_array)
            .and_then(|models| {
                models
                    .iter()
                    .find(|m| m.get("name").and_then(Value::as_str) == Some(self.model_id.as_str()))
            })
            .and_then(|model| model.get("digest"))
            .and_then(Value::as_str)
            .ok_or(EmbeddingProviderError::IdentityMismatch)?;
        if !is_canonical_sha256(&self.model_revision)
            || digest.len() != 64
            || !digest
                .bytes()
                .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
            || format!("sha256:{digest}") != self.model_revision
        {
            return Err(EmbeddingProviderError::IdentityMismatch);
        }
        let version_response = self.object("api/version", None).await?;
        let version = version_response
            .get("version")
            .and_then(Value::as_str)
            .filter(|v| !v.is_empty())
            .ok_or(EmbeddingProviderError::IdentityMismatch)?;
        let observed = format!(
            "ollama:{version}@{}",
            self.base_url.as_str().trim_end_matches('/')
        );
        if observed != self.runtime_identity {
            return Err(EmbeddingProviderError::IdentityMismatch);
        }
        Ok(())
    }
}

/// Decodes the only transfer coding accepted at this boundary. Chunk
/// extensions and malformed trailer fields are rejected rather than ignored so
/// JSON is never parsed from ambiguously framed bytes.
fn decode_ollama_chunked_body(input: &[u8]) -> Result<Vec<u8>, EmbeddingProviderError> {
    let mut cursor = 0;
    let mut decoded = Vec::new();
    loop {
        let size_end = input[cursor..]
            .windows(2)
            .position(|window| window == b"\r\n")
            .map(|offset| cursor + offset)
            .ok_or(EmbeddingProviderError::MalformedResponse)?;
        let size = std::str::from_utf8(&input[cursor..size_end])
            .ok()
            .filter(|value| !value.is_empty() && value.bytes().all(|byte| byte.is_ascii_hexdigit()))
            .and_then(|value| usize::from_str_radix(value, 16).ok())
            .ok_or(EmbeddingProviderError::MalformedResponse)?;
        cursor = size_end + 2;
        if size == 0 {
            loop {
                let trailer_end = input[cursor..]
                    .windows(2)
                    .position(|window| window == b"\r\n")
                    .map(|offset| cursor + offset)
                    .ok_or(EmbeddingProviderError::MalformedResponse)?;
                if trailer_end == cursor {
                    if trailer_end + 2 != input.len() {
                        return Err(EmbeddingProviderError::MalformedResponse);
                    }
                    return Ok(decoded);
                }
                let trailer = &input[cursor..trailer_end];
                let Some(colon) = trailer.iter().position(|byte| *byte == b':') else {
                    return Err(EmbeddingProviderError::MalformedResponse);
                };
                let name = &trailer[..colon];
                let value = &trailer[colon + 1..];
                if name.is_empty()
                    || !name.iter().all(|byte| {
                        byte.is_ascii_alphanumeric()
                            || matches!(
                                byte,
                                b'!' | b'#'
                                    | b'$'
                                    | b'%'
                                    | b'&'
                                    | b'\''
                                    | b'*'
                                    | b'+'
                                    | b'-'
                                    | b'.'
                                    | b'^'
                                    | b'_'
                                    | b'`'
                                    | b'|'
                                    | b'~'
                            )
                    })
                    || !value
                        .iter()
                        .all(|byte| *byte == b'\t' || (*byte >= b' ' && *byte != 0x7f))
                {
                    return Err(EmbeddingProviderError::MalformedResponse);
                }
                cursor = trailer_end + 2;
            }
        }
        let end = cursor
            .checked_add(size)
            .ok_or(EmbeddingProviderError::MalformedResponse)?;
        let after_data = end
            .checked_add(2)
            .ok_or(EmbeddingProviderError::MalformedResponse)?;
        if after_data > input.len() || &input[end..after_data] != b"\r\n" {
            return Err(EmbeddingProviderError::MalformedResponse);
        }
        if decoded
            .len()
            .checked_add(size)
            .filter(|length| *length <= OLLAMA_RESPONSE_LIMIT)
            .is_none()
        {
            return Err(EmbeddingProviderError::MalformedResponse);
        }
        decoded.extend_from_slice(&input[cursor..end]);
        cursor = after_data;
    }
}

#[async_trait]
impl EmbeddingProvider for OllamaEmbeddingProvider {
    async fn embed(
        &self,
        document: &str,
        dimension: usize,
    ) -> Result<Vec<f64>, EmbeddingProviderError> {
        self.verify_identity().await?;
        let response = self
            .object(
                "api/embed",
                Some(serde_json::json!({"model": self.model_id, "input": document})),
            )
            .await?;
        let vectors = response
            .get("embeddings")
            .and_then(Value::as_array)
            .filter(|v| v.len() == 1)
            .ok_or(EmbeddingProviderError::MalformedResponse)?;
        let vector = vectors[0]
            .as_array()
            .ok_or(EmbeddingProviderError::MalformedResponse)?;
        if vector.len() != dimension {
            return Err(EmbeddingProviderError::WrongDimension);
        }
        let vector = vector
            .iter()
            .map(|v| v.as_f64().ok_or(EmbeddingProviderError::InvalidVector))
            .collect::<Result<Vec<_>, _>>()?;
        let norm = vector.iter().map(|v| v * v).sum::<f64>();
        if !norm.is_finite() || norm <= 0.0 || vector.iter().any(|v| !v.is_finite()) {
            return Err(EmbeddingProviderError::InvalidVector);
        }
        self.verify_identity().await?;
        Ok(vector)
    }
}

struct UnavailableEmbeddingProvider;

#[async_trait]
impl EmbeddingProvider for UnavailableEmbeddingProvider {
    async fn embed(
        &self,
        _document: &str,
        _dimension: usize,
    ) -> Result<Vec<f64>, EmbeddingProviderError> {
        Err(EmbeddingProviderError::Unavailable)
    }
}

#[derive(Clone)]
pub struct ProjectionWorker {
    pool: PgPool,
    worker_id: String,
    metrics: Metrics,
    provider: Arc<dyn EmbeddingProvider>,
}

impl ProjectionWorker {
    pub fn new(pool: PgPool, worker_id: String, metrics: Metrics) -> anyhow::Result<Self> {
        Self::new_with_provider(
            pool,
            worker_id,
            metrics,
            Arc::new(UnavailableEmbeddingProvider),
        )
    }

    pub fn new_with_provider(
        pool: PgPool,
        worker_id: String,
        metrics: Metrics,
        provider: Arc<dyn EmbeddingProvider>,
    ) -> anyhow::Result<Self> {
        if worker_id.trim().is_empty() {
            anyhow::bail!("search worker id must not be empty");
        }
        Ok(Self {
            pool,
            worker_id,
            metrics,
            provider,
        })
    }

    /// Starts a bounded rebuild generation.  No activation occurs here.
    pub async fn start_generation(&self, spec: GenerationSpec<'_>) -> anyhow::Result<i64> {
        if spec.provider != "local:ollama" {
            anyhow::bail!("unsupported search embedding provider");
        }
        if spec.dimension <= 0 || spec.dimension > 8192 || !spec.is_valid_model_revision() {
            anyhow::bail!("search generation identity is invalid");
        }
        if spec.generation_id != spec.derived_id() {
            anyhow::bail!("search generation id is not canonical for its immutable identity");
        }
        let mut tx = self.pool.begin().await?;
        // A migration starts tracking future mutations.  This idempotent seed
        // makes legacy rows resumable without treating a missing revision as a
        // public/visible value.
        sqlx::query(
            "INSERT INTO search_node_versions (node_id,source_version,source_revision) \
            SELECT id,1,'node-1' FROM domain_nodes ON CONFLICT (node_id) DO NOTHING",
        )
        .execute(&mut *tx)
        .await?;
        let identity = sqlx::query("INSERT INTO search_index_generations (generation_id, provider, model_id, model_revision, runtime_identity, dimension, document_revision, normalization_revision, ranking_revision, state, expected_nodes) \
                     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'building',(SELECT count(*) FROM domain_nodes)) \
                     ON CONFLICT (generation_id) DO UPDATE SET generation_id=EXCLUDED.generation_id \
                     WHERE search_index_generations.provider=EXCLUDED.provider \
                       AND search_index_generations.model_id=EXCLUDED.model_id \
                       AND search_index_generations.model_revision=EXCLUDED.model_revision \
                       AND search_index_generations.runtime_identity=EXCLUDED.runtime_identity \
                       AND search_index_generations.dimension=EXCLUDED.dimension \
                       AND search_index_generations.document_revision=EXCLUDED.document_revision \
                       AND search_index_generations.normalization_revision=EXCLUDED.normalization_revision \
                       AND search_index_generations.ranking_revision=EXCLUDED.ranking_revision \
                     RETURNING generation_id")
            .bind(spec.generation_id).bind(spec.provider).bind(spec.model_id).bind(spec.model_revision).bind(spec.runtime_identity)
            .bind(spec.dimension).bind(DOCUMENT_REVISION).bind(NORMALIZATION_REVISION).bind(RANKING_REVISION)
            .fetch_optional(&mut *tx).await?;
        if identity.is_none() {
            anyhow::bail!("search generation identity mismatch");
        }
        let inserted = sqlx::query("INSERT INTO search_projection_jobs (generation_id,node_id,source_version,source_revision,operation) \
            SELECT $1, v.node_id,v.source_version,v.source_revision,'upsert' FROM search_node_versions v JOIN domain_nodes n ON n.id=v.node_id \
            ON CONFLICT DO NOTHING")
            .bind(spec.generation_id).execute(&mut *tx).await?.rows_affected() as i64;
        tx.commit().await?;
        Ok(inserted)
    }

    pub async fn claim_and_process_one(&self) -> anyhow::Result<ProcessOutcome> {
        let job = sqlx::query("WITH picked AS (SELECT id FROM search_projection_jobs \
            WHERE (state IN ('pending','retry') AND available_at <= NOW()) OR (state='claimed' AND claim_until <= NOW()) \
            ORDER BY available_at,id FOR UPDATE SKIP LOCKED LIMIT 1) \
            UPDATE search_projection_jobs j SET state='claimed', claimed_by=$1, claim_until=NOW()+make_interval(secs=>$2), attempt_count=j.attempt_count+1 \
            FROM picked WHERE j.id=picked.id RETURNING j.id,j.generation_id,j.node_id,j.source_version,j.source_revision,j.operation,j.attempt_count")
            .bind(&self.worker_id).bind(CLAIM_SECONDS).fetch_optional(&self.pool).await?;
        let Some(job) = job else {
            return Ok(ProcessOutcome::Empty);
        };
        let id: i64 = job.get("id");
        let generation: String = job.get("generation_id");
        let node_id: String = job.get("node_id");
        let version: i64 = job.get("source_version");
        let revision: String = job.get("source_revision");
        let operation: String = job.get("operation");
        let attempts: i32 = job.get("attempt_count");
        let result = if operation == "delete" {
            self.delete_if_current(&generation, &node_id, version, &revision)
                .await?
        } else {
            self.upsert_if_current(&generation, &node_id, version, &revision)
                .await?
        };
        let outcome = match result {
            Ok(outcome) => outcome,
            Err(code) => {
                self.finish(id, "failed", Some(code)).await?;
                self.metrics.search_projection_outcome("failed");
                return Ok(ProcessOutcome::Failed);
            }
        };
        match outcome {
            // Provider outages never exhaust a job. The retry ledger remains
            // recoverable until a later worker with a provider catches up.
            ProcessOutcome::PendingProvider => {
                self.retry(id, attempts, "provider_unavailable").await?
            }
            ProcessOutcome::Stale => self.finish(id, "stale", Some("stale_revision")).await?,
            _ => self.finish(id, "done", None).await?,
        }
        self.metrics.search_projection_outcome(match outcome {
            ProcessOutcome::Processed => "processed",
            ProcessOutcome::Stale => "stale",
            ProcessOutcome::PendingProvider => "pending",
            ProcessOutcome::Deleted => "deleted",
            ProcessOutcome::Failed => "failed",
            ProcessOutcome::Empty => "empty",
        });
        Ok(outcome)
    }

    /// Read-only operational view: no document text, tags, or vectors escape.
    pub async fn status_snapshot(&self) -> anyhow::Result<ProjectionStatusSnapshot> {
        let row = sqlx::query("SELECT count(*) FILTER (WHERE state='pending') AS pending, count(*) FILTER (WHERE state='claimed') AS claimed, count(*) FILTER (WHERE state='retry') AS retry, count(*) FILTER (WHERE state='done') AS done, count(*) FILTER (WHERE state='stale') AS stale, count(*) FILTER (WHERE state='failed') AS failed FROM search_projection_jobs")
            .fetch_one(&self.pool).await?;
        let active = sqlx::query("SELECT generation_id,provider,model_id,model_revision,runtime_identity,dimension,document_revision,normalization_revision,ranking_revision,expected_nodes,completed_nodes FROM search_index_generations WHERE state='active'")
            .fetch_optional(&self.pool).await?;
        let rebuild = sqlx::query("SELECT expected_nodes,completed_nodes FROM search_index_generations WHERE state='building' ORDER BY created_at DESC,generation_id DESC LIMIT 1")
            .fetch_optional(&self.pool).await?;
        // Projection freshness is distinct from generation activation.  Read
        // only state and timestamp metadata, never projection content.
        let last_successful_projection_at = sqlx::query_scalar(
            "SELECT max(p.indexed_at) \
             FROM search_node_projections p \
             JOIN search_index_generations g ON g.generation_id=p.generation_id \
             WHERE p.semantic_state='ready' \
               AND g.state IN ('building','ready','active')",
        )
        .fetch_one(&self.pool)
        .await?;
        Ok(ProjectionStatusSnapshot {
            pending_jobs: row.get::<i64, _>("pending"),
            claimed_jobs: row.get::<i64, _>("claimed"),
            retry_jobs: row.get::<i64, _>("retry"),
            done_jobs: row.get::<i64, _>("done"),
            stale_jobs: row.get::<i64, _>("stale"),
            failed_jobs: row.get::<i64, _>("failed"),
            active_generation_id: active.as_ref().map(|row| row.get("generation_id")),
            active_generation_identity: active.as_ref().map(|row| {
                format!(
                    "{}:{}:{}:{}:{}:{}:{}:{}",
                    row.get::<String, _>("provider"),
                    row.get::<String, _>("model_id"),
                    row.get::<String, _>("model_revision"),
                    row.get::<String, _>("runtime_identity"),
                    row.get::<i32, _>("dimension"),
                    row.get::<String, _>("document_revision"),
                    row.get::<String, _>("normalization_revision"),
                    row.get::<String, _>("ranking_revision")
                )
            }),
            rebuild_expected_nodes: rebuild.as_ref().map(|row| row.get("expected_nodes")),
            rebuild_completed_nodes: rebuild.as_ref().map(|row| row.get("completed_nodes")),
            last_successful_projection_at,
        })
    }

    /// Deterministic digest over projection identity and metadata, deliberately
    /// excluding `searchable_text`, tags, and raw embeddings.
    pub async fn integrity_digest(&self, generation_id: &str) -> anyhow::Result<String> {
        let rows = sqlx::query("SELECT p.node_id,p.source_version,p.source_revision,p.content_sha256,p.language,p.kind,p.status,p.visibility_scopes,p.semantic_state,g.provider,g.model_id,g.model_revision,g.runtime_identity,g.dimension,g.document_revision,g.normalization_revision,g.ranking_revision FROM search_node_projections p JOIN search_index_generations g ON g.generation_id=p.generation_id WHERE p.generation_id=$1 ORDER BY p.node_id")
            .bind(generation_id).fetch_all(&self.pool).await?;
        let mut digest = Sha256::new();
        for row in rows {
            for value in [
                row.get::<String, _>("node_id"),
                row.get::<i64, _>("source_version").to_string(),
                row.get::<String, _>("source_revision"),
                row.get::<String, _>("content_sha256"),
                row.get::<String, _>("language"),
                row.get::<String, _>("kind"),
                row.get::<String, _>("status"),
                row.get::<Vec<String>, _>("visibility_scopes")
                    .join("\u{1f}"),
                row.get::<String, _>("semantic_state"),
                row.get::<String, _>("provider"),
                row.get::<String, _>("model_id"),
                row.get::<String, _>("model_revision"),
                row.get::<String, _>("runtime_identity"),
                row.get::<i32, _>("dimension").to_string(),
                row.get::<String, _>("document_revision"),
                row.get::<String, _>("normalization_revision"),
                row.get::<String, _>("ranking_revision"),
            ] {
                digest.update(value.as_bytes());
                digest.update([0]);
            }
        }
        Ok(hex::encode(digest.finalize()))
    }

    async fn delete_if_current(
        &self,
        generation: &str,
        node: &str,
        version: i64,
        revision: &str,
    ) -> anyhow::Result<Result<ProcessOutcome, &'static str>> {
        // The current tombstone is part of the mutating statement: a slow old
        // worker cannot delete a projection after a newer canonical revision.
        let current: bool = sqlx::query_scalar("WITH current AS (SELECT 1 FROM search_node_versions WHERE node_id=$1 AND source_version=$2 AND source_revision=$3 AND deleted_at IS NOT NULL FOR UPDATE), deleted AS (DELETE FROM search_node_projections p USING current, search_index_generations g WHERE p.node_id=$1 AND p.generation_id=$4 AND g.generation_id=p.generation_id AND g.state IN ('building','ready','active') RETURNING 1) SELECT EXISTS (SELECT 1 FROM current)")
            .bind(node).bind(version).bind(revision).bind(generation).fetch_one(&self.pool).await?;
        Ok(Ok(if current {
            ProcessOutcome::Deleted
        } else {
            ProcessOutcome::Stale
        }))
    }

    async fn upsert_if_current(
        &self,
        generation: &str,
        node: &str,
        version: i64,
        revision: &str,
    ) -> anyhow::Result<Result<ProcessOutcome, &'static str>> {
        let row = sqlx::query("SELECT n.kind,n.title,n.payload::text,g.dimension FROM domain_nodes n JOIN search_node_versions v ON v.node_id=n.id JOIN search_index_generations g ON g.generation_id=$2 WHERE n.id=$1 AND v.source_version=$3 AND v.source_revision=$4 AND v.deleted_at IS NULL")
            .bind(node).bind(generation).bind(version).bind(revision).fetch_optional(&self.pool).await?;
        let Some(row) = row else {
            return Ok(Ok(ProcessOutcome::Stale));
        };
        let document = match SearchDocument::from_row(
            node,
            &row.get::<String, _>("kind"),
            &row.get::<String, _>("title"),
            &row.get::<String, _>("payload"),
        ) {
            Ok(document) => document,
            Err(_) => return Ok(Err("document_invalid")),
        };
        let dimension: i32 = row.get("dimension");
        let embedding = match self
            .provider
            .embed(&document.text, dimension as usize)
            .await
        {
            Ok(vector)
                if vector.len() == dimension as usize
                    && vector.iter().all(|v| v.is_finite())
                    && vector.iter().map(|v| v * v).sum::<f64>() > 0.0 =>
            {
                vector
            }
            Ok(vector) if vector.len() != dimension as usize => {
                return Ok(Err("provider_wrong_dimension"))
            }
            Ok(_) => return Ok(Err("provider_invalid_vector")),
            Err(EmbeddingProviderError::Unavailable) => {
                return Ok(Ok(ProcessOutcome::PendingProvider))
            }
            Err(error) => return Ok(Err(error.code())),
        };
        // This INSERT is itself revision fenced. Its affected-row semantics
        // classify a concurrent canonical mutation as Stale, closing TOCTOU.
        let written = sqlx::query("INSERT INTO search_node_projections (generation_id,node_id,source_version,source_revision,content_sha256,title,tags,searchable_text,language,kind,status,visibility_scopes,semantic_state,embedding) \
            SELECT $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,'ready',$13 \
            FROM (SELECT v.node_id FROM search_node_versions v JOIN domain_nodes n ON n.id=v.node_id JOIN search_index_generations g ON g.generation_id=$1 WHERE n.id=$2 AND v.source_version=$3 AND v.source_revision=$4 AND v.deleted_at IS NULL AND g.state IN ('building','ready','active') FOR UPDATE OF v) current \
            ON CONFLICT (generation_id,node_id) DO UPDATE SET source_version=EXCLUDED.source_version,source_revision=EXCLUDED.source_revision,content_sha256=EXCLUDED.content_sha256,title=EXCLUDED.title,tags=EXCLUDED.tags,searchable_text=EXCLUDED.searchable_text,language=EXCLUDED.language,kind=EXCLUDED.kind,status=EXCLUDED.status,visibility_scopes=EXCLUDED.visibility_scopes,semantic_state='ready',embedding=EXCLUDED.embedding,indexed_at=clock_timestamp() \
            WHERE search_node_projections.source_version <= EXCLUDED.source_version")
            .bind(generation).bind(node).bind(version).bind(revision).bind(document.hash()).bind(&document.title).bind(&document.tags).bind(&document.text).bind(&document.language).bind(&document.kind).bind(&document.status).bind(&document.scopes).bind(embedding).execute(&self.pool).await?.rows_affected();
        Ok(Ok(if written == 1 {
            ProcessOutcome::Processed
        } else {
            ProcessOutcome::Stale
        }))
    }

    async fn finish(&self, id: i64, state: &str, code: Option<&str>) -> anyhow::Result<()> {
        sqlx::query("UPDATE search_projection_jobs SET state=$2,claimed_by=NULL,claim_until=NULL,completed_at=NOW(),last_error_code=$3 WHERE id=$1 AND claimed_by=$4")
            .bind(id).bind(state).bind(code).bind(&self.worker_id).execute(&self.pool).await?;
        sqlx::query("UPDATE search_index_generations g SET expected_nodes=(SELECT count(*) FROM search_projection_jobs j WHERE j.generation_id=g.generation_id), completed_nodes=(SELECT count(*) FROM search_projection_jobs j WHERE j.generation_id=g.generation_id AND j.state IN ('done','stale')), state=CASE WHEN g.state='building' AND NOT EXISTS (SELECT 1 FROM search_index_generations r WHERE r.state='ready' AND r.generation_id<>g.generation_id) AND NOT EXISTS (SELECT 1 FROM search_projection_jobs j LEFT JOIN search_node_projections p ON p.generation_id=j.generation_id AND p.node_id=j.node_id WHERE j.generation_id=g.generation_id AND (j.state NOT IN ('done','stale') OR (j.operation='upsert' AND EXISTS (SELECT 1 FROM search_node_versions v WHERE v.node_id=j.node_id AND v.source_version=j.source_version AND v.source_revision=j.source_revision AND v.deleted_at IS NULL) AND (p.semantic_state IS DISTINCT FROM 'ready' OR cardinality(p.embedding) IS DISTINCT FROM g.dimension)))) AND NOT EXISTS (SELECT 1 FROM search_node_versions v WHERE v.deleted_at IS NULL AND NOT EXISTS (SELECT 1 FROM search_node_projections p WHERE p.generation_id=g.generation_id AND p.node_id=v.node_id AND p.source_version=v.source_version AND p.source_revision=v.source_revision AND p.semantic_state='ready' AND cardinality(p.embedding)=g.dimension)) THEN 'ready' ELSE g.state END WHERE g.generation_id=(SELECT generation_id FROM search_projection_jobs WHERE id=$1)")
            .bind(id).execute(&self.pool).await?;
        Ok(())
    }
    async fn retry(&self, id: i64, attempts: i32, code: &str) -> anyhow::Result<()> {
        let secs = (2_i32.pow(attempts.clamp(1, 7) as u32)).min(300);
        sqlx::query("UPDATE search_projection_jobs SET state='retry',claimed_by=NULL,claim_until=NULL,available_at=NOW()+make_interval(secs=>$2),last_error_code=$3 WHERE id=$1 AND claimed_by=$4")
            .bind(id).bind(secs).bind(code).bind(&self.worker_id).execute(&self.pool).await?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::{
        EmbeddingProvider, EmbeddingProviderError, GenerationSpec, OllamaEmbeddingProvider,
        SearchDocument, OLLAMA_RESPONSE_LIMIT,
    };
    use tokio::{
        io::{AsyncReadExt, AsyncWriteExt},
        net::TcpListener,
    };

    async fn serve_one_response(response: Vec<u8>) -> (u16, tokio::task::JoinHandle<()>) {
        let listener = TcpListener::bind("127.0.0.1:0")
            .await
            .expect("bind loopback");
        let port = listener.local_addr().expect("address").port();
        let server = tokio::spawn(async move {
            let (mut stream, _) = listener.accept().await.expect("accept");
            let mut request = [0_u8; 4096];
            stream.read(&mut request).await.expect("read request");
            stream.write_all(&response).await.expect("response");
        });
        (port, server)
    }

    fn test_provider(port: u16) -> OllamaEmbeddingProvider {
        OllamaEmbeddingProvider::new(
            &format!("http://127.0.0.1:{port}/"),
            "test-model".into(),
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".into(),
            format!("ollama:test-runtime@http://127.0.0.1:{port}"),
        )
        .expect("provider")
    }

    fn chunked(body: &str) -> String {
        format!("{:X}\r\n{body}\r\n0\r\n\r\n", body.len())
    }

    #[test]
    fn document_excludes_address_and_fails_closed_visibility() {
        let private = SearchDocument::from_row(
            "node-1",
            "Werkstatt",
            "Fahrradhilfe",
            r#"{"summary":"Reparatur","address":"secret lane 9","tags":["Rad"]}"#,
        )
        .expect("document");
        assert_eq!(private.status, "hidden");
        assert!(private.scopes.is_empty());
        assert!(!private.text.contains("secret lane 9"));

        let public = SearchDocument::from_row(
            "node-1",
            "Werkstatt",
            "Fahrradhilfe",
            r#"{"search_visibility":"public","summary":"Reparatur","tags":["Rad"]}"#,
        )
        .expect("document");
        assert_eq!(public.status, "active");
        assert_eq!(public.scopes, ["public"]);
    }

    #[test]
    fn document_hash_changes_for_indexed_content_not_unindexed_payload() {
        let first = SearchDocument::from_row("node", "Kind", "Titel", r#"{"address":"a"}"#)
            .expect("document");
        let same = SearchDocument::from_row("node", "Kind", "Titel", r#"{"address":"b"}"#)
            .expect("document");
        let changed = SearchDocument::from_row("node", "Kind", "Titel", r#"{"summary":"neu"}"#)
            .expect("document");
        assert_eq!(first.hash(), same.hash());
        assert_ne!(first.hash(), changed.hash());
    }

    #[tokio::test]
    async fn ollama_boundary_uses_only_mocked_loopback_and_rechecks_identity() {
        let listener = TcpListener::bind("127.0.0.1:0")
            .await
            .expect("bind loopback");
        let port = listener.local_addr().expect("address").port();
        let server = tokio::spawn(async move {
            for _ in 0..5 {
                let (mut stream, _) = listener.accept().await.expect("accept");
                let mut request = [0_u8; 4096];
                let count = stream.read(&mut request).await.expect("read request");
                let request = std::str::from_utf8(&request[..count]).expect("request utf8");
                let body = if request.starts_with("GET /api/tags ") {
                    r#"{"models":[{"name":"test-model","digest":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]}"#
                } else if request.starts_with("GET /api/version ") {
                    r#"{"version":"test-runtime"}"#
                } else if request.starts_with("POST /api/embed ") {
                    r#"{"embeddings":[[0.25,0.5]]}"#
                } else {
                    panic!("unexpected request: {request}");
                };
                let response = if request.starts_with("GET /api/version ") {
                    format!("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}", body.len(), body)
                } else {
                    format!("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n{}", chunked(body))
                };
                stream
                    .write_all(response.as_bytes())
                    .await
                    .expect("response");
            }
        });
        let origin = format!("http://127.0.0.1:{port}/");
        let provider = OllamaEmbeddingProvider::new(
            &origin,
            "test-model".into(),
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".into(),
            format!("ollama:test-runtime@http://127.0.0.1:{port}"),
        )
        .expect("provider");
        assert_eq!(
            provider.embed("only a test", 2).await.expect("embedding"),
            vec![0.25, 0.5]
        );
        server.await.expect("server");
        assert!(matches!(
            OllamaEmbeddingProvider::new(
                "https://127.0.0.1:11434/",
                "m".into(),
                "r".into(),
                "x".into()
            ),
            Err(EmbeddingProviderError::Unsupported)
        ));
        assert!(matches!(
            OllamaEmbeddingProvider::new(
                "http://example.invalid/",
                "m".into(),
                "r".into(),
                "x".into()
            ),
            Err(EmbeddingProviderError::Unsupported)
        ));
    }

    #[tokio::test]
    async fn ollama_boundary_rejects_malformed_chunk_size() {
        let (port, server) = serve_one_response(
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nnope\r\n{}\r\n0\r\n\r\n"
                .to_vec(),
        )
        .await;
        assert!(matches!(
            test_provider(port).object("api/tags", None).await,
            Err(EmbeddingProviderError::MalformedResponse)
        ));
        server.await.expect("server");
    }

    #[tokio::test]
    async fn ollama_boundary_rejects_unsupported_transfer_coding() {
        let (port, server) =
            serve_one_response(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: gzip\r\n\r\n{}".to_vec())
                .await;
        assert!(matches!(
            test_provider(port).object("api/tags", None).await,
            Err(EmbeddingProviderError::MalformedResponse)
        ));
        server.await.expect("server");
    }

    #[tokio::test]
    async fn ollama_boundary_rejects_content_length_and_chunked() {
        let body = chunked("{}");
        let (port, server) = serve_one_response(
            format!(
                "HTTP/1.1 200 OK\r\nContent-Length: 2\r\nTransfer-Encoding: chunked\r\n\r\n{body}"
            )
            .into_bytes(),
        )
        .await;
        assert!(matches!(
            test_provider(port).object("api/tags", None).await,
            Err(EmbeddingProviderError::MalformedResponse)
        ));
        server.await.expect("server");
    }

    #[tokio::test]
    async fn ollama_boundary_rejects_chunked_decoded_body_over_limit() {
        let body = "x".repeat(OLLAMA_RESPONSE_LIMIT + 1);
        let response = format!(
            "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n{:X}\r\n{body}\r\n0\r\n\r\n",
            body.len()
        );
        let (port, server) = serve_one_response(response.into_bytes()).await;
        assert!(matches!(
            test_provider(port).object("api/tags", None).await,
            Err(EmbeddingProviderError::MalformedResponse)
        ));
        server.await.expect("server");
    }

    #[test]
    fn generation_identity_is_python_t004_byte_compatible() {
        let spec = GenerationSpec {
            generation_id: "ignored while deriving",
            provider: "local:ollama",
            model_id: "qwen3-embedding:4b",
            model_revision:
                "sha256:df5bd2e3c74cd8d069d21dc038f1b359fcdc9458fce1c99bd43c9eb1518ff907",
            runtime_identity: "ollama:0.12.6@http://127.0.0.1:11434",
            dimension: 2560,
        };
        let payload = serde_jcs::to_vec(&serde_json::json!({
            "model": {"provider":"local:ollama","model_id":"qwen3-embedding:4b","model_revision":"sha256:df5bd2e3c74cd8d069d21dc038f1b359fcdc9458fce1c99bd43c9eb1518ff907","runtime_id":"ollama:0.12.6@http://127.0.0.1:11434","dimensions":2560},
            "document_revision":"node-document-v1",
            "normalization_revision":"weltgewebe-search-normalization-v1",
            "ranking_revision":"weltgewebe-hybrid-ranking-v2"
        })).expect("JCS");
        assert_eq!(std::str::from_utf8(&payload).expect("utf8"), "{\"document_revision\":\"node-document-v1\",\"model\":{\"dimensions\":2560,\"model_id\":\"qwen3-embedding:4b\",\"model_revision\":\"sha256:df5bd2e3c74cd8d069d21dc038f1b359fcdc9458fce1c99bd43c9eb1518ff907\",\"provider\":\"local:ollama\",\"runtime_id\":\"ollama:0.12.6@http://127.0.0.1:11434\"},\"normalization_revision\":\"weltgewebe-search-normalization-v1\",\"ranking_revision\":\"weltgewebe-hybrid-ranking-v2\"}");
        assert_eq!(
            spec.derived_id(),
            "search-gen-46e7aba00f4c40aec10569dc42c9e12205a215d98036291bf006136467653b52"
        );
    }
}

#[derive(Debug)]
struct SearchDocument {
    title: String,
    tags: Vec<String>,
    summary: String,
    info: String,
    text: String,
    language: String,
    kind: String,
    status: String,
    scopes: Vec<String>,
}
impl SearchDocument {
    fn from_row(node_id: &str, kind: &str, title: &str, payload: &str) -> anyhow::Result<Self> {
        let payload: Value =
            serde_json::from_str(payload).context("domain node payload is not JSON")?;
        let tags = payload
            .get("tags")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .filter_map(Value::as_str)
            .map(normalize)
            .filter(|s| !s.is_empty())
            .collect::<Vec<_>>();
        let mut tags = tags;
        tags.sort();
        tags.dedup();
        let summary = normalize(payload.get("summary").and_then(Value::as_str).unwrap_or(""));
        let info = normalize(payload.get("info").and_then(Value::as_str).unwrap_or(""));
        let language = normalize(
            payload
                .get("language")
                .and_then(Value::as_str)
                .filter(|v| !v.trim().is_empty())
                .unwrap_or("und"),
        );
        // Visibility is fail-closed: legacy/missing values are hidden. No address
        // or arbitrary payload key is ever incorporated into the document.
        let public = payload.get("search_visibility").and_then(Value::as_str) == Some("public");
        let title = normalize(title);
        let kind = normalize(kind);
        let tag_text = tags.join(" ");
        let text = [
            title.as_str(),
            kind.as_str(),
            summary.as_str(),
            info.as_str(),
            tag_text.as_str(),
        ]
        .join("\n");
        if text.trim().is_empty() {
            anyhow::bail!("search document for {node_id} is empty");
        }
        Ok(Self {
            title,
            tags,
            summary,
            info,
            text,
            language,
            kind,
            status: if public { "active" } else { "hidden" }.to_owned(),
            scopes: if public {
                vec!["public".to_owned()]
            } else {
                vec![]
            },
        })
    }
    fn hash(&self) -> String {
        let mut h = Sha256::new();
        let tags = self.tags.join("\u{1f}");
        for (label, value) in [
            ("document_revision", DOCUMENT_REVISION),
            ("normalization_revision", NORMALIZATION_REVISION),
            ("title", self.title.as_str()),
            ("summary", self.summary.as_str()),
            ("info", self.info.as_str()),
            ("tags", tags.as_str()),
            ("language", self.language.as_str()),
            ("kind", self.kind.as_str()),
        ] {
            h.update(label.as_bytes());
            h.update([0]);
            h.update(value.as_bytes());
            h.update([0]);
        }
        hex::encode(h.finalize())
    }
}

fn normalize(value: &str) -> String {
    value.nfkc().collect::<String>().trim().to_owned()
}

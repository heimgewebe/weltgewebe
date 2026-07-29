//! Public node conversations backed exclusively by PostgreSQL.
//!
//! Every PostgreSQL node owns exactly one public conversation through the
//! migration trigger. Reads are public. Creating, editing and tombstoning
//! messages uses the existing Weber/Admin write gate in `routes::api_router`;
//! this module additionally enforces author-or-admin ownership.
//!
//! Message creation is limited by a PostgreSQL-backed rolling minute window.
//! A transaction-scoped advisory lock serializes the count-and-insert decision
//! per conversation and author across API replicas. Idempotent replays are
//! resolved before the limit is evaluated, so a safe retry never consumes a
//! second allowance or becomes spuriously rate-limited.

use axum::{
    extract::{Path, Query, State},
    http::{
        header::{IF_MATCH, RETRY_AFTER},
        HeaderMap, HeaderValue, StatusCode,
    },
    response::{IntoResponse, Response},
    Extension, Json,
};
use chrono::{DateTime, SecondsFormat, Utc};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sqlx::{PgPool, Postgres, Transaction};
use uuid::Uuid;

use crate::{
    auth::role::Role, config::DomainReadSource, middleware::auth::AuthContext, state::ApiState,
};

use super::{
    nodes::ensure_node_activity_faden,
    query::{decode_cursor, encode_cursor},
};

const DEFAULT_MESSAGE_PAGE_SIZE: usize = 20;
const MAX_MESSAGE_PAGE_SIZE: usize = 50;
const MAX_MESSAGE_LENGTH: usize = 4_000;
const MESSAGE_RATE_LIMIT_PER_MINUTE: i64 = 10;

type ConversationRow = (
    String,
    Option<String>,
    Option<String>,
    Option<String>,
    String,
    String,
    DateTime<Utc>,
    DateTime<Utc>,
    Option<DateTime<Utc>>,
    Option<DateTime<Utc>>,
);

type MessageRow = (
    String,
    String,
    Option<String>,
    String,
    Option<String>,
    DateTime<Utc>,
    DateTime<Utc>,
    Option<DateTime<Utc>>,
);

#[derive(Debug, Clone, Serialize)]
pub struct ConversationView {
    pub id: String,
    pub conversation_type: String,
    pub lifecycle_state: String,
    pub node_id: Option<String>,
    pub node_id_snapshot: Option<String>,
    pub node_title_snapshot: Option<String>,
    pub visibility: String,
    pub created_at: String,
    pub updated_at: String,
    pub archived_at: Option<String>,
    pub deleted_at: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct MessageView {
    pub id: String,
    pub conversation_id: String,
    pub author_account_id: Option<String>,
    pub author_title: String,
    pub content: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    pub deleted_at: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct MessagePage {
    pub items: Vec<MessageView>,
    pub page: MessagePageMeta,
}

#[derive(Debug, Serialize)]
pub struct MessagePageMeta {
    pub limit: usize,
    pub next_cursor: Option<String>,
    pub has_more: bool,
}

#[derive(Debug)]
pub struct ConversationApiError {
    status: StatusCode,
    code: &'static str,
    message: &'static str,
    current: Option<Value>,
    retry_after_seconds: Option<u64>,
}

impl ConversationApiError {
    fn new(status: StatusCode, code: &'static str, message: &'static str) -> Self {
        Self {
            status,
            code,
            message,
            current: None,
            retry_after_seconds: None,
        }
    }

    fn current(mut self, message: &MessageView) -> Self {
        self.current = Some(json!(message));
        self
    }

    fn retry_after(mut self, seconds: u64) -> Self {
        self.retry_after_seconds = Some(seconds);
        self
    }
}

impl IntoResponse for ConversationApiError {
    fn into_response(self) -> Response {
        let retry_after_seconds = self.retry_after_seconds;
        let mut body = json!({
            "code": self.code,
            "message": self.message,
        });
        if let Some(current) = self.current {
            body["current"] = current;
        }
        let mut response = (self.status, Json(body)).into_response();
        if let Some(seconds) = retry_after_seconds {
            if let Ok(value) = HeaderValue::from_str(&seconds.to_string()) {
                response.headers_mut().insert(RETRY_AFTER, value);
            }
        }
        response
    }
}

fn timestamp(value: DateTime<Utc>) -> String {
    value.to_rfc3339_opts(SecondsFormat::AutoSi, true)
}

fn conversation_from_row(row: ConversationRow) -> ConversationView {
    let lifecycle_state = if row.8.is_some() {
        "archived"
    } else {
        "active"
    };
    ConversationView {
        id: row.0,
        conversation_type: row.4,
        lifecycle_state: lifecycle_state.to_string(),
        node_id: row.1,
        node_id_snapshot: row.2,
        node_title_snapshot: row.3,
        visibility: row.5,
        created_at: timestamp(row.6),
        updated_at: timestamp(row.7),
        archived_at: row.8.map(timestamp),
        deleted_at: row.9.map(timestamp),
    }
}

fn message_from_row(row: MessageRow) -> MessageView {
    MessageView {
        id: row.0,
        conversation_id: row.1,
        author_account_id: row.2,
        author_title: row.3,
        content: row.4,
        created_at: timestamp(row.5),
        updated_at: timestamp(row.6),
        deleted_at: row.7.map(timestamp),
    }
}

fn database_error(context: &'static str, error: sqlx::Error) -> ConversationApiError {
    tracing::error!(%error, context, "node conversation database operation failed");
    ConversationApiError::new(
        StatusCode::INTERNAL_SERVER_ERROR,
        "conversation_database_error",
        "the conversation store could not complete the request",
    )
}

fn require_pool(state: &ApiState) -> Result<&PgPool, ConversationApiError> {
    if state.config.domain_read_source != DomainReadSource::Postgres {
        return Err(ConversationApiError::new(
            StatusCode::SERVICE_UNAVAILABLE,
            "conversation_store_unavailable",
            "node conversations require the canonical PostgreSQL domain source",
        ));
    }
    state.db_pool.as_ref().ok_or_else(|| {
        ConversationApiError::new(
            StatusCode::SERVICE_UNAVAILABLE,
            "conversation_store_unavailable",
            "node conversations require an available PostgreSQL connection",
        )
    })
}

fn account_id(auth: &AuthContext) -> Result<&str, ConversationApiError> {
    auth.account_id.as_deref().ok_or_else(|| {
        ConversationApiError::new(
            StatusCode::UNAUTHORIZED,
            "authentication_required",
            "an authenticated account is required",
        )
    })
}

async fn project_message_participation_faden(
    state: &ApiState,
    auth: &AuthContext,
    node_id: Option<&str>,
    message_id: &str,
) {
    let Some(node_id) = node_id else {
        return;
    };
    if let Err((status, message)) =
        ensure_node_activity_faden(state, auth, node_id, "conversation_message", message_id).await
    {
        tracing::error!(
            event = "conversation.message_faden_projection.failed",
            node_id,
            message_id,
            %status,
            error = %message,
            "Message remains successful because it is already durable; the derived Faden is missing"
        );
    }
}

fn validate_content(content: &str) -> Result<String, ConversationApiError> {
    let content = content.trim();
    let length = content.chars().count();
    if length == 0 || length > MAX_MESSAGE_LENGTH {
        return Err(ConversationApiError::new(
            StatusCode::BAD_REQUEST,
            "invalid_message_content",
            "message content must contain between 1 and 4000 characters",
        ));
    }
    Ok(content.to_string())
}

fn validate_author_title(title: &str) -> Result<String, ConversationApiError> {
    let title = title.trim();
    let length = title.chars().count();
    if length == 0 || length > 200 {
        return Err(ConversationApiError::new(
            StatusCode::CONFLICT,
            "author_title_invalid",
            "the canonical account title must contain between 1 and 200 characters",
        ));
    }
    Ok(title.to_string())
}

fn parse_conversation_id(value: &str) -> Result<String, ConversationApiError> {
    Uuid::parse_str(value)
        .map(|id| id.to_string())
        .map_err(|_| {
            ConversationApiError::new(
                StatusCode::NOT_FOUND,
                "conversation_not_found",
                "the node conversation does not exist",
            )
        })
}

fn parse_message_id(value: &str) -> Result<String, ConversationApiError> {
    Uuid::parse_str(value)
        .map(|id| id.to_string())
        .map_err(|_| {
            ConversationApiError::new(
                StatusCode::NOT_FOUND,
                "message_not_found",
                "the message does not exist in this conversation",
            )
        })
}

fn parse_idempotency_key(headers: &HeaderMap) -> Result<String, ConversationApiError> {
    let raw = headers
        .get("Idempotency-Key")
        .and_then(|value| value.to_str().ok())
        .ok_or_else(|| {
            ConversationApiError::new(
                StatusCode::BAD_REQUEST,
                "idempotency_key_required",
                "Idempotency-Key must be a UUID",
            )
        })?;
    Uuid::parse_str(raw)
        .map(|value| value.to_string())
        .map_err(|_| {
            ConversationApiError::new(
                StatusCode::BAD_REQUEST,
                "invalid_idempotency_key",
                "Idempotency-Key must be a UUID",
            )
        })
}

fn check_precondition(
    headers: &HeaderMap,
    current: &MessageView,
) -> Result<(), ConversationApiError> {
    let expected = format!("\"{}\"", current.updated_at);
    match headers.get(IF_MATCH).and_then(|value| value.to_str().ok()) {
        Some(provided) if provided == expected => Ok(()),
        Some(_) => Err(ConversationApiError::new(
            StatusCode::PRECONDITION_FAILED,
            "message_version_conflict",
            "the message was changed by another request",
        )
        .current(current)),
        None => Err(ConversationApiError::new(
            StatusCode::PRECONDITION_REQUIRED,
            "message_version_required",
            "If-Match with the current message updated_at is required",
        )
        .current(current)),
    }
}

fn conversation_is_writable(conversation_type: &str, governance_source: Option<&str>) -> bool {
    match conversation_type {
        "node" => true,
        "governance_proposal" => governance_source == Some("canonical"),
        _ => false,
    }
}

async fn require_conversation_writable(
    tx: &mut Transaction<'_, Postgres>,
    conversation_id: &str,
) -> Result<(), ConversationApiError> {
    // Fast-path node conversations without touching the global governance cutover row.
    // The first read is only a classification hint; the row is locked and re-read below
    // before the write is authorized, so deletion or an unexpected type change cannot race.
    let observed_type: Option<String> = sqlx::query_scalar(
        "SELECT conversation_type FROM domain_conversations WHERE id = $1::uuid AND deleted_at IS NULL",
    )
    .bind(conversation_id)
    .fetch_optional(&mut **tx)
    .await
    .map_err(|error| database_error("classify conversation write target", error))?;

    let observed_type = observed_type.ok_or_else(|| {
        ConversationApiError::new(
            StatusCode::NOT_FOUND,
            "conversation_not_found",
            "the conversation does not exist",
        )
    })?;

    if observed_type == "node" {
        let locked_target: Option<(String, Option<String>, Option<DateTime<Utc>>)> =
            sqlx::query_as(
                "SELECT conversation_type, node_id, archived_at \
                 FROM domain_conversations \
                 WHERE id = $1::uuid AND deleted_at IS NULL FOR SHARE",
            )
            .bind(conversation_id)
            .fetch_optional(&mut **tx)
            .await
            .map_err(|error| database_error("lock node conversation write target", error))?;

        return match locked_target {
            Some((conversation_type, Some(_), None)) if conversation_type == "node" => Ok(()),
            Some((conversation_type, None, Some(_))) if conversation_type == "node" => {
                Err(ConversationApiError::new(
                    StatusCode::CONFLICT,
                    "conversation_archived",
                    "the node conversation is archived and read-only",
                ))
            }
            None => Err(ConversationApiError::new(
                StatusCode::NOT_FOUND,
                "conversation_not_found",
                "the conversation does not exist",
            )),
            Some(_) => Err(ConversationApiError::new(
                StatusCode::CONFLICT,
                "conversation_write_target_changed",
                "the conversation write target changed while the request was in flight",
            )),
        };
    }

    // Governance writes use one lock order everywhere: cutover singleton first,
    // conversation row second. This keeps the source stable through commit and
    // prevents a rollback to legacy while an authorized canonical write is in flight.
    let governance_source: Option<String> = sqlx::query_scalar(
        "SELECT governance_source FROM domain_conversation_cutover_state WHERE singleton FOR SHARE",
    )
    .fetch_optional(&mut **tx)
    .await
    .map_err(|error| database_error("lock conversation write cutover", error))?;

    let conversation_type: Option<String> = sqlx::query_scalar(
        "SELECT conversation_type FROM domain_conversations WHERE id = $1::uuid AND deleted_at IS NULL FOR SHARE",
    )
    .bind(conversation_id)
    .fetch_optional(&mut **tx)
    .await
    .map_err(|error| database_error("check conversation write target", error))?;

    let conversation_type = conversation_type.ok_or_else(|| {
        ConversationApiError::new(
            StatusCode::NOT_FOUND,
            "conversation_not_found",
            "the conversation does not exist",
        )
    })?;

    if conversation_type != observed_type {
        return Err(ConversationApiError::new(
            StatusCode::CONFLICT,
            "conversation_write_target_changed",
            "the conversation write target changed while the request was in flight",
        ));
    }

    if conversation_is_writable(&conversation_type, governance_source.as_deref()) {
        return Ok(());
    }

    Err(ConversationApiError::new(
        StatusCode::CONFLICT,
        "conversation_write_not_active",
        "governance conversation writes are not active before canonical cutover",
    ))
}

async fn require_conversation_tombstone_allowed(
    tx: &mut Transaction<'_, Postgres>,
    conversation_id: &str,
) -> Result<(), ConversationApiError> {
    let observed_type: Option<String> = sqlx::query_scalar(
        "SELECT conversation_type FROM domain_conversations WHERE id = $1::uuid AND deleted_at IS NULL",
    )
    .bind(conversation_id)
    .fetch_optional(&mut **tx)
    .await
    .map_err(|error| database_error("classify conversation tombstone target", error))?;

    let observed_type = observed_type.ok_or_else(|| {
        ConversationApiError::new(
            StatusCode::NOT_FOUND,
            "conversation_not_found",
            "the conversation does not exist",
        )
    })?;

    if observed_type == "node" {
        let locked_target: Option<(String, Option<String>, Option<DateTime<Utc>>)> =
            sqlx::query_as(
                "SELECT conversation_type, node_id, archived_at \
                 FROM domain_conversations \
                 WHERE id = $1::uuid AND deleted_at IS NULL FOR SHARE",
            )
            .bind(conversation_id)
            .fetch_optional(&mut **tx)
            .await
            .map_err(|error| database_error("lock node conversation tombstone target", error))?;

        return match locked_target {
            Some((conversation_type, Some(_), None)) if conversation_type == "node" => Ok(()),
            Some((conversation_type, None, Some(_))) if conversation_type == "node" => Ok(()),
            None => Err(ConversationApiError::new(
                StatusCode::NOT_FOUND,
                "conversation_not_found",
                "the conversation does not exist",
            )),
            Some(_) => Err(ConversationApiError::new(
                StatusCode::CONFLICT,
                "conversation_write_target_changed",
                "the conversation write target changed while the request was in flight",
            )),
        };
    }

    require_conversation_writable(tx, conversation_id).await
}

async fn load_message_for_update(
    tx: &mut Transaction<'_, Postgres>,
    conversation_id: &str,
    message_id: &str,
) -> Result<MessageView, ConversationApiError> {
    let row: Option<MessageRow> = sqlx::query_as(
        "SELECT id::text, conversation_id::text, author_account_id, author_title, content, \
                created_at, updated_at, deleted_at \
         FROM domain_messages \
         WHERE id = $1::uuid AND conversation_id = $2::uuid \
         FOR UPDATE",
    )
    .bind(message_id)
    .bind(conversation_id)
    .fetch_optional(&mut **tx)
    .await
    .map_err(|error| database_error("load message for update", error))?;

    row.map(message_from_row).ok_or_else(|| {
        ConversationApiError::new(
            StatusCode::NOT_FOUND,
            "message_not_found",
            "the message does not exist in this conversation",
        )
    })
}

fn require_author(auth: &AuthContext, message: &MessageView) -> Result<(), ConversationApiError> {
    if auth
        .account_id
        .as_deref()
        .is_some_and(|account_id| message.author_account_id.as_deref() == Some(account_id))
    {
        return Ok(());
    }
    Err(ConversationApiError::new(
        StatusCode::FORBIDDEN,
        "message_author_required",
        "only the message author may edit this message",
    ))
}

fn require_author_or_admin(
    auth: &AuthContext,
    message: &MessageView,
) -> Result<(), ConversationApiError> {
    if auth.role == Role::Admin
        || auth
            .account_id
            .as_deref()
            .is_some_and(|account_id| message.author_account_id.as_deref() == Some(account_id))
    {
        return Ok(());
    }
    Err(ConversationApiError::new(
        StatusCode::FORBIDDEN,
        "message_owner_required",
        "only the message author or an administrator may remove this message",
    ))
}

pub async fn get_node_conversation(
    State(state): State<ApiState>,
    Path(node_id): Path<String>,
) -> Result<Json<ConversationView>, ConversationApiError> {
    let pool = require_pool(&state)?;
    let row: Option<ConversationRow> = sqlx::query_as(
        "SELECT id::text, node_id, node_id_snapshot, node_title_snapshot, \
                conversation_type, visibility, created_at, updated_at, archived_at, deleted_at \
         FROM domain_conversations WHERE node_id = $1 AND deleted_at IS NULL",
    )
    .bind(node_id)
    .fetch_optional(pool)
    .await
    .map_err(|error| database_error("get node conversation", error))?;

    row.map(conversation_from_row).map(Json).ok_or_else(|| {
        ConversationApiError::new(
            StatusCode::NOT_FOUND,
            "conversation_not_found",
            "the node conversation does not exist",
        )
    })
}

pub async fn get_conversation(
    State(state): State<ApiState>,
    Path(id): Path<String>,
) -> Result<Json<ConversationView>, ConversationApiError> {
    let pool = require_pool(&state)?;
    let id = parse_conversation_id(&id)?;
    let row: Option<ConversationRow> = sqlx::query_as(
        "SELECT id::text, node_id, node_id_snapshot, node_title_snapshot, \
                conversation_type, visibility, created_at, updated_at, archived_at, deleted_at \
         FROM domain_conversations WHERE id = $1::uuid AND deleted_at IS NULL",
    )
    .bind(id)
    .fetch_optional(pool)
    .await
    .map_err(|error| database_error("get conversation", error))?;

    row.map(conversation_from_row).map(Json).ok_or_else(|| {
        ConversationApiError::new(
            StatusCode::NOT_FOUND,
            "conversation_not_found",
            "the node conversation does not exist",
        )
    })
}

#[derive(Debug, Deserialize)]
pub struct MessageListQuery {
    limit: Option<usize>,
    cursor: Option<String>,
}

pub async fn list_messages(
    State(state): State<ApiState>,
    Path(conversation_id): Path<String>,
    Query(query): Query<MessageListQuery>,
) -> Result<Json<MessagePage>, ConversationApiError> {
    let pool = require_pool(&state)?;
    let conversation_id = parse_conversation_id(&conversation_id)?;
    let exists: bool = sqlx::query_scalar(
        "SELECT EXISTS(SELECT 1 FROM domain_conversations \
         WHERE id = $1::uuid AND deleted_at IS NULL)",
    )
    .bind(&conversation_id)
    .fetch_one(pool)
    .await
    .map_err(|error| database_error("check conversation for message list", error))?;
    if !exists {
        return Err(ConversationApiError::new(
            StatusCode::NOT_FOUND,
            "conversation_not_found",
            "the node conversation does not exist",
        ));
    }

    let limit = query.limit.unwrap_or(DEFAULT_MESSAGE_PAGE_SIZE);
    if limit == 0 || limit > MAX_MESSAGE_PAGE_SIZE {
        return Err(ConversationApiError::new(
            StatusCode::BAD_REQUEST,
            "invalid_page_size",
            "limit must be between 1 and 50",
        ));
    }

    let cursor_id = match query.cursor.as_deref() {
        Some(token) if !token.is_empty() => {
            let decoded = decode_cursor(token).map_err(|_| {
                ConversationApiError::new(
                    StatusCode::BAD_REQUEST,
                    "invalid_cursor",
                    "cursor is malformed or does not belong to this conversation",
                )
            })?;
            let canonical = Uuid::parse_str(&decoded).map_err(|_| {
                ConversationApiError::new(
                    StatusCode::BAD_REQUEST,
                    "invalid_cursor",
                    "cursor is malformed or does not belong to this conversation",
                )
            })?;
            Some(canonical.to_string())
        }
        _ => None,
    };

    let rows: Vec<MessageRow> = if let Some(cursor_id) = cursor_id {
        let cursor_position: Option<(DateTime<Utc>, String)> = sqlx::query_as(
            "SELECT created_at, id::text FROM domain_messages \
             WHERE id = $1::uuid AND conversation_id = $2::uuid",
        )
        .bind(cursor_id)
        .bind(&conversation_id)
        .fetch_optional(pool)
        .await
        .map_err(|error| database_error("resolve message cursor", error))?;
        let (cursor_created_at, cursor_id) = cursor_position.ok_or_else(|| {
            ConversationApiError::new(
                StatusCode::BAD_REQUEST,
                "invalid_cursor",
                "cursor is malformed or does not belong to this conversation",
            )
        })?;
        sqlx::query_as(
            "SELECT id::text, conversation_id::text, author_account_id, author_title, content, \
                    created_at, updated_at, deleted_at \
             FROM domain_messages \
             WHERE conversation_id = $1::uuid \
               AND (created_at, id) < ($2, $3::uuid) \
             ORDER BY created_at DESC, id DESC LIMIT $4",
        )
        .bind(&conversation_id)
        .bind(cursor_created_at)
        .bind(cursor_id)
        .bind((limit + 1) as i64)
        .fetch_all(pool)
        .await
        .map_err(|error| database_error("list messages after cursor", error))?
    } else {
        sqlx::query_as(
            "SELECT id::text, conversation_id::text, author_account_id, author_title, content, \
                    created_at, updated_at, deleted_at \
             FROM domain_messages WHERE conversation_id = $1::uuid \
             ORDER BY created_at DESC, id DESC LIMIT $2",
        )
        .bind(&conversation_id)
        .bind((limit + 1) as i64)
        .fetch_all(pool)
        .await
        .map_err(|error| database_error("list messages", error))?
    };

    let has_more = rows.len() > limit;
    let mut items: Vec<MessageView> = rows.into_iter().take(limit).map(message_from_row).collect();
    items.reverse();
    // The page is returned oldest-first for the UI, so the first item is the
    // oldest row in this page and therefore the boundary for the next older page.
    let next_cursor = if has_more {
        items.first().map(|message| encode_cursor(&message.id))
    } else {
        None
    };

    Ok(Json(MessagePage {
        items,
        page: MessagePageMeta {
            limit,
            next_cursor,
            has_more,
        },
    }))
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CreateMessageRequest {
    content: String,
}

pub async fn create_message(
    State(state): State<ApiState>,
    Path(conversation_id): Path<String>,
    Extension(auth): Extension<AuthContext>,
    headers: HeaderMap,
    Json(request): Json<CreateMessageRequest>,
) -> Result<(StatusCode, Json<MessageView>), ConversationApiError> {
    let pool = require_pool(&state)?;
    let author_account_id = account_id(&auth)?.to_string();
    let idempotency_key = parse_idempotency_key(&headers)?;
    let content = validate_content(&request.content)?;
    let conversation_id = parse_conversation_id(&conversation_id)?;

    let mut tx = pool
        .begin()
        .await
        .map_err(|error| database_error("begin create message", error))?;
    require_conversation_writable(&mut tx, &conversation_id).await?;
    let node_id: Option<String> =
        sqlx::query_scalar("SELECT node_id FROM domain_conversations WHERE id = $1::uuid")
            .bind(&conversation_id)
            .fetch_one(&mut *tx)
            .await
            .map_err(|error| database_error("load conversation node for participation", error))?;

    let author_title: Option<String> =
        sqlx::query_scalar("SELECT title FROM domain_accounts WHERE id = $1")
            .bind(&author_account_id)
            .fetch_optional(&mut *tx)
            .await
            .map_err(|error| database_error("load message author", error))?;
    let author_title = author_title.ok_or_else(|| {
        ConversationApiError::new(
            StatusCode::CONFLICT,
            "author_account_not_persisted",
            "the authenticated account is not present in the canonical domain store",
        )
    })?;
    let author_title = validate_author_title(&author_title)?;

    let rate_limit_key =
        format!("node-conversation-message-rate:{conversation_id}:{author_account_id}");
    sqlx::query("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))")
        .bind(&rate_limit_key)
        .fetch_one(&mut *tx)
        .await
        .map_err(|error| database_error("lock message rate window", error))?;

    let existing: Option<MessageRow> = sqlx::query_as(
        "SELECT id::text, conversation_id::text, author_account_id, author_title, content,
                created_at, updated_at, deleted_at
         FROM domain_messages
         WHERE conversation_id = $1::uuid
           AND author_account_id = $2
           AND idempotency_key = $3::uuid",
    )
    .bind(&conversation_id)
    .bind(&author_account_id)
    .bind(&idempotency_key)
    .fetch_optional(&mut *tx)
    .await
    .map_err(|error| database_error("load idempotent message", error))?;

    if let Some(existing) = existing {
        let existing = message_from_row(existing);
        if existing.content.as_deref() != Some(content.as_str()) || existing.deleted_at.is_some() {
            return Err(ConversationApiError::new(
                StatusCode::CONFLICT,
                "idempotency_key_conflict",
                "the Idempotency-Key was already used for a different message",
            ));
        }
        let message_id = existing.id.clone();
        tx.commit()
            .await
            .map_err(|error| database_error("commit idempotent message replay", error))?;
        project_message_participation_faden(&state, &auth, node_id.as_deref(), &message_id).await;
        return Ok((StatusCode::OK, Json(existing)));
    }

    let recent_count: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM domain_messages
         WHERE conversation_id = $1::uuid
           AND author_account_id = $2
           AND created_at > NOW() - INTERVAL '1 minute'",
    )
    .bind(&conversation_id)
    .bind(&author_account_id)
    .fetch_one(&mut *tx)
    .await
    .map_err(|error| database_error("count recent messages", error))?;
    if recent_count >= MESSAGE_RATE_LIMIT_PER_MINUTE {
        return Err(ConversationApiError::new(
            StatusCode::TOO_MANY_REQUESTS,
            "message_rate_limited",
            "at most 10 new messages per minute are allowed in one conversation",
        )
        .retry_after(60));
    }

    let message_id = Uuid::new_v4().to_string();
    let row: MessageRow = sqlx::query_as(
        "INSERT INTO domain_messages (
             id, conversation_id, author_account_id, author_title, content, idempotency_key
         ) VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::uuid)
         RETURNING id::text, conversation_id::text, author_account_id, author_title, content,
                   created_at, updated_at, deleted_at",
    )
    .bind(message_id)
    .bind(&conversation_id)
    .bind(&author_account_id)
    .bind(&author_title)
    .bind(&content)
    .bind(&idempotency_key)
    .fetch_one(&mut *tx)
    .await
    .map_err(|error| database_error("insert message", error))?;
    let message = message_from_row(row);

    tx.commit()
        .await
        .map_err(|error| database_error("commit message create", error))?;
    project_message_participation_faden(&state, &auth, node_id.as_deref(), &message.id).await;
    Ok((StatusCode::CREATED, Json(message)))
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UpdateMessageRequest {
    content: String,
}

pub async fn update_message(
    State(state): State<ApiState>,
    Path((conversation_id, message_id)): Path<(String, String)>,
    Extension(auth): Extension<AuthContext>,
    headers: HeaderMap,
    Json(request): Json<UpdateMessageRequest>,
) -> Result<Json<MessageView>, ConversationApiError> {
    let pool = require_pool(&state)?;
    let content = validate_content(&request.content)?;
    let conversation_id = parse_conversation_id(&conversation_id)?;
    let message_id = parse_message_id(&message_id)?;
    let mut tx = pool
        .begin()
        .await
        .map_err(|error| database_error("begin message update", error))?;
    require_conversation_writable(&mut tx, &conversation_id).await?;
    let current = load_message_for_update(&mut tx, &conversation_id, &message_id).await?;
    require_author(&auth, &current)?;
    check_precondition(&headers, &current)?;
    if current.deleted_at.is_some() {
        return Err(ConversationApiError::new(
            StatusCode::CONFLICT,
            "message_deleted",
            "a tombstoned message cannot be edited",
        ));
    }

    let row: MessageRow = sqlx::query_as(
        "UPDATE domain_messages
         SET content = $1,
             updated_at = GREATEST(NOW(), updated_at + INTERVAL '1 microsecond')
         WHERE id = $2::uuid
         RETURNING id::text, conversation_id::text, author_account_id, author_title, content,
                   created_at, updated_at, deleted_at",
    )
    .bind(content)
    .bind(message_id)
    .fetch_one(&mut *tx)
    .await
    .map_err(|error| database_error("update message", error))?;
    tx.commit()
        .await
        .map_err(|error| database_error("commit message update", error))?;
    Ok(Json(message_from_row(row)))
}

pub async fn delete_message(
    State(state): State<ApiState>,
    Path((conversation_id, message_id)): Path<(String, String)>,
    Extension(auth): Extension<AuthContext>,
    headers: HeaderMap,
) -> Result<Json<MessageView>, ConversationApiError> {
    let pool = require_pool(&state)?;
    let conversation_id = parse_conversation_id(&conversation_id)?;
    let message_id = parse_message_id(&message_id)?;
    let mut tx = pool
        .begin()
        .await
        .map_err(|error| database_error("begin message tombstone", error))?;
    require_conversation_tombstone_allowed(&mut tx, &conversation_id).await?;
    let current = load_message_for_update(&mut tx, &conversation_id, &message_id).await?;
    require_author_or_admin(&auth, &current)?;
    check_precondition(&headers, &current)?;
    if current.deleted_at.is_some() {
        tx.commit()
            .await
            .map_err(|error| database_error("commit existing tombstone", error))?;
        return Ok(Json(current));
    }

    let row: MessageRow = sqlx::query_as(
        "UPDATE domain_messages
         SET content = NULL,
             deleted_at = GREATEST(NOW(), updated_at + INTERVAL '1 microsecond'),
             updated_at = GREATEST(NOW(), updated_at + INTERVAL '1 microsecond')
         WHERE id = $1::uuid
         RETURNING id::text, conversation_id::text, author_account_id, author_title, content,
                   created_at, updated_at, deleted_at",
    )
    .bind(message_id)
    .fetch_one(&mut *tx)
    .await
    .map_err(|error| database_error("tombstone message", error))?;
    tx.commit()
        .await
        .map_err(|error| database_error("commit message tombstone", error))?;
    Ok(Json(message_from_row(row)))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn content_validation_trims_and_bounds_plain_text() {
        assert_eq!(validate_content("  Hallo  ").unwrap(), "Hallo");
        assert_eq!(
            validate_content("   ").unwrap_err().code,
            "invalid_message_content"
        );
        assert_eq!(
            validate_content(&"x".repeat(MAX_MESSAGE_LENGTH + 1))
                .unwrap_err()
                .code,
            "invalid_message_content"
        );
    }

    #[test]
    fn conversation_write_cutover_keeps_governance_on_legacy_until_canonical() {
        assert!(conversation_is_writable("node", Some("legacy")));
        assert!(!conversation_is_writable(
            "governance_proposal",
            Some("legacy")
        ));
        assert!(conversation_is_writable(
            "governance_proposal",
            Some("canonical")
        ));
        assert!(!conversation_is_writable("governance_proposal", None));
        assert!(!conversation_is_writable("unknown", Some("canonical")));
    }

    #[test]
    fn conversation_view_exposes_active_node_lifecycle() {
        let created_at = DateTime::parse_from_rfc3339("2026-07-27T08:00:00Z")
            .unwrap()
            .with_timezone(&Utc);
        let view = conversation_from_row((
            Uuid::new_v4().to_string(),
            Some("active-node".to_string()),
            None,
            None,
            "node".to_string(),
            "public".to_string(),
            created_at,
            created_at,
            None,
            None,
        ));

        assert_eq!(view.lifecycle_state, "active");
        assert_eq!(view.node_id.as_deref(), Some("active-node"));
        assert_eq!(view.node_id_snapshot, None);
        assert_eq!(view.archived_at, None);
    }

    #[test]
    fn conversation_view_accepts_governance_target_without_node() {
        let created_at = DateTime::parse_from_rfc3339("2026-07-22T12:00:00Z")
            .unwrap()
            .with_timezone(&Utc);
        let updated_at = DateTime::parse_from_rfc3339("2026-07-22T12:00:01Z")
            .unwrap()
            .with_timezone(&Utc);
        let view = conversation_from_row((
            Uuid::new_v4().to_string(),
            None,
            None,
            None,
            "governance_proposal".to_string(),
            "public".to_string(),
            created_at,
            updated_at,
            None,
            None,
        ));

        assert_eq!(view.conversation_type, "governance_proposal");
        assert_eq!(view.lifecycle_state, "active");
        assert_eq!(view.node_id, None);
        assert_eq!(view.node_id_snapshot, None);
        assert_eq!(view.archived_at, None);
    }

    #[test]
    fn conversation_view_exposes_archived_node_context() {
        let created_at = DateTime::parse_from_rfc3339("2026-07-27T09:00:00Z")
            .unwrap()
            .with_timezone(&Utc);
        let archived_at = DateTime::parse_from_rfc3339("2026-07-27T09:05:00Z")
            .unwrap()
            .with_timezone(&Utc);
        let view = conversation_from_row((
            Uuid::new_v4().to_string(),
            None,
            Some("deleted-node".to_string()),
            Some("Gelöschter Knoten".to_string()),
            "node".to_string(),
            "public".to_string(),
            created_at,
            archived_at,
            Some(archived_at),
            None,
        ));

        assert_eq!(view.lifecycle_state, "archived");
        assert_eq!(view.node_id, None);
        assert_eq!(view.node_id_snapshot.as_deref(), Some("deleted-node"));
        assert_eq!(
            view.node_title_snapshot.as_deref(),
            Some("Gelöschter Knoten")
        );
        assert_eq!(view.archived_at.as_deref(), Some("2026-07-27T09:05:00Z"));
    }

    #[test]
    fn precondition_uses_the_public_updated_at_value() {
        let message = MessageView {
            id: Uuid::new_v4().to_string(),
            conversation_id: Uuid::new_v4().to_string(),
            author_account_id: Some("account-a".to_string()),
            author_title: "A".to_string(),
            content: Some("Hallo".to_string()),
            created_at: "2026-07-19T12:00:00Z".to_string(),
            updated_at: "2026-07-19T12:00:00.123456Z".to_string(),
            deleted_at: None,
        };
        let mut headers = HeaderMap::new();
        headers.insert(IF_MATCH, "\"2026-07-19T12:00:00.123456Z\"".parse().unwrap());
        assert!(check_precondition(&headers, &message).is_ok());
        headers.insert(IF_MATCH, "\"stale\"".parse().unwrap());
        assert_eq!(
            check_precondition(&headers, &message).unwrap_err().code,
            "message_version_conflict"
        );
    }
}

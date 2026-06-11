use super::query::{
    cursor_page, parse_cursor_params, parse_usize_param, validate_cursor_limit, ListResponse,
    MAX_PAGE_SIZE,
};
use crate::state::{ApiState, OrderedCache};
use crate::utils::edges_path;
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    Json,
};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tokio::{
    fs::File,
    io::{AsyncBufReadExt, BufReader},
};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Edge {
    pub id: String,
    pub source_id: String,
    pub source_type: Option<String>,
    pub target_id: String,
    pub target_type: Option<String>,
    #[serde(alias = "kind", alias = "edgeKind")]
    pub edge_kind: String,
    pub note: Option<String>,
    pub created_at: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
pub struct EdgeParticipantDetails {
    pub id: String,
    pub title: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub r#type: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
pub struct EdgeWithDetails {
    #[serde(flatten)]
    pub edge: Edge,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source_details: Option<EdgeParticipantDetails>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub target_details: Option<EdgeParticipantDetails>,
}

pub(crate) const DEFAULT_MAX_EDGES_CACHE: usize = 500_000;

pub(crate) fn max_edges_cache_limit() -> usize {
    match std::env::var("MAX_EDGES_CACHE") {
        Ok(val) => match val.parse::<usize>() {
            Ok(v) => v,
            Err(_) => {
                tracing::warn!(
                    value = %val,
                    "Invalid MAX_EDGES_CACHE, falling back to default 500,000"
                );
                DEFAULT_MAX_EDGES_CACHE
            }
        },
        Err(_) => DEFAULT_MAX_EDGES_CACHE,
    }
}

pub async fn load_edges() -> OrderedCache<Edge> {
    let start = std::time::Instant::now();
    let path = edges_path();
    let file = match File::open(&path).await {
        Ok(f) => f,
        Err(e) => {
            tracing::warn!(
                ?path,
                ?e,
                "Failed to open edges file, returning empty cache"
            );
            return OrderedCache::new();
        }
    };
    let mut lines = BufReader::new(file).lines();
    let mut edges = OrderedCache::new();
    let mut records_read = 0;
    let mut duplicates_count = 0;

    let max_edges = max_edges_cache_limit();

    while let Ok(Some(line)) = lines.next_line().await {
        if records_read >= max_edges {
            tracing::warn!(
                ?path,
                max_edges,
                "Edges cache limit reached, truncating load"
            );
            break;
        }
        records_read += 1;

        let edge: Edge = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(e) => {
                // Secure logging: avoid logging full payload, just length and error
                tracing::warn!(error = %e, line_len = line.len(), "failed to parse edge JSON");
                continue;
            }
        };
        if edges.insert(edge.id.clone(), edge) {
            duplicates_count += 1;
        }
    }

    let load_ms = start.elapsed().as_millis();
    tracing::info!(
        count = edges.len(),
        duplicates_count,
        load_ms,
        ?path,
        "Loaded edges into memory cache"
    );
    edges
}

pub async fn list_edges(
    State(state): State<ApiState>,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Json<ListResponse<Edge>>, StatusCode> {
    let src = params.get("source_id");
    let dst = params.get("target_id");
    let limit: usize = parse_usize_param(&params, "limit", 250)?.min(MAX_PAGE_SIZE);
    let (cursor_mode, after_id) = parse_cursor_params(&params)?;
    validate_cursor_limit(cursor_mode, limit)?;

    let matches = |edge: &&Edge| {
        if let Some(s) = src {
            if edge.source_id != *s {
                return false;
            }
        }
        if let Some(d) = dst {
            if edge.target_id != *d {
                return false;
            }
        }
        true
    };

    let cache = state.edges.read().await;

    if cursor_mode {
        // Cursor mode sorts by stable id ascending (see query::cursor_page),
        // independent of the file/insertion order used by the legacy path.
        let refs: Vec<&Edge> = cache.iter_in_order().filter(matches).collect();
        let page = cursor_page(
            refs,
            limit,
            after_id.as_deref(),
            |edge: &Edge| edge.id.as_str(),
            |edge: &Edge| edge.clone(),
        );
        Ok(Json(ListResponse::Cursor(page)))
    } else {
        let offset: usize = parse_usize_param(&params, "offset", 0)?;
        let out: Vec<Edge> = cache
            .iter_in_order()
            .filter(matches)
            .skip(offset)
            .take(limit)
            .cloned()
            .collect();
        Ok(Json(ListResponse::Legacy(out)))
    }
}

pub async fn get_edge(
    State(state): State<ApiState>,
    Path(id): Path<String>,
) -> Result<Json<EdgeWithDetails>, StatusCode> {
    let cache = state.edges.read().await;
    let edge = cache.get(&id).cloned().ok_or(StatusCode::NOT_FOUND)?;

    let mut source_details = None;
    let mut target_details = None;

    if let Some(src_type) = &edge.source_type {
        if src_type == "account" {
            let accounts = state.accounts.read().await;
            if let Some(account) = accounts.get(&edge.source_id) {
                source_details = Some(EdgeParticipantDetails {
                    id: account.public.id.clone(),
                    title: account.public.title.clone(),
                    r#type: Some(account.public.kind.clone()),
                });
            }
        } else if src_type == "node" {
            let nodes_cache = state.nodes.read().await;
            if let Some(node) = nodes_cache.get(&edge.source_id) {
                source_details = Some(EdgeParticipantDetails {
                    id: node.id.clone(),
                    title: node.title.clone(),
                    r#type: Some(node.kind.clone()),
                });
            }
        }
    }

    if let Some(tgt_type) = &edge.target_type {
        if tgt_type == "account" {
            let accounts = state.accounts.read().await;
            if let Some(account) = accounts.get(&edge.target_id) {
                target_details = Some(EdgeParticipantDetails {
                    id: account.public.id.clone(),
                    title: account.public.title.clone(),
                    r#type: Some(account.public.kind.clone()),
                });
            }
        } else if tgt_type == "node" {
            let nodes_cache = state.nodes.read().await;
            if let Some(node) = nodes_cache.get(&edge.target_id) {
                target_details = Some(EdgeParticipantDetails {
                    id: node.id.clone(),
                    title: node.title.clone(),
                    r#type: Some(node.kind.clone()),
                });
            }
        }
    }

    Ok(Json(EdgeWithDetails {
        edge,
        source_details,
        target_details,
    }))
}

/// Edge-create request contract — OPT-ARC-001 Phase E-C, PR-1 (Semantik-Lock).
///
/// This module locks the *accepted* shape and validation rules of a future
/// `POST /edges` create request **without** wiring a route, handler, extractor,
/// or persistence. The upcoming POST /edges PR consumes `CreateEdgeRequest` /
/// `CreateEdgeRequest::validate`; until then nothing outside the unit tests
/// references these items, so the whole not-yet-wired contract carries a single
/// `#[allow(dead_code)]` to keep the strict `-D warnings` lib build green.
///
/// Locked semantics (see
/// `docs/reports/domain-edge-create-semantics-preflight.md`):
/// - `created_at` is not accepted from clients — the server owns the timestamp.
/// - `expires_at` is not accepted — it must never be silently dropped, so it is
///   rejected via `deny_unknown_fields` rather than ignored.
/// - `payload` / `metadata` are not accepted (the edge contract forbids them).
/// - any other unknown field is rejected instead of silently ignored.
/// - `source_type` / `target_type` are optional but, when present, enum-checked.
/// - `edge_kind` is required and enum-checked.
/// - `source_id` / `target_id` are required and must be non-blank.
/// - `id` is optional but, when present, must be non-blank.
/// - `note` is optional but, when present, must be non-blank and ≤ 1000 chars.
///
/// `deny_unknown_fields` is applied **only** to `CreateEdgeRequest`, never to the
/// read-side `Edge` model, so existing JSONL/read semantics stay untouched.
#[allow(dead_code)] // used by upcoming POST /edges PR (OPT-ARC-001 Phase E-C)
mod edge_create {
    /// Allowed `edge_kind` values, mirroring `contracts/domain/edge.schema.json`.
    const EDGE_KIND_VALUES: [&str; 4] = ["delegation", "membership", "ownership", "reference"];

    /// Allowed `source_type` / `target_type` values, mirroring the edge contract.
    const EDGE_PARTICIPANT_TYPE_VALUES: [&str; 3] = ["role", "node", "account"];

    /// Maximum `note` length in characters, mirroring the edge contract
    /// (`maxLength: 1000`). JSON Schema counts characters, not bytes.
    const EDGE_NOTE_MAX_LEN: usize = 1000;

    /// Accepted shape of a future `POST /edges` create request.
    ///
    /// `created_at`, `expires_at`, `payload`, and `metadata` are intentionally
    /// absent; together with `deny_unknown_fields` they are rejected rather than
    /// silently dropped.
    #[derive(Debug, serde::Deserialize)]
    #[serde(deny_unknown_fields)]
    struct CreateEdgeRequest {
        id: Option<String>,
        source_id: String,
        target_id: String,
        edge_kind: String,
        source_type: Option<String>,
        target_type: Option<String>,
        note: Option<String>,
    }

    /// Validated form of a `CreateEdgeRequest`.
    ///
    /// Values are preserved verbatim — no lowercasing, no trimming into storage.
    /// Whitespace is only inspected to reject blank required/optional fields.
    #[derive(Debug, Clone, PartialEq, Eq)]
    struct ValidatedCreateEdge {
        id: Option<String>,
        source_id: String,
        target_id: String,
        edge_kind: String,
        source_type: Option<String>,
        target_type: Option<String>,
        note: Option<String>,
    }

    /// Why a `CreateEdgeRequest` failed validation.
    ///
    /// Intentionally HTTP-agnostic: this PR fixes the create contract and its
    /// validation only. Status-code mapping belongs to the POST /edges PR.
    #[derive(Debug, Clone, PartialEq, Eq)]
    enum EdgeCreateValidationError {
        /// A required field was missing/blank, or an optional field that, when
        /// present, must be non-blank (`id`, `note`) was blank.
        MissingOrEmptyField(&'static str),
        /// An enum-constrained field held a value outside its allowed set.
        InvalidEnumValue { field: &'static str, value: String },
        /// `note` exceeded the contract maximum of 1000 characters.
        NoteTooLong,
    }

    /// Reject a field that is empty or whitespace-only.
    fn require_non_blank(
        field: &'static str,
        value: &str,
    ) -> Result<(), EdgeCreateValidationError> {
        if value.trim().is_empty() {
            return Err(EdgeCreateValidationError::MissingOrEmptyField(field));
        }
        Ok(())
    }

    /// Reject a value outside its allowed enum set. Matching is exact: wrong
    /// casing fails (no case-folding, no normalization).
    fn require_enum(
        field: &'static str,
        value: &str,
        allowed: &[&str],
    ) -> Result<(), EdgeCreateValidationError> {
        if allowed.contains(&value) {
            Ok(())
        } else {
            Err(EdgeCreateValidationError::InvalidEnumValue {
                field,
                value: value.to_string(),
            })
        }
    }

    impl CreateEdgeRequest {
        /// Validate into a `ValidatedCreateEdge` without mutating values.
        ///
        /// Pure: no persistence, no UUID generation, no timestamping. Required
        /// string fields must be non-blank; `id`/`note`, when present, must be
        /// non-blank; `note` must be ≤ 1000 characters; `edge_kind` and any
        /// present `source_type`/`target_type` must be exact enum members.
        fn validate(self) -> Result<ValidatedCreateEdge, EdgeCreateValidationError> {
            require_non_blank("source_id", &self.source_id)?;
            require_non_blank("target_id", &self.target_id)?;
            require_non_blank("edge_kind", &self.edge_kind)?;

            if let Some(id) = &self.id {
                require_non_blank("id", id)?;
            }
            if let Some(note) = &self.note {
                require_non_blank("note", note)?;
                if note.chars().count() > EDGE_NOTE_MAX_LEN {
                    return Err(EdgeCreateValidationError::NoteTooLong);
                }
            }

            require_enum("edge_kind", &self.edge_kind, &EDGE_KIND_VALUES)?;
            if let Some(source_type) = &self.source_type {
                require_enum("source_type", source_type, &EDGE_PARTICIPANT_TYPE_VALUES)?;
            }
            if let Some(target_type) = &self.target_type {
                require_enum("target_type", target_type, &EDGE_PARTICIPANT_TYPE_VALUES)?;
            }

            Ok(ValidatedCreateEdge {
                id: self.id,
                source_id: self.source_id,
                target_id: self.target_id,
                edge_kind: self.edge_kind,
                source_type: self.source_type,
                target_type: self.target_type,
                note: self.note,
            })
        }
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        fn valid_request() -> CreateEdgeRequest {
            CreateEdgeRequest {
                id: None,
                source_id: "n1".to_string(),
                target_id: "n2".to_string(),
                edge_kind: "reference".to_string(),
                source_type: None,
                target_type: None,
                note: None,
            }
        }

        // ---- positive: accepted shapes ----

        #[test]
        fn edge_create_request_accepts_minimal_payload() {
            let json = r#"{"source_id":"n1","target_id":"n2","edge_kind":"reference"}"#;
            let req = serde_json::from_str::<CreateEdgeRequest>(json)
                .expect("minimal request must deserialize");
            assert_eq!(
                req.validate(),
                Ok(ValidatedCreateEdge {
                    id: None,
                    source_id: "n1".to_string(),
                    target_id: "n2".to_string(),
                    edge_kind: "reference".to_string(),
                    source_type: None,
                    target_type: None,
                    note: None,
                })
            );
        }

        #[test]
        fn edge_create_request_accepts_full_payload() {
            let json = r#"{
                "id": "e1",
                "source_id": "n1",
                "target_id": "n2",
                "edge_kind": "ownership",
                "source_type": "node",
                "target_type": "account",
                "note": "a note"
            }"#;
            let req = serde_json::from_str::<CreateEdgeRequest>(json)
                .expect("full request must deserialize");
            assert_eq!(
                req.validate(),
                Ok(ValidatedCreateEdge {
                    id: Some("e1".to_string()),
                    source_id: "n1".to_string(),
                    target_id: "n2".to_string(),
                    edge_kind: "ownership".to_string(),
                    source_type: Some("node".to_string()),
                    target_type: Some("account".to_string()),
                    note: Some("a note".to_string()),
                })
            );
        }

        #[test]
        fn edge_create_request_validates_edge_kind_enum() {
            for kind in EDGE_KIND_VALUES {
                let mut req = valid_request();
                req.edge_kind = kind.to_string();
                assert!(
                    req.validate().is_ok(),
                    "edge_kind `{kind}` must be accepted"
                );
            }

            let mut req = valid_request();
            req.edge_kind = "frobnicate".to_string();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::InvalidEnumValue {
                    field: "edge_kind",
                    value: "frobnicate".to_string(),
                })
            );
        }

        #[test]
        fn edge_create_request_accepts_optional_source_and_target_type() {
            for ty in EDGE_PARTICIPANT_TYPE_VALUES {
                let mut req = valid_request();
                req.source_type = Some(ty.to_string());
                req.target_type = Some(ty.to_string());
                let validated = req.validate().expect("participant type must be accepted");
                assert_eq!(validated.source_type.as_deref(), Some(ty));
                assert_eq!(validated.target_type.as_deref(), Some(ty));
            }
        }

        // ---- negative: deny_unknown_fields / silent-drop protection ----

        #[test]
        fn edge_create_request_rejects_expires_at_to_prevent_silent_drop() {
            let json = r#"{"source_id":"n1","target_id":"n2","edge_kind":"reference","expires_at":"2026-01-01T00:00:00Z"}"#;
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(json).is_err(),
                "expires_at must be rejected, never silently dropped"
            );
        }

        #[test]
        fn edge_create_request_rejects_created_at_because_server_owns_timestamp() {
            let json = r#"{"source_id":"n1","target_id":"n2","edge_kind":"reference","created_at":"2026-01-01T00:00:00Z"}"#;
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(json).is_err(),
                "created_at must be rejected; the server owns the create timestamp"
            );
        }

        #[test]
        fn edge_create_request_rejects_payload_and_metadata() {
            let payload =
                r#"{"source_id":"n1","target_id":"n2","edge_kind":"reference","payload":{}}"#;
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(payload).is_err(),
                "payload must be rejected"
            );
            let metadata =
                r#"{"source_id":"n1","target_id":"n2","edge_kind":"reference","metadata":{}}"#;
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(metadata).is_err(),
                "metadata must be rejected"
            );
        }

        #[test]
        fn edge_create_request_rejects_unknown_fields() {
            let json = r#"{"source_id":"n1","target_id":"n2","edge_kind":"reference","wat":true}"#;
            assert!(
                serde_json::from_str::<CreateEdgeRequest>(json).is_err(),
                "unknown fields must be rejected, never silently ignored"
            );
        }

        // ---- negative: required fields missing (serde level) ----

        #[test]
        fn edge_create_request_rejects_missing_source_id() {
            let json = r#"{"target_id":"n2","edge_kind":"reference"}"#;
            assert!(serde_json::from_str::<CreateEdgeRequest>(json).is_err());
        }

        #[test]
        fn edge_create_request_rejects_missing_target_id() {
            let json = r#"{"source_id":"n1","edge_kind":"reference"}"#;
            assert!(serde_json::from_str::<CreateEdgeRequest>(json).is_err());
        }

        #[test]
        fn edge_create_request_rejects_missing_edge_kind() {
            let json = r#"{"source_id":"n1","target_id":"n2"}"#;
            assert!(serde_json::from_str::<CreateEdgeRequest>(json).is_err());
        }

        // ---- negative: blank required / optional fields (validate level) ----

        #[test]
        fn edge_create_request_rejects_blank_source_id() {
            let mut req = valid_request();
            req.source_id = "   ".to_string();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::MissingOrEmptyField("source_id"))
            );
        }

        #[test]
        fn edge_create_request_rejects_blank_target_id() {
            let mut req = valid_request();
            req.target_id = String::new();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::MissingOrEmptyField("target_id"))
            );
        }

        #[test]
        fn edge_create_request_rejects_blank_edge_kind() {
            let mut req = valid_request();
            req.edge_kind = "  ".to_string();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::MissingOrEmptyField("edge_kind"))
            );
        }

        #[test]
        fn edge_create_request_rejects_blank_id_when_present() {
            let mut req = valid_request();
            req.id = Some("   ".to_string());
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::MissingOrEmptyField("id"))
            );
        }

        #[test]
        fn edge_create_request_rejects_blank_note_when_present() {
            let mut req = valid_request();
            req.note = Some("   ".to_string());
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::MissingOrEmptyField("note"))
            );
        }

        // ---- negative: invalid enums (validate level) ----

        #[test]
        fn edge_create_request_rejects_invalid_source_type() {
            let mut req = valid_request();
            req.source_type = Some("group".to_string());
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::InvalidEnumValue {
                    field: "source_type",
                    value: "group".to_string(),
                })
            );
        }

        #[test]
        fn edge_create_request_rejects_invalid_target_type() {
            let mut req = valid_request();
            req.target_type = Some("group".to_string());
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::InvalidEnumValue {
                    field: "target_type",
                    value: "group".to_string(),
                })
            );
        }

        #[test]
        fn edge_create_request_rejects_uppercase_enum_values() {
            // Wrong casing must fail — no automatic lowercasing / normalization.
            let mut req = valid_request();
            req.edge_kind = "Reference".to_string();
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::InvalidEnumValue {
                    field: "edge_kind",
                    value: "Reference".to_string(),
                })
            );

            let mut req = valid_request();
            req.source_type = Some("Node".to_string());
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::InvalidEnumValue {
                    field: "source_type",
                    value: "Node".to_string(),
                })
            );

            let mut req = valid_request();
            req.target_type = Some("Account".to_string());
            assert_eq!(
                req.validate(),
                Err(EdgeCreateValidationError::InvalidEnumValue {
                    field: "target_type",
                    value: "Account".to_string(),
                })
            );
        }

        // ---- negative / boundary: note length ----

        #[test]
        fn edge_create_request_accepts_note_at_max_length() {
            let mut req = valid_request();
            req.note = Some("a".repeat(EDGE_NOTE_MAX_LEN));
            let validated = req
                .validate()
                .expect("note of exactly the max length must be accepted");
            assert_eq!(
                validated.note.map(|n| n.chars().count()),
                Some(EDGE_NOTE_MAX_LEN)
            );
        }

        #[test]
        fn edge_create_request_rejects_note_over_max_length() {
            let mut req = valid_request();
            req.note = Some("a".repeat(EDGE_NOTE_MAX_LEN + 1));
            assert_eq!(req.validate(), Err(EdgeCreateValidationError::NoteTooLong));
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{max_edges_cache_limit, DEFAULT_MAX_EDGES_CACHE};
    use crate::test_helpers::EnvGuard;
    use serial_test::serial;

    #[test]
    #[serial]
    fn max_edges_cache_invalid_falls_back_to_default() {
        let _env = EnvGuard::set("MAX_EDGES_CACHE", "not-a-number");

        assert_eq!(max_edges_cache_limit(), DEFAULT_MAX_EDGES_CACHE);
    }

    #[test]
    #[serial]
    fn max_edges_cache_absent_returns_default() {
        let _env = EnvGuard::unset("MAX_EDGES_CACHE");

        assert_eq!(max_edges_cache_limit(), DEFAULT_MAX_EDGES_CACHE);
    }
}

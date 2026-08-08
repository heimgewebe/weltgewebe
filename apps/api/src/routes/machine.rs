use axum::{
    extract::{Path, State},
    http::{header::IF_MATCH, HeaderMap, StatusCode},
    middleware::from_fn,
    response::{IntoResponse, Response},
    routing::{get, post},
    Extension, Json, Router,
};
use serde_json::{json, Map, Value};
use uuid::Uuid;

use crate::{
    middleware::{auth::AuthContext, authz::require_authenticated},
    state::ApiState,
    telemetry::BuildInfo,
};

use super::{
    auth::SESSION_COOKIE_NAME,
    collective_write_guard::{
        create_node_serialized, delete_node_serialized, patch_node_serialized,
        replace_node_serialized,
    },
    nodes::UpdateNode,
};

pub const MACHINE_PROTOCOL: &str = "weltgewebe-machine/1";

#[derive(Clone, Copy, Debug)]
struct ApiOperation {
    method: &'static str,
    path: &'static str,
    auth: &'static str,
    write_safety: &'static str,
}

const fn op(
    method: &'static str,
    path: &'static str,
    auth: &'static str,
    write_safety: &'static str,
) -> ApiOperation {
    ApiOperation {
        method,
        path,
        auth,
        write_safety,
    }
}

const API_OPERATIONS: &[ApiOperation] = &[
    op("GET", "/search", "public", "read"),
    op("GET", "/nodes/search", "public", "read"),
    op("GET", "/nodes", "public", "read"),
    op("POST", "/nodes", "session", "operation_id_optional"),
    op("GET", "/nodes/{id}", "public", "read"),
    op("PATCH", "/nodes/{id}", "session", "if_match_required"),
    op("PUT", "/nodes/{id}", "session", "if_match_required"),
    op("DELETE", "/nodes/{id}", "session", "if_match_required"),
    op("GET", "/direct-conversations", "session", "read"),
    op("POST", "/direct-conversations", "session", "handler_specific"),
    op("GET", "/notifications/preferences", "session", "read"),
    op("PUT", "/notifications/preferences", "session", "handler_specific"),
    op("GET", "/push/config", "session", "read"),
    op("POST", "/push/subscriptions", "session", "handler_specific"),
    op("DELETE", "/push/subscriptions", "session", "handler_specific"),
    op("POST", "/direct-conversations/{id}/read", "session", "handler_specific"),
    op("PUT", "/direct-conversations/{id}/block", "session", "handler_specific"),
    op("DELETE", "/direct-conversations/{id}/block", "session", "handler_specific"),
    op("GET", "/nodes/{id}/conversation", "public", "read"),
    op("GET", "/conversations/{id}", "public", "read"),
    op("GET", "/conversations/{id}/messages", "public", "read"),
    op("POST", "/conversations/{id}/messages", "session", "handler_specific"),
    op(
        "PATCH",
        "/conversations/{conversation_id}/messages/{message_id}",
        "session",
        "handler_specific",
    ),
    op(
        "DELETE",
        "/conversations/{conversation_id}/messages/{message_id}",
        "session",
        "handler_specific",
    ),
    op("GET", "/edges", "public", "read"),
    op("GET", "/edges/{id}", "public", "read"),
    op("GET", "/ortswebereien", "public", "read"),
    op("GET", "/ortswebereien/{id}", "public", "read"),
    op("GET", "/webgemeindezentren", "public", "read"),
    op("GET", "/webgemeindezentren/{id}", "public", "read"),
    op("GET", "/accounts", "admin", "read"),
    op("POST", "/accounts", "admin", "handler_specific"),
    op("GET", "/accounts/me/profile", "session", "read"),
    op("PATCH", "/accounts/me/profile", "session", "handler_specific"),
    op("GET", "/accounts/{id}", "public", "read"),
    op("GET", "/proposals", "public", "read"),
    op("POST", "/proposals", "handler_enforced", "handler_specific"),
    op("GET", "/proposals/{id}", "public", "read"),
    op("POST", "/proposals/{id}/veto", "write_role", "handler_specific"),
    op("PUT", "/proposals/{id}/vote", "write_role", "handler_specific"),
    op("GET", "/proposals/{id}/messages", "public", "read"),
    op("POST", "/proposals/{id}/messages", "session", "handler_specific"),
    op("POST", "/accounts/me/exit", "handler_enforced", "handler_specific"),
    op("GET", "/auth/dev/accounts", "development_only", "read"),
    op("POST", "/auth/dev/login", "development_only", "handler_specific"),
    op("POST", "/auth/magic-link/request", "public", "handler_specific"),
    op("GET", "/auth/magic-link/consume", "public", "read"),
    op("POST", "/auth/magic-link/consume", "public", "handler_specific"),
    op("POST", "/auth/logout", "session", "handler_specific"),
    op("POST", "/auth/logout-all", "session", "handler_specific"),
    op("GET", "/auth/devices", "session", "read"),
    op("DELETE", "/auth/devices/{id}", "session", "handler_specific"),
    op("GET", "/auth/me", "session", "read"),
    op("PUT", "/auth/me/email", "session", "handler_specific"),
    op("GET", "/auth/session", "session", "read"),
    op("POST", "/auth/session/refresh", "session", "handler_specific"),
    op(
        "POST",
        "/auth/step-up/magic-link/request",
        "session",
        "handler_specific",
    ),
    op(
        "POST",
        "/auth/step-up/magic-link/consume",
        "session",
        "handler_specific",
    ),
    op(
        "POST",
        "/auth/passkeys/register/options",
        "session",
        "handler_specific",
    ),
    op(
        "POST",
        "/auth/passkeys/register/verify",
        "session",
        "handler_specific",
    ),
    op(
        "POST",
        "/auth/passkeys/auth/options",
        "public",
        "handler_specific",
    ),
    op(
        "POST",
        "/auth/passkeys/auth/verify",
        "public",
        "handler_specific",
    ),
    op(
        "POST",
        "/machine/v1/nodes",
        "session",
        "operation_id_required",
    ),
    op(
        "PATCH",
        "/machine/v1/nodes/{id}",
        "session",
        "if_match_required",
    ),
    op(
        "PUT",
        "/machine/v1/nodes/{id}",
        "session",
        "if_match_required",
    ),
    op(
        "DELETE",
        "/machine/v1/nodes/{id}",
        "session",
        "if_match_required",
    ),
];

const ROOT_OPERATIONS: &[ApiOperation] = &[
    op("GET", "/.well-known/weltgewebe", "public", "read"),
    op("GET", "/openapi.json", "public", "read"),
    op("GET", "/schemas/domain/{name}.json", "public", "read"),
    op(
        "GET",
        "/schemas/federation/v1/{name}.json",
        "public",
        "read",
    ),
    op("GET", "/health/live", "public", "read"),
    op("GET", "/health/ready", "public", "read"),
    op("GET", "/version", "public", "read"),
    op("GET", "/metrics", "public", "read"),
    op("GET", "/federation/v1/cell", "public", "read"),
    op(
        "POST",
        "/federation/v1/events",
        "federation_signature",
        "signed_event",
    ),
    op("GET", "/federation/v1/objects", "public", "read"),
];

pub fn api_routes() -> Router<ApiState> {
    Router::new()
        .route(
            "/machine/v1/nodes",
            post(create_machine_node).route_layer(from_fn(require_authenticated)),
        )
        .route(
            "/machine/v1/nodes/{id}",
            axum::routing::patch(patch_machine_node)
                .put(replace_machine_node)
                .delete(delete_machine_node)
                .route_layer(from_fn(require_authenticated)),
        )
}

pub fn root_routes() -> Router<ApiState> {
    Router::new()
        .route("/.well-known/weltgewebe", get(machine_descriptor))
        .route("/openapi.json", get(openapi))
        .route("/schemas/domain/{name}.json", get(domain_schema))
        .route(
            "/schemas/federation/v1/{name}.json",
            get(federation_schema),
        )
}

fn machine_problem(status: StatusCode, code: &'static str, message: &'static str) -> Response {
    (
        status,
        Json(json!({
            "code": code,
            "message": message,
            "contract": MACHINE_PROTOCOL,
        })),
    )
        .into_response()
}

fn canonical_operation_id(payload: &Value) -> bool {
    let Some(raw) = payload.get("operation_id").and_then(Value::as_str) else {
        return false;
    };
    Uuid::parse_str(raw)
        .ok()
        .is_some_and(|parsed| parsed.to_string() == raw)
}

fn require_if_match(headers: &HeaderMap) -> Result<(), Response> {
    if headers.get(IF_MATCH).is_some() {
        return Ok(());
    }
    Err(machine_problem(
        StatusCode::PRECONDITION_REQUIRED,
        "machine_if_match_required",
        "Machine node mutations require If-Match with the current node ETag.",
    ))
}

async fn create_machine_node(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
    Json(payload): Json<Value>,
) -> Response {
    if !canonical_operation_id(&payload) {
        return machine_problem(
            StatusCode::UNPROCESSABLE_ENTITY,
            "machine_operation_id_required",
            "Machine node creation requires a canonical lowercase UUID operation_id.",
        );
    }
    create_node_serialized(State(state), Extension(auth), Json(payload)).await
}

async fn patch_machine_node(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
    Path(id): Path<String>,
    headers: HeaderMap,
    Json(payload): Json<UpdateNode>,
) -> Response {
    if let Err(response) = require_if_match(&headers) {
        return response;
    }
    patch_node_serialized(
        State(state),
        Extension(auth),
        Path(id),
        headers,
        Json(payload),
    )
    .await
}

async fn replace_machine_node(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
    Path(id): Path<String>,
    headers: HeaderMap,
    Json(payload): Json<Value>,
) -> Response {
    if let Err(response) = require_if_match(&headers) {
        return response;
    }
    replace_node_serialized(
        State(state),
        Extension(auth),
        Path(id),
        headers,
        Json(payload),
    )
    .await
}

async fn delete_machine_node(
    State(state): State<ApiState>,
    Extension(auth): Extension<AuthContext>,
    Path(id): Path<String>,
    headers: HeaderMap,
) -> Response {
    if let Err(response) = require_if_match(&headers) {
        return response;
    }
    delete_node_serialized(State(state), Extension(auth), Path(id), headers).await
}

async fn machine_descriptor() -> Json<Value> {
    let build = BuildInfo::collect();
    Json(json!({
        "protocol": MACHINE_PROTOCOL,
        "schema_version": 1,
        "build": {
            "version": build.version,
            "commit": build.commit,
            "build_timestamp": build.build_timestamp,
        },
        "api": {
            "canonical_base": "/api",
            "openapi": "/openapi.json",
            "operation_count": API_OPERATIONS.len(),
            "compatibility_root_alias": true,
        },
        "capabilities": [
            "api-discovery",
            "openapi-3.1",
            "json-schema-2020-12",
            "safe-node-writes-v1",
            "conditional-node-mutations",
            "idempotent-node-create",
            "federation-v1"
        ],
        "schemas": {
            "domain": {
                "account": "/schemas/domain/account.json",
                "conversation": "/schemas/domain/conversation.json",
                "edge": "/schemas/domain/edge.json",
                "message": "/schemas/domain/message.json",
                "node": "/schemas/domain/node.json",
                "role": "/schemas/domain/role.json"
            },
            "federation": {
                "cell_descriptor": "/schemas/federation/v1/cell-descriptor.json",
                "event": "/schemas/federation/v1/event.json"
            }
        },
        "write_profiles": {
            "safe-node-writes-v1": {
                "create": {
                    "method": "POST",
                    "path": "/api/machine/v1/nodes",
                    "operation_id": "required canonical lowercase UUID"
                },
                "mutate": {
                    "methods": ["PATCH", "PUT", "DELETE"],
                    "path": "/api/machine/v1/nodes/{id}",
                    "precondition": "If-Match required"
                },
                "authentication": "gewebe_session cookie",
                "csrf": "same-origin session write rules apply",
                "audit": "existing node mutation audit and actor binding apply"
            }
        },
        "federation": {
            "protocol": "wg-federation/1",
            "descriptor": "/federation/v1/cell",
            "events": "/federation/v1/events",
            "objects": "/federation/v1/objects"
        }
    }))
}

async fn openapi() -> Json<Value> {
    Json(openapi_document())
}

fn openapi_document() -> Value {
    let mut paths = Map::new();
    for operation in ROOT_OPERATIONS {
        insert_openapi_operation(&mut paths, operation.path.to_string(), operation);
    }
    for operation in API_OPERATIONS {
        insert_openapi_operation(&mut paths, format!("/api{}", operation.path), operation);
    }

    json!({
        "openapi": "3.1.0",
        "info": {
            "title": "Weltgewebe Machine Surface",
            "version": "1",
            "description": "Machine-discoverable operation surface. Core domain payload schemas are served as canonical JSON Schemas; handler-specific request semantics remain explicitly marked instead of being guessed."
        },
        "servers": [{ "url": "/" }],
        "paths": paths,
        "components": {
            "securitySchemes": {
                "sessionCookie": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": SESSION_COOKIE_NAME
                }
            },
            "schemas": {
                "Account": { "$ref": "/schemas/domain/account.json" },
                "Conversation": { "$ref": "/schemas/domain/conversation.json" },
                "Edge": { "$ref": "/schemas/domain/edge.json" },
                "Message": { "$ref": "/schemas/domain/message.json" },
                "Node": { "$ref": "/schemas/domain/node.json" },
                "Role": { "$ref": "/schemas/domain/role.json" },
                "FederationCell": { "$ref": "/schemas/federation/v1/cell-descriptor.json" },
                "FederationEvent": { "$ref": "/schemas/federation/v1/event.json" }
            }
        },
        "x-weltgewebe-contract": MACHINE_PROTOCOL,
        "x-weltgewebe-completeness": "operation-surface-plus-core-schemas"
    })
}

fn insert_openapi_operation(paths: &mut Map<String, Value>, path: String, operation: &ApiOperation) {
    let entry = paths.entry(path.clone()).or_insert_with(|| json!({}));
    let object = entry
        .as_object_mut()
        .expect("OpenAPI path entries are always objects");
    object.insert(
        operation.method.to_ascii_lowercase(),
        openapi_operation(&path, operation),
    );
}

fn openapi_operation(path: &str, operation: &ApiOperation) -> Value {
    let mut value = json!({
        "operationId": operation_id(operation.method, path),
        "summary": format!("{} {}", operation.method, path),
        "responses": {
            "2XX": { "description": "Successful response" },
            "4XX": { "description": "Client, authorization or precondition failure" },
            "5XX": { "description": "Server or dependency failure" }
        },
        "x-weltgewebe-auth": operation.auth,
        "x-weltgewebe-write-safety": operation.write_safety
    });

    let object = value
        .as_object_mut()
        .expect("OpenAPI operation is always an object");

    let parameters = path_parameters(path);
    if !parameters.is_empty() {
        object.insert("parameters".to_string(), Value::Array(parameters));
    }

    if matches!(operation.auth, "session" | "admin" | "write_role" | "handler_enforced") {
        object.insert("security".to_string(), json!([{ "sessionCookie": [] }]));
    }

    if !matches!(operation.method, "GET" | "DELETE") {
        let schema = if operation.write_safety == "operation_id_required" {
            json!({
                "type": "object",
                "required": ["operation_id"],
                "properties": {
                    "operation_id": { "type": "string", "format": "uuid" }
                },
                "additionalProperties": true
            })
        } else {
            json!({ "type": "object", "additionalProperties": true })
        };
        object.insert(
            "requestBody".to_string(),
            json!({
                "required": true,
                "content": {
                    "application/json": { "schema": schema }
                }
            }),
        );
    }

    value
}

fn operation_id(method: &str, path: &str) -> String {
    let normalized: String = path
        .chars()
        .map(|character| {
            if character.is_ascii_alphanumeric() {
                character
            } else {
                '_'
            }
        })
        .collect();
    format!(
        "{}_{}",
        method.to_ascii_lowercase(),
        normalized.trim_matches('_')
    )
}

fn path_parameters(path: &str) -> Vec<Value> {
    path.split('/')
        .filter_map(|segment| segment.strip_prefix('{')?.strip_suffix('}'))
        .map(|name| {
            json!({
                "name": name,
                "in": "path",
                "required": true,
                "schema": { "type": "string" }
            })
        })
        .collect()
}

async fn domain_schema(Path(name): Path<String>) -> Response {
    schema_response(domain_schema_text(&name))
}

async fn federation_schema(Path(name): Path<String>) -> Response {
    schema_response(federation_schema_text(&name))
}

fn schema_response(schema: Option<&'static str>) -> Response {
    let Some(schema) = schema else {
        return StatusCode::NOT_FOUND.into_response();
    };
    match serde_json::from_str::<Value>(schema) {
        Ok(value) => Json(value).into_response(),
        Err(error) => {
            tracing::error!(%error, "embedded machine schema is invalid JSON");
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

fn domain_schema_text(name: &str) -> Option<&'static str> {
    match name {
        "account" => Some(include_str!("../../../../contracts/domain/account.schema.json")),
        "conversation" => Some(include_str!(
            "../../../../contracts/domain/conversation.schema.json"
        )),
        "edge" => Some(include_str!("../../../../contracts/domain/edge.schema.json")),
        "message" => Some(include_str!("../../../../contracts/domain/message.schema.json")),
        "node" => Some(include_str!("../../../../contracts/domain/node.schema.json")),
        "role" => Some(include_str!("../../../../contracts/domain/role.schema.json")),
        _ => None,
    }
}

fn federation_schema_text(name: &str) -> Option<&'static str> {
    match name {
        "cell-descriptor" => Some(include_str!(
            "../../../../contracts/federation/v1/cell-descriptor.schema.json"
        )),
        "event" => Some(include_str!(
            "../../../../contracts/federation/v1/event.schema.json"
        )),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use std::collections::BTreeSet;

    use super::{openapi_document, API_OPERATIONS, MACHINE_PROTOCOL};

    #[test]
    fn operation_manifest_has_no_duplicates() {
        let operations: BTreeSet<_> = API_OPERATIONS
            .iter()
            .map(|operation| (operation.method, operation.path))
            .collect();
        assert_eq!(operations.len(), API_OPERATIONS.len());
    }

    #[test]
    fn machine_writes_have_explicit_retry_or_concurrency_safety() {
        let machine_writes: Vec<_> = API_OPERATIONS
            .iter()
            .filter(|operation| operation.path.starts_with("/machine/"))
            .collect();
        assert!(!machine_writes.is_empty());
        for operation in machine_writes {
            assert!(matches!(
                operation.write_safety,
                "operation_id_required" | "if_match_required"
            ));
        }
    }

    #[test]
    fn openapi_contains_every_manifest_operation() {
        let document = openapi_document();
        let paths = document["paths"]
            .as_object()
            .expect("OpenAPI paths must be an object");
        for operation in API_OPERATIONS {
            let path = format!("/api{}", operation.path);
            let item = paths.get(&path).expect("manifest path missing from OpenAPI");
            assert!(
                item.get(operation.method.to_ascii_lowercase()).is_some(),
                "{} {} missing from OpenAPI",
                operation.method,
                path
            );
        }
        assert_eq!(document["x-weltgewebe-contract"], MACHINE_PROTOCOL);
    }
}

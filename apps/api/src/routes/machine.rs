use axum::{
    extract::{Path, State},
    http::{header::IF_MATCH, HeaderMap, StatusCode},
    middleware::from_fn,
    response::{IntoResponse, Response},
    routing::{get, post},
    Extension, Json, Router,
};
use serde_json::{json, Value};
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
const OPENAPI_TEXT: &str = include_str!("../../../../contracts/machine/openapi.json");

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
            "operation_count": openapi_operation_count(),
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
                "authentication": SESSION_COOKIE_NAME,
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

async fn openapi() -> Response {
    match openapi_document() {
        Ok(document) => Json(document).into_response(),
        Err(error) => {
            tracing::error!(%error, "embedded OpenAPI machine contract is invalid JSON");
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

fn openapi_document() -> Result<Value, serde_json::Error> {
    serde_json::from_str(OPENAPI_TEXT)
}

fn openapi_operation_count() -> usize {
    openapi_document()
        .ok()
        .and_then(|document| document.get("paths").and_then(Value::as_object).cloned())
        .map(|paths| {
            paths
                .values()
                .filter_map(Value::as_object)
                .map(|path| {
                    path.keys()
                        .filter(|key| {
                            matches!(
                                key.as_str(),
                                "get" | "post" | "put" | "patch" | "delete" | "options"
                            )
                        })
                        .count()
                })
                .sum()
        })
        .unwrap_or(0)
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
        "account" => Some(include_str!(
            "../../../../contracts/domain/account.schema.json"
        )),
        "conversation" => Some(include_str!(
            "../../../../contracts/domain/conversation.schema.json"
        )),
        "edge" => Some(include_str!(
            "../../../../contracts/domain/edge.schema.json"
        )),
        "message" => Some(include_str!(
            "../../../../contracts/domain/message.schema.json"
        )),
        "node" => Some(include_str!(
            "../../../../contracts/domain/node.schema.json"
        )),
        "role" => Some(include_str!(
            "../../../../contracts/domain/role.schema.json"
        )),
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

    use serde_json::Value;

    use super::{openapi_document, MACHINE_PROTOCOL};

    fn route_paths(source: &str) -> BTreeSet<String> {
        let mut paths = BTreeSet::new();
        let mut rest = source;

        while let Some(index) = rest.find(".route(") {
            rest = &rest[index + ".route(".len()..];
            let trimmed = rest.trim_start();
            let Some(quoted) = trimmed.strip_prefix('"') else {
                continue;
            };
            let Some(end) = quoted.find('"') else {
                break;
            };
            paths.insert(quoted[..end].to_string());
            rest = &quoted[end + 1..];
        }

        paths
    }

    fn openapi_paths(document: &Value) -> BTreeSet<String> {
        document["paths"]
            .as_object()
            .expect("OpenAPI paths must be an object")
            .keys()
            .cloned()
            .collect()
    }

    #[test]
    fn openapi_contract_is_valid_and_versioned() {
        let document = openapi_document().expect("OpenAPI contract must parse");
        assert_eq!(document["openapi"], "3.1.0");
        assert_eq!(document["x-weltgewebe-contract"], MACHINE_PROTOCOL);
    }

    #[test]
    fn router_paths_are_covered_by_openapi_contract() {
        let document = openapi_document().expect("OpenAPI contract must parse");
        let documented = openapi_paths(&document);

        for path in route_paths(include_str!("mod.rs"))
            .into_iter()
            .filter(|path| !path.contains("/testing/"))
        {
            assert!(
                documented.contains(&format!("/api{path}")),
                "API router path {path} is missing from OpenAPI"
            );
        }

        for path in route_paths(include_str!("machine.rs")) {
            let documented_path = if path.starts_with("/machine/") {
                format!("/api{path}")
            } else {
                path.clone()
            };
            assert!(
                documented.contains(&documented_path),
                "machine router path {path} is missing from OpenAPI"
            );
        }
    }

    #[test]
    fn machine_mutations_have_explicit_safety_contracts() {
        let document = openapi_document().expect("OpenAPI contract must parse");
        let create = &document["paths"]["/api/machine/v1/nodes"]["post"];
        assert_eq!(
            create["x-weltgewebe-write-safety"],
            "operation_id_required"
        );

        let node = &document["paths"]["/api/machine/v1/nodes/{id}"];
        for method in ["patch", "put", "delete"] {
            assert_eq!(
                node[method]["x-weltgewebe-write-safety"],
                "if_match_required"
            );
            let parameters = node[method]["parameters"]
                .as_array()
                .expect("machine mutation must describe If-Match");
            assert!(parameters.iter().any(|parameter| {
                parameter["name"] == "If-Match"
                    && parameter["in"] == "header"
                    && parameter["required"] == true
            }));
        }
    }
}

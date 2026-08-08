use axum::{
    extract::{Path, State},
    http::{header::IF_MATCH, HeaderMap, StatusCode},
    middleware::from_fn,
    response::{IntoResponse, Response},
    routing::{get, post},
    Extension, Json, Router,
};
use serde::Deserialize;
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
const OPERATION_MANIFEST: &str = include_str!("../../../../contracts/machine/operations.json");

#[derive(Clone, Debug, Deserialize)]
struct MachineManifest {
    schema_version: u8,
    contract: String,
    operations: Vec<ApiOperation>,
}

#[derive(Clone, Debug, Deserialize)]
struct ApiOperation {
    method: String,
    path: String,
    auth: String,
    write_safety: String,
}

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

fn machine_manifest() -> Result<MachineManifest, serde_json::Error> {
    serde_json::from_str(OPERATION_MANIFEST)
}

async fn machine_descriptor() -> Response {
    let manifest = match machine_manifest() {
        Ok(manifest) => manifest,
        Err(error) => {
            tracing::error!(%error, "embedded machine operation manifest is invalid JSON");
            return StatusCode::INTERNAL_SERVER_ERROR.into_response();
        }
    };
    let build = BuildInfo::collect();

    Json(json!({
        "protocol": manifest.contract,
        "schema_version": manifest.schema_version,
        "build": {
            "version": build.version,
            "commit": build.commit,
            "build_timestamp": build.build_timestamp,
        },
        "api": {
            "canonical_base": "/api",
            "openapi": "/openapi.json",
            "operation_count": manifest.operations.len(),
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
    .into_response()
}

async fn openapi() -> Response {
    match openapi_document() {
        Ok(document) => Json(document).into_response(),
        Err(error) => {
            tracing::error!(%error, "failed to build OpenAPI machine contract");
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

fn openapi_document() -> Result<Value, serde_json::Error> {
    let manifest = machine_manifest()?;
    let mut paths = Map::new();

    for operation in &manifest.operations {
        insert_openapi_operation(&mut paths, operation);
    }

    Ok(json!({
        "openapi": "3.1.0",
        "info": {
            "title": "Weltgewebe Machine Surface",
            "version": manifest.schema_version.to_string(),
            "description": "Machine-discoverable operation surface. Handler-specific payloads are explicitly marked instead of guessed; canonical JSON Schemas are linked separately."
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
                "FederationCell": {
                    "$ref": "/schemas/federation/v1/cell-descriptor.json"
                },
                "FederationEvent": {
                    "$ref": "/schemas/federation/v1/event.json"
                }
            }
        },
        "x-weltgewebe-contract": manifest.contract,
        "x-weltgewebe-completeness": "operation-surface-plus-core-schemas",
        "x-weltgewebe-discovery": "/.well-known/weltgewebe"
    }))
}

fn insert_openapi_operation(paths: &mut Map<String, Value>, operation: &ApiOperation) {
    let item = paths
        .entry(operation.path.clone())
        .or_insert_with(|| json!({}));
    let item = item
        .as_object_mut()
        .expect("OpenAPI path entries are always objects");
    item.insert(
        operation.method.to_ascii_lowercase(),
        openapi_operation(operation),
    );
}

fn openapi_operation(operation: &ApiOperation) -> Value {
    let mut value = json!({
        "operationId": operation_id(&operation.method, &operation.path),
        "summary": format!("{} {}", operation.method, operation.path),
        "responses": {
            "200": { "description": "Successful response" },
            "default": { "description": "Error response" }
        },
        "x-weltgewebe-auth": operation.auth.as_str(),
        "x-weltgewebe-write-safety": operation.write_safety.as_str()
    });
    let object = value
        .as_object_mut()
        .expect("OpenAPI operation is always an object");

    let mut parameters = path_parameters(&operation.path);
    if operation.write_safety == "if_match_required" {
        parameters.push(json!({
            "name": "If-Match",
            "in": "header",
            "required": true,
            "description": "Current node ETag. Prevents lost updates.",
            "schema": { "type": "string" }
        }));
    }
    if !parameters.is_empty() {
        object.insert("parameters".to_string(), Value::Array(parameters));
    }

    if matches!(
        operation.auth.as_str(),
        "session" | "admin" | "write_role" | "handler_enforced"
    ) {
        object.insert("security".to_string(), json!([{ "sessionCookie": [] }]));
    }

    if operation.method == "POST" && operation.path == "/api/machine/v1/nodes" {
        object.insert(
            "requestBody".to_string(),
            json!({
                "required": true,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["operation_id"],
                            "properties": {
                                "operation_id": {
                                    "type": "string",
                                    "format": "uuid"
                                }
                            },
                            "additionalProperties": true
                        }
                    }
                }
            }),
        );
    }

    if operation.method == "POST" && operation.path == "/federation/v1/events" {
        object.insert(
            "requestBody".to_string(),
            json!({
                "required": true,
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "/schemas/federation/v1/event.json"
                        }
                    }
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

    use super::{machine_manifest, openapi_document, MACHINE_PROTOCOL};

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
    fn operation_manifest_is_versioned_and_unique() {
        let manifest = machine_manifest().expect("machine manifest must parse");
        assert_eq!(manifest.schema_version, 1);
        assert_eq!(manifest.contract, MACHINE_PROTOCOL);

        let unique: BTreeSet<_> = manifest
            .operations
            .iter()
            .map(|operation| (&operation.method, &operation.path))
            .collect();
        assert_eq!(unique.len(), manifest.operations.len());
    }

    #[test]
    fn router_paths_are_covered_by_operation_manifest() {
        let manifest = machine_manifest().expect("machine manifest must parse");
        let documented: BTreeSet<_> = manifest
            .operations
            .iter()
            .map(|operation| operation.path.as_str())
            .collect();

        for path in route_paths(include_str!("mod.rs"))
            .into_iter()
            .filter(|path| !path.contains("/testing/"))
        {
            assert!(
                documented.contains(format!("/api{path}").as_str()),
                "API router path {path} is missing from machine manifest"
            );
        }

        for path in route_paths(include_str!("machine.rs")) {
            let documented_path = if path.starts_with("/machine/") {
                format!("/api{path}")
            } else {
                path.clone()
            };
            assert!(
                documented.contains(documented_path.as_str()),
                "machine router path {path} is missing from machine manifest"
            );
        }
    }

    #[test]
    fn openapi_contains_every_manifest_operation() {
        let manifest = machine_manifest().expect("machine manifest must parse");
        let document = openapi_document().expect("OpenAPI contract must build");
        let paths = document["paths"]
            .as_object()
            .expect("OpenAPI paths must be an object");

        for operation in &manifest.operations {
            let item = paths
                .get(&operation.path)
                .expect("manifest path missing from OpenAPI");
            let method = operation.method.to_ascii_lowercase();
            assert!(
                item.get(&method).is_some(),
                "{} {} is missing from OpenAPI",
                operation.method,
                operation.path
            );
        }
    }

    #[test]
    fn machine_mutations_have_explicit_safety_contracts() {
        let document = openapi_document().expect("OpenAPI contract must build");
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

    #[test]
    fn openapi_contract_is_versioned() {
        let document = openapi_document().expect("OpenAPI contract must build");
        assert_eq!(document["openapi"], "3.1.0");
        assert_eq!(document["x-weltgewebe-contract"], MACHINE_PROTOCOL);
    }

    #[test]
    fn openapi_paths_are_nonempty() {
        let document = openapi_document().expect("OpenAPI contract must build");
        assert!(!openapi_paths(&document).is_empty());
    }
}

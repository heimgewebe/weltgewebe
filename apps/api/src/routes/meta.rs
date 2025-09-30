use axum::{routing::get, Json, Router};
use serde_json::{json, Value};

use crate::state::ApiState;
use crate::telemetry::BuildInfo;

pub fn meta_routes() -> Router<ApiState> {
    Router::new().route("/version", get(version))
}

async fn version() -> Json<Value> {
    let info = BuildInfo::collect();
    Json(json!({
        "version": info.version,
        "commit": info.commit,
        "build_timestamp": info.build_timestamp,
    }))
}

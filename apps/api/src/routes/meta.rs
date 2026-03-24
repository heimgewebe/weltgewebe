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

#[cfg(test)]
mod tests {
    use crate::telemetry::BuildInfo;

    #[test]
    fn build_info_version_is_not_empty() {
        let info = BuildInfo::collect();
        assert!(!info.version.is_empty(), "version must not be empty");
    }

    #[test]
    fn build_info_version_matches_cargo_pkg() {
        let info = BuildInfo::collect();
        assert_eq!(info.version, env!("CARGO_PKG_VERSION"));
    }
}

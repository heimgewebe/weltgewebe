use axum::{
    http::{HeaderMap, HeaderName, HeaderValue},
    response::IntoResponse,
    routing::get,
    Json, Router,
};
use serde_json::json;

use crate::state::ApiState;
use crate::telemetry::BuildInfo;

pub const API_BUILD_HEADER: &str = "x-weltgewebe-api-build";

pub fn meta_routes() -> Router<ApiState> {
    Router::new().route("/version", get(version))
}

async fn version() -> impl IntoResponse {
    let info = BuildInfo::collect();
    let mut headers = HeaderMap::new();
    headers.insert(
        HeaderName::from_static(API_BUILD_HEADER),
        HeaderValue::from_static(info.commit),
    );

    (
        headers,
        Json(json!({
            "version": info.version,
            "commit": info.commit,
            "build_timestamp": info.build_timestamp,
        })),
    )
}

#[cfg(test)]
mod tests {
    use axum::response::IntoResponse;

    use super::{version, API_BUILD_HEADER};
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

    #[tokio::test]
    async fn version_response_exposes_the_binary_commit_header() {
        let response = version().await.into_response();
        assert_eq!(
            response
                .headers()
                .get(API_BUILD_HEADER)
                .and_then(|value| value.to_str().ok()),
            Some(BuildInfo::collect().commit),
        );
    }
}

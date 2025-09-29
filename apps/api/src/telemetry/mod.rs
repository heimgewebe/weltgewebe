use std::sync::Arc;

use axum::{
    extract::State, http::header, http::HeaderValue, http::StatusCode, response::IntoResponse,
};
use prometheus::{Encoder, IntCounterVec, IntGaugeVec, Opts, Registry, TextEncoder};

use crate::state::ApiState;

#[derive(Clone, Debug)]
pub struct BuildInfo {
    pub version: &'static str,
    pub commit: &'static str,
    pub build_timestamp: &'static str,
}

impl BuildInfo {
    pub fn collect() -> Self {
        Self {
            version: env!("CARGO_PKG_VERSION"),
            commit: option_env!("GIT_COMMIT_SHA").unwrap_or("unknown"),
            build_timestamp: option_env!("BUILD_TIMESTAMP").unwrap_or("unknown"),
        }
    }
}

#[derive(Clone)]
pub struct Metrics {
    inner: Arc<MetricsInner>,
}

struct MetricsInner {
    registry: Registry,
    pub http_requests_total: IntCounterVec,
}

impl Metrics {
    pub fn try_new(build_info: BuildInfo) -> Result<Self, prometheus::Error> {
        let http_opts = Opts::new("http_requests_total", "Total number of HTTP requests");
        let http_requests_total = IntCounterVec::new(http_opts, &["method", "path"])?;

        let build_opts = Opts::new("build_info", "Build information for the API");
        let build_info_metric = IntGaugeVec::new(build_opts, &["version", "commit", "built_at"])?;

        let registry = Registry::new();
        registry.register(Box::new(http_requests_total.clone()))?;
        registry.register(Box::new(build_info_metric.clone()))?;

        build_info_metric
            .with_label_values(&[
                build_info.version,
                build_info.commit,
                build_info.build_timestamp,
            ])
            .set(1);

        Ok(Self {
            inner: Arc::new(MetricsInner {
                registry,
                http_requests_total,
            }),
        })
    }

    pub fn http_requests_total(&self) -> &IntCounterVec {
        &self.inner.http_requests_total
    }

    pub fn render(&self) -> Result<Vec<u8>, prometheus::Error> {
        let metric_families = self.inner.registry.gather();
        let encoder = TextEncoder::new();
        let mut buffer = Vec::new();
        encoder.encode(&metric_families, &mut buffer)?;
        Ok(buffer)
    }
}

pub async fn metrics_handler(State(state): State<ApiState>) -> impl IntoResponse {
    let content_type = HeaderValue::from_static("text/plain; version=0.0.4; charset=utf-8");
    match state.metrics.render() {
        Ok(body) => (StatusCode::OK, [(header::CONTENT_TYPE, content_type)], body).into_response(),
        Err(error) => {
            tracing::error!(error = %error, "failed to encode metrics");
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

use std::{
    future::Future,
    pin::Pin,
    sync::Arc,
    task::{Context, Poll},
};

pub mod health;

use axum::{
    extract::{MatchedPath, State},
    http::{header, HeaderValue, Request, StatusCode},
    response::{IntoResponse, Response},
};
use prometheus::{Encoder, IntCounterVec, IntGauge, IntGaugeVec, Opts, Registry, TextEncoder};
use tower::{Layer, Service};

use crate::state::ApiState;

const UNMATCHED_ROUTE_LABEL: &str = "<unmatched>";

fn metrics_path_label<B>(request: &Request<B>) -> String {
    request
        .extensions()
        .get::<MatchedPath>()
        .map(|path| path.as_str().to_owned())
        .unwrap_or_else(|| UNMATCHED_ROUTE_LABEL.to_owned())
}

#[cfg(debug_assertions)]
const GIT_COMMIT_SHA: &str = match option_env!("GIT_COMMIT_SHA") {
    Some(value) => value,
    None => "unknown",
};
#[cfg(not(debug_assertions))]
const GIT_COMMIT_SHA: &str = env!(
    "GIT_COMMIT_SHA",
    "release builds require GIT_COMMIT_SHA to bind the API binary to its source commit"
);

#[cfg(debug_assertions)]
const BUILD_TIMESTAMP: &str = match option_env!("BUILD_TIMESTAMP") {
    Some(value) => value,
    None => "unknown",
};
#[cfg(not(debug_assertions))]
const BUILD_TIMESTAMP: &str = env!(
    "BUILD_TIMESTAMP",
    "release builds require BUILD_TIMESTAMP to bind the API binary to a deterministic Git timestamp"
);

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
            commit: GIT_COMMIT_SHA,
            build_timestamp: BUILD_TIMESTAMP,
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
    pub nodes_cache_count: IntGauge,
    pub edges_cache_count: IntGauge,
    pub search_projection_jobs_total: IntCounterVec,
}

impl Metrics {
    pub fn try_new(build_info: BuildInfo) -> Result<Self, prometheus::Error> {
        let http_opts = Opts::new("http_requests_total", "Total number of HTTP requests");
        let http_requests_total = IntCounterVec::new(http_opts, &["method", "path", "status"])?;

        let build_opts = Opts::new("build_info", "Build information for the API");
        let build_info_metric =
            IntGaugeVec::new(build_opts, &["version", "commit", "build_timestamp"])?;

        let nodes_count_opts = Opts::new("nodes_cache_count", "Number of nodes in memory cache");
        let nodes_cache_count = IntGauge::with_opts(nodes_count_opts)?;

        let edges_count_opts = Opts::new("edges_cache_count", "Number of edges in memory cache");
        let edges_cache_count = IntGauge::with_opts(edges_count_opts)?;

        let search_projection_jobs_total = IntCounterVec::new(
            Opts::new(
                "search_projection_jobs_total",
                "Projection worker outcomes without node, text, query, or vector labels",
            ),
            &["outcome"],
        )?;

        let registry = Registry::new();
        registry.register(Box::new(http_requests_total.clone()))?;
        registry.register(Box::new(build_info_metric.clone()))?;
        registry.register(Box::new(nodes_cache_count.clone()))?;
        registry.register(Box::new(edges_cache_count.clone()))?;
        registry.register(Box::new(search_projection_jobs_total.clone()))?;

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
                nodes_cache_count,
                edges_cache_count,
                search_projection_jobs_total,
            }),
        })
    }

    pub fn set_nodes_cache_count(&self, count: i64) {
        self.inner.nodes_cache_count.set(count);
    }

    pub fn set_edges_cache_count(&self, count: i64) {
        self.inner.edges_cache_count.set(count);
    }

    pub fn http_requests_total(&self) -> &IntCounterVec {
        &self.inner.http_requests_total
    }

    /// Outcome labels are from a fixed enum; callers must never attach node
    /// identifiers, source text, queries, provider responses, or vectors.
    pub fn search_projection_outcome(&self, outcome: &str) {
        self.inner
            .search_projection_jobs_total
            .with_label_values(&[outcome])
            .inc();
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

#[derive(Clone)]
pub struct MetricsLayer {
    metrics: Metrics,
}

impl MetricsLayer {
    pub fn new(metrics: Metrics) -> Self {
        Self { metrics }
    }
}

impl<S> Layer<S> for MetricsLayer {
    type Service = MetricsService<S>;

    fn layer(&self, inner: S) -> Self::Service {
        MetricsService {
            inner,
            metrics: self.metrics.clone(),
        }
    }
}

#[derive(Clone)]
pub struct MetricsService<S> {
    inner: S,
    metrics: Metrics,
}

impl<S, B> Service<Request<B>> for MetricsService<S>
where
    S: Service<Request<B>>,
    S::Future: Send + 'static,
    S::Response: IntoResponse,
    B: Send + 'static,
{
    type Response = Response;
    type Error = S::Error;
    type Future = Pin<Box<dyn Future<Output = Result<Self::Response, Self::Error>> + Send>>;

    fn poll_ready(&mut self, cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        self.inner.poll_ready(cx)
    }

    fn call(&mut self, request: Request<B>) -> Self::Future {
        let method = request.method().as_str().to_owned();
        // Never fall back to the raw URI path here. Unmatched paths are attacker-controlled;
        // using them as Prometheus label values creates one time series per unique 404 path
        // and allows unbounded label-cardinality growth. Known routes still use Axum's
        // normalized route template from `MatchedPath`.
        let path = metrics_path_label(&request);
        let metrics = self.metrics.clone();
        let future = self.inner.call(request);

        Box::pin(async move {
            match future.await {
                Ok(response) => {
                    let response: Response = response.into_response();
                    let status = response.status().as_u16().to_string();
                    metrics
                        .http_requests_total()
                        .with_label_values(&[method.as_str(), path.as_str(), status.as_str()])
                        .inc();
                    Ok(response)
                }
                Err(error) => Err(error),
            }
        })
    }
}

#[cfg(test)]
mod tests {
    use super::{metrics_path_label, UNMATCHED_ROUTE_LABEL};
    use axum::http::Request;

    #[test]
    fn unmatched_paths_collapse_to_one_low_cardinality_metrics_label() {
        let first = Request::builder()
            .uri("/attacker-controlled/a")
            .body(())
            .expect("request");
        let second = Request::builder()
            .uri("/attacker-controlled/b")
            .body(())
            .expect("request");

        assert_eq!(metrics_path_label(&first), UNMATCHED_ROUTE_LABEL);
        assert_eq!(metrics_path_label(&second), UNMATCHED_ROUTE_LABEL);
        assert_eq!(metrics_path_label(&first), metrics_path_label(&second));
    }
}

use std::{
    future::Future,
    pin::Pin,
    sync::Arc,
    task::{Context, Poll},
    time::Duration,
};

pub mod health;

use axum::{
    extract::{MatchedPath, State},
    http::{header, HeaderValue, Request, StatusCode},
    response::{IntoResponse, Response},
};
use prometheus::{
    Encoder, Histogram, HistogramOpts, IntCounter, IntCounterVec, IntGauge, IntGaugeVec, Opts,
    Registry, TextEncoder,
};
use tower::{Layer, Service};

use crate::state::ApiState;

const UNMATCHED_ROUTE_LABEL: &str = "<unmatched>";

/// Fixed set of search service request outcomes. The label set is bounded by
/// the type system rather than by a runtime string match, so an exhaustive
/// match at the call site is the only place new outcomes can be introduced.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SearchRequestOutcome {
    Hybrid,
    LexicalFallback,
    ProviderContractError,
    Unavailable,
    InvalidRequest,
    Internal,
}

impl SearchRequestOutcome {
    fn as_label(self) -> &'static str {
        match self {
            Self::Hybrid => "hybrid",
            Self::LexicalFallback => "lexical_fallback",
            Self::ProviderContractError => "provider_contract_error",
            Self::Unavailable => "unavailable",
            Self::InvalidRequest => "invalid_request",
            Self::Internal => "internal",
        }
    }
}

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
    pub search_requests_total: IntCounterVec,
    pub search_candidate_set_overflow_total: IntCounter,
    pub search_request_duration_seconds: Histogram,
    pub search_repository_duration_seconds: Histogram,
    pub search_provider_duration_seconds: Histogram,
    pub search_authorized_candidates: Histogram,
    pub search_lexical_candidates: Histogram,
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

        let search_requests_total = IntCounterVec::new(
            Opts::new(
                "search_requests_total",
                "Search service outcomes using only fixed, non-user-controlled labels",
            ),
            &["outcome"],
        )?;

        let search_candidate_set_overflow_total = IntCounter::new(
            "search_candidate_set_overflow_total",
            "Search requests rejected because the authorized candidate transfer exceeded its hard bound",
        )?;

        let duration_buckets = vec![
            0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
        ];
        // MAX_AUTHORIZED_CANDIDATES (search/repository.rs) hard-bounds this at
        // 1000; the repository layer rejects any request before an over-bound
        // count would ever reach this histogram, so 1000.0 is the true max
        // bucket and no sentinel bucket above it is meaningful.
        let candidate_buckets = vec![
            1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 750.0, 1000.0,
        ];
        let lexical_candidate_buckets = vec![0.0, 1.0, 2.0, 5.0, 10.0];
        let search_request_duration_seconds = Histogram::with_opts(
            HistogramOpts::new(
                "search_request_duration_seconds",
                "End-to-end search service duration without query or identity labels",
            )
            .buckets(duration_buckets.clone()),
        )?;
        let search_repository_duration_seconds = Histogram::with_opts(
            HistogramOpts::new(
                "search_repository_duration_seconds",
                "PostgreSQL search candidate retrieval duration without query or identity labels",
            )
            .buckets(duration_buckets.clone()),
        )?;
        let search_provider_duration_seconds = Histogram::with_opts(
            HistogramOpts::new(
                "search_provider_duration_seconds",
                "Search query embedding provider duration without query, model, or vector labels",
            )
            .buckets(duration_buckets),
        )?;
        let search_authorized_candidates = Histogram::with_opts(
            HistogramOpts::new(
                "search_authorized_candidates",
                "Authorized search candidates transferred to the API per request",
            )
            .buckets(candidate_buckets.clone()),
        )?;
        let search_lexical_candidates = Histogram::with_opts(
            HistogramOpts::new(
                "search_lexical_candidates",
                "Lexical candidates in the authoritative top-ten prefix per search request",
            )
            .buckets(lexical_candidate_buckets),
        )?;

        let registry = Registry::new();
        registry.register(Box::new(http_requests_total.clone()))?;
        registry.register(Box::new(build_info_metric.clone()))?;
        registry.register(Box::new(nodes_cache_count.clone()))?;
        registry.register(Box::new(edges_cache_count.clone()))?;
        registry.register(Box::new(search_projection_jobs_total.clone()))?;
        registry.register(Box::new(search_requests_total.clone()))?;
        registry.register(Box::new(search_candidate_set_overflow_total.clone()))?;
        registry.register(Box::new(search_request_duration_seconds.clone()))?;
        registry.register(Box::new(search_repository_duration_seconds.clone()))?;
        registry.register(Box::new(search_provider_duration_seconds.clone()))?;
        registry.register(Box::new(search_authorized_candidates.clone()))?;
        registry.register(Box::new(search_lexical_candidates.clone()))?;

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
                search_requests_total,
                search_candidate_set_overflow_total,
                search_request_duration_seconds,
                search_repository_duration_seconds,
                search_provider_duration_seconds,
                search_authorized_candidates,
                search_lexical_candidates,
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

    /// Queries, identities, node ids, and provider text must never become
    /// labels; `SearchRequestOutcome` bounds the label set at compile time.
    pub fn search_request_outcome(&self, outcome: SearchRequestOutcome) {
        self.inner
            .search_requests_total
            .with_label_values(&[outcome.as_label()])
            .inc();
    }

    pub fn search_candidate_set_overflow(&self) {
        self.inner.search_candidate_set_overflow_total.inc();
    }

    pub fn observe_search_request_duration(&self, duration: Duration) {
        self.inner
            .search_request_duration_seconds
            .observe(duration.as_secs_f64());
    }

    pub fn observe_search_repository_duration(&self, duration: Duration) {
        self.inner
            .search_repository_duration_seconds
            .observe(duration.as_secs_f64());
    }

    pub fn observe_search_provider_duration(&self, duration: Duration) {
        self.inner
            .search_provider_duration_seconds
            .observe(duration.as_secs_f64());
    }

    pub fn observe_search_candidate_counts(&self, authorized: usize, lexical: usize) {
        self.inner
            .search_authorized_candidates
            .observe(authorized as f64);
        self.inner.search_lexical_candidates.observe(lexical as f64);
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
    use std::time::Duration;

    use super::{BuildInfo, Metrics, MetricsLayer, SearchRequestOutcome, UNMATCHED_ROUTE_LABEL};
    use axum::{body::Body, http::Request, routing::get, Router};
    use tower::ServiceExt;

    fn test_metrics() -> Metrics {
        Metrics::try_new(BuildInfo {
            version: "test",
            commit: "test",
            build_timestamp: "test",
        })
        .expect("metrics")
    }

    #[test]
    fn search_request_outcome_records_exactly_one_observation_per_bounded_label() {
        let metrics = test_metrics();
        let outcomes = [
            (SearchRequestOutcome::Hybrid, "hybrid"),
            (SearchRequestOutcome::LexicalFallback, "lexical_fallback"),
            (
                SearchRequestOutcome::ProviderContractError,
                "provider_contract_error",
            ),
            (SearchRequestOutcome::Unavailable, "unavailable"),
            (SearchRequestOutcome::InvalidRequest, "invalid_request"),
            (SearchRequestOutcome::Internal, "internal"),
        ];
        for (outcome, _) in outcomes {
            metrics.search_request_outcome(outcome);
        }

        let rendered = String::from_utf8(metrics.render().expect("render metrics")).expect("utf8");
        for (_, label) in outcomes {
            assert!(
                rendered.contains(&format!("search_requests_total{{outcome=\"{label}\"}} 1")),
                "expected exactly one recorded observation for outcome {label}"
            );
        }
    }

    #[test]
    fn search_cost_metrics_use_bounded_non_user_controlled_labels_and_record_observations() {
        let metrics = test_metrics();
        metrics.search_request_outcome(SearchRequestOutcome::Hybrid);
        metrics.search_candidate_set_overflow();
        metrics.observe_search_request_duration(Duration::from_millis(25));
        metrics.observe_search_repository_duration(Duration::from_millis(10));
        metrics.observe_search_provider_duration(Duration::from_millis(5));
        metrics.observe_search_candidate_counts(37, 10);

        let rendered = String::from_utf8(metrics.render().expect("render metrics")).expect("utf8");
        assert!(rendered.contains("search_requests_total{outcome=\"hybrid\"} 1"));
        assert!(rendered.contains("search_candidate_set_overflow_total 1"));
        assert!(rendered.contains("search_request_duration_seconds_count 1"));
        assert!(rendered.contains("search_repository_duration_seconds_count 1"));
        assert!(rendered.contains("search_provider_duration_seconds_count 1"));
        assert!(rendered.contains("search_authorized_candidates_sum 37"));
        assert!(rendered.contains("search_lexical_candidates_sum 10"));
        assert!(!rendered.contains("query="));
        assert!(!rendered.contains("node_id="));
    }

    #[test]
    fn search_authorized_candidates_histogram_has_no_bucket_above_the_hard_bound() {
        let metrics = test_metrics();
        metrics.observe_search_candidate_counts(1000, 10);

        let rendered = String::from_utf8(metrics.render().expect("render metrics")).expect("utf8");
        assert!(rendered.contains("search_authorized_candidates_bucket{le=\"1000\"}"));
        assert!(
            !rendered.contains("search_authorized_candidates_bucket{le=\"1001\"}"),
            "MAX_AUTHORIZED_CANDIDATES rejects requests before a >1000 count ever reaches this histogram"
        );
    }

    #[tokio::test]
    async fn known_dynamic_routes_keep_one_normalized_matched_path_label() {
        let metrics = test_metrics();
        let app = Router::new()
            .route("/known/{id}", get(|| async { "ok" }))
            .layer(MetricsLayer::new(metrics.clone()));

        for uri in ["/known/1", "/known/2"] {
            let response = app
                .clone()
                .oneshot(
                    Request::builder()
                        .uri(uri)
                        .body(Body::empty())
                        .expect("request"),
                )
                .await
                .expect("response");
            assert!(response.status().is_success());
        }

        let rendered = String::from_utf8(metrics.render().expect("render metrics")).expect("utf8");
        assert!(rendered.contains("path=\"/known/{id}\""));
        assert!(!rendered.contains("path=\"/known/1\""));
        assert!(!rendered.contains("path=\"/known/2\""));
    }

    #[tokio::test]
    async fn real_unmatched_requests_collapse_to_one_metrics_label() {
        let metrics = test_metrics();
        let app = Router::new()
            .route("/known/{id}", get(|| async { "ok" }))
            .layer(MetricsLayer::new(metrics.clone()));

        for uri in ["/attacker-controlled/a", "/attacker-controlled/b"] {
            let response = app
                .clone()
                .oneshot(
                    Request::builder()
                        .uri(uri)
                        .body(Body::empty())
                        .expect("request"),
                )
                .await
                .expect("response");
            assert_eq!(response.status(), axum::http::StatusCode::NOT_FOUND);
        }

        let rendered = String::from_utf8(metrics.render().expect("render metrics")).expect("utf8");
        assert!(rendered.contains(&format!("path=\"{UNMATCHED_ROUTE_LABEL}\"")));
        assert!(!rendered.contains("path=\"/attacker-controlled/a\""));
        assert!(!rendered.contains("path=\"/attacker-controlled/b\""));
    }
}

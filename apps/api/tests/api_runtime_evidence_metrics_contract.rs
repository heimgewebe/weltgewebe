//! Locks the exact Prometheus metric shape that
//! scripts/performance/api_runtime_evidence.py depends on for the
//! api_runtime measurement declared in policies/performance.v1.json.
//!
//! That tool reuses this crate's existing telemetry instead of building a
//! new observability path: it cross-checks the `path="/search"` series of
//! `http_requests_total` (recorded once per HTTP request by the metrics
//! middleware) against the unlabelled `search_repository_duration_seconds`
//! histogram (recorded once per PostgreSQL repository call in
//! search::service::execute_search_inner) as its deterministic
//! query-count evidence, and reads the histogram's `_bucket`/`_sum`/`_count`
//! series to estimate PostgreSQL search-repository latency percentiles.
//!
//! If the metric names, the `le`/`path` label shapes, or the "exactly one
//! _count/_sum sample" invariant ever drift, this test fails before the
//! Python evidence tool silently misparses or misattributes the evidence.

use std::time::Duration;

use weltgewebe_api::telemetry::{BuildInfo, Metrics};

fn test_metrics() -> Metrics {
    Metrics::try_new(BuildInfo {
        version: "test",
        commit: "test",
        build_timestamp: "test",
    })
    .expect("metrics registry must construct")
}

#[test]
fn search_repository_duration_seconds_is_an_unlabelled_histogram_with_the_inf_bucket() {
    let metrics = test_metrics();
    metrics.observe_search_repository_duration(Duration::from_millis(7));

    let rendered =
        String::from_utf8(metrics.render().expect("render metrics")).expect("utf8 metrics text");

    assert!(
        rendered.contains("search_repository_duration_seconds_bucket{le=\"+Inf\"} 1"),
        "the evidence tool requires an unlabelled +Inf bucket to close the histogram:\n{rendered}"
    );
    assert!(
        rendered.contains("search_repository_duration_seconds_sum "),
        "the evidence tool requires an unlabelled _sum series:\n{rendered}"
    );
    assert_eq!(
        rendered
            .lines()
            .filter(|line| line.starts_with("search_repository_duration_seconds_count"))
            .count(),
        1,
        "the evidence tool requires exactly one _count sample (no extra labels)"
    );
}

#[test]
fn http_requests_total_carries_a_path_label_the_evidence_tool_can_filter_on() {
    let metrics = test_metrics();
    metrics
        .http_requests_total()
        .with_label_values(&["GET", "/search", "200"])
        .inc();
    metrics
        .http_requests_total()
        .with_label_values(&["GET", "/health/live", "200"])
        .inc();

    let rendered =
        String::from_utf8(metrics.render().expect("render metrics")).expect("utf8 metrics text");

    assert!(
        rendered.contains("http_requests_total{method=\"GET\",path=\"/search\",status=\"200\"} 1"),
        "the evidence tool sums http_requests_total{{path=\"/search\"}} as its expected query count:\n{rendered}"
    );
    assert!(
        !rendered
            .contains("http_requests_total{method=\"GET\",path=\"/health/live\",status=\"200\"} 2"),
        "the /search series must not be conflated with other routes"
    );
}

#[test]
fn search_repository_duration_is_observed_independently_of_search_request_duration() {
    // The evidence tool's deterministic query-count mechanism relies on
    // search_repository_duration_seconds counting PostgreSQL repository
    // calls specifically, not overall request handling. Confirm the two
    // histograms are distinct series that can move independently.
    let metrics = test_metrics();
    metrics.observe_search_repository_duration(Duration::from_millis(5));
    metrics.observe_search_repository_duration(Duration::from_millis(5));
    metrics.observe_search_request_duration(Duration::from_millis(50));

    let rendered =
        String::from_utf8(metrics.render().expect("render metrics")).expect("utf8 metrics text");

    assert!(rendered.contains("search_repository_duration_seconds_count 2"));
    assert!(rendered.contains("search_request_duration_seconds_count 1"));
}

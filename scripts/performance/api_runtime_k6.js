// Mixed-health-and-read workload for the api_runtime measurement declared in
// policies/performance.v1.json (measurements.api_runtime.scenario).
//
// This script only produces samples (a k6 JSON summary via handleSummary).
// scripts/performance/api_runtime_evidence.py applies the canonical
// thresholds from that policy file, so the pass/fail decision has exactly
// one source of truth. Do not add k6 `thresholds` here: a second, drifting
// copy of the budget would defeat that single-source-of-truth guarantee.
import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL;
if (!BASE_URL) {
  throw new Error('BASE_URL is required, e.g. http://127.0.0.1:8080');
}

const SEARCH_QUERY = __ENV.API_RUNTIME_SEARCH_QUERY || 'werkstatt';
const DATASET_PROFILE = __ENV.API_RUNTIME_DATASET_PROFILE || 'domain-scale-ci';
const CONCURRENCY_PROFILE =
  __ENV.API_RUNTIME_CONCURRENCY_PROFILE || 'mixed-health-and-read';

// k6's http_req_failed metric only reflects network-level errors by default
// (DNS/TCP/timeout), never HTTP status codes, which would make the
// http_request_failed_rate gate blind to real 5xx responses. Only
// /health/ready legitimately reports 503 for expected unavailability (its
// dependencies are still starting up); every other endpoint, including
// /search, must return 200 to count as a success, so a 503 there is a real
// failure and must count against http_req_failed. The 503 tolerance below is
// therefore scoped to the /health/ready request only, not set globally.
http.setResponseCallback(http.expectedStatuses(200));
const READY_RESPONSE_CALLBACK = http.expectedStatuses(200, 503);

export const options = {
  vus: Number(__ENV.API_RUNTIME_VUS || 10),
  duration: `${Number(__ENV.API_RUNTIME_DURATION_SECONDS || 30)}s`,
  // Explicit percentiles so scripts/performance/api_runtime_evidence.py can
  // read exact p50/p95/p99 values out of the summary without guessing at
  // k6's default stat set.
  summaryTrendStats: ['avg', 'min', 'med', 'p(50)', 'p(95)', 'p(99)', 'max'],
};

export default function () {
  const live = http.get(`${BASE_URL}/health/live`);
  check(live, { 'live 200': (r) => r.status === 200 });

  const ready = http.get(`${BASE_URL}/health/ready`, {
    responseCallback: READY_RESPONSE_CALLBACK,
  });
  check(ready, { 'ready 2xx/5xx': (r) => r.status === 200 || r.status === 503 });

  // The only read endpoint in the mix that is wired to PostgreSQL repository
  // telemetry (search_repository_duration_seconds); scripts/performance/
  // api_runtime_evidence.py cross-checks its request count against that
  // histogram's observation count as its deterministic query-count evidence.
  // Unlike /health/ready, /search has no legitimate 503 case in this
  // scenario, so it uses the default (200-only) response callback: a 503
  // here is real evidence of /search unavailability and must surface in
  // http_req_failed rather than being silently tolerated.
  const search = http.get(
    `${BASE_URL}/search?q=${encodeURIComponent(SEARCH_QUERY)}&limit=5`,
  );
  check(search, {
    'search 200': (r) => r.status === 200,
  });
}

// Binds this run's k6 summary to the exact scenario it exercised so
// scripts/performance/api_runtime_evidence.py can refuse contradictory
// evidence (a summary recorded under different VUs/duration/profiles than
// the canonical policy declares).
export function handleSummary(data) {
  const enriched = Object.assign({}, data, {
    weltgewebe_scenario: {
      virtual_users: options.vus,
      duration_seconds: Number(String(options.duration).replace(/s$/, '')),
      dataset_profile: DATASET_PROFILE,
      concurrency_profile: CONCURRENCY_PROFILE,
    },
  });
  const outputPath =
    __ENV.API_RUNTIME_SUMMARY_PATH || 'api-runtime-summary.json';
  return { [outputPath]: JSON.stringify(enriched) };
}

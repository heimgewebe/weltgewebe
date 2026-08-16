"""Tests for scripts/performance/api_runtime_evidence.py.

Covers: policy schema/scenario binding, Prometheus text parsing (counters and
histograms, including counter-reset and malformed-input rejection), k6
summary parsing, end-to-end evidence assembly (pass and fail), the
deterministic query-count cross-check on missing/contradictory evidence,
git-HEAD/policy revision binding via `verify`, and the regression-fixture
negative case that must demonstrably fail the gate.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.performance import api_runtime_evidence as evidence  # noqa: E402

POLICY_PATH = ROOT / "policies/performance.v1.json"
FAKE_GIT_HEAD = "a" * 40
FAKE_POLICY_SHA256 = "b" * 64


def _load_policy() -> dict:
    return evidence.load_policy(POLICY_PATH)


def _canonical_scenario() -> dict:
    return {
        "virtual_users": 10,
        "duration_seconds": 30,
        "dataset_profile": "domain-scale-ci",
        "concurrency_profile": "mixed-health-and-read",
    }


def _k6_summary(
    *,
    p50=20.0,
    p95=40.0,
    p99=60.0,
    failed_rate=0.0,
    total_requests=300,
    scenario=None,
) -> dict:
    return {
        "metrics": {
            "http_req_duration": {"values": {"p(50)": p50, "p(95)": p95, "p(99)": p99}},
            "http_req_failed": {"values": {"rate": failed_rate}},
            "http_reqs": {"values": {"count": total_requests}},
        },
        "weltgewebe_scenario": scenario if scenario is not None else _canonical_scenario(),
    }


def _prometheus_text(*, search_count: int, search_sum_seconds: float, http_search_requests: int) -> str:
    return evidence._render_prometheus_fixture(
        search_count=search_count,
        search_sum_seconds=search_sum_seconds,
        http_search_requests=http_search_requests,
    )


class PolicyBindingTests(unittest.TestCase):
    def test_real_policy_scenario_matches_the_documented_ci_contract(self) -> None:
        policy = _load_policy()
        contract = evidence.api_runtime_section(policy)
        self.assertEqual(contract["scenario"], _canonical_scenario())
        self.assertEqual(contract["thresholds"]["http_request_duration_ms"], 300.0)
        self.assertEqual(contract["thresholds"]["http_request_duration_p99_ms"], 750.0)
        self.assertEqual(contract["thresholds"]["http_request_failed_rate"], 0.01)

    def test_load_policy_rejects_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "not valid JSON"):
                evidence.load_policy(path)

    def test_load_policy_rejects_wrong_contract_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps({"contract_id": "other", "measurements": {}}), encoding="utf-8")
            with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "contract_id"):
                evidence.load_policy(path)

    def test_scenario_must_define_exactly_the_canonical_fields(self) -> None:
        policy = _load_policy()
        broken = json.loads(json.dumps(policy))
        del broken["measurements"]["api_runtime"]["scenario"]["dataset_profile"]
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "scenario"):
            evidence.api_runtime_section(broken)

    def test_metrics_must_define_exactly_the_canonical_threshold_set(self) -> None:
        policy = _load_policy()
        broken = json.loads(json.dumps(policy))
        del broken["measurements"]["api_runtime"]["metrics"]["http_request_failed_rate"]
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "metrics"):
            evidence.api_runtime_section(broken)

    def test_metric_max_must_be_finite_and_non_negative(self) -> None:
        policy = _load_policy()
        broken = json.loads(json.dumps(policy))
        broken["measurements"]["api_runtime"]["metrics"]["http_request_failed_rate"]["max"] = -1
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "max"):
            evidence.api_runtime_section(broken)


class PrometheusParsingTests(unittest.TestCase):
    def test_parses_counters_and_histograms(self) -> None:
        text = _prometheus_text(search_count=5, search_sum_seconds=1.0, http_search_requests=5)
        families = evidence.parse_prometheus_text(text)
        self.assertIn("search_repository_duration_seconds_bucket", families)
        self.assertEqual(
            evidence.sum_counter(families, "http_requests_total", {"path": "/search"}), 5.0
        )

    def test_rejects_unparseable_lines(self) -> None:
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "cannot parse"):
            evidence.parse_prometheus_text("this is not a metric line at all {{{")

    def test_sum_counter_raises_when_metric_absent(self) -> None:
        families = evidence.parse_prometheus_text("some_other_metric 1\n")
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "http_requests_total"):
            evidence.sum_counter(families, "http_requests_total")

    def test_sum_counter_raises_when_label_filter_matches_nothing(self) -> None:
        families = evidence.parse_prometheus_text(
            'http_requests_total{method="GET",path="/health/live",status="200"} 3\n'
        )
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "no samples matching"):
            evidence.sum_counter(families, "http_requests_total", {"path": "/search"})

    def test_histogram_snapshot_requires_the_inf_bucket(self) -> None:
        families = evidence.parse_prometheus_text(
            'search_repository_duration_seconds_bucket{le="0.1"} 1\n'
            "search_repository_duration_seconds_sum 0.05\n"
            "search_repository_duration_seconds_count 1\n"
        )
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, r"\+Inf"):
            evidence.histogram_snapshot(families, "search_repository_duration_seconds")

    def test_histogram_delta_detects_counter_reset(self) -> None:
        before = evidence.parse_prometheus_text(
            _prometheus_text(search_count=10, search_sum_seconds=1.0, http_search_requests=10)
        )
        after = evidence.parse_prometheus_text(
            _prometheus_text(search_count=3, search_sum_seconds=0.3, http_search_requests=3)
        )
        before_hist = evidence.histogram_snapshot(before, "search_repository_duration_seconds")
        after_hist = evidence.histogram_snapshot(after, "search_repository_duration_seconds")
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "counter reset"):
            evidence.histogram_delta(before_hist, after_hist)

    def test_histogram_quantile_linear_interpolation(self) -> None:
        # 10 observations spread evenly across two buckets: exercise the
        # interpolation path (not just the exact-boundary shortcuts).
        text = (
            "# TYPE x histogram\n"
            'x_bucket{le="0.1"} 5\n'
            'x_bucket{le="0.2"} 10\n'
            'x_bucket{le="+Inf"} 10\n'
            "x_sum 1.0\n"
            "x_count 10\n"
        )
        families = evidence.parse_prometheus_text(text)
        snapshot = evidence.histogram_snapshot(families, "x")
        median_ms = evidence.histogram_quantile_ms(snapshot, 0.5)
        self.assertAlmostEqual(median_ms, 100.0, places=6)

    def test_histogram_quantile_in_overflow_bucket_is_conservative(self) -> None:
        text = (
            'x_bucket{le="0.1"} 0\n'
            'x_bucket{le="+Inf"} 5\n'
            "x_sum 5.0\n"
            "x_count 5\n"
        )
        families = evidence.parse_prometheus_text(text)
        snapshot = evidence.histogram_snapshot(families, "x")
        p99_ms = evidence.histogram_quantile_ms(snapshot, 0.99)
        self.assertEqual(p99_ms, 100.0)


class K6SummaryParsingTests(unittest.TestCase):
    def test_extracts_http_metrics(self) -> None:
        summary = _k6_summary(p95=123.0, p99=456.0, failed_rate=0.002, total_requests=42)
        result = evidence.extract_http_metrics(summary)
        self.assertEqual(result["p95_ms"], 123.0)
        self.assertEqual(result["p99_ms"], 456.0)
        self.assertEqual(result["failed_rate"], 0.002)
        self.assertEqual(result["total_requests"], 42)

    def test_rejects_zero_requests(self) -> None:
        summary = _k6_summary(total_requests=0)
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "zero HTTP requests"):
            evidence.extract_http_metrics(summary)

    def test_missing_scenario_block_is_rejected(self) -> None:
        summary = _k6_summary()
        del summary["weltgewebe_scenario"]
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "weltgewebe_scenario"):
            evidence.extract_declared_scenario(summary)


class AssembleReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = _load_policy()

    def test_passing_run_produces_a_bound_pass_report(self) -> None:
        k6_summary = _k6_summary(p50=15.0, p95=40.0, p99=60.0, failed_rate=0.0, total_requests=300)
        before = _prometheus_text(search_count=0, search_sum_seconds=0.0, http_search_requests=0)
        after = _prometheus_text(search_count=100, search_sum_seconds=1.0, http_search_requests=100)

        report = evidence.assemble_report(
            policy=self.policy,
            k6_summary=k6_summary,
            metrics_before_text=before,
            metrics_after_text=after,
            resource_receipt=None,
            database_connections=4,
            git_head=FAKE_GIT_HEAD,
            policy_sha256=FAKE_POLICY_SHA256,
        )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["revision"]["git_head"], FAKE_GIT_HEAD)
        self.assertEqual(report["revision"]["policy_sha256"], FAKE_POLICY_SHA256)
        self.assertEqual(report["scenario"], _canonical_scenario())
        self.assertEqual(
            report["metrics"]["database"]["query_count"],
            {
                "expected_from_http_requests_total": 100,
                "observed_from_search_repository_duration_seconds_count": 100,
            },
        )
        self.assertEqual(report["metrics"]["resources"]["database_connections"], 4)
        self.assertNotIn("api_replica", report["metrics"]["resources"])

    def test_folds_in_a_valid_resource_receipt(self) -> None:
        k6_summary = _k6_summary()
        before = _prometheus_text(search_count=0, search_sum_seconds=0.0, http_search_requests=0)
        after = _prometheus_text(search_count=10, search_sum_seconds=0.1, http_search_requests=10)
        receipt = {
            "container_name": "weltgewebe-api",
            "sample_count": 30,
            "cpu_percent": 12.5,
            "memory_bytes": 104857600,
        }
        report = evidence.assemble_report(
            policy=self.policy,
            k6_summary=k6_summary,
            metrics_before_text=before,
            metrics_after_text=after,
            resource_receipt=receipt,
            database_connections=2,
            git_head=FAKE_GIT_HEAD,
            policy_sha256=FAKE_POLICY_SHA256,
        )
        self.assertEqual(report["metrics"]["resources"]["api_replica"], receipt)

    def test_threshold_breach_produces_a_soft_fail_with_explicit_failures(self) -> None:
        k6_summary = _k6_summary(p95=999.0, p99=999.0, failed_rate=0.5, total_requests=300)
        before = _prometheus_text(search_count=0, search_sum_seconds=0.0, http_search_requests=0)
        after = _prometheus_text(search_count=10, search_sum_seconds=0.1, http_search_requests=10)

        report = evidence.assemble_report(
            policy=self.policy,
            k6_summary=k6_summary,
            metrics_before_text=before,
            metrics_after_text=after,
            resource_receipt=None,
            database_connections=1,
            git_head=FAKE_GIT_HEAD,
            policy_sha256=FAKE_POLICY_SHA256,
        )
        self.assertEqual(report["status"], "fail")
        self.assertEqual(len(report["failures"]), 3)

    def test_scenario_mismatch_is_a_hard_failure(self) -> None:
        mismatched_scenario = _canonical_scenario()
        mismatched_scenario["virtual_users"] = 50
        k6_summary = _k6_summary(scenario=mismatched_scenario)
        before = _prometheus_text(search_count=0, search_sum_seconds=0.0, http_search_requests=0)
        after = _prometheus_text(search_count=10, search_sum_seconds=0.1, http_search_requests=10)

        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "scenario"):
            evidence.assemble_report(
                policy=self.policy,
                k6_summary=k6_summary,
                metrics_before_text=before,
                metrics_after_text=after,
                resource_receipt=None,
                database_connections=1,
                git_head=FAKE_GIT_HEAD,
                policy_sha256=FAKE_POLICY_SHA256,
            )

    def test_contradictory_query_count_is_a_hard_failure(self) -> None:
        k6_summary = _k6_summary()
        before = _prometheus_text(search_count=0, search_sum_seconds=0.0, http_search_requests=0)
        # http_requests_total says 40 requests reached /search, but the
        # repository histogram only observed 10 queries: a contradiction that
        # must fail closed rather than silently averaging away.
        after = _prometheus_text(search_count=10, search_sum_seconds=0.1, http_search_requests=40)

        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "contradictory evidence"):
            evidence.assemble_report(
                policy=self.policy,
                k6_summary=k6_summary,
                metrics_before_text=before,
                metrics_after_text=after,
                resource_receipt=None,
                database_connections=1,
                git_head=FAKE_GIT_HEAD,
                policy_sha256=FAKE_POLICY_SHA256,
            )

    def test_zero_observed_queries_is_a_hard_failure(self) -> None:
        k6_summary = _k6_summary()
        before = _prometheus_text(search_count=0, search_sum_seconds=0.0, http_search_requests=0)
        after = _prometheus_text(search_count=0, search_sum_seconds=0.0, http_search_requests=0)

        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "no PostgreSQL"):
            evidence.assemble_report(
                policy=self.policy,
                k6_summary=k6_summary,
                metrics_before_text=before,
                metrics_after_text=after,
                resource_receipt=None,
                database_connections=1,
                git_head=FAKE_GIT_HEAD,
                policy_sha256=FAKE_POLICY_SHA256,
            )

    def test_rejects_a_malformed_git_head(self) -> None:
        k6_summary = _k6_summary()
        before = _prometheus_text(search_count=0, search_sum_seconds=0.0, http_search_requests=0)
        after = _prometheus_text(search_count=10, search_sum_seconds=0.1, http_search_requests=10)
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "git_head"):
            evidence.assemble_report(
                policy=self.policy,
                k6_summary=k6_summary,
                metrics_before_text=before,
                metrics_after_text=after,
                resource_receipt=None,
                database_connections=1,
                git_head="not-a-sha",
                policy_sha256=FAKE_POLICY_SHA256,
            )


class MissingAndInvalidInputTests(unittest.TestCase):
    def test_missing_k6_summary_file_fails_closed(self) -> None:
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "cannot read"):
            evidence._read_text(Path("/nonexistent/does-not-exist.json"), "metrics-before snapshot")

    def test_missing_resource_receipt_file_fails_closed(self) -> None:
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "cannot read"):
            evidence.load_resource_receipt(Path("/nonexistent/receipt.json"))

    def test_resource_receipt_rejects_wrong_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "contract": "something-else",
                        "container_name": "x",
                        "sample_count": 1,
                        "peaks": {"cpu_percent": 1.0, "memory_bytes": 1},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "contract"):
                evidence.load_resource_receipt(path)

    def test_resource_receipt_rejects_negative_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "contract": evidence.RESOURCE_RECEIPT_CONTRACT,
                        "container_name": "x",
                        "sample_count": 1,
                        "peaks": {"cpu_percent": 1.0, "memory_bytes": -1},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "memory_bytes"):
                evidence.load_resource_receipt(path)

    def test_database_connections_must_be_non_negative(self) -> None:
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "non-negative"):
            evidence.validate_database_connections(-1)
        self.assertEqual(evidence.validate_database_connections(0), 0)


class RevisionBindingTests(unittest.TestCase):
    def test_verify_accepts_a_matching_report(self) -> None:
        report = {
            "schema_version": evidence.SCHEMA_VERSION,
            "contract_id": evidence.CONTRACT_ID,
            "revision": {"git_head": FAKE_GIT_HEAD, "policy_sha256": FAKE_POLICY_SHA256},
        }
        evidence.verify_report(
            report, expected_git_head=FAKE_GIT_HEAD, expected_policy_sha256=FAKE_POLICY_SHA256
        )

    def test_verify_rejects_a_stale_git_head(self) -> None:
        report = {
            "schema_version": evidence.SCHEMA_VERSION,
            "contract_id": evidence.CONTRACT_ID,
            "revision": {"git_head": "c" * 40, "policy_sha256": FAKE_POLICY_SHA256},
        }
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "git HEAD"):
            evidence.verify_report(
                report, expected_git_head=FAKE_GIT_HEAD, expected_policy_sha256=FAKE_POLICY_SHA256
            )

    def test_verify_rejects_a_stale_policy_revision(self) -> None:
        report = {
            "schema_version": evidence.SCHEMA_VERSION,
            "contract_id": evidence.CONTRACT_ID,
            "revision": {"git_head": FAKE_GIT_HEAD, "policy_sha256": "d" * 64},
        }
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "performance.v1.json revision"):
            evidence.verify_report(
                report, expected_git_head=FAKE_GIT_HEAD, expected_policy_sha256=FAKE_POLICY_SHA256
            )

    def test_verify_rejects_an_unrecognized_artifact(self) -> None:
        with self.assertRaisesRegex(evidence.ApiRuntimeEvidenceError, "not a recognizable"):
            evidence.verify_report(
                {"schema_version": 1, "contract_id": "wrong"},
                expected_git_head=FAKE_GIT_HEAD,
                expected_policy_sha256=FAKE_POLICY_SHA256,
            )

    def test_git_head_resolves_a_real_sha_in_this_checkout(self) -> None:
        head = evidence.git_head(ROOT)
        self.assertRegex(head, r"^[0-9a-f]{40}$")


class RegressionFixtureCliTests(unittest.TestCase):
    """The controlled negative mode: prove the gate fails closed end-to-end
    through the actual CLI, not just the internal function."""

    def test_regression_fixture_makes_check_exit_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture_dir = Path(directory) / "fixture"
            report_path = Path(directory) / "report.json"

            generate = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/performance/api_runtime_evidence.py"),
                    "regression-fixture",
                    "--output-dir",
                    str(fixture_dir),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(generate.returncode, 0, generate.stderr)

            check = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/performance/api_runtime_evidence.py"),
                    "check",
                    "--k6-summary",
                    str(fixture_dir / "k6-summary.json"),
                    "--metrics-before",
                    str(fixture_dir / "metrics-before.prom"),
                    "--metrics-after",
                    str(fixture_dir / "metrics-after.prom"),
                    "--database-connections",
                    "1",
                    "--report",
                    str(report_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(check.returncode, 2, check.stdout + check.stderr)
            report = json.loads(check.stdout)
            self.assertEqual(report["status"], "fail")
            self.assertTrue(report["failures"], "the regression fixture must record concrete failures")
            self.assertRegex(report["revision"]["git_head"], r"^[0-9a-f]{40}$")

            verify = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/performance/api_runtime_evidence.py"),
                    "verify",
                    "--report",
                    str(report_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)

    def test_check_passes_cleanly_against_a_hand_built_healthy_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            k6_path = root / "k6-summary.json"
            before_path = root / "before.prom"
            after_path = root / "after.prom"
            report_path = root / "report.json"

            k6_path.write_text(json.dumps(_k6_summary()), encoding="utf-8")
            before_path.write_text(
                _prometheus_text(search_count=0, search_sum_seconds=0.0, http_search_requests=0),
                encoding="utf-8",
            )
            after_path.write_text(
                _prometheus_text(search_count=50, search_sum_seconds=0.5, http_search_requests=50),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/performance/api_runtime_evidence.py"),
                    "check",
                    "--k6-summary",
                    str(k6_path),
                    "--metrics-before",
                    str(before_path),
                    "--metrics-after",
                    str(after_path),
                    "--database-connections",
                    "0",
                    "--report",
                    str(report_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "pass")


if __name__ == "__main__":
    unittest.main()

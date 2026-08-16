#!/usr/bin/env python3
"""Turn the api_runtime section of policies/performance.v1.json into
executable, revision-bound measurement evidence.

This tool does not build a new observability stack. It reuses the API's
existing Prometheus telemetry (apps/api/src/telemetry/mod.rs) and a k6
workload (scripts/performance/api_runtime_k6.js) that exercises the exact
10 VU / 30s domain-scale-ci mixed-health-and-read contract declared in the
canonical performance policy.

Evidence flow:
  1. Scrape /metrics before the k6 run (--metrics-before).
  2. Run scripts/performance/api_runtime_k6.js against the target API,
     exporting its JSON summary (--k6-summary).
  3. Scrape /metrics again after the run (--metrics-after).
  4. Sample CPU/memory for the API replica with
     scripts/performance/container_resource_sampler.py (--resource-receipt)
     and read PostgreSQL's connection count from pg_stat_activity
     (--database-connections).
  5. Run `check` to assemble a single machine-readable, revision-bound
     evidence artifact and apply the canonical thresholds.

The canonical performance.v1 contract remains the single source of truth for
thresholds: this tool reads them at check time rather than embedding a
second, driftable copy.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = Path("policies/performance.v1.json")

SCHEMA_VERSION = 1
CONTRACT_ID = "weltgewebe-performance-v1#/measurements/api_runtime"
RESOURCE_RECEIPT_CONTRACT = "api-replica-resource-sample-v1"

REQUIRED_SCENARIO_FIELDS = (
    "virtual_users",
    "duration_seconds",
    "dataset_profile",
    "concurrency_profile",
)
REQUIRED_METRIC_KEYS = (
    "http_request_duration_ms",
    "http_request_duration_p99_ms",
    "http_request_failed_rate",
)

QUERY_HISTOGRAM_NAME = "search_repository_duration_seconds"
HTTP_COUNTER_NAME = "http_requests_total"
SEARCH_PATH_LABEL = "/search"

GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ApiRuntimeEvidenceError(RuntimeError):
    """Raised when an input, the policy, or the assembled evidence is invalid."""


# --------------------------------------------------------------------------
# Small deterministic helpers shared with the style of
# scripts/performance/domain_scale.py (kept self-contained rather than
# imported, so this module has no import-time coupling to that script).
# --------------------------------------------------------------------------


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ApiRuntimeEvidenceError(f"cannot hash file {path}: {exc}") from exc
    return digest.hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    absolute = Path(os.path.abspath(path))
    absolute.parent.mkdir(parents=True, exist_ok=True)
    if absolute.is_symlink() or (absolute.exists() and not absolute.is_file()):
        raise ApiRuntimeEvidenceError(f"output must be absent or a regular file: {absolute}")
    fd, temporary_name = tempfile.mkstemp(prefix=f".{absolute.name}.", dir=absolute.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(temporary, absolute)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _atomic_json(path: Path, value: Any) -> None:
    _atomic_write(path, canonical_json_bytes(value))


def _atomic_text(path: Path, text: str) -> None:
    _atomic_write(path, text.encode("utf-8"))


def _read_text(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ApiRuntimeEvidenceError(f"cannot read {label} at {path}: {exc}") from exc


def _read_json(path: Path, label: str) -> Any:
    text = _read_text(path, label)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ApiRuntimeEvidenceError(f"{label} at {path} is not valid JSON: {exc}") from exc


# --------------------------------------------------------------------------
# Canonical policy binding
# --------------------------------------------------------------------------


def load_policy(path: Path) -> dict[str, Any]:
    parsed = _read_json(path, "performance contract")
    if not isinstance(parsed, dict):
        raise ApiRuntimeEvidenceError("performance contract must be a JSON object")
    if parsed.get("contract_id") != "weltgewebe-performance-v1":
        raise ApiRuntimeEvidenceError(
            "performance contract has an unexpected contract_id; refusing to bind evidence to it"
        )
    if not isinstance(parsed.get("measurements"), dict):
        raise ApiRuntimeEvidenceError("performance contract is missing measurements")
    return parsed


def _scalar_scenario(value: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(REQUIRED_SCENARIO_FIELDS):
        raise ApiRuntimeEvidenceError(
            f"{label} must define exactly {', '.join(REQUIRED_SCENARIO_FIELDS)}"
        )
    vus = value["virtual_users"]
    duration = value["duration_seconds"]
    dataset_profile = value["dataset_profile"]
    concurrency_profile = value["concurrency_profile"]
    if not isinstance(vus, int) or isinstance(vus, bool) or vus < 1:
        raise ApiRuntimeEvidenceError(f"{label}.virtual_users must be a positive integer")
    if not isinstance(duration, int) or isinstance(duration, bool) or duration < 1:
        raise ApiRuntimeEvidenceError(f"{label}.duration_seconds must be a positive integer")
    if not isinstance(dataset_profile, str) or not dataset_profile:
        raise ApiRuntimeEvidenceError(f"{label}.dataset_profile must be a non-empty string")
    if not isinstance(concurrency_profile, str) or not concurrency_profile:
        raise ApiRuntimeEvidenceError(f"{label}.concurrency_profile must be a non-empty string")
    return {
        "virtual_users": vus,
        "duration_seconds": duration,
        "dataset_profile": dataset_profile,
        "concurrency_profile": concurrency_profile,
    }


def api_runtime_section(policy: Mapping[str, Any]) -> dict[str, Any]:
    section = policy["measurements"].get("api_runtime")
    if not isinstance(section, dict):
        raise ApiRuntimeEvidenceError("performance contract is missing measurements.api_runtime")

    scenario = _scalar_scenario(section.get("scenario"), "measurements.api_runtime.scenario")

    metrics = section.get("metrics")
    if not isinstance(metrics, dict) or set(metrics) != set(REQUIRED_METRIC_KEYS):
        raise ApiRuntimeEvidenceError(
            "measurements.api_runtime.metrics must define exactly "
            f"{', '.join(REQUIRED_METRIC_KEYS)}"
        )
    thresholds: dict[str, float] = {}
    for key in REQUIRED_METRIC_KEYS:
        entry = metrics[key]
        if not isinstance(entry, dict) or "max" not in entry:
            raise ApiRuntimeEvidenceError(f"measurements.api_runtime.metrics.{key} must define max")
        max_value = entry["max"]
        if (
            not isinstance(max_value, (int, float))
            or isinstance(max_value, bool)
            or not math.isfinite(max_value)
            or max_value < 0
        ):
            raise ApiRuntimeEvidenceError(
                f"measurements.api_runtime.metrics.{key}.max must be a finite number >= 0"
            )
        thresholds[key] = float(max_value)

    return {"scenario": scenario, "thresholds": thresholds}


# --------------------------------------------------------------------------
# Prometheus text-exposition parsing
# --------------------------------------------------------------------------

_METRIC_LINE_RE = re.compile(
    r"^(?P<name>[A-Za-z_:][A-Za-z0-9_:]*)(\{(?P<labels>.*)\})?\s+(?P<value>\S+)\s*$"
)
_LABEL_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)="((?:[^"\\]|\\.)*)"')
_ESCAPE_RE = re.compile(r"\\(.)")


def _unescape_label(value: str) -> str:
    return _ESCAPE_RE.sub(lambda match: {"\\": "\\", '"': '"', "n": "\n"}.get(match.group(1), match.group(1)), value)


PrometheusSample = tuple[dict[str, str], float]
PrometheusFamilies = dict[str, list[PrometheusSample]]


def parse_prometheus_text(text: str) -> PrometheusFamilies:
    families: PrometheusFamilies = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _METRIC_LINE_RE.match(line)
        if not match:
            raise ApiRuntimeEvidenceError(f"cannot parse Prometheus exposition line: {line!r}")
        name = match.group("name")
        raw_labels = match.group("labels") or ""
        labels = {key: _unescape_label(value) for key, value in _LABEL_RE.findall(raw_labels)}
        raw_value = match.group("value")
        try:
            value = float(raw_value)
        except ValueError as exc:
            raise ApiRuntimeEvidenceError(
                f"cannot parse Prometheus sample value {raw_value!r}: {exc}"
            ) from exc
        families.setdefault(name, []).append((labels, value))
    return families


def sum_counter(
    families: PrometheusFamilies, name: str, label_filter: Mapping[str, str] | None = None
) -> float:
    samples = families.get(name)
    if not samples:
        raise ApiRuntimeEvidenceError(f"Prometheus metric {name} was not found in the scrape")
    total = 0.0
    matched = False
    for labels, value in samples:
        if label_filter is not None and any(labels.get(k) != v for k, v in label_filter.items()):
            continue
        matched = True
        total += value
    if not matched:
        raise ApiRuntimeEvidenceError(
            f"Prometheus metric {name} has no samples matching labels {dict(label_filter or {})}"
        )
    return total


@dataclasses.dataclass(frozen=True)
class HistogramSnapshot:
    buckets: dict[str, float]
    total_count: float
    total_sum: float


def histogram_snapshot(families: PrometheusFamilies, base_name: str) -> HistogramSnapshot:
    bucket_samples = families.get(f"{base_name}_bucket")
    if not bucket_samples:
        raise ApiRuntimeEvidenceError(f"Prometheus histogram {base_name} has no _bucket samples")
    buckets: dict[str, float] = {}
    for labels, value in bucket_samples:
        le = labels.get("le")
        if le is None:
            raise ApiRuntimeEvidenceError(
                f"Prometheus histogram {base_name}_bucket sample is missing the le label"
            )
        if le in buckets:
            raise ApiRuntimeEvidenceError(
                f"Prometheus histogram {base_name}_bucket has a duplicate le={le} sample"
            )
        buckets[le] = value
    if "+Inf" not in buckets:
        raise ApiRuntimeEvidenceError(
            f"Prometheus histogram {base_name}_bucket is missing the +Inf bucket"
        )
    count_samples = families.get(f"{base_name}_count")
    sum_samples = families.get(f"{base_name}_sum")
    if not count_samples or not sum_samples:
        raise ApiRuntimeEvidenceError(f"Prometheus histogram {base_name} is missing _count or _sum")
    if len(count_samples) != 1 or len(sum_samples) != 1:
        raise ApiRuntimeEvidenceError(
            f"Prometheus histogram {base_name} must be unlabelled (exactly one _count/_sum sample)"
        )
    return HistogramSnapshot(
        buckets=buckets, total_count=count_samples[0][1], total_sum=sum_samples[0][1]
    )


def histogram_delta(before: HistogramSnapshot, after: HistogramSnapshot) -> HistogramSnapshot:
    if set(before.buckets) != set(after.buckets):
        raise ApiRuntimeEvidenceError(
            "histogram bucket boundaries changed between the before/after scrapes"
        )
    delta_buckets: dict[str, float] = {}
    for le, after_value in after.buckets.items():
        before_value = before.buckets[le]
        delta = after_value - before_value
        if delta < 0:
            raise ApiRuntimeEvidenceError(
                f"histogram bucket le={le} decreased between scrapes (counter reset?)"
            )
        delta_buckets[le] = delta
    delta_count = after.total_count - before.total_count
    delta_sum = after.total_sum - before.total_sum
    if delta_count < 0 or delta_sum < 0:
        raise ApiRuntimeEvidenceError(
            "histogram count/sum decreased between scrapes (counter reset?)"
        )
    return HistogramSnapshot(buckets=delta_buckets, total_count=delta_count, total_sum=delta_sum)


def _sorted_bucket_bounds(buckets: Mapping[str, float]) -> list[tuple[float, float]]:
    bounds = [
        (math.inf if le == "+Inf" else float(le), count) for le, count in buckets.items()
    ]
    bounds.sort(key=lambda item: item[0])
    return bounds


def histogram_quantile_ms(snapshot: HistogramSnapshot, quantile: float) -> float:
    if not 0.0 < quantile < 1.0:
        raise ApiRuntimeEvidenceError("quantile must be between 0 and 1 exclusive")
    if snapshot.total_count <= 0:
        raise ApiRuntimeEvidenceError("cannot compute a quantile from zero observations")
    target = quantile * snapshot.total_count
    lower_bound = 0.0
    lower_count = 0.0
    for le_value, cumulative in _sorted_bucket_bounds(snapshot.buckets):
        if cumulative >= target:
            if le_value == math.inf:
                # The target falls in the open-ended overflow bucket. Report the
                # last finite boundary: a conservative (non-optimistic) estimate
                # rather than inventing an upper bound.
                return lower_bound * 1000.0
            if cumulative == lower_count:
                return le_value * 1000.0
            fraction = (target - lower_count) / (cumulative - lower_count)
            estimate = lower_bound + fraction * (le_value - lower_bound)
            return estimate * 1000.0
        lower_bound = le_value
        lower_count = cumulative
    raise ApiRuntimeEvidenceError(  # pragma: no cover - +Inf always covers count
        "histogram buckets do not cover the requested quantile"
    )


# --------------------------------------------------------------------------
# k6 summary parsing
# --------------------------------------------------------------------------


def load_k6_summary(path: Path) -> dict[str, Any]:
    parsed = _read_json(path, "k6 summary")
    if not isinstance(parsed, dict):
        raise ApiRuntimeEvidenceError("k6 summary must be a JSON object")
    return parsed


def extract_declared_scenario(summary: Mapping[str, Any]) -> dict[str, Any]:
    scenario = summary.get("weltgewebe_scenario")
    if not isinstance(scenario, dict):
        raise ApiRuntimeEvidenceError(
            "k6 summary is missing weltgewebe_scenario; the summary was not produced by "
            "scripts/performance/api_runtime_k6.js"
        )
    return _scalar_scenario(scenario, "k6 summary weltgewebe_scenario")


def _metric_value(summary: Mapping[str, Any], metric_name: str, value_key: str) -> float:
    metrics = summary.get("metrics")
    if not isinstance(metrics, dict):
        raise ApiRuntimeEvidenceError("k6 summary is missing metrics")
    entry = metrics.get(metric_name)
    if not isinstance(entry, dict):
        raise ApiRuntimeEvidenceError(f"k6 summary is missing metric {metric_name}")
    values = entry.get("values")
    if not isinstance(values, dict) or value_key not in values:
        raise ApiRuntimeEvidenceError(f"k6 summary metric {metric_name} is missing values.{value_key}")
    raw = values[value_key]
    if not isinstance(raw, (int, float)) or isinstance(raw, bool) or not math.isfinite(raw):
        raise ApiRuntimeEvidenceError(
            f"k6 summary metric {metric_name}.{value_key} must be a finite number"
        )
    return float(raw)


def extract_http_metrics(summary: Mapping[str, Any]) -> dict[str, Any]:
    p50 = _metric_value(summary, "http_req_duration", "p(50)")
    p95 = _metric_value(summary, "http_req_duration", "p(95)")
    p99 = _metric_value(summary, "http_req_duration", "p(99)")
    failed_rate = _metric_value(summary, "http_req_failed", "rate")
    total_requests = _metric_value(summary, "http_reqs", "count")
    if total_requests <= 0:
        raise ApiRuntimeEvidenceError(
            "k6 summary reports zero HTTP requests; the load scenario did not run"
        )
    if not (0.0 <= failed_rate <= 1.0):
        raise ApiRuntimeEvidenceError("k6 summary http_req_failed rate must be between 0 and 1")
    return {
        "p50_ms": p50,
        "p95_ms": p95,
        "p99_ms": p99,
        "failed_rate": failed_rate,
        "total_requests": int(total_requests),
    }


# --------------------------------------------------------------------------
# Container resource receipt (scripts/performance/container_resource_sampler.py)
# --------------------------------------------------------------------------


def load_resource_receipt(path: Path) -> dict[str, Any]:
    parsed = _read_json(path, "container resource receipt")
    if not isinstance(parsed, dict):
        raise ApiRuntimeEvidenceError("container resource receipt must be a JSON object")
    if parsed.get("schema_version") != 1:
        raise ApiRuntimeEvidenceError("container resource receipt must use schema_version 1")
    if parsed.get("contract") != RESOURCE_RECEIPT_CONTRACT:
        raise ApiRuntimeEvidenceError(
            f"container resource receipt must use contract {RESOURCE_RECEIPT_CONTRACT!r}"
        )
    container_name = parsed.get("container_name")
    if not isinstance(container_name, str) or not container_name:
        raise ApiRuntimeEvidenceError("container resource receipt must name a container")
    sample_count = parsed.get("sample_count")
    if not isinstance(sample_count, int) or isinstance(sample_count, bool) or sample_count < 1:
        raise ApiRuntimeEvidenceError("container resource receipt must record at least one sample")
    peaks = parsed.get("peaks")
    if not isinstance(peaks, dict):
        raise ApiRuntimeEvidenceError("container resource receipt is missing peaks")
    cpu_percent = peaks.get("cpu_percent")
    memory_bytes = peaks.get("memory_bytes")
    if (
        not isinstance(cpu_percent, (int, float))
        or isinstance(cpu_percent, bool)
        or not math.isfinite(cpu_percent)
        or cpu_percent < 0
    ):
        raise ApiRuntimeEvidenceError("container resource receipt peaks.cpu_percent is invalid")
    if not isinstance(memory_bytes, int) or isinstance(memory_bytes, bool) or memory_bytes < 0:
        raise ApiRuntimeEvidenceError("container resource receipt peaks.memory_bytes is invalid")
    return {
        "container_name": container_name,
        "sample_count": sample_count,
        "cpu_percent": float(cpu_percent),
        "memory_bytes": memory_bytes,
    }


def validate_database_connections(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ApiRuntimeEvidenceError("database_connections must be a non-negative integer")
    return value


# --------------------------------------------------------------------------
# Evidence assembly
# --------------------------------------------------------------------------


def assemble_report(
    *,
    policy: Mapping[str, Any],
    k6_summary: Mapping[str, Any],
    metrics_before_text: str,
    metrics_after_text: str,
    resource_receipt: Mapping[str, Any] | None,
    database_connections: int,
    git_head: str,
    policy_sha256: str,
) -> dict[str, Any]:
    if not GIT_SHA_RE.fullmatch(git_head):
        raise ApiRuntimeEvidenceError(f"git_head must be a 40-hex sha: {git_head!r}")
    if not SHA256_RE.fullmatch(policy_sha256):
        raise ApiRuntimeEvidenceError(f"policy_sha256 must be a 64-hex sha256: {policy_sha256!r}")

    contract = api_runtime_section(policy)
    declared_scenario = extract_declared_scenario(k6_summary)
    if declared_scenario != contract["scenario"]:
        raise ApiRuntimeEvidenceError(
            "k6 summary scenario does not match measurements.api_runtime.scenario in the "
            f"performance contract: recorded={declared_scenario!r} canonical={contract['scenario']!r}"
        )

    http_metrics = extract_http_metrics(k6_summary)

    before_families = parse_prometheus_text(metrics_before_text)
    after_families = parse_prometheus_text(metrics_after_text)

    http_search_before = sum_counter(before_families, HTTP_COUNTER_NAME, {"path": SEARCH_PATH_LABEL})
    http_search_after = sum_counter(after_families, HTTP_COUNTER_NAME, {"path": SEARCH_PATH_LABEL})
    http_requests_delta = http_search_after - http_search_before
    if http_requests_delta < 0:
        raise ApiRuntimeEvidenceError(
            f'{HTTP_COUNTER_NAME}{{path="{SEARCH_PATH_LABEL}"}} decreased between scrapes '
            "(counter reset?)"
        )

    before_hist = histogram_snapshot(before_families, QUERY_HISTOGRAM_NAME)
    after_hist = histogram_snapshot(after_families, QUERY_HISTOGRAM_NAME)
    delta_hist = histogram_delta(before_hist, after_hist)

    if delta_hist.total_count <= 0:
        raise ApiRuntimeEvidenceError(
            "no PostgreSQL search-repository queries were observed during the run"
        )

    # Deterministic query-count evidence: cross-check two independently
    # instrumented Prometheus counters (the HTTP middleware and the
    # repository call site) instead of sampling with pg_stat_statements.
    expected_queries = int(round(http_requests_delta))
    observed_queries = int(round(delta_hist.total_count))
    if expected_queries != observed_queries:
        raise ApiRuntimeEvidenceError(
            "contradictory evidence: "
            f'{HTTP_COUNTER_NAME}{{path="{SEARCH_PATH_LABEL}"}} recorded {expected_queries} requests '
            f"but {QUERY_HISTOGRAM_NAME}_count recorded {observed_queries} PostgreSQL repository queries"
        )

    db_p50 = histogram_quantile_ms(delta_hist, 0.50)
    db_p95 = histogram_quantile_ms(delta_hist, 0.95)
    db_p99 = histogram_quantile_ms(delta_hist, 0.99)
    db_mean = (delta_hist.total_sum / delta_hist.total_count) * 1000.0

    resources: dict[str, Any] = {"database_connections": database_connections}
    if resource_receipt is not None:
        resources["api_replica"] = dict(resource_receipt)

    thresholds = contract["thresholds"]
    failures: list[str] = []
    if http_metrics["p95_ms"] > thresholds["http_request_duration_ms"]:
        failures.append(
            f"http_request_duration_ms p95 {http_metrics['p95_ms']:.3f}ms exceeds the "
            f"{thresholds['http_request_duration_ms']:.3f}ms budget"
        )
    if http_metrics["p99_ms"] > thresholds["http_request_duration_p99_ms"]:
        failures.append(
            f"http_request_duration_p99_ms {http_metrics['p99_ms']:.3f}ms exceeds the "
            f"{thresholds['http_request_duration_p99_ms']:.3f}ms budget"
        )
    if http_metrics["failed_rate"] > thresholds["http_request_failed_rate"]:
        failures.append(
            f"http_request_failed_rate {http_metrics['failed_rate']:.4f} exceeds the "
            f"{thresholds['http_request_failed_rate']:.4f} budget"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
        "status": "fail" if failures else "pass",
        "revision": {
            "git_head": git_head,
            "policy_sha256": policy_sha256,
        },
        "scenario": contract["scenario"],
        "metrics": {
            "http": {
                "p50_ms": http_metrics["p50_ms"],
                "p95_ms": http_metrics["p95_ms"],
                "p99_ms": http_metrics["p99_ms"],
                "failed_rate": http_metrics["failed_rate"],
                "total_requests": http_metrics["total_requests"],
            },
            "database": {
                "search_repository_duration_ms": {
                    "p50": db_p50,
                    "p95": db_p95,
                    "p99": db_p99,
                    "mean": db_mean,
                },
                "query_count": {
                    "expected_from_http_requests_total": expected_queries,
                    "observed_from_search_repository_duration_seconds_count": observed_queries,
                },
            },
            "resources": resources,
        },
        "thresholds": thresholds,
        "failures": failures,
        "limitations": [
            "This artifact establishes latency and failure-rate evidence for the exact k6 run and "
            "PostgreSQL-backed dataset it was generated from; it does not establish steady-state "
            "production capacity.",
            "api_replica cpu/memory and database_connections are point samples attached from the "
            "same run and are not yet gated by a blocking threshold (see measurements."
            "api_replica_resources in the performance contract).",
        ],
    }


def verify_report(
    report: Mapping[str, Any], *, expected_git_head: str, expected_policy_sha256: str
) -> None:
    if (
        not isinstance(report, dict)
        or report.get("schema_version") != SCHEMA_VERSION
        or report.get("contract_id") != CONTRACT_ID
    ):
        raise ApiRuntimeEvidenceError("report is not a recognizable api_runtime evidence artifact")
    revision = report.get("revision")
    if not isinstance(revision, dict):
        raise ApiRuntimeEvidenceError("report is missing its revision binding")
    recorded_head = revision.get("git_head")
    recorded_policy_sha256 = revision.get("policy_sha256")
    if recorded_head != expected_git_head:
        raise ApiRuntimeEvidenceError(
            f"report is bound to git HEAD {recorded_head!r}, but the current checkout is at "
            f"{expected_git_head!r}"
        )
    if recorded_policy_sha256 != expected_policy_sha256:
        raise ApiRuntimeEvidenceError(
            "report is bound to a different policies/performance.v1.json revision than the "
            f"current checkout (recorded {recorded_policy_sha256!r}, current "
            f"{expected_policy_sha256!r})"
        )


# --------------------------------------------------------------------------
# Regression fixture: a controlled negative mode that demonstrably fails the
# gate without needing a live API, database, or k6 binary.
# --------------------------------------------------------------------------

_HISTOGRAM_BUCKETS_SECONDS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


def _render_prometheus_fixture(
    *, search_count: int, search_sum_seconds: float, http_search_requests: int
) -> str:
    lines = [
        "# HELP search_repository_duration_seconds fixture",
        "# TYPE search_repository_duration_seconds histogram",
    ]
    for bound in _HISTOGRAM_BUCKETS_SECONDS:
        cumulative = search_count if bound >= _HISTOGRAM_BUCKETS_SECONDS[-1] else 0
        lines.append(f'search_repository_duration_seconds_bucket{{le="{bound}"}} {cumulative}')
    lines.append(f'search_repository_duration_seconds_bucket{{le="+Inf"}} {search_count}')
    lines.append(f"search_repository_duration_seconds_sum {search_sum_seconds}")
    lines.append(f"search_repository_duration_seconds_count {search_count}")
    lines.append(
        f'http_requests_total{{method="GET",path="{SEARCH_PATH_LABEL}",status="200"}} '
        f"{http_search_requests}"
    )
    return "\n".join(lines) + "\n"


def render_regression_fixture(policy: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    """Write a self-consistent (query counts match) but threshold-violating
    fixture set, so `check` against it demonstrates the gate failing closed.
    """
    contract = api_runtime_section(policy)
    scenario = contract["scenario"]
    thresholds = contract["thresholds"]
    output_dir.mkdir(parents=True, exist_ok=True)

    breached_p95 = thresholds["http_request_duration_ms"] * 4.0 + 100.0
    breached_p99 = thresholds["http_request_duration_p99_ms"] * 4.0 + 100.0
    breached_failed_rate = min(1.0, thresholds["http_request_failed_rate"] * 10.0 + 0.5)

    k6_summary = {
        "metrics": {
            "http_req_duration": {
                "values": {
                    "p(50)": breached_p95 / 2.0,
                    "p(95)": breached_p95,
                    "p(99)": breached_p99,
                }
            },
            "http_req_failed": {"values": {"rate": breached_failed_rate}},
            "http_reqs": {"values": {"count": 300}},
        },
        "weltgewebe_scenario": dict(scenario),
    }

    query_count = 100
    metrics_before = _render_prometheus_fixture(
        search_count=0, search_sum_seconds=0.0, http_search_requests=0
    )
    metrics_after = _render_prometheus_fixture(
        search_count=query_count, search_sum_seconds=45.0, http_search_requests=query_count
    )

    paths = {
        "k6_summary": output_dir / "k6-summary.json",
        "metrics_before": output_dir / "metrics-before.prom",
        "metrics_after": output_dir / "metrics-after.prom",
    }
    _atomic_json(paths["k6_summary"], k6_summary)
    _atomic_text(paths["metrics_before"], metrics_before)
    _atomic_text(paths["metrics_after"], metrics_after)
    return paths


# --------------------------------------------------------------------------
# Revision binding
# --------------------------------------------------------------------------


def git_head(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError as exc:
        raise ApiRuntimeEvidenceError(f"cannot invoke git to resolve HEAD: {exc}") from exc
    if result.returncode != 0:
        raise ApiRuntimeEvidenceError(f"git rev-parse HEAD failed: {result.stderr.strip()}")
    sha = result.stdout.strip()
    if not GIT_SHA_RE.fullmatch(sha):
        raise ApiRuntimeEvidenceError(f"git HEAD is not a 40-hex sha: {sha!r}")
    return sha


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _cli_validate(args: argparse.Namespace) -> int:
    policy = load_policy(args.policy)
    api_runtime_section(policy)
    print(
        json.dumps(
            {"schema_version": SCHEMA_VERSION, "status": "pass", "policy": str(args.policy)},
            sort_keys=True,
        )
    )
    return 0


def _cli_check(args: argparse.Namespace) -> int:
    policy = load_policy(args.policy)
    k6_summary = load_k6_summary(args.k6_summary)
    metrics_before_text = _read_text(args.metrics_before, "metrics-before snapshot")
    metrics_after_text = _read_text(args.metrics_after, "metrics-after snapshot")
    resource_receipt = (
        load_resource_receipt(args.resource_receipt) if args.resource_receipt is not None else None
    )
    database_connections = validate_database_connections(args.database_connections)
    head = git_head(REPO_ROOT)
    policy_sha256 = sha256_file(args.policy)

    report = assemble_report(
        policy=policy,
        k6_summary=k6_summary,
        metrics_before_text=metrics_before_text,
        metrics_after_text=metrics_after_text,
        resource_receipt=resource_receipt,
        database_connections=database_connections,
        git_head=head,
        policy_sha256=policy_sha256,
    )
    if args.report is not None:
        _atomic_json(args.report, report)
    sys.stdout.buffer.write(canonical_json_bytes(report))
    if report["status"] != "pass":
        print("api-runtime-evidence: " + "; ".join(report["failures"]), file=sys.stderr)
        return 2
    return 0


def _cli_verify(args: argparse.Namespace) -> int:
    report = _read_json(args.report, "evidence report")
    head = git_head(REPO_ROOT)
    policy_sha256 = sha256_file(args.policy)
    verify_report(report, expected_git_head=head, expected_policy_sha256=policy_sha256)
    print(
        json.dumps(
            {"schema_version": SCHEMA_VERSION, "status": "pass", "report": str(args.report)},
            sort_keys=True,
        )
    )
    return 0


def _cli_regression_fixture(args: argparse.Namespace) -> int:
    policy = load_policy(args.policy)
    paths = render_regression_fixture(policy, args.output_dir)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "files": {name: str(path) for name, path in paths.items()},
        "note": (
            "This fixture is self-consistent (query counts match) but breaches every canonical "
            "api_runtime threshold on purpose. Run `check` against it (with any non-negative "
            "--database-connections and without --resource-receipt) to prove the gate fails "
            "closed; it must exit with status 2."
        ),
    }
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="validate the api_runtime policy contract")

    check = subparsers.add_parser("check", help="assemble and gate an api_runtime evidence artifact")
    check.add_argument("--k6-summary", type=Path, required=True)
    check.add_argument("--metrics-before", type=Path, required=True)
    check.add_argument("--metrics-after", type=Path, required=True)
    check.add_argument("--resource-receipt", type=Path, default=None)
    check.add_argument("--database-connections", type=int, required=True)
    check.add_argument("--report", type=Path, default=None)

    verify = subparsers.add_parser("verify", help="re-bind a previously assembled report")
    verify.add_argument("--report", type=Path, required=True)

    regression = subparsers.add_parser(
        "regression-fixture", help="write a threshold-violating fixture that proves the gate fails"
    )
    regression.add_argument("--output-dir", type=Path, required=True)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return _cli_validate(args)
        if args.command == "check":
            return _cli_check(args)
        if args.command == "verify":
            return _cli_verify(args)
        if args.command == "regression-fixture":
            return _cli_regression_fixture(args)
        parser.error(f"unsupported command {args.command}")
        return 2
    except ApiRuntimeEvidenceError as exc:
        print(f"api-runtime-evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

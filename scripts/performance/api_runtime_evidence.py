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
     and PostgreSQL connections with scripts/performance/
     postgres_connection_sampler.py (--database-connections-receipt).
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
import importlib.util
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

try:
    from scripts.performance import api_runtime_live_binding as live_binding
except ModuleNotFoundError:  # direct script execution: sibling module is on sys.path
    import api_runtime_live_binding as live_binding

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = Path("policies/performance.v1.json")

SCHEMA_VERSION = 1
CONTRACT_ID = "weltgewebe-performance-v1#/measurements/api_runtime"
RESOURCE_RECEIPT_CONTRACT = "api-replica-resource-sample-v2"
DATABASE_CONNECTION_RECEIPT_CONTRACT = "postgres-connection-sample-v1"
DOMAIN_SCALE_GENERATOR = "scripts/performance/domain_scale.py"
BUILD_INFO_NAME = "build_info"
DATASET_MANIFEST_SUMMARY_KEY = "weltgewebe_dataset_manifest_sha256"

REQUIRED_SCENARIO_FIELDS = (
    "virtual_users",
    "duration_seconds",
    "dataset_profile",
    "concurrency_profile",
    "search_query",
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
    search_query = value["search_query"]
    if not isinstance(vus, int) or isinstance(vus, bool) or vus < 1:
        raise ApiRuntimeEvidenceError(f"{label}.virtual_users must be a positive integer")
    if not isinstance(duration, int) or isinstance(duration, bool) or duration < 1:
        raise ApiRuntimeEvidenceError(f"{label}.duration_seconds must be a positive integer")
    if not isinstance(dataset_profile, str) or not dataset_profile:
        raise ApiRuntimeEvidenceError(f"{label}.dataset_profile must be a non-empty string")
    if not isinstance(concurrency_profile, str) or not concurrency_profile:
        raise ApiRuntimeEvidenceError(f"{label}.concurrency_profile must be a non-empty string")
    if not isinstance(search_query, str) or not search_query:
        raise ApiRuntimeEvidenceError(f"{label}.search_query must be a non-empty string")
    return {
        "virtual_users": vus,
        "duration_seconds": duration,
        "dataset_profile": dataset_profile,
        "concurrency_profile": concurrency_profile,
        "search_query": search_query,
    }


def api_runtime_section(policy: Mapping[str, Any]) -> dict[str, Any]:
    section = policy["measurements"].get("api_runtime")
    if not isinstance(section, dict):
        raise ApiRuntimeEvidenceError("performance contract is missing measurements.api_runtime")

    scenario = _scalar_scenario(section.get("scenario"), "measurements.api_runtime.scenario")

    dataset_profile = scenario["dataset_profile"]
    prefix = "domain-scale-"
    if not dataset_profile.startswith(prefix) or dataset_profile == prefix:
        raise ApiRuntimeEvidenceError(
            "measurements.api_runtime.scenario.dataset_profile must name a domain-scale profile"
        )
    profile = dataset_profile.removeprefix(prefix)

    database_scale = policy["measurements"].get("database_scale")
    if not isinstance(database_scale, dict):
        raise ApiRuntimeEvidenceError(
            "performance contract is missing measurements.database_scale for dataset binding"
        )
    generator = database_scale.get("runner")
    config = database_scale.get("config")
    profiles = database_scale.get("profiles")
    if generator != DOMAIN_SCALE_GENERATOR:
        raise ApiRuntimeEvidenceError(
            f"measurements.database_scale.runner must be {DOMAIN_SCALE_GENERATOR!r}"
        )
    if not isinstance(config, str) or not config:
        raise ApiRuntimeEvidenceError("measurements.database_scale.config must be a path")
    if (
        not isinstance(profiles, list)
        or any(not isinstance(item, str) or not item for item in profiles)
        or profile not in profiles
    ):
        raise ApiRuntimeEvidenceError(
            "api_runtime dataset profile must be present in measurements.database_scale.profiles"
        )

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

    return {
        "scenario": scenario,
        "dataset_proof": {
            "generator": generator,
            "config": config,
            "profile": profile,
        },
        "thresholds": thresholds,
    }


def _load_domain_scale_module(generator_path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("weltgewebe_domain_scale", generator_path)
    if spec is None or spec.loader is None:
        raise ApiRuntimeEvidenceError(f"cannot load dataset generator {generator_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (OSError, ImportError, RuntimeError) as exc:
        raise ApiRuntimeEvidenceError(f"cannot load dataset generator {generator_path}: {exc}") from exc
    return module


def load_dataset_binding(
    manifest_path: Path,
    contract: Mapping[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    proof = contract.get("dataset_proof")
    if not isinstance(proof, dict):
        raise ApiRuntimeEvidenceError("api_runtime contract is missing dataset_proof")

    generator_path = Path(str(proof["generator"]))
    if not generator_path.is_absolute():
        generator_path = repo_root / generator_path
    config_path = Path(str(proof["config"]))
    if not config_path.is_absolute():
        config_path = repo_root / config_path
    if not generator_path.is_file():
        raise ApiRuntimeEvidenceError(f"dataset generator is missing: {generator_path}")
    if not config_path.is_file():
        raise ApiRuntimeEvidenceError(f"dataset config is missing: {config_path}")

    module = _load_domain_scale_module(generator_path)
    try:
        _, manifest = module.load_bound_manifest(manifest_path, config_path)
    except module.DomainScaleError as exc:
        raise ApiRuntimeEvidenceError(f"dataset manifest is not valid: {exc}") from exc
    if manifest.get("profile") != proof.get("profile"):
        raise ApiRuntimeEvidenceError(
            "dataset manifest profile does not match the derived measurements.database_scale profile"
        )

    files = manifest["files"]
    return {
        "manifest_sha256": sha256_file(manifest_path),
        "generator": manifest["generator"],
        "config_sha256": manifest["config_sha256"],
        "database_schema": manifest["database_schema"],
        "profile": manifest["profile"],
        "counts": dict(manifest["counts"]),
        "files": {
            "nodes": dict(files["nodes"]),
            "edges": dict(files["edges"]),
        },
    }


def extract_dataset_manifest_sha256(summary: Mapping[str, Any]) -> str:
    digest = summary.get(DATASET_MANIFEST_SUMMARY_KEY)
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        raise ApiRuntimeEvidenceError(
            f"k6 summary is missing a valid {DATASET_MANIFEST_SUMMARY_KEY} binding"
        )
    return digest


def extract_runtime_workload_bindings(summary: Mapping[str, Any]) -> dict[str, str]:
    search_query = summary.get(live_binding.SEARCH_QUERY_SUMMARY_KEY)
    if not isinstance(search_query, str) or not search_query:
        raise ApiRuntimeEvidenceError(
            f"k6 summary is missing a valid {live_binding.SEARCH_QUERY_SUMMARY_KEY} binding"
        )
    run_id = summary.get(live_binding.RUN_ID_SUMMARY_KEY)
    if not isinstance(run_id, str) or not live_binding.RUN_ID_RE.fullmatch(run_id):
        raise ApiRuntimeEvidenceError(
            f"k6 summary is missing a valid {live_binding.RUN_ID_SUMMARY_KEY} binding"
        )
    k6_image = summary.get(live_binding.K6_IMAGE_SUMMARY_KEY)
    if not isinstance(k6_image, str) or not live_binding.DIGEST_IMAGE_RE.fullmatch(k6_image):
        raise ApiRuntimeEvidenceError(
            f"k6 summary is missing a digest-bound {live_binding.K6_IMAGE_SUMMARY_KEY}"
        )
    return {
        "search_query": search_query,
        "run_id": run_id,
        "k6_image_reference": k6_image,
    }


def load_live_runtime_binding(path: Path) -> dict[str, Any]:
    parsed = _read_json(path, "api runtime live binding")
    try:
        return live_binding.validate_receipt(parsed)
    except live_binding.LiveBindingError as exc:
        raise ApiRuntimeEvidenceError(f"api runtime live binding is invalid: {exc}") from exc


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


def measured_api_commit(families: PrometheusFamilies) -> str:
    samples = families.get(BUILD_INFO_NAME)
    if not samples or len(samples) != 1:
        raise ApiRuntimeEvidenceError(
            "Prometheus build_info must contain exactly one sample for revision binding"
        )
    labels, value = samples[0]
    if not math.isfinite(value) or value != 1.0:
        raise ApiRuntimeEvidenceError("Prometheus build_info must have the gauge value 1")
    commit = labels.get("commit")
    if not isinstance(commit, str) or not GIT_SHA_RE.fullmatch(commit):
        raise ApiRuntimeEvidenceError(
            "Prometheus build_info commit must be a release-bound 40-hex git SHA"
        )
    return commit


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
                raise ApiRuntimeEvidenceError(
                    "requested histogram quantile falls in the open-ended +Inf bucket; "
                    "finite latency is not established"
                )
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
    if parsed.get("schema_version") != 2:
        raise ApiRuntimeEvidenceError("container resource receipt must use schema_version 2")
    if parsed.get("contract") != RESOURCE_RECEIPT_CONTRACT:
        raise ApiRuntimeEvidenceError(
            f"container resource receipt must use contract {RESOURCE_RECEIPT_CONTRACT!r}"
        )
    run_id = parsed.get("run_id")
    if not isinstance(run_id, str) or not live_binding.RUN_ID_RE.fullmatch(run_id):
        raise ApiRuntimeEvidenceError("container resource receipt run_id is invalid")
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
        "run_id": run_id,
        "container_name": container_name,
        "sample_count": sample_count,
        "peak_cpu_percent": float(cpu_percent),
        "peak_memory_bytes": memory_bytes,
    }


def load_database_connection_receipt(path: Path) -> dict[str, Any]:
    parsed = _read_json(path, "PostgreSQL connection receipt")
    if not isinstance(parsed, dict):
        raise ApiRuntimeEvidenceError("PostgreSQL connection receipt must be a JSON object")
    if parsed.get("schema_version") != 1:
        raise ApiRuntimeEvidenceError("PostgreSQL connection receipt must use schema_version 1")
    if parsed.get("contract") != DATABASE_CONNECTION_RECEIPT_CONTRACT:
        raise ApiRuntimeEvidenceError(
            f"PostgreSQL connection receipt must use contract {DATABASE_CONNECTION_RECEIPT_CONTRACT!r}"
        )
    normalized = {
        "run_id": parsed.get("run_id"),
        "database_container": parsed.get("database_container"),
        "max_connections": parsed.get("max_connections"),
        "sample_count": parsed.get("sample_count"),
        "samples": parsed.get("samples"),
    }
    return validate_normalized_database_connection_receipt(normalized)


def validate_normalized_resource_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "run_id",
        "container_name",
        "sample_count",
        "peak_cpu_percent",
        "peak_memory_bytes",
    }:
        raise ApiRuntimeEvidenceError(
            "normalized API replica resource evidence has an invalid shape"
        )
    run_id = value["run_id"]
    if not isinstance(run_id, str) or not live_binding.RUN_ID_RE.fullmatch(run_id):
        raise ApiRuntimeEvidenceError("API replica resource evidence run_id is invalid")
    container_name = value["container_name"]
    sample_count = value["sample_count"]
    cpu_percent = value["peak_cpu_percent"]
    memory_bytes = value["peak_memory_bytes"]
    if not isinstance(container_name, str) or not container_name:
        raise ApiRuntimeEvidenceError("API replica resource evidence must name a container")
    if not isinstance(sample_count, int) or isinstance(sample_count, bool) or sample_count < 1:
        raise ApiRuntimeEvidenceError("API replica resource evidence must contain samples")
    if (
        not isinstance(cpu_percent, (int, float))
        or isinstance(cpu_percent, bool)
        or not math.isfinite(cpu_percent)
        or cpu_percent < 0
    ):
        raise ApiRuntimeEvidenceError("API replica peak_cpu_percent is invalid")
    if not isinstance(memory_bytes, int) or isinstance(memory_bytes, bool) or memory_bytes < 0:
        raise ApiRuntimeEvidenceError("API replica peak_memory_bytes is invalid")
    return dict(value)


def validate_normalized_database_connection_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "run_id",
        "database_container",
        "max_connections",
        "sample_count",
        "samples",
    }:
        raise ApiRuntimeEvidenceError("normalized PostgreSQL connection evidence has an invalid shape")
    run_id = value["run_id"]
    if not isinstance(run_id, str) or not live_binding.RUN_ID_RE.fullmatch(run_id):
        raise ApiRuntimeEvidenceError("PostgreSQL connection evidence run_id is invalid")
    database_container = value["database_container"]
    if not isinstance(database_container, str) or not live_binding.CONTAINER_RE.fullmatch(
        database_container
    ):
        raise ApiRuntimeEvidenceError("PostgreSQL connection evidence container is invalid")
    sample_count = value["sample_count"]
    samples = value["samples"]
    max_connections = value["max_connections"]
    if not isinstance(sample_count, int) or isinstance(sample_count, bool) or sample_count < 1:
        raise ApiRuntimeEvidenceError("PostgreSQL connection evidence must contain samples")
    if not isinstance(samples, list) or len(samples) != sample_count:
        raise ApiRuntimeEvidenceError(
            "PostgreSQL connection evidence samples must match sample_count"
        )
    for sample in samples:
        if not isinstance(sample, int) or isinstance(sample, bool) or sample < 0:
            raise ApiRuntimeEvidenceError("PostgreSQL connection evidence contains an invalid sample")
    if (
        not isinstance(max_connections, int)
        or isinstance(max_connections, bool)
        or max_connections < 0
        or max_connections != max(samples)
    ):
        raise ApiRuntimeEvidenceError(
            "PostgreSQL connection evidence max_connections must equal max(samples)"
        )
    return {
        "run_id": run_id,
        "database_container": database_container,
        "max_connections": max_connections,
        "sample_count": sample_count,
        "samples": list(samples),
    }


def threshold_failures(
    http_metrics: Mapping[str, Any], thresholds: Mapping[str, float]
) -> list[str]:
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
    return failures


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
    dataset_binding: Mapping[str, Any],
    runtime_binding: Mapping[str, Any] | None,
    database_connection_receipt: Mapping[str, Any] | None,
    git_head: str,
    policy_sha256: str,
) -> dict[str, Any]:
    if not GIT_SHA_RE.fullmatch(git_head):
        raise ApiRuntimeEvidenceError(f"git_head must be a 40-hex sha: {git_head!r}")
    if not SHA256_RE.fullmatch(policy_sha256):
        raise ApiRuntimeEvidenceError(f"policy_sha256 must be a 64-hex sha256: {policy_sha256!r}")
    if resource_receipt is None:
        raise ApiRuntimeEvidenceError(
            "resource_receipt is required so api_runtime evidence cannot pass without "
            "API replica CPU/memory measurement"
        )
    normalized_resource_receipt = validate_normalized_resource_receipt(resource_receipt)
    if database_connection_receipt is None:
        raise ApiRuntimeEvidenceError(
            "database_connection_receipt is required so DB connection evidence cannot be reused blindly"
        )
    normalized_database_connection_receipt = validate_normalized_database_connection_receipt(
        database_connection_receipt
    )
    if runtime_binding is None:
        raise ApiRuntimeEvidenceError(
            "runtime_binding is required so fixture hashes cannot pass without live database/search binding"
        )
    try:
        normalized_runtime_binding = live_binding.validate_receipt(runtime_binding)
    except live_binding.LiveBindingError as exc:
        raise ApiRuntimeEvidenceError(f"api runtime live binding is invalid: {exc}") from exc

    if normalized_runtime_binding["git_head"] != git_head:
        raise ApiRuntimeEvidenceError(
            "api runtime live binding git_head does not match the evidence checkout revision"
        )
    runtime_dataset = normalized_runtime_binding["dataset"]
    if runtime_dataset["manifest_sha256"] != dataset_binding.get("manifest_sha256"):
        raise ApiRuntimeEvidenceError(
            "api runtime live binding manifest digest does not match the validated fixture"
        )
    expected_node_count = dataset_binding.get("counts", {}).get("nodes")
    if runtime_dataset["domain_nodes_count"] != expected_node_count:
        raise ApiRuntimeEvidenceError(
            "api runtime live binding domain-node count does not match the validated fixture"
        )
    current_candidate_limit, current_candidate_source_sha256 = live_binding.candidate_limit_binding(
        REPO_ROOT
    )
    runtime_search = normalized_runtime_binding["search"]
    if (
        runtime_search["candidate_limit_contract"] != current_candidate_limit
        or runtime_search["candidate_limit_source_sha256"] != current_candidate_source_sha256
    ):
        raise ApiRuntimeEvidenceError(
            "api runtime live binding search-candidate safety contract does not match this checkout"
        )
    runtime_identity = normalized_runtime_binding["runtime"]
    if runtime_identity["api_commit"] != git_head:
        raise ApiRuntimeEvidenceError(
            "api runtime live binding measured API commit does not match git HEAD"
        )
    run_id = normalized_runtime_binding["run_id"]
    if normalized_resource_receipt["run_id"] != run_id:
        raise ApiRuntimeEvidenceError(
            "API resource receipt run_id does not match the live runtime binding"
        )
    if normalized_resource_receipt["container_name"] != runtime_identity["api_container"]["name"]:
        raise ApiRuntimeEvidenceError(
            "API resource receipt container does not match the measured API container"
        )
    if normalized_database_connection_receipt["run_id"] != run_id:
        raise ApiRuntimeEvidenceError(
            "PostgreSQL connection receipt run_id does not match the live runtime binding"
        )
    if (
        normalized_database_connection_receipt["database_container"]
        != runtime_identity["postgres_container"]["name"]
    ):
        raise ApiRuntimeEvidenceError(
            "PostgreSQL connection receipt container does not match the measured database container"
        )

    contract = api_runtime_section(policy)
    declared_scenario = extract_declared_scenario(k6_summary)
    if declared_scenario != contract["scenario"]:
        raise ApiRuntimeEvidenceError(
            "k6 summary scenario does not match measurements.api_runtime.scenario in the "
            f"performance contract: recorded={declared_scenario!r} canonical={contract['scenario']!r}"
        )

    dataset_manifest_sha256 = extract_dataset_manifest_sha256(k6_summary)
    workload_binding = extract_runtime_workload_bindings(k6_summary)
    if workload_binding["run_id"] != run_id:
        raise ApiRuntimeEvidenceError(
            "k6 run_id does not match the live runtime binding"
        )
    if workload_binding["search_query"] != runtime_search["query"]:
        raise ApiRuntimeEvidenceError(
            "k6 search query does not match the query proven by the live runtime binding"
        )
    if workload_binding["k6_image_reference"] != runtime_identity["k6_image_reference"]:
        raise ApiRuntimeEvidenceError(
            "k6 image identity does not match the digest proven by the live runtime binding"
        )
    recorded_dataset_sha256 = dataset_binding.get("manifest_sha256")
    if dataset_manifest_sha256 != recorded_dataset_sha256:
        raise ApiRuntimeEvidenceError(
            "k6 summary dataset manifest digest does not match the validated fixture manifest"
        )
    if dataset_binding.get("profile") != contract["dataset_proof"]["profile"]:
        raise ApiRuntimeEvidenceError(
            "dataset binding profile does not match the performance contract"
        )

    http_metrics = extract_http_metrics(k6_summary)

    before_families = parse_prometheus_text(metrics_before_text)
    after_families = parse_prometheus_text(metrics_after_text)

    before_api_commit = measured_api_commit(before_families)
    after_api_commit = measured_api_commit(after_families)
    if before_api_commit != after_api_commit:
        raise ApiRuntimeEvidenceError(
            "measured API build_info commit changed between the before/after scrapes"
        )
    if before_api_commit != git_head:
        raise ApiRuntimeEvidenceError(
            f"measured API build_info commit {before_api_commit!r} does not match git HEAD "
            f"{git_head!r}"
        )

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

    resources: dict[str, Any] = {
        "api_replica": normalized_resource_receipt,
        "postgres_connections": normalized_database_connection_receipt,
    }

    thresholds = contract["thresholds"]
    failures = threshold_failures(http_metrics, thresholds)

    return {
        "schema_version": SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
        "status": "fail" if failures else "pass",
        "revision": {
            "git_head": git_head,
            "measured_api_commit": before_api_commit,
            "policy_sha256": policy_sha256,
        },
        "dataset": dict(dataset_binding),
        "runtime_binding": normalized_runtime_binding,
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
            "This artifact establishes latency and failure-rate evidence for the exact k6 run "
            "against the measured API revision and a live binding that content-hashes domain_nodes "
            "against the deterministic fixture and binds the active search generation/projections; "
            "it does not establish steady-state production capacity or production data distribution.",
            "api_replica peak_cpu_percent/peak_memory_bytes and PostgreSQL connection samples are "
            "bound to the same explicit run_id as k6 and the live-runtime receipt and are not yet "
            "gated by a blocking threshold (see measurements.api_replica_resources in the contract).",
            "dataset is bound both to the canonical domain-scale fixture manifest and to the isolated "
            "live database/search state recorded in runtime_binding; this is experiment-data evidence, "
            "not evidence about production contents, production distribution, or future revisions.",
        ],
    }


def _finite_nonnegative(value: Any, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < 0
    ):
        raise ApiRuntimeEvidenceError(f"report {label} must be a finite number >= 0")
    return float(value)


def _validate_complete_report(
    report: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    expected_git_head: str,
    expected_policy_sha256: str,
    expected_dataset_binding: Mapping[str, Any],
) -> None:
    expected_keys = {
        "schema_version",
        "contract_id",
        "status",
        "revision",
        "dataset",
        "runtime_binding",
        "scenario",
        "metrics",
        "thresholds",
        "failures",
        "limitations",
    }
    if not isinstance(report, dict) or set(report) != expected_keys:
        raise ApiRuntimeEvidenceError(
            "report does not contain the complete api_runtime evidence schema"
        )
    if report.get("schema_version") != SCHEMA_VERSION or report.get("contract_id") != CONTRACT_ID:
        raise ApiRuntimeEvidenceError("report is not a recognizable api_runtime evidence artifact")

    contract = api_runtime_section(policy)
    revision = report.get("revision")
    if not isinstance(revision, dict) or set(revision) != {
        "git_head",
        "measured_api_commit",
        "policy_sha256",
    }:
        raise ApiRuntimeEvidenceError("report is missing its complete revision binding")
    recorded_head = revision.get("git_head")
    measured_commit = revision.get("measured_api_commit")
    recorded_policy_sha256 = revision.get("policy_sha256")
    if recorded_head != expected_git_head:
        raise ApiRuntimeEvidenceError(
            f"report is bound to git HEAD {recorded_head!r}, but the current checkout is at "
            f"{expected_git_head!r}"
        )
    if measured_commit != expected_git_head:
        raise ApiRuntimeEvidenceError(
            f"report measured API commit {measured_commit!r} does not match current git HEAD "
            f"{expected_git_head!r}"
        )
    if recorded_policy_sha256 != expected_policy_sha256:
        raise ApiRuntimeEvidenceError(
            "report is bound to a different policies/performance.v1.json revision than the "
            f"current checkout (recorded {recorded_policy_sha256!r}, current "
            f"{expected_policy_sha256!r})"
        )
    if report.get("scenario") != contract["scenario"]:
        raise ApiRuntimeEvidenceError("report scenario does not match the current performance contract")
    if report.get("dataset") != expected_dataset_binding:
        raise ApiRuntimeEvidenceError(
            "report dataset binding does not match the validated fixture manifest"
        )
    try:
        report_runtime_binding = live_binding.validate_receipt(report.get("runtime_binding"))
    except live_binding.LiveBindingError as exc:
        raise ApiRuntimeEvidenceError(f"report runtime binding is invalid: {exc}") from exc
    if report_runtime_binding["git_head"] != expected_git_head:
        raise ApiRuntimeEvidenceError("report runtime binding does not match current git HEAD")
    if (
        report_runtime_binding["dataset"]["manifest_sha256"]
        != expected_dataset_binding.get("manifest_sha256")
        or report_runtime_binding["dataset"]["domain_nodes_count"]
        != expected_dataset_binding.get("counts", {}).get("nodes")
    ):
        raise ApiRuntimeEvidenceError(
            "report runtime binding does not match the validated dataset binding"
        )
    current_candidate_limit, current_candidate_source_sha256 = live_binding.candidate_limit_binding(
        REPO_ROOT
    )
    if (
        report_runtime_binding["search"]["candidate_limit_contract"] != current_candidate_limit
        or report_runtime_binding["search"]["candidate_limit_source_sha256"]
        != current_candidate_source_sha256
    ):
        raise ApiRuntimeEvidenceError(
            "report runtime binding candidate safety contract does not match current checkout"
        )
    if report.get("thresholds") != contract["thresholds"]:
        raise ApiRuntimeEvidenceError(
            "report thresholds do not match the current performance contract"
        )

    metrics = report.get("metrics")
    if not isinstance(metrics, dict) or set(metrics) != {"http", "database", "resources"}:
        raise ApiRuntimeEvidenceError("report metrics have an invalid shape")
    http = metrics["http"]
    if not isinstance(http, dict) or set(http) != {
        "p50_ms",
        "p95_ms",
        "p99_ms",
        "failed_rate",
        "total_requests",
    }:
        raise ApiRuntimeEvidenceError("report HTTP metrics have an invalid shape")
    p50 = _finite_nonnegative(http["p50_ms"], "metrics.http.p50_ms")
    p95 = _finite_nonnegative(http["p95_ms"], "metrics.http.p95_ms")
    p99 = _finite_nonnegative(http["p99_ms"], "metrics.http.p99_ms")
    if not p50 <= p95 <= p99:
        raise ApiRuntimeEvidenceError("report HTTP percentiles must be monotonic")
    failed_rate = _finite_nonnegative(http["failed_rate"], "metrics.http.failed_rate")
    if failed_rate > 1.0:
        raise ApiRuntimeEvidenceError("report metrics.http.failed_rate must be <= 1")
    total_requests = http["total_requests"]
    if not isinstance(total_requests, int) or isinstance(total_requests, bool) or total_requests < 1:
        raise ApiRuntimeEvidenceError(
            "report metrics.http.total_requests must be a positive integer"
        )

    database = metrics["database"]
    if not isinstance(database, dict) or set(database) != {
        "search_repository_duration_ms",
        "query_count",
    }:
        raise ApiRuntimeEvidenceError("report database metrics have an invalid shape")
    duration = database["search_repository_duration_ms"]
    if not isinstance(duration, dict) or set(duration) != {"p50", "p95", "p99", "mean"}:
        raise ApiRuntimeEvidenceError("report database duration metrics have an invalid shape")
    db_p50 = _finite_nonnegative(duration["p50"], "database duration p50")
    db_p95 = _finite_nonnegative(duration["p95"], "database duration p95")
    db_p99 = _finite_nonnegative(duration["p99"], "database duration p99")
    _finite_nonnegative(duration["mean"], "database duration mean")
    if not db_p50 <= db_p95 <= db_p99:
        raise ApiRuntimeEvidenceError("report database percentiles must be monotonic")

    query_count = database["query_count"]
    if not isinstance(query_count, dict) or set(query_count) != {
        "expected_from_http_requests_total",
        "observed_from_search_repository_duration_seconds_count",
    }:
        raise ApiRuntimeEvidenceError("report query-count evidence has an invalid shape")
    expected_queries = query_count["expected_from_http_requests_total"]
    observed_queries = query_count["observed_from_search_repository_duration_seconds_count"]
    for label, value in (("expected", expected_queries), ("observed", observed_queries)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ApiRuntimeEvidenceError(f"report {label} query count must be a positive integer")
    if expected_queries != observed_queries:
        raise ApiRuntimeEvidenceError("report contains contradictory query-count evidence")

    resources = metrics["resources"]
    if not isinstance(resources, dict) or set(resources) != {
        "api_replica",
        "postgres_connections",
    }:
        raise ApiRuntimeEvidenceError("report resource evidence has an invalid shape")
    report_api_resource = validate_normalized_resource_receipt(resources["api_replica"])
    report_db_resource = validate_normalized_database_connection_receipt(
        resources["postgres_connections"]
    )
    report_run_id = report_runtime_binding["run_id"]
    if report_api_resource["run_id"] != report_run_id or report_db_resource["run_id"] != report_run_id:
        raise ApiRuntimeEvidenceError("report resource receipts do not match runtime_binding run_id")
    if (
        report_api_resource["container_name"]
        != report_runtime_binding["runtime"]["api_container"]["name"]
        or report_db_resource["database_container"]
        != report_runtime_binding["runtime"]["postgres_container"]["name"]
    ):
        raise ApiRuntimeEvidenceError("report resource receipts do not match runtime containers")

    recomputed_failures = threshold_failures(http, contract["thresholds"])
    if report.get("failures") != recomputed_failures:
        raise ApiRuntimeEvidenceError(
            "report failure list does not match recomputed threshold results"
        )
    expected_status = "fail" if recomputed_failures else "pass"
    if report.get("status") != expected_status:
        raise ApiRuntimeEvidenceError(
            "report status does not match recomputed threshold results"
        )
    limitations = report.get("limitations")
    if not isinstance(limitations, list) or not limitations or any(
        not isinstance(item, str) or not item for item in limitations
    ):
        raise ApiRuntimeEvidenceError("report limitations must be a non-empty string list")


def verify_report(
    report: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    expected_git_head: str,
    expected_policy_sha256: str,
    expected_dataset_binding: Mapping[str, Any],
) -> None:
    _validate_complete_report(
        report,
        policy=policy,
        expected_git_head=expected_git_head,
        expected_policy_sha256=expected_policy_sha256,
        expected_dataset_binding=expected_dataset_binding,
    )
    if report.get("status") != "pass":
        raise ApiRuntimeEvidenceError(
            f"report is revision-bound but does not pass the performance gate: {report.get('status')!r}"
        )


# --------------------------------------------------------------------------
# Regression fixture: a controlled negative mode that demonstrably fails the
# gate without needing a live API, database, or k6 binary.
# --------------------------------------------------------------------------

_HISTOGRAM_BUCKETS_SECONDS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


def _render_prometheus_fixture(
    *, search_count: int, search_sum_seconds: float, http_search_requests: int, git_commit: str
) -> str:
    lines = [
        f'build_info{{build_timestamp="fixture",commit="{git_commit}",version="fixture"}} 1',
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


def render_regression_fixture(
    policy: Mapping[str, Any],
    output_dir: Path,
    *,
    dataset_manifest_sha256: str,
    dataset_node_count: int,
    git_commit: str,
) -> dict[str, Path]:
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

    regression_run_id = "api-runtime-regression-fixture"
    regression_search_query = "Scale"
    regression_k6_image = "grafana/k6@sha256:" + ("9" * 64)
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
        DATASET_MANIFEST_SUMMARY_KEY: dataset_manifest_sha256,
        live_binding.SEARCH_QUERY_SUMMARY_KEY: regression_search_query,
        live_binding.RUN_ID_SUMMARY_KEY: regression_run_id,
        live_binding.K6_IMAGE_SUMMARY_KEY: regression_k6_image,
        "weltgewebe_scenario": dict(scenario),
    }

    query_count = 100
    metrics_before = _render_prometheus_fixture(
        search_count=0, search_sum_seconds=0.0, http_search_requests=0, git_commit=git_commit
    )
    metrics_after = _render_prometheus_fixture(
        search_count=query_count,
        search_sum_seconds=45.0,
        http_search_requests=query_count,
        git_commit=git_commit,
    )

    paths = {
        "k6_summary": output_dir / "k6-summary.json",
        "metrics_before": output_dir / "metrics-before.prom",
        "metrics_after": output_dir / "metrics-after.prom",
        "resource_receipt": output_dir / "resource-receipt.json",
        "runtime_binding": output_dir / "runtime-binding.json",
        "database_connection_receipt": output_dir / "database-connections.json",
    }
    _atomic_json(paths["k6_summary"], k6_summary)
    _atomic_text(paths["metrics_before"], metrics_before)
    _atomic_text(paths["metrics_after"], metrics_after)
    _atomic_json(
        paths["resource_receipt"],
        {
            "schema_version": 2,
            "contract": RESOURCE_RECEIPT_CONTRACT,
            "run_id": regression_run_id,
            "container_name": "api-regression-fixture",
            "peaks": {"cpu_percent": 25.0, "memory_bytes": 134217728},
            "sample_count": 30,
        },
    )
    candidate_limit, candidate_source_sha256 = live_binding.candidate_limit_binding(REPO_ROOT)
    active_projection_count = min(candidate_limit, dataset_node_count)
    if active_projection_count < 1:
        raise ApiRuntimeEvidenceError("regression fixture requires at least one dataset node")
    synthetic_content_sha256 = "8" * 64
    synthetic_image_id = "sha256:" + ("7" * 64)
    regression_runtime_binding = {
        "schema_version": live_binding.SCHEMA_VERSION,
        "contract": live_binding.CONTRACT,
        "run_id": regression_run_id,
        "git_head": git_commit,
        "dataset": {
            "manifest_sha256": dataset_manifest_sha256,
            "domain_nodes_count": dataset_node_count,
            "fixture_nodes_content_sha256": synthetic_content_sha256,
            "database_nodes_content_sha256": synthetic_content_sha256,
        },
        "search": {
            "query": regression_search_query,
            "mode": "lexical_fallback",
            "generation_id": "regression-fixture-generation",
            "candidate_limit_contract": candidate_limit,
            "candidate_limit_source": str(live_binding.CANDIDATE_LIMIT_SOURCE),
            "candidate_limit_source_sha256": candidate_source_sha256,
            "expected_nodes": active_projection_count,
            "completed_nodes": active_projection_count,
            "active_projection_count": active_projection_count,
            "fixture_projection_content_sha256": synthetic_content_sha256,
            "database_projection_content_sha256": synthetic_content_sha256,
            "sampled_items": [{"id": "fixture-node", "title": "Scale fixture node"}],
        },
        "runtime": {
            "api_commit": git_commit,
            "api_container": {
                "name": "api-regression-fixture",
                "image_reference": "fixture/api@sha256:" + ("6" * 64),
                "image_id": synthetic_image_id,
            },
            "postgres_container": {
                "name": "db-regression-fixture",
                "image_reference": "fixture/postgres@sha256:" + ("5" * 64),
                "image_id": synthetic_image_id,
            },
            "k6_image_reference": regression_k6_image,
        },
    }
    try:
        regression_runtime_binding = live_binding.validate_receipt(regression_runtime_binding)
    except live_binding.LiveBindingError as exc:
        raise ApiRuntimeEvidenceError(f"cannot build regression runtime binding: {exc}") from exc
    _atomic_json(paths["runtime_binding"], regression_runtime_binding)
    _atomic_json(
        paths["database_connection_receipt"],
        {
            "schema_version": 1,
            "contract": DATABASE_CONNECTION_RECEIPT_CONTRACT,
            "run_id": regression_run_id,
            "database_container": "db-regression-fixture",
            "max_connections": 5,
            "sample_count": 3,
            "samples": [4, 5, 4],
        },
    )
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
    resource_receipt = load_resource_receipt(args.resource_receipt)
    runtime_binding = load_live_runtime_binding(args.runtime_binding)
    database_connection_receipt = load_database_connection_receipt(
        args.database_connections_receipt
    )
    dataset_binding = load_dataset_binding(args.dataset_manifest, api_runtime_section(policy))
    head = git_head(REPO_ROOT)
    policy_sha256 = sha256_file(args.policy)

    report = assemble_report(
        policy=policy,
        k6_summary=k6_summary,
        metrics_before_text=metrics_before_text,
        metrics_after_text=metrics_after_text,
        resource_receipt=resource_receipt,
        dataset_binding=dataset_binding,
        runtime_binding=runtime_binding,
        database_connection_receipt=database_connection_receipt,
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
    policy = load_policy(args.policy)
    dataset_binding = load_dataset_binding(args.dataset_manifest, api_runtime_section(policy))
    head = git_head(REPO_ROOT)
    policy_sha256 = sha256_file(args.policy)
    verify_report(
        report,
        policy=policy,
        expected_git_head=head,
        expected_policy_sha256=policy_sha256,
        expected_dataset_binding=dataset_binding,
    )
    print(
        json.dumps(
            {"schema_version": SCHEMA_VERSION, "status": "pass", "report": str(args.report)},
            sort_keys=True,
        )
    )
    return 0


def _cli_regression_fixture(args: argparse.Namespace) -> int:
    policy = load_policy(args.policy)
    dataset_binding = load_dataset_binding(args.dataset_manifest, api_runtime_section(policy))
    paths = render_regression_fixture(
        policy,
        args.output_dir,
        dataset_manifest_sha256=dataset_binding["manifest_sha256"],
        dataset_node_count=dataset_binding["counts"]["nodes"],
        git_commit=git_head(REPO_ROOT),
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "files": {name: str(path) for name, path in paths.items()},
        "note": (
            "This fixture is self-consistent (query counts match) but breaches every canonical "
            "api_runtime threshold on purpose. Run `check` against it with the generated "
            "--resource-receipt, --runtime-binding, and --database-connections-receipt "
            "to prove the "
            "gate fails closed; it must exit with status 2."
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
    check.add_argument("--resource-receipt", type=Path, required=True)
    check.add_argument("--dataset-manifest", type=Path, required=True)
    check.add_argument("--runtime-binding", type=Path, required=True)
    check.add_argument("--database-connections-receipt", type=Path, required=True)
    check.add_argument("--report", type=Path, default=None)

    verify = subparsers.add_parser("verify", help="re-bind a previously assembled report")
    verify.add_argument("--report", type=Path, required=True)
    verify.add_argument("--dataset-manifest", type=Path, required=True)

    regression = subparsers.add_parser(
        "regression-fixture", help="write a threshold-violating fixture that proves the gate fails"
    )
    regression.add_argument("--output-dir", type=Path, required=True)
    regression.add_argument("--dataset-manifest", type=Path, required=True)

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

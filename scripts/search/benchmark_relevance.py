"""Reproducible synthetic relevance benchmark for Weltgewebe Semantic Search v1.

The checked-in quality proof never stores embeddings. CI can validate the
synthetic corpus, lexical baselines, model identities, quality metrics and the
selection decision without requiring Ollama or network access.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import statistics
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from scripts.search.validate_relevance_goldset import (
    DEFAULT_DATASET,
    DEFAULT_SCHEMA,
    ValidationError,
    load_json_object,
    validate_goldset,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULT = ROOT / "contracts/search/examples/relevance-benchmark.heim-pc.json"
BENCHMARK_REVISION = "semantic-search-benchmark-v1"
DEFAULT_MODELS = ("qwen3-embedding:0.6b", "qwen3-embedding:4b", "qwen3-embedding:8b")
RANK_CLASSES = {
    "exact_title": 0,
    "exact_tag": 1,
    "title_prefix": 2,
    "typo": 3,
    "full_text": 4,
    "semantic": 5,
}
STOP_WORDS = {
    "aber", "als", "am", "an", "auch", "auf", "aus", "bei", "bin", "bis",
    "das", "dass", "dem", "den", "der", "des", "die", "ein", "eine", "einem",
    "einen", "einer", "es", "etwas", "für", "gegen", "gemeinsam", "hat", "ich",
    "im", "in", "ist", "kann", "man", "mein", "meine", "mit", "möchte", "nach",
    "nicht", "nur", "oder", "ohne", "sich", "sie", "soll", "um", "und", "von",
    "vor", "was", "wenn", "wer", "wie", "will", "wir", "wo", "zu", "zum", "zur",
}
RAW_VECTOR_KEYS = {"embedding", "embeddings", "vector", "vectors"}
MAX_OLLAMA_RESPONSE_BYTES = 32 * 1024 * 1024
DOES_NOT_ESTABLISH = (
    "production relevance",
    "PostgreSQL FTS or pg_trgm parity",
    "pgvector availability",
    "runtime integration",
    "public live proof",
    "SemantAH archive authority",
    "independent reproduction of Ollama outputs in CI",
    "performance timings as deterministic CI evidence",
)


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).split())


def client_lower(text: str) -> str:
    """Approximate JavaScript trim().toLocaleLowerCase("de-DE") without token rewriting."""

    return text.strip().lower()


def tokens(text: str) -> set[str]:
    return {token for token in normalize(text).split() if len(token) >= 2 and token not in STOP_WORDS}


def trigrams(text: str) -> set[str]:
    value = f"  {normalize(text)} "
    return {value[index : index + 3] for index in range(max(0, len(value) - 2))}


def trigram_similarity(left: str, right: str) -> float:
    left_set = trigrams(left)
    right_set = trigrams(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("embedding dimensions differ or are empty")
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


def node_document(node: dict[str, Any]) -> str:
    return "\n".join(
        (
            f"Titel: {node['title']}",
            f"Kurzbeschreibung: {node['summary']}",
            f"Information: {node['body']}",
            f"Tags: {', '.join(node['tags'])}",
            f"Art: {node['kind']}",
            f"Sprache: {node['language']}",
        )
    )


def query_document(query: str) -> str:
    return "Aufgabe: Finde den relevantesten sichtbaren Weltgewebe-Knoten.\nAnfrage: " + query


def node_by_id(dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {node["id"]: node for node in dataset["nodes"]}


def candidate_nodes(dataset: dict[str, Any], case: dict[str, Any]) -> list[dict[str, Any]]:
    lookup = node_by_id(dataset)
    return [lookup[node_id] for node_id in case["visibility_context"]["visible_node_ids"]]


def current_substring_rank(dataset: dict[str, Any], case: dict[str, Any]) -> list[str]:
    """Mirror deriveSearchResults: visible input order, whole-query substring, cap 10."""

    query = client_lower(case["query"])
    result: list[str] = []
    for node in candidate_nodes(dataset, case):
        searchable_terms = [node["title"], node["summary"], *node["tags"], "Knoten", node["kind"]]
        if any(query in client_lower(term) for term in searchable_terms):
            result.append(node["id"])
        if len(result) == 10:
            break
    return result


def _fts_score(query: str, node: dict[str, Any]) -> tuple[int, float]:
    query_tokens = tokens(query)
    if not query_tokens:
        return 0, 0.0
    fields = (
        (tokens(node["title"]), 4.0),
        (tokens(" ".join(node["tags"])), 3.0),
        (tokens(node["summary"]), 2.0),
        (tokens(node["kind"]), 2.0),
        (tokens(node["body"]), 1.0),
    )
    matched: set[str] = set()
    weighted = 0.0
    for field_tokens, weight in fields:
        common = query_tokens & field_tokens
        matched.update(common)
        weighted += weight * len(common)
    required = 1 if len(query_tokens) <= 3 else 2
    if len(matched) < required:
        return len(matched), 0.0
    return len(matched), weighted / (4.0 * len(query_tokens))


def lexical_signal(query: str, node: dict[str, Any]) -> tuple[int, float, str] | None:
    normalized_query = normalize(query)
    normalized_title = normalize(node["title"])
    normalized_tags = {normalize(tag) for tag in node["tags"]}
    if normalized_title == normalized_query:
        return RANK_CLASSES["exact_title"], 1.0, "exact_title"
    if normalized_query in normalized_tags:
        return RANK_CLASSES["exact_tag"], 1.0, "exact_tag"
    if normalized_title.startswith(normalized_query):
        return RANK_CLASSES["title_prefix"], len(normalized_query) / len(normalized_title), "title_prefix"

    typo_score = max(
        trigram_similarity(query, node["title"]),
        trigram_similarity(query, node["summary"]),
        *(trigram_similarity(query, tag) for tag in node["tags"]),
    )
    if typo_score >= 0.30:
        return RANK_CLASSES["typo"], typo_score, "typo"

    matched, full_text_score = _fts_score(query, node)
    if matched and full_text_score > 0.0:
        return RANK_CLASSES["full_text"], full_text_score, "full_text"
    return None


def lexical_reference_rank(dataset: dict[str, Any], case: dict[str, Any]) -> list[str]:
    scored: list[tuple[int, float, str]] = []
    for node in candidate_nodes(dataset, case):
        signal = lexical_signal(case["query"], node)
        if signal is not None:
            rank_class, score, _ = signal
            scored.append((rank_class, -score, node["id"]))
    scored.sort()
    return [node_id for _, _, node_id in scored[:10]]


def hybrid_rank(
    dataset: dict[str, Any],
    case: dict[str, Any],
    query_vector: list[float],
    node_vectors: dict[str, list[float]],
) -> list[str]:
    scored: list[tuple[int, float, str]] = []
    for node in candidate_nodes(dataset, case):
        signal = lexical_signal(case["query"], node)
        if signal is None:
            semantic_score = cosine_similarity(query_vector, node_vectors[node["id"]])
            scored.append((RANK_CLASSES["semantic"], -semantic_score, node["id"]))
        else:
            rank_class, lexical_score, _ = signal
            scored.append((rank_class, -lexical_score, node["id"]))
    scored.sort()
    return [node_id for _, _, node_id in scored[:10]]


def quality_report(dataset: dict[str, Any], rankings: dict[str, list[str]]) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    per_class: dict[str, dict[str, int]] = {}
    top1_count = 0
    top3_count = 0
    natural_count = 0
    natural_top3_count = 0
    false_top1_count = 0
    no_result_count = 0
    visibility_leak_count = 0
    exact_guard_failures: list[str] = []

    for case in dataset["cases"]:
        ranked = rankings[case["id"]]
        if (
            not isinstance(ranked, list)
            or len(ranked) > 10
            or len(ranked) != len(set(ranked))
            or any(not isinstance(node_id, str) for node_id in ranked)
        ):
            raise ValueError(f"invalid ranking evidence for {case['id']}")
        relevant = set(case["relevant_node_ids"])
        visible = set(case["visibility_context"]["visible_node_ids"])
        excluded = set(case["excluded_node_ids"])
        top1_relevant = bool(ranked and ranked[0] in relevant)
        top3_relevant = bool(relevant.intersection(ranked[:3]))
        relevant_rank = next((index + 1 for index, item in enumerate(ranked) if item in relevant), None)
        leaks = sorted((set(ranked) - visible) | (set(ranked) & excluded))
        visibility_leak_count += len(leaks)
        top1_count += int(top1_relevant)
        top3_count += int(top3_relevant)
        if not ranked:
            no_result_count += 1
        elif not top1_relevant:
            false_top1_count += 1
        if case["natural_language"]:
            natural_count += 1
            natural_top3_count += int(top3_relevant)
        if case["expected_rank_class"] in {"exact_title", "exact_tag"} and not top1_relevant:
            exact_guard_failures.append(case["id"])
        bucket = per_class.setdefault(case["expected_rank_class"], {"count": 0, "top1": 0, "top3": 0})
        bucket["count"] += 1
        bucket["top1"] += int(top1_relevant)
        bucket["top3"] += int(top3_relevant)
        cases.append(
            {
                "case_id": case["id"],
                "ranked_node_ids": ranked,
                "top3": ranked[:3],
                "relevant_rank": relevant_rank,
                "top1_relevant": top1_relevant,
                "top3_relevant": top3_relevant,
                "visibility_leaks": leaks,
            }
        )

    return {
        "case_count": len(dataset["cases"]),
        "natural_case_count": natural_count,
        "top1_relevant_count": top1_count,
        "top1_relevant_rate": round(top1_count / len(dataset["cases"]), 6),
        "top3_relevant_count": top3_count,
        "top3_relevant_rate": round(top3_count / len(dataset["cases"]), 6),
        "natural_top3_relevant_count": natural_top3_count,
        "natural_top3_relevant_rate": round(natural_top3_count / natural_count, 6),
        "false_top1_count": false_top1_count,
        "no_result_count": no_result_count,
        "visibility_leak_count": visibility_leak_count,
        "exact_guard_failures": exact_guard_failures,
        "per_expected_rank_class": per_class,
        "cases": cases,
    }


def verify_quality_evidence(dataset: dict[str, Any], quality: dict[str, Any]) -> None:
    """Recompute every aggregate from the complete stored per-case rankings."""

    records = quality.get("cases")
    if not isinstance(records, list):
        raise ValidationError("model quality evidence requires case records")
    rankings: dict[str, list[str]] = {}
    required_fields = {
        "case_id",
        "ranked_node_ids",
        "top3",
        "relevant_rank",
        "top1_relevant",
        "top3_relevant",
        "visibility_leaks",
    }
    for record in records:
        if not isinstance(record, dict) or set(record) != required_fields:
            raise ValidationError("model quality case evidence has an invalid shape")
        case_id = record.get("case_id")
        ranked = record.get("ranked_node_ids")
        if not isinstance(case_id, str) or case_id in rankings:
            raise ValidationError("model quality case ids are invalid or duplicated")
        if (
            not isinstance(ranked, list)
            or len(ranked) > 10
            or len(ranked) != len(set(ranked))
            or any(not isinstance(node_id, str) for node_id in ranked)
        ):
            raise ValidationError(f"model ranking evidence is invalid for {case_id!r}")
        rankings[case_id] = ranked
    expected_case_ids = {case["id"] for case in dataset["cases"]}
    if set(rankings) != expected_case_ids:
        raise ValidationError("model result does not cover the exact goldset cases")
    try:
        expected = quality_report(dataset, rankings)
    except (KeyError, ValueError) as error:
        raise ValidationError(f"model ranking evidence is invalid: {error}") from error
    if quality != expected:
        raise ValidationError("model quality aggregates or case evidence are inconsistent")


def timed_rankings(dataset: dict[str, Any], ranker: Any) -> tuple[dict[str, list[str]], dict[str, float]]:
    durations: list[float] = []
    rankings: dict[str, list[str]] = {}
    for case in dataset["cases"]:
        started = time.perf_counter()
        rankings[case["id"]] = ranker(dataset, case)
        durations.append((time.perf_counter() - started) * 1000.0)
    return rankings, latency_report(durations)


def latency_report(values: Iterable[float]) -> dict[str, float]:
    ordered = sorted(values)
    if not ordered:
        return {"median_ms": 0.0, "p95_ms": 0.0, "maximum_ms": 0.0}
    p95_index = min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)
    return {
        "median_ms": round(statistics.median(ordered), 3),
        "p95_ms": round(ordered[p95_index], 3),
        "maximum_ms": round(max(ordered), 3),
    }


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


class OllamaClient:
    def __init__(self, base_url: str, timeout_seconds: int = 900) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Ollama benchmark URL must be an unauthenticated loopback HTTP origin")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirectHandler())

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers={"Content-Type": "application/json"},
            method="GET" if payload is None else "POST",
        )
        try:
            with self.opener.open(request, timeout=self.timeout_seconds) as response:
                payload = response.read(MAX_OLLAMA_RESPONSE_BYTES + 1)
                if len(payload) > MAX_OLLAMA_RESPONSE_BYTES:
                    raise RuntimeError(f"Ollama response exceeds {MAX_OLLAMA_RESPONSE_BYTES} bytes")
                value = json.loads(payload.decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Ollama request failed for {path}: {error}") from error
        if not isinstance(value, dict):
            raise RuntimeError(f"Ollama returned a non-object for {path}")
        return value

    def identity(self, model: str) -> dict[str, Any]:
        tags = self._request("/api/tags").get("models", [])
        match = next((item for item in tags if item.get("name") == model), None)
        if not isinstance(match, dict):
            raise RuntimeError(f"Ollama model is not installed: {model}")
        details = match.get("details") if isinstance(match.get("details"), dict) else {}
        digest = match.get("digest")
        size_bytes = match.get("size")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise RuntimeError(f"Ollama model digest is invalid for {model}")
        if not isinstance(size_bytes, int) or size_bytes <= 0:
            raise RuntimeError(f"Ollama model size is invalid for {model}")
        return {
            "name": model,
            "digest": "sha256:" + digest,
            "size_bytes": size_bytes,
            "family": details.get("family"),
            "parameter_size": details.get("parameter_size"),
            "quantization_level": details.get("quantization_level"),
        }

    def embed(self, model: str, texts: list[str]) -> tuple[list[list[float]], float]:
        started = time.perf_counter()
        response = self._request(
            "/api/embed",
            {"model": model, "input": texts, "truncate": False, "keep_alive": "5m"},
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        embeddings = response.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise RuntimeError("Ollama returned an unexpected embedding count")
        vectors: list[list[float]] = []
        for vector in embeddings:
            if (
                not isinstance(vector, list)
                or not vector
                or not all(type(item) in {int, float} and math.isfinite(float(item)) for item in vector)
            ):
                raise RuntimeError("Ollama returned an invalid embedding vector")
            vectors.append([float(item) for item in vector])
        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1:
            raise RuntimeError("Ollama mixed embedding dimensions")
        return vectors, elapsed_ms


def evaluate_model(dataset: dict[str, Any], model: str, client: OllamaClient) -> dict[str, Any]:
    active_nodes = [node for node in dataset["nodes"] if node["status"] == "active"]
    documents = [node_document(node) for node in active_nodes]
    queries = [query_document(case["query"]) for case in dataset["cases"]]
    identity = client.identity(model)
    document_vectors, document_elapsed = client.embed(model, documents)
    query_vectors, query_elapsed = client.embed(model, queries)
    identity_after = client.identity(model)
    if identity_after != identity:
        raise RuntimeError(f"Ollama model identity changed during measurement: {model}")
    node_vectors = {node["id"]: vector for node, vector in zip(active_nodes, document_vectors, strict=True)}
    dimensions = len(document_vectors[0])
    rankings: dict[str, list[str]] = {}
    rank_durations: list[float] = []
    for case, query_vector in zip(dataset["cases"], query_vectors, strict=True):
        started = time.perf_counter()
        rankings[case["id"]] = hybrid_rank(dataset, case, query_vector, node_vectors)
        rank_durations.append((time.perf_counter() - started) * 1000.0)
    identity["dimensions"] = dimensions
    return {
        "model": identity,
        "quality": quality_report(dataset, rankings),
        "performance": {
            "document_embedding_total_ms": round(document_elapsed, 3),
            "query_embedding_total_ms": round(query_elapsed, 3),
            "ranking": latency_report(rank_durations),
            "document_count": len(documents),
            "query_count": len(queries),
        },
    }


def choose_decision(lexical: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
    threshold = 0.85
    minimum_gain_cases = 2
    baseline_quality = lexical["quality"]
    assessed: list[dict[str, Any]] = []
    for item in models:
        quality = item["quality"]
        gain = quality["natural_top3_relevant_count"] - baseline_quality["natural_top3_relevant_count"]
        qualifies = (
            not quality["exact_guard_failures"]
            and quality["visibility_leak_count"] == 0
            and quality["natural_top3_relevant_rate"] >= threshold
            and quality["false_top1_count"] <= baseline_quality["false_top1_count"]
        )
        meaningful = gain >= minimum_gain_cases
        assessed.append(
            {
                "model": item["model"]["name"],
                "qualifies": qualifies,
                "meaningful_incremental_gain": meaningful,
                "natural_top3_gain_cases": gain,
            }
        )
    winner = next((item for item in assessed if item["qualifies"] and item["meaningful_incremental_gain"]), None)
    if winner is None:
        return {
            "outcome": "stop_embedding_path",
            "selected_model": None,
            "reason": "No local candidate both met the quality gates and improved natural-language Top-3 by at least two cases over the lexical reference.",
            "quality_thresholds": {"natural_top3_rate": threshold, "minimum_gain_cases": minimum_gain_cases},
            "assessed_models": assessed,
        }
    return {
        "outcome": "select_smallest_qualifying_local_model",
        "selected_model": winner["model"],
        "reason": "The smallest local model meeting all gates and the minimum incremental relevance gain is selected for T003/T004 planning.",
        "quality_thresholds": {"natural_top3_rate": threshold, "minimum_gain_cases": minimum_gain_cases},
        "assessed_models": assessed,
    }


def contains_raw_vectors(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.casefold() in RAW_VECTOR_KEYS:
                return True
            if contains_raw_vectors(item):
                return True
    elif isinstance(value, list):
        if len(value) >= 32 and all(type(item) in {int, float} for item in value):
            return True
        return any(contains_raw_vectors(item) for item in value)
    return False


def _require_exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValidationError(f"{label} has an invalid shape")
    return value


def _require_nonnegative_number(value: Any, label: str) -> float:
    if type(value) not in {int, float} or not math.isfinite(float(value)) or float(value) < 0.0:
        raise ValidationError(f"{label} must be a finite non-negative number")
    return float(value)


def _validate_latency(value: Any, label: str) -> None:
    latency = _require_exact_keys(value, {"median_ms", "p95_ms", "maximum_ms"}, label)
    median = _require_nonnegative_number(latency["median_ms"], f"{label}.median_ms")
    p95 = _require_nonnegative_number(latency["p95_ms"], f"{label}.p95_ms")
    maximum = _require_nonnegative_number(latency["maximum_ms"], f"{label}.maximum_ms")
    if not median <= p95 <= maximum:
        raise ValidationError(f"{label} latency order is invalid")


def validate_result_shape(result: dict[str, Any]) -> None:
    _require_exact_keys(
        result,
        {
            "schema_version",
            "kind",
            "benchmark_revision",
            "measured_at",
            "dataset",
            "benchmark_source_sha256",
            "environment",
            "baselines",
            "models",
            "decision",
            "does_not_establish",
        },
        "benchmark result",
    )
    if result["schema_version"] != 1:
        raise ValidationError("benchmark result schema version is invalid")
    measured_at = result["measured_at"]
    try:
        parsed_time = datetime.fromisoformat(str(measured_at).removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise ValidationError("benchmark measured_at is invalid") from error
    if not isinstance(measured_at, str) or not measured_at.endswith("Z") or parsed_time.tzinfo is None:
        raise ValidationError("benchmark measured_at is invalid")

    _require_exact_keys(
        result["dataset"],
        {"path", "dataset_id", "document_revision", "sha256", "schema_sha256", "node_count", "case_count", "privacy_class"},
        "benchmark dataset identity",
    )
    environment = _require_exact_keys(
        result["environment"],
        {"host_class", "platform", "python", "ollama_url", "external_cost_usd"},
        "benchmark environment",
    )
    if environment["host_class"] != "heim-pc-local":
        raise ValidationError("benchmark host class is invalid")
    for key in ("platform", "python", "ollama_url"):
        if not isinstance(environment[key], str) or not environment[key].strip():
            raise ValidationError(f"benchmark environment {key} is invalid")
    try:
        OllamaClient(environment["ollama_url"])
    except (TypeError, ValueError) as error:
        raise ValidationError("benchmark environment is not loopback-bound") from error
    if environment["external_cost_usd"] != 0:
        raise ValidationError("benchmark claims non-zero external cost")

    baselines = result["baselines"]
    if not isinstance(baselines, list) or len(baselines) != 2:
        raise ValidationError("benchmark requires exactly two baselines")
    for index, baseline in enumerate(baselines):
        entry = _require_exact_keys(baseline, {"name", "quality", "performance"}, f"baseline[{index}]")
        _validate_latency(entry["performance"], f"baseline[{index}].performance")

    models = result["models"]
    if not isinstance(models, list) or len(models) != len(DEFAULT_MODELS):
        raise ValidationError("benchmark requires the exact local model count")
    for index, item in enumerate(models):
        entry = _require_exact_keys(item, {"model", "quality", "performance"}, f"model[{index}]")
        model = _require_exact_keys(
            entry["model"],
            {"name", "digest", "size_bytes", "family", "parameter_size", "quantization_level", "dimensions"},
            f"model[{index}].identity",
        )
        for key in ("name", "digest", "family", "parameter_size", "quantization_level"):
            if not isinstance(model[key], str) or not model[key].strip():
                raise ValidationError(f"model[{index}] {key} is invalid")
        if not isinstance(model["size_bytes"], int) or isinstance(model["size_bytes"], bool) or model["size_bytes"] <= 0:
            raise ValidationError(f"model[{index}] size is invalid")
        if not isinstance(model["dimensions"], int) or isinstance(model["dimensions"], bool) or model["dimensions"] <= 0:
            raise ValidationError(f"model[{index}] dimension is invalid")
        performance = _require_exact_keys(
            entry["performance"],
            {"document_embedding_total_ms", "query_embedding_total_ms", "ranking", "document_count", "query_count"},
            f"model[{index}].performance",
        )
        _require_nonnegative_number(performance["document_embedding_total_ms"], f"model[{index}].document_embedding_total_ms")
        _require_nonnegative_number(performance["query_embedding_total_ms"], f"model[{index}].query_embedding_total_ms")
        _validate_latency(performance["ranking"], f"model[{index}].ranking")
        for key in ("document_count", "query_count"):
            if not isinstance(performance[key], int) or isinstance(performance[key], bool) or performance[key] <= 0:
                raise ValidationError(f"model[{index}].{key} is invalid")

    decision = _require_exact_keys(
        result["decision"],
        {"outcome", "selected_model", "reason", "quality_thresholds", "assessed_models"},
        "benchmark decision",
    )
    _require_exact_keys(decision["quality_thresholds"], {"natural_top3_rate", "minimum_gain_cases"}, "decision thresholds")
    assessed = decision["assessed_models"]
    if not isinstance(assessed, list) or len(assessed) != len(DEFAULT_MODELS):
        raise ValidationError("decision assessed model set is invalid")
    for index, item in enumerate(assessed):
        _require_exact_keys(
            item,
            {"model", "qualifies", "meaningful_incremental_gain", "natural_top3_gain_cases"},
            f"decision.assessed_models[{index}]",
        )
    if result["does_not_establish"] != list(DOES_NOT_ESTABLISH):
        raise ValidationError("benchmark non-claims are stale or incomplete")
    if contains_raw_vectors(result):
        raise ValidationError("benchmark result contains raw-vector-like data")


def build_result(dataset_path: Path, schema_path: Path, models: list[str], ollama_url: str) -> dict[str, Any]:
    schema = load_json_object(schema_path)
    dataset = load_json_object(dataset_path)
    validate_goldset(dataset, schema)
    substring_rankings, substring_latency = timed_rankings(dataset, current_substring_rank)
    lexical_rankings, lexical_latency = timed_rankings(dataset, lexical_reference_rank)
    substring = {"name": "current_client_substring", "quality": quality_report(dataset, substring_rankings), "performance": substring_latency}
    lexical = {"name": "fts_trigram_reference", "quality": quality_report(dataset, lexical_rankings), "performance": lexical_latency}
    client = OllamaClient(ollama_url)
    model_results = [evaluate_model(dataset, model, client) for model in models]
    result = {
        "schema_version": 1,
        "kind": "weltgewebe_semantic_search_relevance_benchmark",
        "benchmark_revision": BENCHMARK_REVISION,
        "measured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "dataset": {
            "path": str(dataset_path.relative_to(ROOT)),
            "dataset_id": dataset["dataset_id"],
            "document_revision": dataset["document_revision"],
            "sha256": sha256_path(dataset_path),
            "schema_sha256": sha256_path(schema_path),
            "node_count": len(dataset["nodes"]),
            "case_count": len(dataset["cases"]),
            "privacy_class": dataset["privacy_class"],
        },
        "benchmark_source_sha256": sha256_path(Path(__file__)),
        "environment": {
            "host_class": "heim-pc-local",
            "platform": platform.platform(),
            "python": platform.python_version(),
            "ollama_url": ollama_url,
            "external_cost_usd": 0,
        },
        "baselines": [substring, lexical],
        "models": model_results,
        "decision": choose_decision(lexical, model_results),
        "does_not_establish": list(DOES_NOT_ESTABLISH),
    }
    if contains_raw_vectors(result):
        raise RuntimeError("benchmark result would contain raw vectors")
    return result


def _strip_performance(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "performance"}


def check_result(result_path: Path, dataset_path: Path, schema_path: Path) -> None:
    result = load_json_object(result_path)
    validate_result_shape(result)
    if result.get("kind") != "weltgewebe_semantic_search_relevance_benchmark":
        raise ValidationError("benchmark result has an unexpected kind")
    if result.get("benchmark_revision") != BENCHMARK_REVISION:
        raise ValidationError("benchmark revision is stale")
    if result.get("benchmark_source_sha256") != sha256_path(Path(__file__)):
        raise ValidationError("benchmark source hash is stale")
    schema = load_json_object(schema_path)
    dataset = load_json_object(dataset_path)
    validate_goldset(dataset, schema)
    identity = result["dataset"]
    expected_identity = {
        "path": str(dataset_path.relative_to(ROOT)),
        "dataset_id": dataset["dataset_id"],
        "document_revision": dataset["document_revision"],
        "sha256": sha256_path(dataset_path),
        "schema_sha256": sha256_path(schema_path),
        "node_count": len(dataset["nodes"]),
        "case_count": len(dataset["cases"]),
        "privacy_class": dataset["privacy_class"],
    }
    if identity != expected_identity:
        raise ValidationError("benchmark dataset identity is stale")
    substring_rankings, _ = timed_rankings(dataset, current_substring_rank)
    lexical_rankings, _ = timed_rankings(dataset, lexical_reference_rank)
    expected = [
        {"name": "current_client_substring", "quality": quality_report(dataset, substring_rankings)},
        {"name": "fts_trigram_reference", "quality": quality_report(dataset, lexical_rankings)},
    ]
    actual = [_strip_performance(item) for item in result.get("baselines", [])]
    if actual != expected:
        raise ValidationError("checked-in lexical baseline evidence is stale")
    models = result.get("models")
    if not isinstance(models, list) or not models:
        raise ValidationError("benchmark result requires measured local models")
    model_names = [item.get("model", {}).get("name") for item in models]
    if model_names != list(DEFAULT_MODELS):
        raise ValidationError("benchmark result does not cover the exact required local model set")
    digests = [item.get("model", {}).get("digest") for item in models]
    if len(digests) != len(set(digests)):
        raise ValidationError("benchmark result contains duplicate model digests")
    sizes = [item["model"]["size_bytes"] for item in models]
    if sizes != sorted(sizes) or len(sizes) != len(set(sizes)):
        raise ValidationError("benchmark model sizes are not strictly increasing")
    active_document_count = sum(node["status"] == "active" for node in dataset["nodes"])
    for item in models:
        model = item.get("model", {})
        quality = item.get("quality", {})
        digest = model.get("digest")
        if not isinstance(digest, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None:
            raise ValidationError("model digest is missing or invalid")
        if not isinstance(model.get("dimensions"), int) or model["dimensions"] <= 0:
            raise ValidationError("model dimension is missing or invalid")
        performance = item["performance"]
        if performance["document_count"] != active_document_count:
            raise ValidationError("model document count is stale")
        if performance["query_count"] != len(dataset["cases"]):
            raise ValidationError("model query count is stale")
        verify_quality_evidence(dataset, quality)
        if quality.get("visibility_leak_count") != 0:
            raise ValidationError("model result contains a visibility leak")
    lexical = next(item for item in result["baselines"] if item["name"] == "fts_trigram_reference")
    expected_decision = choose_decision(lexical, models)
    if result.get("decision") != expected_decision:
        raise ValidationError("model selection decision is stale or inconsistent")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure or validate the synthetic Semantic Search v1 benchmark.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--check-result", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.check_result:
            check_result(args.output, args.dataset, args.schema)
            print(f"semantic-search benchmark evidence valid: {args.output}")
            return 0
        result = build_result(args.dataset, args.schema, args.models, args.ollama_url)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "decision": result["decision"]}, ensure_ascii=False, indent=2))
        return 0
    except (ValidationError, RuntimeError, ValueError) as error:
        print(f"semantic-search benchmark failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

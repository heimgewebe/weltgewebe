"""Measure and validate the T004 local hybrid-ranking core."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from scripts.search.benchmark_relevance import (
    DEFAULT_MODELS,
    DEFAULT_RESULT as T002_RESULT,
    OllamaClient,
    contains_raw_vectors,
    latency_report,
    quality_report,
    verify_quality_evidence,
)
from scripts.search.hybrid_ranking_core import (
    DOES_NOT_ESTABLISH,
    MAX_CANDIDATES,
    MAX_DIMENSIONS,
    NORMALIZATION_REVISION,
    RANKING_REVISION,
    SEMANTIC_MINIMUM_COSINE,
    SEMANTIC_MINIMUM_MARGIN,
    GenerationIdentity,
    LocalEmbeddingProvider,
    ModelIdentity,
    ProviderBoundaryError,
    ProviderUnavailableError,
    SearchCoreError,
    SearchDocument,
    SearchQuery,
    embed_bound,
    rank_hybrid,
)
from scripts.search.validate_relevance_goldset import (
    DEFAULT_DATASET,
    DEFAULT_SCHEMA,
    ValidationError,
    load_json_object,
    validate_goldset,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "contracts/search/examples/hybrid-ranking-core.heim-pc.json"
T003_RECEIPT = ROOT / "contracts/search/examples/postgres-foundation.heim-pc.json"
TASK_ID = "WELTGEWEBE-SEMANTIC-SEARCH-V1-T004"
KIND = "weltgewebe_semantic_search_hybrid_ranking_core"
SOURCE_MODE = "repository_base_plus_hash_bound_worktree_sources"
QUALITY_THRESHOLD = 0.85
MINIMUM_GAIN_CASES = 2
T003_NATURAL_TOP3 = 14
T003_FALSE_TOP1 = 0
T003_VISIBILITY_LEAKS = 0
SOURCE_PATHS = (
    "architecture/semantic-search.md",
    "contracts/search/examples/relevance-goldset.example.json",
    "contracts/search/relevance-goldset.schema.json",
    "contracts/search/examples/relevance-benchmark.heim-pc.json",
    "contracts/search/examples/postgres-foundation.heim-pc.json",
    "contracts/search/hybrid-ranking-core-receipt.schema.json",
    "scripts/search/hybrid_ranking_core.py",
    "scripts/search/probe_hybrid_ranking_core.py",
    "scripts/ci/tests/test_semantic_search_ranking_core.py",
)


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def document_from_node(node: dict[str, Any]) -> SearchDocument:
    return SearchDocument.from_mapping(
        {
            "node_id": node["id"],
            "title": node["title"],
            "summary": node["summary"],
            "body": node["body"],
            "tags": list(node["tags"]),
            "kind": node["kind"],
            "language": node["language"],
            "privacy_class": "synthetic",
            "contains_personal_data": node["contains_personal_data"],
        }
    )


def query_from_case(case: dict[str, Any]) -> SearchQuery:
    return SearchQuery(case["query"], "synthetic", case["contains_personal_data"])


class OllamaProvider(LocalEmbeddingProvider):
    """Loopback provider bound to one checked-in T002 model identity."""

    def __init__(self, base_url: str, reference: dict[str, Any]) -> None:
        self.client = OllamaClient(base_url)
        self.base_url = base_url.rstrip("/")
        self.reference = reference
        self.elapsed_ms: list[float] = []

    def identity(self) -> ModelIdentity:
        try:
            live = self.client.identity(self.reference["name"])
            version = self.client._request("/api/version").get("version")
        except RuntimeError as error:
            raise ProviderUnavailableError(str(error)) from error
        if not isinstance(version, str) or not version:
            raise ProviderBoundaryError("Ollama runtime version is missing")
        if (
            live["digest"] != self.reference["digest"]
            or live["size_bytes"] != self.reference["size_bytes"]
        ):
            raise ProviderBoundaryError("Ollama model identity differs from T002")
        return ModelIdentity(
            provider="local:ollama",
            model_id=self.reference["name"],
            model_revision=live["digest"],
            runtime_id=f"ollama:{version}@{self.base_url}",
            dimensions=self.reference["dimensions"],
        )

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        try:
            vectors, elapsed = self.client.embed(self.reference["name"], list(texts))
        except RuntimeError as error:
            raise ProviderUnavailableError(str(error)) from error
        self.elapsed_ms.append(elapsed)
        return vectors


def reference_models() -> list[dict[str, Any]]:
    models = load_json_object(T002_RESULT).get("models")
    if not isinstance(models, list):
        raise ValidationError("T002 result has no model list")
    result = [dict(item["model"]) for item in models]
    if [item["name"] for item in result] != list(DEFAULT_MODELS):
        raise ValidationError("T002 model set is stale")
    return result


def active_documents(dataset: dict[str, Any]) -> list[SearchDocument]:
    return [
        document_from_node(node)
        for node in dataset["nodes"]
        if node["status"] == "active"
    ]


def t003_postgres_rankings(dataset: dict[str, Any]) -> dict[str, list[str]]:
    receipt = load_json_object(T003_RECEIPT)
    quality = receipt.get("quality", {}).get("postgres_fts_pg_trgm")
    if not isinstance(quality, dict):
        raise ValidationError("T003 PostgreSQL quality evidence is missing")
    verify_quality_evidence(dataset, quality)
    return {item["case_id"]: list(item["ranked_node_ids"]) for item in quality["cases"]}


def measure_model(
    dataset: dict[str, Any],
    documents: list[SearchDocument],
    reference: dict[str, Any],
    ollama_url: str,
    postgres_rankings: dict[str, list[str]],
) -> dict[str, Any]:
    queries = [query_from_case(case) for case in dataset["cases"]]
    provider = OllamaProvider(ollama_url, reference)
    generation, document_vectors, query_vectors = embed_bound(
        provider, documents, queries, document_revision=dataset["document_revision"]
    )
    if len(provider.elapsed_ms) != 2:
        raise RuntimeError("expected exactly two embedding calls")
    by_id = {item.node_id: item for item in documents}
    rankings: dict[str, list[str]] = {}
    durations: list[float] = []
    for case, query, query_vector in zip(
        dataset["cases"], queries, query_vectors, strict=True
    ):
        candidates = [
            by_id[node_id] for node_id in case["visibility_context"]["visible_node_ids"]
        ]
        vectors = {item.node_id: document_vectors[item.node_id] for item in candidates}
        started = time.perf_counter()
        result = rank_hybrid(
            query,
            candidates,
            generation,
            query_vector,
            vectors,
            lexical_ranked_node_ids=postgres_rankings[case["id"]],
        )
        durations.append((time.perf_counter() - started) * 1000.0)
        rankings[case["id"]] = list(result.ranked_node_ids)
    live = provider.client.identity(reference["name"])
    model = generation.model.as_dict()
    model.update(
        {
            "size_bytes": live["size_bytes"],
            "family": live["family"],
            "parameter_size": live["parameter_size"],
            "quantization_level": live["quantization_level"],
        }
    )
    return {
        "model": model,
        "generation": generation.as_dict(),
        "quality": quality_report(dataset, rankings),
        "performance": {
            "document_embedding_total_ms": round(provider.elapsed_ms[0], 3),
            "query_embedding_total_ms": round(provider.elapsed_ms[1], 3),
            "ranking": latency_report(durations),
            "document_count": len(documents),
            "query_count": len(queries),
        },
    }


def choose_decision(models: list[dict[str, Any]]) -> dict[str, Any]:
    assessed: list[dict[str, Any]] = []
    for item in sorted(
        models,
        key=lambda value: (value["model"]["size_bytes"], value["model"]["model_id"]),
    ):
        quality = item["quality"]
        gain = quality["natural_top3_relevant_count"] - T003_NATURAL_TOP3
        qualifies = (
            not quality["exact_guard_failures"]
            and quality["visibility_leak_count"] <= T003_VISIBILITY_LEAKS
            and quality["natural_top3_relevant_rate"] >= QUALITY_THRESHOLD
            and quality["false_top1_count"] <= T003_FALSE_TOP1
        )
        assessed.append(
            {
                "model_id": item["model"]["model_id"],
                "model_revision": item["model"]["model_revision"],
                "size_bytes": item["model"]["size_bytes"],
                "qualifies": qualifies,
                "meaningful_incremental_gain": gain >= MINIMUM_GAIN_CASES,
                "natural_top3_gain_cases": gain,
                "false_top1_count": quality["false_top1_count"],
            }
        )
    winner = next(
        (
            item
            for item in assessed
            if item["qualifies"] and item["meaningful_incremental_gain"]
        ),
        None,
    )
    thresholds = {
        "natural_top3_rate": QUALITY_THRESHOLD,
        "maximum_false_top1": T003_FALSE_TOP1,
        "maximum_visibility_leaks": T003_VISIBILITY_LEAKS,
        "minimum_gain_cases": MINIMUM_GAIN_CASES,
    }
    if winner is None:
        return {
            "outcome": "stop_embedding_path",
            "selected_model": None,
            "reason": "No local model met every T004 quality gate with meaningful gain over T003.",
            "quality_thresholds": thresholds,
            "assessed_models": assessed,
        }
    return {
        "outcome": "select_smallest_qualifying_local_model",
        "selected_model": winner["model_id"],
        "reason": "The smallest measured local model satisfying every T004 gate is selected.",
        "quality_thresholds": thresholds,
        "assessed_models": assessed,
    }


def source_identity() -> dict[str, Any]:
    files = {relative: sha256_path(ROOT / relative) for relative in SOURCE_PATHS}
    return {
        "repository_head_at_measurement": _git("rev-parse", "HEAD"),
        "measurement_source_mode": SOURCE_MODE,
        "worktree_dirty_at_measurement": bool(
            _git("status", "--porcelain", "--untracked-files=normal")
        ),
        "source_files": files,
        "source_manifest_sha256": canonical_sha256(files),
    }


def build_receipt(
    dataset_path: Path, schema_path: Path, ollama_url: str
) -> dict[str, Any]:
    schema = load_json_object(schema_path)
    dataset = load_json_object(dataset_path)
    validate_goldset(dataset, schema)
    documents = active_documents(dataset)
    postgres_rankings = t003_postgres_rankings(dataset)
    models = [
        measure_model(dataset, documents, item, ollama_url, postgres_rankings)
        for item in reference_models()
    ]
    receipt = {
        "schema_version": 1,
        "kind": KIND,
        "task_id": TASK_ID,
        "measured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": source_identity(),
        "dataset": {
            "path": str(dataset_path.relative_to(ROOT)),
            "dataset_id": dataset["dataset_id"],
            "document_revision": dataset["document_revision"],
            "sha256": sha256_path(dataset_path),
            "schema_sha256": sha256_path(schema_path),
            "privacy_class": dataset["privacy_class"],
            "node_count": len(dataset["nodes"]),
            "active_document_count": len(documents),
            "case_count": len(dataset["cases"]),
            "natural_case_count": sum(
                case["natural_language"] for case in dataset["cases"]
            ),
        },
        "environment": {
            "host_class": "heim-pc-local",
            "platform": platform.platform(),
            "python": platform.python_version(),
            "ollama_url": ollama_url,
            "external_cost_usd": 0,
        },
        "ranking_contract": {
            "normalization_revision": NORMALIZATION_REVISION,
            "ranking_revision": RANKING_REVISION,
            "semantic_minimum_cosine": SEMANTIC_MINIMUM_COSINE,
            "semantic_minimum_margin": SEMANTIC_MINIMUM_MARGIN,
            "max_dimensions": MAX_DIMENSIONS,
            "max_candidates": MAX_CANDIDATES,
            "hard_precedence": [
                "exact_title",
                "exact_tag",
                "title_prefix",
                "typo",
                "full_text",
                "semantic",
                "node_id",
            ],
            "fallback_condition": "ProviderUnavailableError only",
            "raw_vectors_persisted": False,
        },
        "baseline": {
            "t003_postgresql": {
                "natural_top3_relevant_count": T003_NATURAL_TOP3,
                "natural_case_count": 19,
                "false_top1_count": T003_FALSE_TOP1,
                "visibility_leak_count": T003_VISIBILITY_LEAKS,
                "receipt_sha256": sha256_path(T003_RECEIPT),
            },
            "t004_lexical_core": quality_report(dataset, postgres_rankings),
        },
        "models": models,
        "decision": choose_decision(models),
        "does_not_establish": list(DOES_NOT_ESTABLISH),
    }
    if contains_raw_vectors(receipt):
        raise RuntimeError("T004 receipt contains raw-vector-like data")
    return receipt


def check_receipt(receipt_path: Path, dataset_path: Path, schema_path: Path) -> None:
    receipt = load_json_object(receipt_path)
    if (
        receipt.get("schema_version") != 1
        or receipt.get("kind") != KIND
        or receipt.get("task_id") != TASK_ID
    ):
        raise ValidationError("T004 receipt identity is invalid")
    expected_files = {
        relative: sha256_path(ROOT / relative) for relative in SOURCE_PATHS
    }
    source = receipt.get("source", {})
    if (
        source.get("measurement_source_mode") != SOURCE_MODE
        or source.get("worktree_dirty_at_measurement") is not True
    ):
        raise ValidationError("T004 source mode is invalid")
    if source.get("source_files") != expected_files or source.get(
        "source_manifest_sha256"
    ) != canonical_sha256(expected_files):
        raise ValidationError("T004 source binding is stale")
    schema = load_json_object(schema_path)
    dataset = load_json_object(dataset_path)
    validate_goldset(dataset, schema)
    expected_dataset = {
        "path": str(dataset_path.relative_to(ROOT)),
        "dataset_id": dataset["dataset_id"],
        "document_revision": dataset["document_revision"],
        "sha256": sha256_path(dataset_path),
        "schema_sha256": sha256_path(schema_path),
        "privacy_class": dataset["privacy_class"],
        "node_count": len(dataset["nodes"]),
        "active_document_count": sum(
            node["status"] == "active" for node in dataset["nodes"]
        ),
        "case_count": len(dataset["cases"]),
        "natural_case_count": sum(
            case["natural_language"] for case in dataset["cases"]
        ),
    }
    if receipt.get("dataset") != expected_dataset:
        raise ValidationError("T004 dataset identity is stale")
    expected_contract = {
        "normalization_revision": NORMALIZATION_REVISION,
        "ranking_revision": RANKING_REVISION,
        "semantic_minimum_cosine": SEMANTIC_MINIMUM_COSINE,
        "semantic_minimum_margin": SEMANTIC_MINIMUM_MARGIN,
        "max_dimensions": MAX_DIMENSIONS,
        "max_candidates": MAX_CANDIDATES,
        "hard_precedence": [
            "exact_title",
            "exact_tag",
            "title_prefix",
            "typo",
            "full_text",
            "semantic",
            "node_id",
        ],
        "fallback_condition": "ProviderUnavailableError only",
        "raw_vectors_persisted": False,
    }
    if receipt.get("ranking_contract") != expected_contract:
        raise ValidationError("T004 ranking contract is stale")
    postgres_rankings = t003_postgres_rankings(dataset)
    expected_baseline = {
        "t003_postgresql": {
            "natural_top3_relevant_count": T003_NATURAL_TOP3,
            "natural_case_count": 19,
            "false_top1_count": T003_FALSE_TOP1,
            "visibility_leak_count": T003_VISIBILITY_LEAKS,
            "receipt_sha256": sha256_path(T003_RECEIPT),
        },
        "t004_lexical_core": quality_report(dataset, postgres_rankings),
    }
    if receipt.get("baseline") != expected_baseline:
        raise ValidationError("T004 PostgreSQL baseline is stale")
    models = receipt.get("models")
    if not isinstance(models, list) or [
        item.get("model", {}).get("model_id") for item in models
    ] != list(DEFAULT_MODELS):
        raise ValidationError("T004 model set is invalid")
    references = {item["name"]: item for item in reference_models()}
    for item in models:
        model = item["model"]
        reference = references[model["model_id"]]
        if (
            model["model_revision"] != reference["digest"]
            or model["dimensions"] != reference["dimensions"]
        ):
            raise ValidationError("T004 model identity differs from T002")
        identity = ModelIdentity(
            model["provider"],
            model["model_id"],
            model["model_revision"],
            model["runtime_id"],
            model["dimensions"],
        )
        generation = item["generation"]
        checked = GenerationIdentity(
            generation["generation_id"],
            identity,
            generation["document_revision"],
            generation["normalization_revision"],
            generation["ranking_revision"],
        )
        if checked.as_dict() != generation:
            raise ValidationError("T004 generation identity is inconsistent")
        verify_quality_evidence(dataset, item["quality"])
    if receipt.get("decision") != choose_decision(models):
        raise ValidationError("T004 decision is stale")
    if receipt.get("does_not_establish") != list(
        DOES_NOT_ESTABLISH
    ) or contains_raw_vectors(receipt):
        raise ValidationError(
            "T004 receipt non-claims or raw-vector boundary are invalid"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure or validate the T004 hybrid-ranking core."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.check:
            check_receipt(args.output, args.dataset, args.schema)
            print(f"semantic-search T004 receipt valid: {args.output}")
        else:
            receipt = build_receipt(args.dataset, args.schema, args.ollama_url)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                json.dumps(
                    {"output": str(args.output), "decision": receipt["decision"]},
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return 0
    except (
        OSError,
        subprocess.CalledProcessError,
        SearchCoreError,
        ValidationError,
        RuntimeError,
        ValueError,
    ) as error:
        print(f"semantic-search T004 probe failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

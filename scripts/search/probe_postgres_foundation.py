"""Live PostgreSQL foundation proof for Semantic Search v1 T003.

The measuring mode uses only a disposable Docker container created from the
PostgreSQL image already pinned by Weltgewebe. The checked-in receipt contains
no credentials, raw vectors, provider payloads or production data.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import platform
import re
import secrets
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.search.benchmark_relevance import quality_report
from scripts.search.validate_relevance_goldset import load_json_object, validate_goldset

DATASET = ROOT / "contracts/search/examples/relevance-goldset.example.json"
DATASET_SCHEMA = ROOT / "contracts/search/relevance-goldset.schema.json"
T002_RECEIPT = ROOT / "contracts/search/examples/relevance-benchmark.heim-pc.json"
RESULT = ROOT / "contracts/search/examples/postgres-foundation.heim-pc.json"
RESULT_SCHEMA = ROOT / "contracts/search/postgres-foundation-receipt.schema.json"
DOMAIN_NODES_MIGRATION = ROOT / "apps/api/migrations/20260531000001_create_domain_nodes.up.sql"
UP_MIGRATION = ROOT / "contracts/search/postgres-foundation.up.sql"
DOWN_MIGRATION = ROOT / "contracts/search/postgres-foundation.down.sql"
SOURCE_PATHS = (
    DATASET,
    DATASET_SCHEMA,
    T002_RECEIPT,
    DOMAIN_NODES_MIGRATION,
    UP_MIGRATION,
    DOWN_MIGRATION,
    Path(__file__).resolve(),
    RESULT_SCHEMA,
)
POSTGRES_IMAGE = "postgres:16@sha256:be01cf82fc7dbba824acf0a82e150b4b360f3ff93c6631d7844af431e841a95c"
GENERATION_ID = "t003-qwen3-embedding-8b-reference-v1"
MODEL_ID = "qwen3-embedding:8b"
MODEL_REVISION = "sha256:64b933495768fbd3b87c20583d379728a07471e0c66733a9df87cd1901b3c44b"
MODEL_DIMENSION = 4096
DOES_NOT_ESTABLISH = [
    "production semantic search",
    "production model approval",
    "pgvector availability outside the measured pinned image",
    "search API, worker, web UI or backfill",
    "ANN or HNSW need or approval",
    "production deployment or public semantic live proof",
    "SemantAH shutdown authority",
]


class ProofError(RuntimeError):
    pass


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_json(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def source_file_hashes() -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): sha256_path(path)
        for path in SOURCE_PATHS
    }


def run(argv: list[str], *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env={**os.environ, "LC_ALL": "C.UTF-8"},
    )
    if check and result.returncode != 0:
        raise ProofError(
            f"command failed ({result.returncode}): {argv!r}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_array(values: list[str]) -> str:
    if not values:
        return "ARRAY[]::TEXT[]"
    return "ARRAY[" + ",".join(sql_literal(value) for value in values) + "]::TEXT[]"


def node_document(node: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Titel: {node['title']}",
            f"Kurzbeschreibung: {node['summary']}",
            f"Information: {node['body']}",
            f"Tags: {', '.join(node['tags'])}",
            f"Art: {node['kind']}",
            f"Sprache: {node['language']}",
        ]
    )


class DisposablePostgres:
    def __init__(self) -> None:
        token = hashlib.sha256(f"{os.getpid()}-{time.time_ns()}".encode()).hexdigest()[:12]
        self.name = f"wg-semantic-t003-{token}"

    def docker(self, *args: str, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
        return run(["docker", *args], input_text=input_text, check=check)

    def start(self) -> None:
        os.environ["POSTGRES_PASSWORD"] = secrets.token_urlsafe(32)
        self.docker("rm", "-f", self.name, check=False)
        self.docker(
            "run",
            "-d",
            "--rm",
            "--name",
            self.name,
            "-e",
            "POSTGRES_PASSWORD",
            "-e",
            "POSTGRES_DB=weltgewebe",
            POSTGRES_IMAGE,
        )
        os.environ.pop("POSTGRES_PASSWORD", None)
        stable_successes = 0
        for _ in range(180):
            ready = self.docker(
                "exec",
                self.name,
                "psql",
                "-X",
                "-qAt",
                "-U",
                "postgres",
                "-d",
                "weltgewebe",
                "-c",
                "SELECT 1;",
                check=False,
            )
            if ready.returncode == 0 and ready.stdout.strip() == "1":
                stable_successes += 1
                if stable_successes >= 3:
                    return
            else:
                stable_successes = 0
            time.sleep(0.25)
        logs = self.docker("logs", self.name, check=False)
        raise ProofError(
            "disposable PostgreSQL did not become stably ready: "
            + logs.stdout[-4000:]
            + logs.stderr[-4000:]
        )

    def close(self) -> None:
        self.docker("rm", "-f", self.name, check=False)

    def psql(
        self,
        sql: str,
        *,
        database: str = "weltgewebe",
        check: bool = True,
        tuples: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        argv = ["exec", "-i", self.name, "psql", "-X", "-v", "ON_ERROR_STOP=1"]
        if tuples:
            argv += ["-qAt", "-F", "\t"]
        argv += ["-U", "postgres", "-d", database]
        return self.docker(*argv, input_text=sql, check=check)

    def apply_file(self, path: Path, *, database: str = "weltgewebe") -> None:
        self.psql(path.read_text(encoding="utf-8"), database=database, tuples=False)


def projection_sql(node: dict[str, Any], *, generation_id: str = GENERATION_ID, source_version: int = 1) -> str:
    content_sha = sha256_json(node)
    document = node_document(node)
    return (
        "SELECT weltgewebe_put_search_projection("
        f"{sql_literal(generation_id)}, {sql_literal(node['id'])}, {source_version}, "
        f"{sql_literal(sha256_path(DATASET))}, {sql_literal(content_sha)}, "
        f"{sql_literal(node['title'])}, {sql_array(node['tags'])}, {sql_literal(document)}, "
        f"{sql_literal(node['language'])}, {sql_literal(node['kind'])}, {sql_literal(node['status'])}, "
        f"{sql_array(node['visibility_scopes'])}, NULL);"
    )


def insert_dataset(db: DisposablePostgres, dataset: dict[str, Any], generation_id: str = GENERATION_ID) -> None:
    node_rows = []
    for node in dataset["nodes"]:
        payload = json.dumps(
            {"summary": node["summary"], "info": node["body"], "tags": node["tags"]},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        node_rows.append(
            "("
            + ",".join(
                [
                    sql_literal(node["id"]),
                    sql_literal(node["kind"]),
                    sql_literal(node["title"]),
                    "0",
                    "0",
                    sql_literal(payload) + "::jsonb",
                ]
            )
            + ")"
        )
    db.psql(
        "INSERT INTO domain_nodes (id, kind, title, lat, lon, payload) VALUES "
        + ",".join(node_rows)
        + " ON CONFLICT (id) DO NOTHING;"
    )
    for node in dataset["nodes"]:
        result = db.psql(projection_sql(node, generation_id=generation_id)).stdout.strip()
        if result not in {"inserted", "updated", "idempotent"}:
            raise ProofError(f"unexpected projection write outcome for {node['id']}: {result!r}")


def search_rankings(db: DisposablePostgres, dataset: dict[str, Any]) -> tuple[dict[str, list[str]], list[float]]:
    rankings: dict[str, list[str]] = {}
    durations: list[float] = []
    for case in dataset["cases"]:
        filters = case["visibility_context"]["active_filters"]
        sql = (
            "SELECT node_id FROM weltgewebe_search_lexical_candidates("
            f"{sql_literal(GENERATION_ID)}, "
            f"{sql_literal(case['visibility_context']['viewer_scope'])}, "
            f"{sql_array(case['visibility_context']['visible_node_ids'])}, "
            f"{sql_literal(case['query'])}, "
            f"{sql_array(filters['kinds'])}, {sql_array(filters['tags'])}, "
            f"{sql_array(filters['languages'])}, 10);"
        )
        started = time.perf_counter()
        output = db.psql(sql).stdout.strip()
        durations.append((time.perf_counter() - started) * 1000.0)
        rankings[case["id"]] = [] if not output else output.splitlines()
    return rankings, durations


def latency_report(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)
    return {
        "median_ms": round(statistics.median(ordered), 3),
        "p95_ms": round(ordered[p95_index], 3),
        "maximum_ms": round(max(ordered), 3),
    }


def projection_digest(db: DisposablePostgres, *, database: str = "weltgewebe") -> str:
    rows = db.psql(
        """
        SELECT jsonb_build_object(
            'generation_id', generation_id,
            'node_id', node_id,
            'source_version', source_version,
            'source_revision', source_revision,
            'content_sha256', content_sha256,
            'title', title,
            'tags', tags,
            'searchable_text', searchable_text,
            'language', language,
            'kind', kind,
            'status', status,
            'visibility_scopes', visibility_scopes,
            'embedding', embedding
        )::text
        FROM search_node_projections
        ORDER BY generation_id, node_id;
        """,
        database=database,
    ).stdout.splitlines()
    return hashlib.sha256(("\n".join(rows) + "\n").encode()).hexdigest()


def extension_evidence(db: DisposablePostgres) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    for name in ["pgcrypto", "pg_trgm", "vector"]:
        output = db.psql(
            "SELECT coalesce((SELECT default_version FROM pg_available_extensions WHERE name = "
            + sql_literal(name)
            + "), ''), coalesce((SELECT extversion FROM pg_extension WHERE extname = "
            + sql_literal(name)
            + "), '');"
        ).stdout.rstrip("\n").split("\t")
        available_version, installed_version = (output + [""])[:2]
        evidence[name] = {
            "available": bool(available_version),
            "available_version": available_version or None,
            "installed": bool(installed_version),
            "installed_version": installed_version or None,
        }
    return evidence


def concurrency_proof(db: DisposablePostgres) -> dict[str, Any]:
    node_id = "syn-node-concurrency-proof"
    db.psql(
        "INSERT INTO domain_nodes (id, kind, title, payload) VALUES "
        f"({sql_literal(node_id)}, 'Test', 'Concurrency proof', '{{}}'::jsonb);"
    )
    base = {
        "id": node_id,
        "title": "Concurrency proof",
        "summary": "Concurrent projection update",
        "body": "Only the greatest source version may remain.",
        "tags": ["concurrency"],
        "language": "de",
        "kind": "Test",
        "status": "active",
        "visibility_scopes": ["public"],
    }
    db.psql(projection_sql(base))

    def update(version: int) -> str:
        changed = dict(base)
        changed["summary"] = f"Concurrent projection update version {version}"
        return db.psql(projection_sql(changed, source_version=version)).stdout.strip()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = sorted(executor.map(update, [2, 3]))
    final_version = int(
        db.psql(
            "SELECT source_version FROM search_node_projections WHERE generation_id = "
            f"{sql_literal(GENERATION_ID)} AND node_id = {sql_literal(node_id)};"
        ).stdout.strip()
    )
    current = {**base, "summary": "Concurrent projection update version 3"}
    same_sql = projection_sql(current, source_version=3)
    same = db.psql(same_sql).stdout.strip()
    visibility_conflict_sql = same_sql.replace(
        ", 'active', ARRAY['public']::TEXT[], NULL);",
        ", 'hidden', ARRAY['public']::TEXT[], NULL);",
    )
    if visibility_conflict_sql == same_sql:
        raise ProofError("failed to construct equal-version visibility conflict")
    visibility_conflict = db.psql(visibility_conflict_sql, check=False)
    stale = db.psql(projection_sql(base, source_version=1)).stdout.strip()
    conflict = db.psql(
        "SELECT weltgewebe_put_search_projection("
        f"{sql_literal(GENERATION_ID)}, {sql_literal(node_id)}, 3, 'conflict-revision', "
        f"{'0'*64!r}, 'Conflict', ARRAY['conflict'], 'Conflict', 'de', 'Test', 'active', ARRAY['public'], NULL);",
        check=False,
    )
    db.psql("DELETE FROM domain_nodes WHERE id = " + sql_literal(node_id) + ";")
    if (
        final_version != 3
        or same != "idempotent"
        or stale != "stale"
        or visibility_conflict.returncode == 0
        or conflict.returncode == 0
    ):
        raise ProofError("multi-instance projection conflict contract failed")
    return {
        "parallel_outcomes": outcomes,
        "final_source_version": final_version,
        "idempotent_outcome": same,
        "stale_outcome": stale,
        "equal_version_conflict_rejected": True,
        "equal_version_visibility_conflict_rejected": True,
    }


def measure() -> dict[str, Any]:
    dataset = load_json_object(DATASET)
    validate_goldset(dataset, load_json_object(DATASET_SCHEMA))
    t002 = load_json_object(T002_RECEIPT)
    t002_lexical = next(item for item in t002["baselines"] if item["name"] == "fts_trigram_reference")
    db = DisposablePostgres()
    db.start()
    try:
        db.apply_file(DOMAIN_NODES_MIGRATION)
        db.apply_file(UP_MIGRATION)
        server_version = db.psql("SELECT version();").stdout.strip()
        server_version_num = int(db.psql("SELECT current_setting('server_version_num');").stdout.strip())
        extensions = extension_evidence(db)
        if not extensions["pg_trgm"]["installed"]:
            raise ProofError("pg_trgm is not installed after the T003 proof contract")
        if extensions["vector"]["available"] or extensions["vector"]["installed"]:
            pgvector_decision = "available_but_not_activated_in_t003"
        else:
            pgvector_decision = "stop_pgvector_path_on_canonical_image_until_packaging_is_explicit"

        db.psql(
            "INSERT INTO search_index_generations ("
            "generation_id, provider, model_id, model_revision, dimension, document_revision, normalization_revision, state"
            ") VALUES ("
            f"{sql_literal(GENERATION_ID)}, 'ollama-local-reference', {sql_literal(MODEL_ID)}, "
            f"{sql_literal(MODEL_REVISION)}, {MODEL_DIMENSION}, {sql_literal(dataset['document_revision'])}, "
            "'weltgewebe-search-normalization-v1', 'ready');"
        )
        insert_dataset(db, dataset)
        db.psql("SELECT weltgewebe_activate_search_generation(" + sql_literal(GENERATION_ID) + ");")

        dimension_rejection = db.psql(
            projection_sql(dataset["nodes"][0]).replace(
                ", NULL);", ", ARRAY[1.0]::DOUBLE PRECISION[]);"
            ).replace(", 1, ", ", 2, ", 1),
            check=False,
        )
        if dimension_rejection.returncode == 0:
            raise ProofError("wrong embedding dimension was accepted")

        rankings, durations = search_rankings(db, dataset)
        quality = quality_report(dataset, rankings)
        if quality["visibility_leak_count"] != 0:
            raise ProofError("PostgreSQL ranking leaked a hidden or deleted node")

        all_ids = [node["id"] for node in dataset["nodes"]]
        explicit_boundary = db.psql(
            "SELECT node_id FROM weltgewebe_search_lexical_candidates("
            f"{sql_literal(GENERATION_ID)}, 'public', {sql_array(all_ids)}, "
            "'Fahrrad Reparatur', ARRAY[]::TEXT[], ARRAY[]::TEXT[], ARRAY['de'], 10);"
        ).stdout.splitlines()
        forbidden = {node["id"] for node in dataset["nodes"] if node["status"] != "active"}
        if forbidden.intersection(explicit_boundary):
            raise ProofError("status boundary leaked a hidden or deleted node")
        unauthorized = db.psql(
            "SELECT node_id FROM weltgewebe_search_lexical_candidates("
            f"{sql_literal(GENERATION_ID)}, 'public', ARRAY[]::TEXT[], 'Werkstatt', "
            "ARRAY[]::TEXT[], ARRAY[]::TEXT[], ARRAY['de'], 10);"
        ).stdout.strip()
        if unauthorized:
            raise ProofError("empty authorization set returned candidates")

        db.psql(
            "INSERT INTO search_index_generations (generation_id, provider, model_id, model_revision, dimension, document_revision, normalization_revision, state) "
            "VALUES ('t003-other-generation', 'local-test', 'other', 'sha256:other', 1024, 'node-document-v1', 'weltgewebe-search-normalization-v1', 'ready');"
        )
        db.psql(projection_sql(dataset["nodes"][0], generation_id="t003-other-generation"))
        inactive_generation_results = db.psql(
            "SELECT node_id FROM weltgewebe_search_lexical_candidates("
            "'t003-other-generation', 'public', ARRAY['syn-node-community-garden'], "
            "'Gemeinschaftsgarten Altona', ARRAY[]::TEXT[], ARRAY[]::TEXT[], ARRAY['de'], 10);"
        ).stdout.strip()
        active_generation_count = int(
            db.psql("SELECT count(*) FROM search_index_generations WHERE state = 'active';").stdout.strip()
        )
        if inactive_generation_results or active_generation_count != 1:
            raise ProofError("generation isolation failed")
        db.psql("DELETE FROM search_index_generations WHERE generation_id = 't003-other-generation';")

        concurrency = concurrency_proof(db)
        digest_before = projection_digest(db)
        db.psql("DELETE FROM search_node_projections WHERE generation_id = " + sql_literal(GENERATION_ID) + ";")
        insert_dataset(db, dataset)
        digest_after = projection_digest(db)
        if digest_before != digest_after:
            raise ProofError("deterministic projection regeneration changed the digest")

        db.docker("exec", db.name, "pg_dump", "-Fc", "-U", "postgres", "-d", "weltgewebe", "-f", "/tmp/t003.dump")
        db.docker("exec", db.name, "createdb", "-U", "postgres", "weltgewebe_restore")
        db.docker("exec", db.name, "pg_restore", "-U", "postgres", "-d", "weltgewebe_restore", "/tmp/t003.dump")
        restored_digest = projection_digest(db, database="weltgewebe_restore")
        restored_active = int(
            db.psql(
                "SELECT count(*) FROM search_index_generations WHERE state = 'active';",
                database="weltgewebe_restore",
            ).stdout.strip()
        )
        if restored_digest != digest_before or restored_active != 1:
            raise ProofError("backup/restore changed projection or generation state")
        db.apply_file(DOWN_MIGRATION, database="weltgewebe_restore")
        down_state = db.psql(
            "SELECT to_regclass('public.search_node_projections') IS NULL, to_regclass('public.domain_nodes') IS NOT NULL;",
            database="weltgewebe_restore",
        ).stdout.strip().split("\t")
        if down_state != ["t", "t"]:
            raise ProofError("down migration removed domain truth or retained search projection")

        reference_rankings = {
            case["case_id"]: case["ranked_node_ids"] for case in t002_lexical["quality"]["cases"]
        }
        comparison = []
        for case in dataset["cases"]:
            current = rankings[case["id"]]
            reference = reference_rankings[case["id"]]
            comparison.append(
                {
                    "case_id": case["id"],
                    "identical_top10": current == reference,
                    "postgres_top3": current[:3],
                    "t002_reference_top3": reference[:3],
                }
            )

        docker_version = json.loads(run(["docker", "version", "--format", "{{json .}}"] ).stdout)
        image = json.loads(
            run(
                [
                    "docker",
                    "image",
                    "inspect",
                    POSTGRES_IMAGE,
                    "--format",
                    "{{json .}}",
                ]
            ).stdout
        )
        return {
            "schema_version": 1,
            "kind": "weltgewebe_semantic_search_postgres_foundation",
            "task_id": "WELTGEWEBE-SEMANTIC-SEARCH-V1-T003",
            "measured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": {
                "repository_head_at_measurement": run(["git", "rev-parse", "HEAD"]).stdout.strip(),
                "measurement_source_mode": "repository_base_plus_hash_bound_worktree_sources",
                "worktree_dirty_at_measurement": bool(
                    run(["git", "status", "--porcelain=v1", "--untracked-files=all"]).stdout.strip()
                ),
                "dataset_path": str(DATASET.relative_to(ROOT)),
                "source_files": source_file_hashes(),
                "source_manifest_sha256": sha256_json(source_file_hashes()),
            },
            "environment": {
                "host_class": "heim-pc-local-disposable-container",
                "platform": platform.platform(),
                "python": platform.python_version(),
                "external_cost_usd": 0,
                "docker_client_version": docker_version["Client"]["Version"],
                "docker_server_version": docker_version["Server"]["Version"],
                "postgres_image": POSTGRES_IMAGE,
                "postgres_image_id": image["Id"],
                "postgres_repo_digests": image.get("RepoDigests", []),
            },
            "postgres": {
                "server_version": server_version,
                "server_version_num": server_version_num,
                "extensions": extensions,
                "pgvector_decision": pgvector_decision,
            },
            "schema": {
                "generation_identity_fields": [
                    "provider",
                    "model_id",
                    "model_revision",
                    "dimension",
                    "document_revision",
                    "normalization_revision",
                ],
                "projection_identity_fields": [
                    "source_version",
                    "source_revision",
                    "content_sha256",
                    "generation_id",
                ],
                "hard_candidate_boundaries": [
                    "active generation",
                    "status active",
                    "viewer scope",
                    "explicit allowed node ids",
                    "kind/tag/language filters",
                ],
                "ann_or_hnsw_present": False,
                "embedding_dimension_rejected": True,
            },
            "quality": {
                "postgres_fts_pg_trgm": quality,
                "performance": {
                    "scope": "docker_exec_psql_roundtrip_not_database_only",
                    **latency_report(durations),
                },
                "t002_reference_summary": {
                    key: t002_lexical["quality"][key]
                    for key in [
                        "natural_top3_relevant_count",
                        "natural_top3_relevant_rate",
                        "false_top1_count",
                        "visibility_leak_count",
                    ]
                },
                "parity": {
                    "identical_top10_case_count": sum(item["identical_top10"] for item in comparison),
                    "case_count": len(comparison),
                    "cases": comparison,
                },
            },
            "integrity": {
                "visibility_leak_count": quality["visibility_leak_count"],
                "hidden_or_deleted_excluded_with_all_ids_authorized": True,
                "empty_authorization_returns_no_candidates": True,
                "inactive_generation_returns_no_candidates": True,
                "active_generation_count": active_generation_count,
                "multi_instance": concurrency,
                "regeneration": {
                    "before_sha256": digest_before,
                    "after_sha256": digest_after,
                    "identical": True,
                },
                "backup_restore": {
                    "restored_sha256": restored_digest,
                    "identical": True,
                    "restored_active_generation_count": restored_active,
                    "down_migration_preserves_domain_nodes": True,
                },
            },
            "decision": {
                "postgres_is_canonical_search_projection_store": True,
                "pg_trgm_ready": True,
                "pgvector_ready_on_canonical_image": extensions["vector"]["available"],
                "embedding_runtime_allowed": False,
                "next_required_step": (
                    "package_and_pin_pgvector_or_choose_exact_array_storage_before_embedding_runtime"
                    if not extensions["vector"]["available"]
                    else "T004 may evaluate exact pgvector storage without ANN"
                ),
            },
            "does_not_establish": DOES_NOT_ESTABLISH,
        }
    finally:
        db.close()


def check_result(path: Path) -> None:
    result = load_json_object(path)
    required = {
        "schema_version",
        "kind",
        "task_id",
        "measured_at",
        "source",
        "environment",
        "postgres",
        "schema",
        "quality",
        "integrity",
        "decision",
        "does_not_establish",
    }
    if set(result) != required:
        raise ProofError("receipt has an unexpected top-level shape")
    if result["schema_version"] != 1 or result["kind"] != "weltgewebe_semantic_search_postgres_foundation":
        raise ProofError("receipt identity is invalid")
    if result["task_id"] != "WELTGEWEBE-SEMANTIC-SEARCH-V1-T003":
        raise ProofError("receipt task binding is invalid")
    source = result["source"]
    expected_source_keys = {
        "repository_head_at_measurement",
        "measurement_source_mode",
        "worktree_dirty_at_measurement",
        "dataset_path",
        "source_files",
        "source_manifest_sha256",
    }
    if set(source) != expected_source_keys:
        raise ProofError("receipt source shape is invalid")
    expected_source_files = source_file_hashes()
    if source["source_files"] != expected_source_files:
        raise ProofError("receipt source file hashes are stale")
    if source["source_manifest_sha256"] != sha256_json(expected_source_files):
        raise ProofError("receipt source manifest hash is stale")
    if source["measurement_source_mode"] != "repository_base_plus_hash_bound_worktree_sources":
        raise ProofError("receipt source mode is invalid")
    if source["worktree_dirty_at_measurement"] is not True:
        raise ProofError("receipt must disclose its dirty measurement worktree")
    if result["environment"]["external_cost_usd"] != 0:
        raise ProofError("receipt claims external spend")
    if result["does_not_establish"] != DOES_NOT_ESTABLISH:
        raise ProofError("receipt non-claims are stale")
    if result["schema"]["ann_or_hnsw_present"] is not False:
        raise ProofError("receipt claims ANN/HNSW")
    quality = result["quality"]["postgres_fts_pg_trgm"]
    dataset = load_json_object(DATASET)
    rankings = {item["case_id"]: item["ranked_node_ids"] for item in quality["cases"]}
    if quality != quality_report(dataset, rankings):
        raise ProofError("receipt quality aggregates do not match complete rankings")
    if quality["visibility_leak_count"] != 0:
        raise ProofError("receipt contains a visibility leak")
    if not result["integrity"]["regeneration"]["identical"]:
        raise ProofError("receipt lacks deterministic regeneration")
    if not result["integrity"]["backup_restore"]["identical"]:
        raise ProofError("receipt lacks backup/restore identity")
    if result["postgres"]["extensions"]["pg_trgm"]["installed"] is not True:
        raise ProofError("receipt lacks installed pg_trgm")
    if re.search(r'"(?:embedding|embeddings|vector|vectors)"\s*:\s*\[\s*-?\d', path.read_text(encoding="utf-8")):
        raise ProofError("receipt appears to contain raw vector data")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=RESULT)
    parser.add_argument("--check-result", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.check_result:
            check_result(args.output)
            print(f"semantic-search PostgreSQL foundation receipt valid: {args.output}")
            return 0
        result = measure()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "quality": result["quality"]["postgres_fts_pg_trgm"],
                    "decision": result["decision"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (ProofError, KeyError, ValueError, json.JSONDecodeError) as error:
        print(f"semantic-search PostgreSQL foundation proof failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

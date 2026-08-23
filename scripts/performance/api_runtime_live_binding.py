#!/usr/bin/env python3
"""Capture fail-closed live runtime binding for the api_runtime performance proof.

The canonical threshold decision remains in api_runtime_evidence.py.  This helper
only proves that the isolated API/DB stack being measured is actually bound to
the declared git revision and deterministic domain-scale fixture, and records
the digest-pinned container/tool identities used by the experiment.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = 1
CONTRACT = "api-runtime-live-binding-v1"
CANDIDATE_LIMIT_SOURCE = Path("apps/api/src/search/repository.rs")
K6_IMAGE_SUMMARY_KEY = "weltgewebe_k6_image"
SEARCH_QUERY_SUMMARY_KEY = "weltgewebe_search_query"
RUN_ID_SUMMARY_KEY = "weltgewebe_run_id"

GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DIGEST_IMAGE_RE = re.compile(r"^.+@sha256:[0-9a-f]{64}$")
CONTAINER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
CANDIDATE_LIMIT_RE = re.compile(
    r"pub\s+const\s+MAX_AUTHORIZED_CANDIDATES\s*:\s*usize\s*=\s*(\d+)\s*;"
)
BUILD_INFO_RE = re.compile(
    r'^build_info\{[^}]*commit="(?P<commit>[0-9a-f]{40})"[^}]*\}\s+1(?:\.0+)?\s*$'
)


class LiveBindingError(RuntimeError):
    """Raised when live runtime identity/data evidence is incomplete or contradictory."""


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
        raise LiveBindingError(f"cannot hash file {path}: {exc}") from exc
    return digest.hexdigest()


def _atomic_json(path: Path, value: Any) -> None:
    absolute = Path(os.path.abspath(path))
    absolute.parent.mkdir(parents=True, exist_ok=True)
    if absolute.is_symlink() or (absolute.exists() and not absolute.is_file()):
        raise LiveBindingError(f"output must be absent or a regular file: {absolute}")
    fd, temporary_name = tempfile.mkstemp(prefix=f".{absolute.name}.", dir=absolute.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(temporary, absolute)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _run(argv: Sequence[str], *, cwd: Path = REPO_ROOT, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            list(argv),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LiveBindingError(f"cannot run {argv[0]!r}: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise LiveBindingError(f"command failed ({argv[0]}): {detail}")
    return result.stdout.strip()


def _http_text(url: str, *, timeout: int = 10) -> str:
    request = urllib.request.Request(url, headers={"Accept": "application/json,text/plain,*/*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - loopback/lab URL is explicit CLI input
            if response.status != 200:
                raise LiveBindingError(f"HTTP {response.status} from {url}")
            return response.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise LiveBindingError(f"cannot read {url}: {exc}") from exc


def _http_json(url: str) -> dict[str, Any]:
    text = _http_text(url)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LiveBindingError(f"response from {url} is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise LiveBindingError(f"response from {url} must be a JSON object")
    return value


def _git_head(repo_root: Path) -> str:
    head = _run(["git", "rev-parse", "HEAD"], cwd=repo_root)
    if not GIT_SHA_RE.fullmatch(head):
        raise LiveBindingError(f"git HEAD is not a 40-hex SHA: {head!r}")
    return head


def candidate_limit_binding(repo_root: Path) -> tuple[int, str]:
    path = repo_root / CANDIDATE_LIMIT_SOURCE
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LiveBindingError(f"cannot read search candidate limit source {path}: {exc}") from exc
    matches = CANDIDATE_LIMIT_RE.findall(source)
    if len(matches) != 1:
        raise LiveBindingError(
            "search candidate limit source must contain exactly one MAX_AUTHORIZED_CANDIDATES constant"
        )
    value = int(matches[0])
    if value < 1:
        raise LiveBindingError("MAX_AUTHORIZED_CANDIDATES must be positive")
    return value, sha256_file(path)


def _manifest_and_fixture(manifest_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LiveBindingError(f"cannot read dataset manifest {manifest_path}: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise LiveBindingError("dataset manifest must use schema_version 1")
    counts = manifest.get("counts")
    files = manifest.get("files")
    if not isinstance(counts, dict) or not isinstance(files, dict):
        raise LiveBindingError("dataset manifest is missing counts/files")
    node_count = counts.get("nodes")
    node_file = files.get("nodes")
    if not isinstance(node_count, int) or isinstance(node_count, bool) or node_count < 1:
        raise LiveBindingError("dataset manifest counts.nodes must be a positive integer")
    if not isinstance(node_file, dict):
        raise LiveBindingError("dataset manifest files.nodes is invalid")
    name = node_file.get("name")
    expected_sha = node_file.get("sha256")
    if not isinstance(name, str) or not name or not isinstance(expected_sha, str) or not SHA256_RE.fullmatch(expected_sha):
        raise LiveBindingError("dataset manifest files.nodes must contain name and sha256")
    nodes_path = manifest_path.parent / name
    if sha256_file(nodes_path) != expected_sha:
        raise LiveBindingError("dataset node CSV hash does not match manifest")

    rows: list[dict[str, Any]] = []
    try:
        with nodes_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows.append(
                    {
                        "id": row["id"],
                        "kind": row["kind"],
                        "title": row["title"],
                        "lat": float(row["lat"]),
                        "lon": float(row["lon"]),
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "payload": json.loads(row["payload"]),
                    }
                )
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise LiveBindingError(f"cannot parse dataset node CSV {nodes_path}: {exc}") from exc
    if len(rows) != node_count:
        raise LiveBindingError(
            f"dataset node CSV contains {len(rows)} rows but manifest declares {node_count}"
        )
    return manifest, rows


def _rows_sha256(rows: Sequence[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(canonical_json_bytes(dict(row)))
    return digest.hexdigest()


def _psql(
    container: str,
    sql: str,
    *,
    database_user: str,
    database_name: str,
    timeout: int = 60,
) -> str:
    return _run(
        [
            "docker",
            "exec",
            container,
            "psql",
            "-U",
            database_user,
            "-d",
            database_name,
            "-At",
            "-c",
            sql,
        ],
        timeout=timeout,
    )


def _json_lines(text: str, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LiveBindingError(f"{label} produced invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise LiveBindingError(f"{label} rows must be JSON objects")
        rows.append(value)
    return rows


def _domain_rows(
    container: str,
    *,
    database_user: str,
    database_name: str,
) -> list[dict[str, Any]]:
    sql = r'''
SELECT json_build_object(
  'id', id,
  'kind', kind,
  'title', title,
  'lat', lat,
  'lon', lon,
  'created_at', to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
  'updated_at', to_char(updated_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
  'payload', payload
)::text
FROM domain_nodes
ORDER BY id;
'''
    return _json_lines(
        _psql(
            container,
            sql,
            database_user=database_user,
            database_name=database_name,
            timeout=120,
        ),
        "domain_nodes query",
    )


def _active_generation(
    container: str,
    *,
    database_user: str,
    database_name: str,
) -> dict[str, Any]:
    sql = r'''
SELECT json_build_object(
  'generation_id', generation_id,
  'state', state,
  'expected_nodes', expected_nodes,
  'completed_nodes', completed_nodes
)::text
FROM search_index_generations
WHERE state = 'active'
ORDER BY activated_at DESC NULLS LAST;
'''
    rows = _json_lines(
        _psql(container, sql, database_user=database_user, database_name=database_name),
        "active search generation query",
    )
    if len(rows) != 1:
        raise LiveBindingError(f"expected exactly one active search generation, found {len(rows)}")
    return rows[0]


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _projection_rows(
    container: str,
    generation_id: str,
    *,
    database_user: str,
    database_name: str,
) -> list[dict[str, Any]]:
    sql = f'''
SELECT json_build_object(
  'id', p.node_id,
  'kind', p.kind,
  'title', p.title,
  'search_visibility', n.search_visibility,
  'owner_account_id', weltgewebe_search_node_owner_account_id(n.payload)
)::text
FROM search_node_projections p
JOIN domain_nodes n ON n.id = p.node_id
WHERE p.generation_id = {_sql_literal(generation_id)}
ORDER BY p.node_id;
'''
    return _json_lines(
        _psql(container, sql, database_user=database_user, database_name=database_name),
        "active search projection query",
    )


def _expected_projection_identity(
    projection: Mapping[str, Any], fixture: Mapping[str, Any]
) -> dict[str, str]:
    node_id = projection.get("id")
    if not isinstance(node_id, str) or node_id != fixture.get("id"):
        raise LiveBindingError("active search projection identity does not match fixture")
    visibility = projection.get("search_visibility")
    if visibility not in {"public", "private", "hidden", "revoked"}:
        raise LiveBindingError(
            f"active search projection has invalid search_visibility: {visibility!r}"
        )
    owner_account_id = projection.get("owner_account_id")
    if owner_account_id is not None and (
        not isinstance(owner_account_id, str) or not owner_account_id
    ):
        raise LiveBindingError("active search projection owner_account_id is invalid")
    is_redacted = visibility in {"hidden", "revoked"} or (
        visibility == "private" and owner_account_id is None
    )
    redacted = "[nicht öffentlich]"
    kind = redacted if is_redacted else fixture.get("kind")
    title = redacted if is_redacted else fixture.get("title")
    if not isinstance(kind, str) or not kind or not isinstance(title, str) or not title:
        raise LiveBindingError("fixture projection identity is invalid")
    return {
        "id": node_id,
        "kind": kind,
        "title": title,
        "search_visibility": visibility,
    }


def _container_identity(container: str) -> dict[str, str]:
    if not CONTAINER_RE.fullmatch(container):
        raise LiveBindingError(f"invalid container name: {container!r}")
    image_reference = json.loads(
        _run(["docker", "inspect", container, "--format", "{{json .Config.Image}}"])
    )
    image_id = json.loads(_run(["docker", "inspect", container, "--format", "{{json .Image}}"]))
    if not isinstance(image_reference, str) or not DIGEST_IMAGE_RE.fullmatch(image_reference):
        raise LiveBindingError(
            f"container {container} is not bound to a digest image reference: {image_reference!r}"
        )
    if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise LiveBindingError(f"container {container} has an invalid image id: {image_id!r}")
    return {"name": container, "image_reference": image_reference, "image_id": image_id}


def _api_commit(base_url: str) -> str:
    text = _http_text(base_url.rstrip("/") + "/metrics")
    commits = [match.group("commit") for line in text.splitlines() if (match := BUILD_INFO_RE.match(line))]
    if len(commits) != 1:
        raise LiveBindingError("API metrics must expose exactly one build_info commit")
    return commits[0]


def capture(
    *,
    api_base_url: str,
    api_container: str,
    database_container: str,
    database_user: str,
    database_name: str,
    dataset_manifest: Path,
    search_query: str,
    k6_image: str,
    run_id: str,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    if not search_query:
        raise LiveBindingError("search_query must be non-empty")
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        raise LiveBindingError("run_id has an invalid format")
    if not DIGEST_IMAGE_RE.fullmatch(k6_image):
        raise LiveBindingError("k6 image must be an exact @sha256 digest reference")

    git_head = _git_head(repo_root)
    candidate_limit, candidate_source_sha256 = candidate_limit_binding(repo_root)
    manifest, fixture_rows = _manifest_and_fixture(dataset_manifest)
    fixture_by_id = {row["id"]: row for row in fixture_rows}
    if len(fixture_by_id) != len(fixture_rows):
        raise LiveBindingError("dataset fixture contains duplicate node ids")

    db_rows = _domain_rows(
        database_container,
        database_user=database_user,
        database_name=database_name,
    )
    fixture_sha = _rows_sha256(fixture_rows)
    db_sha = _rows_sha256(db_rows)
    if len(db_rows) != len(fixture_rows) or db_sha != fixture_sha:
        raise LiveBindingError(
            "live domain_nodes content does not match the deterministic dataset fixture"
        )

    generation = _active_generation(
        database_container,
        database_user=database_user,
        database_name=database_name,
    )
    generation_id = generation.get("generation_id")
    if not isinstance(generation_id, str) or not generation_id:
        raise LiveBindingError("active search generation has no generation_id")
    projection_rows = _projection_rows(
        database_container,
        generation_id,
        database_user=database_user,
        database_name=database_name,
    )
    active_count = len(projection_rows)
    # MAX_AUTHORIZED_CANDIDATES caps rows materialized by one repository query;
    # it does not cap the active projection index. Activation requires a
    # projection for every live search_node_version, so large fixtures may
    # legitimately have active_count > candidate_limit.
    expected_nodes = generation.get("expected_nodes")
    completed_nodes = generation.get("completed_nodes")
    if (
        active_count < 1
        or expected_nodes != active_count
        or completed_nodes != active_count
    ):
        raise LiveBindingError("active search generation is incomplete")

    expected_projection_rows: list[dict[str, Any]] = []
    actual_projection_rows: list[dict[str, Any]] = []
    for projection in projection_rows:
        node_id = projection.get("id")
        fixture = fixture_by_id.get(node_id)
        if fixture is None:
            raise LiveBindingError(f"active search projection {node_id!r} is absent from fixture")
        expected_projection_rows.append(_expected_projection_identity(projection, fixture))
        actual_projection_rows.append(
            {
                "id": projection.get("id"),
                "kind": projection.get("kind"),
                "title": projection.get("title"),
                "search_visibility": projection.get("search_visibility"),
            }
        )
    projection_sha = _rows_sha256(actual_projection_rows)
    expected_projection_sha = _rows_sha256(expected_projection_rows)
    if projection_sha != expected_projection_sha:
        raise LiveBindingError("active search projection content does not match fixture nodes")

    api_commit = _api_commit(api_base_url)
    if api_commit != git_head:
        raise LiveBindingError(
            f"API build_info commit {api_commit} does not match checkout HEAD {git_head}"
        )

    search_url = api_base_url.rstrip("/") + "/search?" + urllib.parse.urlencode(
        {"q": search_query, "limit": 5}
    )
    search = _http_json(search_url)
    if search.get("mode") != "lexical_fallback":
        raise LiveBindingError(
            f"search binding requires lexical_fallback, observed {search.get('mode')!r}"
        )
    if search.get("generation_id") != generation_id:
        raise LiveBindingError("/search generation_id does not match the active database generation")
    items = search.get("items")
    if not isinstance(items, list) or not items:
        raise LiveBindingError("/search returned no items for the binding query")
    sampled_items: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            raise LiveBindingError("/search items must be objects")
        node_id = item.get("id")
        title = item.get("title")
        fixture = fixture_by_id.get(node_id)
        if fixture is None or title != fixture["title"]:
            raise LiveBindingError("/search returned an item not matching the deterministic fixture")
        sampled_items.append({"id": str(node_id), "title": str(title)})

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "run_id": run_id,
        "git_head": git_head,
        "dataset": {
            "manifest_sha256": sha256_file(dataset_manifest),
            "domain_nodes_count": len(db_rows),
            "fixture_nodes_content_sha256": fixture_sha,
            "database_nodes_content_sha256": db_sha,
        },
        "search": {
            "query": search_query,
            "mode": "lexical_fallback",
            "generation_id": generation_id,
            "candidate_limit_contract": candidate_limit,
            "candidate_limit_source": str(CANDIDATE_LIMIT_SOURCE),
            "candidate_limit_source_sha256": candidate_source_sha256,
            "expected_nodes": int(expected_nodes),
            "completed_nodes": int(completed_nodes),
            "active_projection_count": active_count,
            "fixture_projection_content_sha256": expected_projection_sha,
            "database_projection_content_sha256": projection_sha,
            "sampled_items": sampled_items,
        },
        "runtime": {
            "api_commit": api_commit,
            "api_container": _container_identity(api_container),
            "postgres_container": _container_identity(database_container),
            "k6_image_reference": k6_image,
        },
    }
    return validate_receipt(receipt)


def validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "contract",
        "run_id",
        "git_head",
        "dataset",
        "search",
        "runtime",
    }:
        raise LiveBindingError("live binding receipt has an invalid top-level shape")
    if value.get("schema_version") != SCHEMA_VERSION or value.get("contract") != CONTRACT:
        raise LiveBindingError("live binding receipt has an unsupported contract/schema")
    run_id = value.get("run_id")
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        raise LiveBindingError("live binding run_id is invalid")
    head = value.get("git_head")
    if not isinstance(head, str) or not GIT_SHA_RE.fullmatch(head):
        raise LiveBindingError("live binding git_head is invalid")

    dataset = value.get("dataset")
    if not isinstance(dataset, dict) or set(dataset) != {
        "manifest_sha256",
        "domain_nodes_count",
        "fixture_nodes_content_sha256",
        "database_nodes_content_sha256",
    }:
        raise LiveBindingError("live binding dataset shape is invalid")
    if not isinstance(dataset["manifest_sha256"], str) or not SHA256_RE.fullmatch(dataset["manifest_sha256"]):
        raise LiveBindingError("live binding manifest_sha256 is invalid")
    if not isinstance(dataset["domain_nodes_count"], int) or isinstance(dataset["domain_nodes_count"], bool) or dataset["domain_nodes_count"] < 1:
        raise LiveBindingError("live binding domain_nodes_count must be positive")
    for key in ("fixture_nodes_content_sha256", "database_nodes_content_sha256"):
        if not isinstance(dataset[key], str) or not SHA256_RE.fullmatch(dataset[key]):
            raise LiveBindingError(f"live binding {key} is invalid")
    if dataset["fixture_nodes_content_sha256"] != dataset["database_nodes_content_sha256"]:
        raise LiveBindingError("live binding domain node content hashes contradict each other")

    search = value.get("search")
    required_search = {
        "query",
        "mode",
        "generation_id",
        "candidate_limit_contract",
        "candidate_limit_source",
        "candidate_limit_source_sha256",
        "expected_nodes",
        "completed_nodes",
        "active_projection_count",
        "fixture_projection_content_sha256",
        "database_projection_content_sha256",
        "sampled_items",
    }
    if not isinstance(search, dict) or set(search) != required_search:
        raise LiveBindingError("live binding search shape is invalid")
    if not isinstance(search["query"], str) or not search["query"]:
        raise LiveBindingError("live binding search query is invalid")
    if search["mode"] != "lexical_fallback":
        raise LiveBindingError("live binding search mode must be lexical_fallback")
    if not isinstance(search["generation_id"], str) or not search["generation_id"]:
        raise LiveBindingError("live binding search generation_id is invalid")
    limit = search["candidate_limit_contract"]
    active = search["active_projection_count"]
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise LiveBindingError("live binding candidate limit must be positive")
    if not isinstance(active, int) or isinstance(active, bool) or active < 1:
        raise LiveBindingError("live binding active projection count must be positive")
    if search["expected_nodes"] != active or search["completed_nodes"] != active:
        raise LiveBindingError("live binding active generation is incomplete")
    if search["candidate_limit_source"] != str(CANDIDATE_LIMIT_SOURCE):
        raise LiveBindingError("live binding candidate-limit source is not canonical")
    if not isinstance(search["candidate_limit_source_sha256"], str) or not SHA256_RE.fullmatch(search["candidate_limit_source_sha256"]):
        raise LiveBindingError("live binding candidate-limit source hash is invalid")
    for key in ("fixture_projection_content_sha256", "database_projection_content_sha256"):
        if not isinstance(search[key], str) or not SHA256_RE.fullmatch(search[key]):
            raise LiveBindingError(f"live binding {key} is invalid")
    if search["fixture_projection_content_sha256"] != search["database_projection_content_sha256"]:
        raise LiveBindingError("live binding active projection hashes contradict each other")
    sampled = search["sampled_items"]
    if not isinstance(sampled, list) or not sampled:
        raise LiveBindingError("live binding search sampled_items must be non-empty")
    for item in sampled:
        if not isinstance(item, dict) or set(item) != {"id", "title"}:
            raise LiveBindingError("live binding sampled search item shape is invalid")
        if not all(isinstance(item[key], str) and item[key] for key in ("id", "title")):
            raise LiveBindingError("live binding sampled search item values are invalid")

    runtime = value.get("runtime")
    if not isinstance(runtime, dict) or set(runtime) != {
        "api_commit",
        "api_container",
        "postgres_container",
        "k6_image_reference",
    }:
        raise LiveBindingError("live binding runtime shape is invalid")
    if runtime["api_commit"] != head:
        raise LiveBindingError("live binding API commit does not match git_head")
    if not isinstance(runtime["k6_image_reference"], str) or not DIGEST_IMAGE_RE.fullmatch(runtime["k6_image_reference"]):
        raise LiveBindingError("live binding k6 image is not digest-bound")
    for label in ("api_container", "postgres_container"):
        container = runtime[label]
        if not isinstance(container, dict) or set(container) != {"name", "image_reference", "image_id"}:
            raise LiveBindingError(f"live binding {label} identity shape is invalid")
        if not isinstance(container["name"], str) or not CONTAINER_RE.fullmatch(container["name"]):
            raise LiveBindingError(f"live binding {label} name is invalid")
        if not isinstance(container["image_reference"], str) or not DIGEST_IMAGE_RE.fullmatch(container["image_reference"]):
            raise LiveBindingError(f"live binding {label} image is not digest-bound")
        if not isinstance(container["image_id"], str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", container["image_id"]):
            raise LiveBindingError(f"live binding {label} image id is invalid")

    return json.loads(json.dumps(value))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", required=True)
    parser.add_argument("--api-container", required=True)
    parser.add_argument("--database-container", required=True)
    parser.add_argument("--database-user", default="welt")
    parser.add_argument("--database-name", default="weltgewebe")
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--search-query", required=True)
    parser.add_argument("--k6-image", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = capture(
            api_base_url=args.api_base_url,
            api_container=args.api_container,
            database_container=args.database_container,
            database_user=args.database_user,
            database_name=args.database_name,
            dataset_manifest=args.dataset_manifest,
            search_query=args.search_query,
            k6_image=args.k6_image,
            run_id=args.run_id,
        )
        _atomic_json(args.output, receipt)
        print(json.dumps({"schema_version": SCHEMA_VERSION, "status": "pass", "output": str(args.output)}, sort_keys=True))
        return 0
    except LiveBindingError as exc:
        print(f"api-runtime-live-binding: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

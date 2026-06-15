import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple
from urllib.parse import parse_qs, unquote, urlparse

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

CLASSIFICATION_COUNTERS = {
    "typed_node_reference": "typed_node_references",
    "typed_node_missing_reference": "typed_node_missing_references",
    "typed_non_node_reference": "typed_non_node_references",
    "typed_unknown_reference": "typed_unknown_references",
    "untyped_existing_node_reference": "untyped_existing_node_references",
    "untyped_missing_reference": "untyped_missing_references",
}

def increment_classification(summary: Dict[str, int], classification: str) -> None:
    try:
        counter_key = CLASSIFICATION_COUNTERS[classification]
    except KeyError:
        raise RuntimeError(f"Unknown edge reference classification: {classification}")
    summary[counter_key] += 1


def hash_ref(ref: str, prefix: str) -> str:
    if not ref:
        return ""
    digest = hashlib.sha256(ref.encode('utf-8')).hexdigest()[:12]
    return f"{prefix}:sha256:{digest}"

def hash_id(id_val: Optional[str]) -> Optional[str]:
    if not id_val:
        return None
    return hash_ref(id_val, "ref")

def hash_edge(id_val: str) -> str:
    return hash_ref(id_val, "edge")

def source_fingerprint(path: str) -> Dict[str, Any]:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return {
        "label": p.name,
        "size_bytes": p.stat().st_size,
        "sha256": h.hexdigest(),
    }

def postgres_env_from_database_url(database_url: str) -> Dict[str, str]:
    parsed = urlparse(database_url)
    env = os.environ.copy()

    # Remove existing PG* env vars
    for key in [
        "PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE",
        "PGSSLMODE", "PGCONNECT_TIMEOUT", "PGAPPNAME",
        "PGSSLROOTCERT", "PGSSLCERT", "PGSSLKEY", "DATABASE_URL"
    ]:
        env.pop(key, None)

    if parsed.hostname:
        env["PGHOST"] = parsed.hostname
    if parsed.port:
        env["PGPORT"] = str(parsed.port)
    if parsed.username:
        env["PGUSER"] = unquote(parsed.username)
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    if parsed.path and parsed.path != "/":
        env["PGDATABASE"] = unquote(parsed.path.lstrip("/"))

    query = parse_qs(parsed.query, keep_blank_values=False)
    query_env_map = {
        "sslmode": "PGSSLMODE",
        "connect_timeout": "PGCONNECT_TIMEOUT",
        "application_name": "PGAPPNAME",
        "sslrootcert": "PGSSLROOTCERT",
        "sslcert": "PGSSLCERT",
        "sslkey": "PGSSLKEY",
    }
    for key, env_key in query_env_map.items():
        values = query.get(key)
        if values:
            env[env_key] = values[-1]

    return env

def sanitize_psql_stderr(stderr: str) -> str:
    text = stderr or ""
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        text = text.replace(database_url, "<redacted>")
        parsed = urlparse(database_url)
        for value in [
            parsed.hostname,
            parsed.username,
            parsed.password,
            parsed.path.lstrip("/") if parsed.path else None,
        ]:
            if value:
                text = text.replace(value, "<redacted>")
    text = re.sub(r"postgres(?:ql)?://\S+", "postgresql://<redacted>", text)
    text = re.sub(r"(?i)(password=)[^ \n\t]+", r"\1<redacted>", text)
    text = re.sub(r"(?i)(PGPASSWORD=)[^ \n\t]+", r"\1<redacted>", text)
    return text[:500]

def iter_psql_json_lines(sql: str, postgres_env: Dict[str, str], label: str) -> Iterator[str]:
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr_file:
        proc = subprocess.Popen(
            ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-c", sql],
            env=postgres_env,
            stdout=subprocess.PIPE,
            stderr=stderr_file,
            text=True,
        )
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.strip()
                if line:
                    yield line
            returncode = proc.wait()
            stderr_file.seek(0)
            stderr = stderr_file.read()
            if returncode != 0:
                logging.error(
                    "Failed to query %s via psql; returncode=%s; stderr=%s",
                    label,
                    returncode,
                    sanitize_psql_stderr(stderr),
                )
                sys.exit(1)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""

def load_jsonl_nodes(path: str) -> Tuple[Set[str], Dict[str, int], Dict[str, Any]]:
    node_ids = set()
    summary = {
        "node_records_total": 0,
        "node_ids_total": 0,
        "node_duplicate_ids": 0,
        "node_invalid_json_records": 0,
        "node_non_object_json_records": 0,
        "nodes_missing_id": 0,
        "nodes_non_string_id": 0,
        "nodes_empty_id": 0,
    }

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                summary["node_records_total"] += 1
                try:
                    obj = json.loads(line)
                    if not isinstance(obj, dict):
                        summary["node_non_object_json_records"] += 1
                        continue

                    if "id" not in obj:
                        summary["nodes_missing_id"] += 1
                        continue

                    if not isinstance(obj["id"], str):
                        summary["nodes_non_string_id"] += 1
                        continue

                    if obj["id"].strip() == "":
                        summary["nodes_empty_id"] += 1
                        continue

                    if obj["id"] in node_ids:
                        summary["node_duplicate_ids"] += 1
                        continue

                    node_ids.add(obj["id"])
                    summary["node_ids_total"] += 1
                except json.JSONDecodeError:
                    summary["node_invalid_json_records"] += 1
    except FileNotFoundError:
        logging.error("Nodes file not found: %s", path)
        sys.exit(1)

    return node_ids, summary, source_fingerprint(path)

def load_postgres_nodes(postgres_env: Dict[str, str]) -> Tuple[Set[str], Dict[str, int]]:
    node_ids = set()
    summary = {
        "node_records_total": 0,
        "node_ids_total": 0,
        "node_duplicate_ids": 0,
        "node_invalid_json_records": 0,
        "node_non_object_json_records": 0,
        "nodes_missing_id": 0,
        "nodes_non_string_id": 0,
        "nodes_empty_id": 0,
    }

    sql = "SELECT json_build_object('id', id) FROM domain_nodes;"
    for line in iter_psql_json_lines(sql, postgres_env, "domain_nodes"):
        summary["node_records_total"] += 1
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            summary["node_invalid_json_records"] += 1
            continue

        if not isinstance(obj, dict):
            summary["node_non_object_json_records"] += 1
            continue
        if "id" not in obj:
            summary["nodes_missing_id"] += 1
            continue
        if not isinstance(obj["id"], str):
            summary["nodes_non_string_id"] += 1
            continue
        if obj["id"].strip() == "":
            summary["nodes_empty_id"] += 1
            continue
        if obj["id"] in node_ids:
            summary["node_duplicate_ids"] += 1
            continue
        node_ids.add(obj["id"])
        summary["node_ids_total"] += 1

    return node_ids, summary

def iter_jsonl_edges(path: str, edge_parse_summary: Dict[str, int]) -> Iterator[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            line_number = 0
            for line in f:
                line_number += 1
                line = line.strip()
                if not line:
                    continue
                edge_parse_summary["edge_records_total"] += 1
                try:
                    obj = json.loads(line)
                    if not isinstance(obj, dict):
                        edge_parse_summary["non_object_json_records"] += 1
                        continue
                    obj["line_number"] = line_number
                    yield obj
                except json.JSONDecodeError:
                    edge_parse_summary["invalid_json_records"] += 1
    except FileNotFoundError:
        logging.error("Edges file not found: %s", path)
        sys.exit(1)

def iter_postgres_edges(postgres_env: Dict[str, str], edge_parse_summary: Dict[str, int]) -> Iterator[Dict[str, Any]]:
    sql = """SELECT json_build_object(
  'id', id,
  'source_id', source_id,
  'target_id', target_id,
  'source_type', payload->>'source_type',
  'target_type', payload->>'target_type'
) FROM domain_edges;
# Type hints are currently stored in domain_edges.payload by the existing
# edge write path/migration; do not reference flat source_type/target_type
# columns unless a later migration introduces them.
"""
    row_number = 0
    for line in iter_psql_json_lines(sql, postgres_env, "domain_edges"):
        row_number += 1
        edge_parse_summary["edge_records_total"] += 1
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            edge_parse_summary["invalid_json_records"] += 1
            continue

        if not isinstance(obj, dict):
            edge_parse_summary["non_object_json_records"] += 1
            continue
        obj["row_number"] = row_number
        yield obj


ALLOWED_TYPE_HINTS = {"node", "account", "role"}

def safe_type_hint_for_finding(type_hint: Any) -> Tuple[Optional[str], Optional[str]]:
    if type_hint is None:
        return None, None
    if isinstance(type_hint, str):
        if type_hint in ALLOWED_TYPE_HINTS:
            return type_hint, "str"
        if len(type_hint) <= 64 and re.fullmatch(r"[A-Za-z0-9_.:-]+", type_hint):
            return type_hint, "str"
        return hash_ref(type_hint, "type_hint"), "str"
    type_hint_type = type(type_hint).__name__
    return f"<{type_hint_type}>", type_hint_type

def classify_edge_side(
    *,
    edge_ref: str,
    side: str,
    target_id: Optional[str],
    type_hint: Optional[Any],
    node_ids: Set[str],
    show_ids: bool,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    target_ref = target_id if show_ids else hash_id(target_id)

    type_hint_value = type_hint if isinstance(type_hint, str) else None
    safe_type_hint, type_hint_type = safe_type_hint_for_finding(type_hint)

    if type_hint_value == "node":
        if target_id in node_ids:
            return "typed_node_reference", None
        else:
            return "typed_node_missing_reference", {"edge_ref": edge_ref, "side": side, "target_ref": target_ref, "type_hint": "node", "classification": "typed_node_missing_reference"}
    elif type_hint_value in ["account", "role"]:
        return "typed_non_node_reference", {"edge_ref": edge_ref, "side": side, "target_ref": target_ref, "type_hint": type_hint_value, "classification": "typed_non_node_reference"}
    elif type_hint is not None:
        finding = {"edge_ref": edge_ref, "side": side, "target_ref": target_ref, "type_hint": safe_type_hint, "classification": "typed_unknown_reference"}
        if type_hint_type:
            finding["type_hint_type"] = type_hint_type
        return "typed_unknown_reference", finding
    else:
        if target_id in node_ids:
            return "untyped_existing_node_reference", None
        else:
            return "untyped_missing_reference", {"edge_ref": edge_ref, "side": side, "target_ref": target_ref, "type_hint": None, "classification": "untyped_missing_reference"}

def append_finding(
    findings: list[Dict[str, Any]],
    finding: Dict[str, Any],
    max_findings: int,
) -> bool:
    if max_findings > 0 and len(findings) < max_findings:
        findings.append(finding)
        return False
    return True

def evaluate_audit_data(
    *,
    node_ids: Set[str],
    edges: Iterable[Dict[str, Any]],
    source: Dict[str, Any],
    source_kind: str,
    show_ids: bool,
    node_parse_summary: Dict[str, int],
    edge_parse_summary: Dict[str, int],
    max_findings: int,
) -> Dict[str, Any]:

    summary = {
        "nodes_total": node_parse_summary["node_ids_total"],
        "edges_total": 0,
        "auditable_edges_total": 0,
        "edge_records_total": 0,
        "edge_sides_total": 0,
        "typed_node_references": 0,
        "typed_node_missing_references": 0,
        "typed_non_node_references": 0,
        "typed_unknown_references": 0,
        "untyped_existing_node_references": 0,
        "untyped_missing_references": 0,
        "node_reference_sides": 0,
        "missing_node_reference_sides": 0,
        "malformed_edges": 0,
        "invalid_json_records": 0,
        "non_object_json_records": 0,
        "edges_with_any_missing_node_reference": 0,
        "edges_with_both_missing_node_references": 0,
        "node_records_total": node_parse_summary["node_records_total"],
        "node_invalid_json_records": node_parse_summary["node_invalid_json_records"],
        "node_non_object_json_records": node_parse_summary["node_non_object_json_records"],
        "nodes_missing_id": node_parse_summary["nodes_missing_id"],
        "nodes_non_string_id": node_parse_summary["nodes_non_string_id"],
        "nodes_empty_id": node_parse_summary["nodes_empty_id"],
        "node_duplicate_ids": node_parse_summary["node_duplicate_ids"],
    }

    findings = []
    findings_truncated = False

    for edge in edges:
        edge_id = edge.get("id")
        source_id = edge.get("source_id")
        target_id = edge.get("target_id")
        source_type = edge.get("source_type")
        target_type = edge.get("target_type")

        if (not is_non_empty_string(edge_id)
            or not is_non_empty_string(source_id)
            or not is_non_empty_string(target_id)):
            summary["malformed_edges"] += 1

            edge_ref = ""
            if "line_number" in edge:
                edge_ref = hash_ref(f"line:{edge['line_number']}", "edge")
            elif "row_number" in edge:
                edge_ref = hash_ref(f"row:{edge['row_number']}", "edge")
            else:
                edge_ref = hash_ref("unknown", "edge")

            finding = {
                "edge_ref": edge_ref,
                "side": "unknown",
                "target_ref": None,
                "type_hint": None,
                "classification": "malformed_edge"
            }
            if append_finding(findings, finding, max_findings):
                findings_truncated = True
            continue

        summary["auditable_edges_total"] += 1
        edge_ref = edge_id if show_ids else hash_edge(edge_id)
        missing_node_count = 0

        # Source
        src_class, src_finding = classify_edge_side(
            edge_ref=edge_ref, side="source", target_id=source_id,
            type_hint=source_type, node_ids=node_ids, show_ids=show_ids
        )
        if src_class == "typed_node_missing_reference" or src_class == "untyped_missing_reference":
            missing_node_count += 1
        increment_classification(summary, src_class)
        if src_finding:
            if append_finding(findings, src_finding, max_findings):
                findings_truncated = True

        # Target
        tgt_class, tgt_finding = classify_edge_side(
            edge_ref=edge_ref, side="target", target_id=target_id,
            type_hint=target_type, node_ids=node_ids, show_ids=show_ids
        )
        if tgt_class == "typed_node_missing_reference" or tgt_class == "untyped_missing_reference":
            missing_node_count += 1
        increment_classification(summary, tgt_class)
        if tgt_finding:
            if append_finding(findings, tgt_finding, max_findings):
                findings_truncated = True

        if missing_node_count > 0:
            summary["edges_with_any_missing_node_reference"] += 1
        if missing_node_count == 2:
            summary["edges_with_both_missing_node_references"] += 1

    summary["edge_records_total"] = edge_parse_summary["edge_records_total"]
    summary["invalid_json_records"] = edge_parse_summary["invalid_json_records"]
    summary["non_object_json_records"] = edge_parse_summary["non_object_json_records"]
    summary["edges_total"] = summary["edge_records_total"]

    summary["edge_sides_total"] = summary["auditable_edges_total"] * 2
    summary["node_reference_sides"] = summary["typed_node_references"] + summary["untyped_existing_node_references"]
    summary["missing_node_reference_sides"] = summary["typed_node_missing_references"] + summary["untyped_missing_references"]

    strict_node_fk_ready = (
        source_kind == "runtime" and
        summary["node_invalid_json_records"] == 0 and
        summary["node_non_object_json_records"] == 0 and
        summary["nodes_missing_id"] == 0 and
        summary["nodes_non_string_id"] == 0 and
        summary["nodes_empty_id"] == 0 and
        summary["node_duplicate_ids"] == 0 and
        summary["malformed_edges"] == 0 and
        summary["invalid_json_records"] == 0 and
        summary["non_object_json_records"] == 0 and
        summary["typed_node_missing_references"] == 0 and
        summary["typed_non_node_references"] == 0 and
        summary["typed_unknown_references"] == 0 and
        summary["untyped_missing_references"] == 0
    )

    loose_reference_semantics_observed = summary["typed_non_node_references"] > 0

    requires_cleanup = (
        summary["node_invalid_json_records"] > 0 or
        summary["node_non_object_json_records"] > 0 or
        summary["nodes_missing_id"] > 0 or
        summary["nodes_non_string_id"] > 0 or
        summary["nodes_empty_id"] > 0 or
        summary["node_duplicate_ids"] > 0 or
        summary["malformed_edges"] > 0 or
        summary["invalid_json_records"] > 0 or
        summary["non_object_json_records"] > 0 or
        summary["typed_node_missing_references"] > 0 or
        summary["untyped_missing_references"] > 0
    )

    requires_policy_decision = (
        summary["typed_non_node_references"] > 0 or
        summary["typed_unknown_references"] > 0 or
        summary["untyped_missing_references"] > 0 or
        summary["typed_node_missing_references"] > 0
    )

    requires_runtime_data_run = source_kind != "runtime"

    type_hint_backfill_recommended = summary["untyped_existing_node_references"] > 0
    fk_compatible_reference_sides = summary["typed_node_references"] + summary["untyped_existing_node_references"]

    findings.sort(key=lambda x: (
        x.get("classification", ""),
        x.get("side", ""),
        x.get("edge_ref", ""),
        str(x.get("target_ref", ""))
    ))

    return {
        "schema_version": "1.0.0",
        "source": source,
        "summary": summary,
        "policy_signals": {
            "strict_node_fk_ready": strict_node_fk_ready,
            "loose_reference_semantics_observed": loose_reference_semantics_observed,
            "requires_policy_decision": requires_policy_decision,
            "requires_cleanup": requires_cleanup,
            "requires_runtime_data_run": requires_runtime_data_run,
            "type_hint_backfill_recommended": type_hint_backfill_recommended,
            "fk_compatible_reference_sides": fk_compatible_reference_sides
        },
        "findings_truncated": findings_truncated,
        "findings_limit": max_findings,
        "findings": findings
    }

def main():
    parser = argparse.ArgumentParser(description="Audit domain edge references")
    parser.add_argument("--nodes-jsonl", type=str, help="Path to nodes JSONL file")
    parser.add_argument("--edges-jsonl", type=str, help="Path to edges JSONL file")
    parser.add_argument("--postgres", action="store_true", help="Run against PostgreSQL runtime")
    parser.add_argument("--source-kind", type=str, choices=["repo-fixture", "runtime", "unknown"], default="unknown", help="Source kind")
    parser.add_argument("--format", type=str, choices=["json"], default="json", help="Output format")
    parser.add_argument("--show-ids", action="store_true", help="Show full IDs (not for committed reports)")
    parser.add_argument("--max-findings", type=int, default=100, help="Maximum number of findings to output")
    args = parser.parse_args()

    if args.max_findings < 0:
        logging.error("--max-findings must be >= 0")
        sys.exit(1)

    if args.postgres:
        if shutil.which("psql") is None:
            logging.error("psql is not available")
            sys.exit(1)

        if "DATABASE_URL" not in os.environ:
            logging.error("DATABASE_URL not set for PostgreSQL audit")
            sys.exit(1)

        postgres_env = postgres_env_from_database_url(os.environ["DATABASE_URL"])
        node_ids, node_summary = load_postgres_nodes(postgres_env)

        edge_parse_summary = {
            "edge_records_total": 0,
            "invalid_json_records": 0,
            "non_object_json_records": 0,
        }
        edges_iterable = iter_postgres_edges(postgres_env, edge_parse_summary)

        source = {
            "kind": "postgres",
            "source_kind": args.source_kind
        }
    elif args.nodes_jsonl and args.edges_jsonl:
        node_ids, node_summary, node_source = load_jsonl_nodes(args.nodes_jsonl)

        edge_parse_summary = {
            "edge_records_total": 0,
            "invalid_json_records": 0,
            "non_object_json_records": 0,
        }
        edges_iterable = iter_jsonl_edges(args.edges_jsonl, edge_parse_summary)

        source = {
            "kind": "jsonl",
            "source_kind": args.source_kind,
            "nodes_source": node_source,
            "edges_source": source_fingerprint(args.edges_jsonl)
        }
    else:
        logging.error("Must provide either --postgres or both --nodes-jsonl and --edges-jsonl")
        sys.exit(1)

    result = evaluate_audit_data(
        node_ids=node_ids,
        edges=edges_iterable,
        source=source,
        source_kind=args.source_kind,
        show_ids=args.show_ids,
        node_parse_summary=node_summary,
        edge_parse_summary=edge_parse_summary,
        max_findings=args.max_findings
    )

    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()

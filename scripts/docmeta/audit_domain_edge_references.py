import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple
from urllib.parse import unquote, urlparse

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def hash_ref(ref: str, prefix: str) -> str:
    if not ref:
        return ""
    digest = hashlib.sha256(ref.encode('utf-8')).hexdigest()[:12]
    return f"{prefix}:sha256:{digest}"

def hash_id(id_val: Optional[str]) -> Optional[str]:
    if not id_val:
        return None
    return hash_ref(id_val, "ref")

def hash_edge(id_val: Optional[str]) -> str:
    if not id_val:
        return "edge:sha256:unknown"
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
    env.pop("DATABASE_URL", None)
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
    return env

def classify_edge_side(
    *,
    edge_ref: str,
    side: str,
    target_id: Optional[str],
    type_hint: Optional[str],
    node_ids: Set[str],
    show_ids: bool,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    target_ref = target_id if show_ids else hash_id(target_id)

    if type_hint == "node":
        if target_id in node_ids:
            return "typed_node_reference", None
        else:
            return "typed_node_missing_reference", {"edge_ref": edge_ref, "side": side, "target_ref": target_ref, "type_hint": "node", "classification": "typed_node_missing_reference"}
    elif type_hint in ["account", "role"]:
        return "typed_non_node_reference", {"edge_ref": edge_ref, "side": side, "target_ref": target_ref, "type_hint": type_hint, "classification": "typed_non_node_reference"}
    elif type_hint is not None:
        return "typed_unknown_reference", {"edge_ref": edge_ref, "side": side, "target_ref": target_ref, "type_hint": type_hint, "classification": "typed_unknown_reference"}
    else:
        if target_id in node_ids:
            return "untyped_existing_node_reference", {"edge_ref": edge_ref, "side": side, "target_ref": target_ref, "type_hint": None, "classification": "untyped_existing_node_reference"}
        else:
            return "untyped_missing_reference", {"edge_ref": edge_ref, "side": side, "target_ref": target_ref, "type_hint": None, "classification": "untyped_missing_reference"}

def load_jsonl_nodes(path: str) -> Tuple[Set[str], Dict[str, int], Dict[str, Any]]:
    node_ids = set()
    summary = {
        "node_records_total": 0,
        "node_ids_total": 0,
        "node_invalid_json_records": 0,
        "node_non_object_json_records": 0,
        "nodes_missing_id": 0,
        "nodes_non_string_id": 0,
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

                    node_ids.add(obj["id"])
                    summary["node_ids_total"] += 1
                except json.JSONDecodeError:
                    summary["node_invalid_json_records"] += 1
    except FileNotFoundError:
        logging.error(f"Nodes file not found: {path}")
        sys.exit(1)

    return node_ids, summary, source_fingerprint(path)

def load_jsonl_edges(path: str) -> Tuple[list[Dict[str, Any]], Dict[str, int], Dict[str, Any]]:
    edges = []
    summary = {
        "edge_records_total": 0,
        "invalid_json_records": 0,
        "non_object_json_records": 0,
    }

    try:
        with open(path, "r", encoding="utf-8") as f:
            line_number = 0
            for line in f:
                line_number += 1
                line = line.strip()
                if not line:
                    continue
                summary["edge_records_total"] += 1
                try:
                    obj = json.loads(line)
                    if not isinstance(obj, dict):
                        summary["non_object_json_records"] += 1
                        continue
                    obj["line_number"] = line_number
                    edges.append(obj)
                except json.JSONDecodeError:
                    summary["invalid_json_records"] += 1
    except FileNotFoundError:
        logging.error(f"Edges file not found: {path}")
        sys.exit(1)

    return edges, summary, source_fingerprint(path)

def load_postgres_nodes(postgres_env: Dict[str, str]) -> Tuple[Set[str], Dict[str, int]]:
    node_ids = set()
    summary = {
        "node_records_total": 0,
        "node_ids_total": 0,
        "node_invalid_json_records": 0,
        "node_non_object_json_records": 0,
        "nodes_missing_id": 0,
        "nodes_non_string_id": 0,
    }

    sql = "SELECT json_build_object('id', id) FROM domain_nodes;"
    try:
        result = subprocess.run(
            ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-c", sql],
            env=postgres_env, capture_output=True, text=True, check=True
        )
        for line in result.stdout.splitlines():
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
                node_ids.add(obj["id"])
                summary["node_ids_total"] += 1
            except json.JSONDecodeError:
                summary["node_invalid_json_records"] += 1
    except subprocess.CalledProcessError as e:
        logging.error("Failed to query domain_nodes via psql; returncode=%s", e.returncode)
        sys.exit(1)

    return node_ids, summary

def load_postgres_edges(postgres_env: Dict[str, str]) -> Tuple[list[Dict[str, Any]], Dict[str, int]]:
    edges = []
    summary = {
        "edge_records_total": 0,
        "invalid_json_records": 0,
        "non_object_json_records": 0,
    }

    sql = """SELECT json_build_object(
  'id', id,
  'source_id', source_id,
  'target_id', target_id,
  'source_type', payload->>'source_type',
  'target_type', payload->>'target_type'
) FROM domain_edges;"""

    try:
        result = subprocess.run(
            ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-c", sql],
            env=postgres_env, capture_output=True, text=True, check=True
        )
        row_number = 0
        for line in result.stdout.splitlines():
            row_number += 1
            line = line.strip()
            if not line:
                continue
            summary["edge_records_total"] += 1
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    summary["non_object_json_records"] += 1
                    continue
                obj["row_number"] = row_number
                edges.append(obj)
            except json.JSONDecodeError:
                summary["invalid_json_records"] += 1
    except subprocess.CalledProcessError as e:
        logging.error("Failed to query domain_edges via psql; returncode=%s", e.returncode)
        sys.exit(1)

    return edges, summary

def evaluate_audit_data(
    *,
    node_ids: Set[str],
    edges: list[Dict[str, Any]],
    source: Dict[str, Any],
    source_kind: str,
    show_ids: bool,
    node_parse_summary: Dict[str, int],
    edge_parse_summary: Dict[str, int],
    max_findings: int,
) -> Dict[str, Any]:

    summary = {
        "nodes_total": node_parse_summary["node_ids_total"],
        "edges_total": 0, # Note: this in old script was edges_total.
        "auditable_edges_total": 0,
        "edge_records_total": edge_parse_summary["edge_records_total"],
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
        "invalid_json_records": edge_parse_summary["invalid_json_records"],
        "non_object_json_records": edge_parse_summary["non_object_json_records"],
        "edges_with_any_missing_node_reference": 0,
        "edges_with_both_missing_node_references": 0,
        "node_records_total": node_parse_summary["node_records_total"],
        "node_invalid_json_records": node_parse_summary["node_invalid_json_records"],
        "node_non_object_json_records": node_parse_summary["node_non_object_json_records"],
        "nodes_missing_id": node_parse_summary["nodes_missing_id"],
        "nodes_non_string_id": node_parse_summary["nodes_non_string_id"],
    }

    findings = []

    for edge in edges:
        edge_id = edge.get("id")
        source_id = edge.get("source_id")
        target_id = edge.get("target_id")
        source_type = edge.get("source_type")
        target_type = edge.get("target_type")

        if not isinstance(edge_id, str) or not isinstance(source_id, str) or not isinstance(target_id, str):
            summary["malformed_edges"] += 1

            edge_ref = ""
            if "line_number" in edge:
                edge_ref = hash_ref(f"line:{edge['line_number']}", "edge")
            elif "row_number" in edge:
                edge_ref = hash_ref(f"row:{edge['row_number']}", "edge")
            else:
                edge_ref = hash_ref("unknown", "edge")

            findings.append({
                "edge_ref": edge_ref,
                "side": "unknown",
                "target_ref": None,
                "type_hint": None,
                "classification": "malformed_edge"
            })
            continue

        summary["auditable_edges_total"] += 1
        summary["edges_total"] += 1
        edge_ref = edge_id if show_ids else hash_edge(edge_id)
        missing_node_count = 0

        # Source
        src_class, src_finding = classify_edge_side(
            edge_ref=edge_ref, side="source", target_id=source_id,
            type_hint=source_type, node_ids=node_ids, show_ids=show_ids
        )
        if src_class == "typed_node_missing_reference" or src_class == "untyped_missing_reference":
            missing_node_count += 1
        summary[src_class + "s"] = summary.get(src_class + "s", 0) + 1
        if src_finding:
            findings.append(src_finding)

        # Target
        tgt_class, tgt_finding = classify_edge_side(
            edge_ref=edge_ref, side="target", target_id=target_id,
            type_hint=target_type, node_ids=node_ids, show_ids=show_ids
        )
        if tgt_class == "typed_node_missing_reference" or tgt_class == "untyped_missing_reference":
            missing_node_count += 1
        summary[tgt_class + "s"] = summary.get(tgt_class + "s", 0) + 1
        if tgt_finding:
            findings.append(tgt_finding)

        if missing_node_count > 0:
            summary["edges_with_any_missing_node_reference"] += 1
        if missing_node_count == 2:
            summary["edges_with_both_missing_node_references"] += 1

    summary["edge_sides_total"] = summary["auditable_edges_total"] * 2
    summary["node_reference_sides"] = summary["typed_node_references"] + summary["untyped_existing_node_references"]
    summary["missing_node_reference_sides"] = summary["typed_node_missing_references"] + summary["untyped_missing_references"]

    strict_node_fk_ready = (
        source_kind == "runtime" and
        summary["node_invalid_json_records"] == 0 and
        summary["node_non_object_json_records"] == 0 and
        summary["nodes_missing_id"] == 0 and
        summary["nodes_non_string_id"] == 0 and
        summary["malformed_edges"] == 0 and
        summary["invalid_json_records"] == 0 and
        summary["non_object_json_records"] == 0 and
        summary["typed_node_missing_references"] == 0 and
        summary["typed_non_node_references"] == 0 and
        summary["typed_unknown_references"] == 0 and
        summary["untyped_existing_node_references"] == 0 and
        summary["untyped_missing_references"] == 0
    )

    loose_reference_semantics_observed = summary["typed_non_node_references"] > 0

    requires_cleanup = (
        summary["node_invalid_json_records"] > 0 or
        summary["node_non_object_json_records"] > 0 or
        summary["nodes_missing_id"] > 0 or
        summary["nodes_non_string_id"] > 0 or
        summary["malformed_edges"] > 0 or
        summary["invalid_json_records"] > 0 or
        summary["non_object_json_records"] > 0 or
        summary["typed_node_missing_references"] > 0 or
        summary["untyped_missing_references"] > 0
    )

    requires_policy_decision = (
        summary["typed_non_node_references"] > 0 or
        summary["typed_unknown_references"] > 0 or
        summary["untyped_existing_node_references"] > 0 or
        summary["untyped_missing_references"] > 0 or
        summary["typed_node_missing_references"] > 0
    )

    requires_runtime_data_run = source_kind != "runtime"

    findings.sort(key=lambda x: (
        x.get("classification", ""),
        x.get("side", ""),
        x.get("edge_ref", ""),
        str(x.get("target_ref", ""))
    ))

    findings_truncated = False
    findings_limit = max_findings
    if len(findings) > max_findings:
        findings = findings[:max_findings]
        findings_truncated = True

    return {
        "schema_version": "1.0.0",
        "source": source,
        "summary": summary,
        "policy_signals": {
            "strict_node_fk_ready": strict_node_fk_ready,
            "loose_reference_semantics_observed": loose_reference_semantics_observed,
            "requires_policy_decision": requires_policy_decision,
            "requires_cleanup": requires_cleanup,
            "requires_runtime_data_run": requires_runtime_data_run
        },
        "findings_truncated": findings_truncated,
        "findings_limit": findings_limit,
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
        if "DATABASE_URL" not in os.environ:
            logging.error("DATABASE_URL not set for PostgreSQL audit")
            sys.exit(1)
        try:
            subprocess.run(["psql", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            logging.error("psql is not available")
            sys.exit(1)

        postgres_env = postgres_env_from_database_url(os.environ["DATABASE_URL"])
        node_ids, node_summary = load_postgres_nodes(postgres_env)
        edges, edge_summary = load_postgres_edges(postgres_env)

        source = {
            "kind": "postgres",
            "source_kind": args.source_kind
        }
    elif args.nodes_jsonl and args.edges_jsonl:
        node_ids, node_summary, node_source = load_jsonl_nodes(args.nodes_jsonl)
        edges, edge_summary, edge_source = load_jsonl_edges(args.edges_jsonl)

        source = {
            "kind": "jsonl",
            "source_kind": args.source_kind,
            "nodes_source": node_source,
            "edges_source": edge_source
        }
    else:
        logging.error("Must provide either --postgres or both --nodes-jsonl and --edges-jsonl")
        sys.exit(1)

    result = evaluate_audit_data(
        node_ids=node_ids,
        edges=edges,
        source=source,
        source_kind=args.source_kind,
        show_ids=args.show_ids,
        node_parse_summary=node_summary,
        edge_parse_summary=edge_summary,
        max_findings=args.max_findings
    )

    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()

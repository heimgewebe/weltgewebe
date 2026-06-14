import argparse
import json
import logging
import subprocess
import sys
import uuid
import hashlib
from typing import Dict, List, Any, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def hash_ref(ref: str, prefix: str) -> str:
    """Return a redacted reference."""
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

def parse_args():
    parser = argparse.ArgumentParser(description="Audit domain edge references")
    parser.add_argument("--nodes-jsonl", type=str, help="Path to nodes JSONL file")
    parser.add_argument("--edges-jsonl", type=str, help="Path to edges JSONL file")
    parser.add_argument("--postgres", action="store_true", help="Run against PostgreSQL runtime")
    parser.add_argument("--source-kind", type=str, choices=["repo-fixture", "runtime", "unknown"], default="unknown", help="Source kind")
    parser.add_argument("--format", type=str, choices=["json", "text"], default="text", help="Output format")
    parser.add_argument("--show-ids", action="store_true", help="Show full IDs (not for committed reports)")
    return parser.parse_args()

def check_postgres_available() -> bool:
    try:
        subprocess.run(["psql", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def audit_jsonl(nodes_path: str, edges_path: str, source_kind: str, show_ids: bool) -> Dict[str, Any]:
    nodes_total = 0
    node_ids = set()

    try:
        with open(nodes_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if not isinstance(obj, dict):
                        continue
                    nodes_total += 1
                    if "id" in obj and isinstance(obj["id"], str):
                        node_ids.add(obj["id"])
                except json.JSONDecodeError:
                    pass
    except FileNotFoundError:
        logging.error(f"Nodes file not found: {nodes_path}")
        sys.exit(1)

    edges_total = 0
    invalid_json_records = 0
    non_object_json_records = 0
    malformed_edges = 0

    typed_node_references = 0
    typed_node_missing_references = 0
    typed_non_node_references = 0
    typed_unknown_references = 0
    untyped_existing_node_references = 0
    untyped_missing_references = 0

    edges_with_any_missing_node_reference = 0
    edges_with_both_missing_node_references = 0

    findings = []

    try:
        with open(edges_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                edges_total += 1
                try:
                    obj = json.loads(line)
                    if not isinstance(obj, dict):
                        non_object_json_records += 1
                        continue

                    edge_id = obj.get("id")
                    source_id = obj.get("source_id")
                    target_id = obj.get("target_id")
                    source_type = obj.get("source_type")
                    target_type = obj.get("target_type")

                    if not isinstance(source_id, str) or not isinstance(target_id, str):
                        malformed_edges += 1
                        continue

                    edge_ref = edge_id if show_ids else hash_edge(edge_id)

                    missing_node_count = 0

                    # Check source
                    source_ref = source_id if show_ids else hash_id(source_id)
                    if source_type == "node":
                        if source_id in node_ids:
                            typed_node_references += 1
                        else:
                            typed_node_missing_references += 1
                            missing_node_count += 1
                            findings.append({"edge_ref": edge_ref, "side": "source", "target_ref": source_ref, "type_hint": "node", "classification": "typed_node_missing_reference"})
                    elif source_type in ["account", "role"]:
                        typed_non_node_references += 1
                        findings.append({"edge_ref": edge_ref, "side": "source", "target_ref": source_ref, "type_hint": source_type, "classification": "typed_non_node_reference"})
                    elif source_type:
                        typed_unknown_references += 1
                        findings.append({"edge_ref": edge_ref, "side": "source", "target_ref": source_ref, "type_hint": source_type, "classification": "typed_unknown_reference"})
                    else:
                        if source_id in node_ids:
                            untyped_existing_node_references += 1
                            findings.append({"edge_ref": edge_ref, "side": "source", "target_ref": source_ref, "type_hint": None, "classification": "untyped_existing_node_reference"})
                        else:
                            untyped_missing_references += 1
                            missing_node_count += 1
                            findings.append({"edge_ref": edge_ref, "side": "source", "target_ref": source_ref, "type_hint": None, "classification": "untyped_missing_reference"})

                    # Check target
                    target_ref = target_id if show_ids else hash_id(target_id)
                    if target_type == "node":
                        if target_id in node_ids:
                            typed_node_references += 1
                        else:
                            typed_node_missing_references += 1
                            missing_node_count += 1
                            findings.append({"edge_ref": edge_ref, "side": "target", "target_ref": target_ref, "type_hint": "node", "classification": "typed_node_missing_reference"})
                    elif target_type in ["account", "role"]:
                        typed_non_node_references += 1
                        findings.append({"edge_ref": edge_ref, "side": "target", "target_ref": target_ref, "type_hint": target_type, "classification": "typed_non_node_reference"})
                    elif target_type:
                        typed_unknown_references += 1
                        findings.append({"edge_ref": edge_ref, "side": "target", "target_ref": target_ref, "type_hint": target_type, "classification": "typed_unknown_reference"})
                    else:
                        if target_id in node_ids:
                            untyped_existing_node_references += 1
                            findings.append({"edge_ref": edge_ref, "side": "target", "target_ref": target_ref, "type_hint": None, "classification": "untyped_existing_node_reference"})
                        else:
                            untyped_missing_references += 1
                            missing_node_count += 1
                            findings.append({"edge_ref": edge_ref, "side": "target", "target_ref": target_ref, "type_hint": None, "classification": "untyped_missing_reference"})

                    if missing_node_count > 0:
                        edges_with_any_missing_node_reference += 1
                    if missing_node_count == 2:
                        edges_with_both_missing_node_references += 1

                except json.JSONDecodeError:
                    invalid_json_records += 1
    except FileNotFoundError:
        logging.error(f"Edges file not found: {edges_path}")
        sys.exit(1)

    edge_sides_total = edges_total * 2
    node_reference_sides = typed_node_references + untyped_existing_node_references
    missing_node_reference_sides = typed_node_missing_references + untyped_missing_references

    strict_node_fk_ready = (
        source_kind == "runtime" and
        typed_node_missing_references == 0 and
        typed_non_node_references == 0 and
        typed_unknown_references == 0 and
        untyped_missing_references == 0 and
        untyped_existing_node_references == 0 and
        malformed_edges == 0 and
        invalid_json_records == 0 and
        non_object_json_records == 0
    )

    loose_reference_semantics_observed = typed_non_node_references > 0

    requires_cleanup = (
        malformed_edges > 0 or
        invalid_json_records > 0 or
        non_object_json_records > 0 or
        typed_node_missing_references > 0 or
        untyped_missing_references > 0
    )

    requires_policy_decision = (
        typed_non_node_references > 0 or
        typed_unknown_references > 0 or
        untyped_existing_node_references > 0 or
        untyped_missing_references > 0 or
        typed_node_missing_references > 0
    )

    requires_runtime_data_run = source_kind != "runtime"

    # Sort findings deterministically
    findings.sort(key=lambda x: (x["classification"], x["side"], x["edge_ref"], str(x["target_ref"])))

    return {
        "schema_version": "1.0.0",
        "source": {
            "kind": "jsonl",
            "source_kind": source_kind,
            "nodes_source": {
                "label": "nodes-jsonl",
                "size_bytes": 0,
                "sha256": ""
            },
            "edges_source": {
                "label": "edges-jsonl",
                "size_bytes": 0,
                "sha256": ""
            }
        },
        "summary": {
            "nodes_total": nodes_total,
            "edges_total": edges_total,
            "edge_sides_total": edge_sides_total,
            "typed_node_references": typed_node_references,
            "typed_node_missing_references": typed_node_missing_references,
            "typed_non_node_references": typed_non_node_references,
            "typed_unknown_references": typed_unknown_references,
            "untyped_existing_node_references": untyped_existing_node_references,
            "untyped_missing_references": untyped_missing_references,
            "node_reference_sides": node_reference_sides,
            "missing_node_reference_sides": missing_node_reference_sides,
            "malformed_edges": malformed_edges,
            "invalid_json_records": invalid_json_records,
            "non_object_json_records": non_object_json_records,
            "edges_with_any_missing_node_reference": edges_with_any_missing_node_reference,
            "edges_with_both_missing_node_references": edges_with_both_missing_node_references
        },
        "policy_signals": {
            "strict_node_fk_ready": strict_node_fk_ready,
            "loose_reference_semantics_observed": loose_reference_semantics_observed,
            "requires_policy_decision": requires_policy_decision,
            "requires_cleanup": requires_cleanup,
            "requires_runtime_data_run": requires_runtime_data_run
        },
        "findings": findings
    }

def audit_postgres(source_kind: str, show_ids: bool) -> Dict[str, Any]:
    import os
    if "DATABASE_URL" not in os.environ:
        logging.error("DATABASE_URL not set for PostgreSQL audit")
        sys.exit(1)

    if not check_postgres_available():
        logging.error("psql is not available")
        sys.exit(1)

    nodes_total = 0
    node_ids = set()

    # Query nodes
    try:
        nodes_result = subprocess.run(
            ["psql", "-d", os.environ["DATABASE_URL"], "-t", "-c", "SELECT id FROM domain_nodes;"],
            capture_output=True, text=True, check=True
        )
        for line in nodes_result.stdout.splitlines():
            nid = line.strip()
            if nid:
                node_ids.add(nid)
                nodes_total += 1
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to query domain_nodes: {e}")
        sys.exit(1)

    # Query edges
    edges_total = 0
    invalid_json_records = 0
    non_object_json_records = 0
    malformed_edges = 0

    typed_node_references = 0
    typed_node_missing_references = 0
    typed_non_node_references = 0
    typed_unknown_references = 0
    untyped_existing_node_references = 0
    untyped_missing_references = 0

    edges_with_any_missing_node_reference = 0
    edges_with_both_missing_node_references = 0

    findings = []

    sql_edges = """
SELECT
  id,
  source_id,
  target_id,
  payload->>'source_type' AS source_type,
  payload->>'target_type' AS target_type
FROM domain_edges;
"""
    try:
        edges_result = subprocess.run(
            ["psql", "-d", os.environ["DATABASE_URL"], "-t", "-P", "format=unaligned", "-P", "fieldsep=|", "-c", sql_edges],
            capture_output=True, text=True, check=True
        )
        for line in edges_result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) < 5:
                malformed_edges += 1
                continue

            edges_total += 1

            edge_id = parts[0]
            source_id = parts[1]
            target_id = parts[2]
            source_type = parts[3] if parts[3] else None
            target_type = parts[4] if parts[4] else None

            if not source_id or not target_id:
                malformed_edges += 1
                continue

            edge_ref = edge_id if show_ids else hash_edge(edge_id)
            missing_node_count = 0

            # Check source
            source_ref = source_id if show_ids else hash_id(source_id)
            if source_type == "node":
                if source_id in node_ids:
                    typed_node_references += 1
                else:
                    typed_node_missing_references += 1
                    missing_node_count += 1
                    findings.append({"edge_ref": edge_ref, "side": "source", "target_ref": source_ref, "type_hint": "node", "classification": "typed_node_missing_reference"})
            elif source_type in ["account", "role"]:
                typed_non_node_references += 1
                findings.append({"edge_ref": edge_ref, "side": "source", "target_ref": source_ref, "type_hint": source_type, "classification": "typed_non_node_reference"})
            elif source_type:
                typed_unknown_references += 1
                findings.append({"edge_ref": edge_ref, "side": "source", "target_ref": source_ref, "type_hint": source_type, "classification": "typed_unknown_reference"})
            else:
                if source_id in node_ids:
                    untyped_existing_node_references += 1
                    findings.append({"edge_ref": edge_ref, "side": "source", "target_ref": source_ref, "type_hint": None, "classification": "untyped_existing_node_reference"})
                else:
                    untyped_missing_references += 1
                    missing_node_count += 1
                    findings.append({"edge_ref": edge_ref, "side": "source", "target_ref": source_ref, "type_hint": None, "classification": "untyped_missing_reference"})

            # Check target
            target_ref = target_id if show_ids else hash_id(target_id)
            if target_type == "node":
                if target_id in node_ids:
                    typed_node_references += 1
                else:
                    typed_node_missing_references += 1
                    missing_node_count += 1
                    findings.append({"edge_ref": edge_ref, "side": "target", "target_ref": target_ref, "type_hint": "node", "classification": "typed_node_missing_reference"})
            elif target_type in ["account", "role"]:
                typed_non_node_references += 1
                findings.append({"edge_ref": edge_ref, "side": "target", "target_ref": target_ref, "type_hint": target_type, "classification": "typed_non_node_reference"})
            elif target_type:
                typed_unknown_references += 1
                findings.append({"edge_ref": edge_ref, "side": "target", "target_ref": target_ref, "type_hint": target_type, "classification": "typed_unknown_reference"})
            else:
                if target_id in node_ids:
                    untyped_existing_node_references += 1
                    findings.append({"edge_ref": edge_ref, "side": "target", "target_ref": target_ref, "type_hint": None, "classification": "untyped_existing_node_reference"})
                else:
                    untyped_missing_references += 1
                    missing_node_count += 1
                    findings.append({"edge_ref": edge_ref, "side": "target", "target_ref": target_ref, "type_hint": None, "classification": "untyped_missing_reference"})

            if missing_node_count > 0:
                edges_with_any_missing_node_reference += 1
            if missing_node_count == 2:
                edges_with_both_missing_node_references += 1

    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to query domain_edges: {e}")
        sys.exit(1)

    edge_sides_total = edges_total * 2
    node_reference_sides = typed_node_references + untyped_existing_node_references
    missing_node_reference_sides = typed_node_missing_references + untyped_missing_references

    strict_node_fk_ready = (
        source_kind == "runtime" and
        typed_node_missing_references == 0 and
        typed_non_node_references == 0 and
        typed_unknown_references == 0 and
        untyped_missing_references == 0 and
        untyped_existing_node_references == 0 and
        malformed_edges == 0 and
        invalid_json_records == 0 and
        non_object_json_records == 0
    )

    loose_reference_semantics_observed = typed_non_node_references > 0

    requires_cleanup = (
        malformed_edges > 0 or
        invalid_json_records > 0 or
        non_object_json_records > 0 or
        typed_node_missing_references > 0 or
        untyped_missing_references > 0
    )

    requires_policy_decision = (
        typed_non_node_references > 0 or
        typed_unknown_references > 0 or
        untyped_existing_node_references > 0 or
        untyped_missing_references > 0 or
        typed_node_missing_references > 0
    )

    requires_runtime_data_run = source_kind != "runtime"

    # Sort findings deterministically
    findings.sort(key=lambda x: (x["classification"], x["side"], x["edge_ref"], str(x["target_ref"])))

    return {
        "schema_version": "1.0.0",
        "source": {"kind": "postgres", "source_kind": source_kind},
        "summary": {
            "nodes_total": nodes_total,
            "edges_total": edges_total,
            "edge_sides_total": edge_sides_total,
            "typed_node_references": typed_node_references,
            "typed_node_missing_references": typed_node_missing_references,
            "typed_non_node_references": typed_non_node_references,
            "typed_unknown_references": typed_unknown_references,
            "untyped_existing_node_references": untyped_existing_node_references,
            "untyped_missing_references": untyped_missing_references,
            "node_reference_sides": node_reference_sides,
            "missing_node_reference_sides": missing_node_reference_sides,
            "malformed_edges": malformed_edges,
            "invalid_json_records": invalid_json_records,
            "non_object_json_records": non_object_json_records,
            "edges_with_any_missing_node_reference": edges_with_any_missing_node_reference,
            "edges_with_both_missing_node_references": edges_with_both_missing_node_references
        },
        "policy_signals": {
            "strict_node_fk_ready": strict_node_fk_ready,
            "loose_reference_semantics_observed": loose_reference_semantics_observed,
            "requires_policy_decision": requires_policy_decision,
            "requires_cleanup": requires_cleanup,
            "requires_runtime_data_run": requires_runtime_data_run
        },
        "findings": findings
    }

def main():
    args = parse_args()

    if args.postgres:
        result = audit_postgres(args.source_kind, args.show_ids)
    elif args.nodes_jsonl and args.edges_jsonl:
        result = audit_jsonl(args.nodes_jsonl, args.edges_jsonl, args.source_kind, args.show_ids)
    else:
        logging.error("Must provide either --postgres or both --nodes-jsonl and --edges-jsonl")
        sys.exit(1)

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(result)

if __name__ == "__main__":
    main()

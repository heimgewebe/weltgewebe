#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from scripts.docmeta.docmeta import REPO_ROOT
from scripts.docmeta.generated_check import write_or_check

OUT_FILE = os.path.join(REPO_ROOT, "docs", "_generated", "doc-coverage.md")


def collect_implementations() -> list[dict[str, object]]:
    registry_file = os.path.join(REPO_ROOT, "audit", "impl-registry.yaml")
    implementations: list[dict[str, object]] = []
    if not os.path.exists(registry_file):
        return implementations
    with open(registry_file, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    current_impl = None
    current_list_field = None
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if line.startswith("  - id:"):
            if current_impl:
                implementations.append(current_impl)
            current_impl = {"id": line_stripped.split("id:")[1].strip()}
            current_list_field = None
        elif current_impl is not None:
            if line_stripped.startswith("path:"):
                current_impl["path"] = line_stripped.split("path:")[1].strip(); current_list_field = None
            elif line_stripped.startswith("impl_type:"):
                current_impl["impl_type"] = line_stripped.split("impl_type:")[1].strip(); current_list_field = None
            elif line_stripped.startswith("status:"):
                current_impl["status"] = line_stripped.split("status:")[1].strip(); current_list_field = None
            elif line_stripped.startswith(("documented_by:", "verified_by:")):
                current_list_field = line_stripped.split(":", 1)[0]
                current_impl[current_list_field] = []
                val = line_stripped.split(":", 1)[1].strip()
                if val == "[]":
                    current_list_field = None
                elif val.startswith("[") and val.endswith("]"):
                    current_impl[current_list_field].extend(x.strip() for x in val[1:-1].split(",") if x.strip())
                    current_list_field = None
            elif line_stripped.startswith(("supersedes:", "deprecated_by:")):
                current_list_field = None
            elif line_stripped.startswith("- ") and current_list_field:
                current_impl[current_list_field].append(line_stripped[2:].strip())
    if current_impl:
        implementations.append(current_impl)
    return implementations


def compute_coverage() -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for impl in collect_implementations():
        kind = str(impl.get("impl_type", "unknown"))
        result.setdefault(kind, {"total": 0, "covered": 0})
        result[kind]["total"] += 1
        docs = impl.get("documented_by", [])
        valid = False
        if isinstance(docs, list):
            for doc in docs:
                rel = str(doc).strip().strip('"').strip("'")
                if rel and os.path.exists(os.path.join(REPO_ROOT, rel)):
                    valid = True
                    break
        if valid:
            result[kind]["covered"] += 1
    return result


def render() -> str:
    data = compute_coverage()
    lines = [
        "---",
        "id: docs.generated.doc-coverage",
        "title: Registered Implementation Documentation Coverage",
        "doc_type: generated",
        "status: active",
        "summary: Abdeckung der in audit/impl-registry.yaml registrierten kritischen Implementierungen.",
        "---",
        "",
        "## Registered Implementation Documentation Coverage",
        "",
        "Generated automatically. Do not edit.",
        "",
        "> **Scope:** This is not repository-wide documentation coverage. It measures only entries registered in `audit/impl-registry.yaml` and the existence of their `documented_by` targets.",
        "",
    ]
    if not data:
        lines.extend([
            "> (No implementations found in audit/impl-registry.yaml)",
            "",
            "| Component | Coverage |",
            "| --- | --- |",
            "| Apps | unknown |",
            "| Contracts | unknown |",
        ])
    else:
        lines.extend(["| Component Type | Coverage | Total | Documented |", "| --- | --- | --- | --- |"])
        for kind, stats in sorted(data.items()):
            total = stats["total"]
            covered = stats["covered"]
            pct = int((covered / total) * 100) if total > 0 else 0
            lines.append(f"| {kind.capitalize()} | {pct}% | {total} | {covered} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare output without rewriting it")
    args = parser.parse_args(argv)
    return write_or_check(OUT_FILE, render(), check=args.check, label=os.path.relpath(OUT_FILE, REPO_ROOT))


if __name__ == "__main__":
    sys.exit(main())

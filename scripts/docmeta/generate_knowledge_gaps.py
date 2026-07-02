#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from scripts.docmeta.docmeta import REPO_ROOT, parse_frontmatter
from scripts.docmeta.generated_check import write_or_check

OUT_FILE = os.path.join(REPO_ROOT, "docs", "_generated", "knowledge-gaps.md")


def is_meaningful_gap(val) -> bool:
    if val is None or isinstance(val, bool):
        return False
    val_str = str(val).strip().lower()
    if not val_str:
        return False
    return val_str not in ["false", "true", "none", "null", "unknown", "n/a", "[]", "{}"]


def collect_gaps() -> list[dict[str, object]]:
    gaps_found: list[dict[str, object]] = []
    docs_dir = os.path.join(REPO_ROOT, "docs")
    for root, dirs, files in os.walk(docs_dir):
        if "_generated" in dirs:
            dirs.remove("_generated")
        for file in files:
            if not file.endswith(".md"):
                continue
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, REPO_ROOT)
            frontmatter = parse_frontmatter(file_path)
            if not frontmatter:
                continue
            doc_gaps: list[str] = []
            val = frontmatter.get("audit_gaps")
            if val is not None:
                if isinstance(val, list):
                    doc_gaps.extend(f"[audit_gaps] {str(item).strip()}" for item in val if is_meaningful_gap(item))
                elif is_meaningful_gap(val):
                    doc_gaps.append(f"[audit_gaps] {str(val).strip()}")
            if doc_gaps:
                gaps_found.append({"id": frontmatter.get("id", rel_path), "path": rel_path, "gaps": doc_gaps})
    return gaps_found


def render() -> str:
    gaps_found = collect_gaps()
    lines = [
        "---",
        "id: docs.generated.knowledge-gaps",
        "title: Knowledge Gaps",
        "doc_type: generated",
        "status: active",
        "summary: Automatisch markierte Wissenslücken in der Repo-Landschaft.",
        "---",
        "",
        "## Weltgewebe Knowledge Gaps",
        "",
        "Generated automatically. Do not edit.",
        "",
        "> **Note:** This report specifically aggregates explicit gaps declared via `audit_gaps` fields in markdown frontmatter. It does not scan the general content of documents.",
        "",
    ]
    if not gaps_found:
        lines.append("- **No critical knowledge gaps reported.**")
    else:
        for item in sorted(gaps_found, key=lambda x: str(x["id"])):
            lines.append(f"### {item['id']}")
            lines.append(f"Source: `{item['path']}`")
            lines.append("")
            for gap in item["gaps"]:
                lines.append(f"- {gap}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare output without rewriting it")
    args = parser.parse_args(argv)
    return write_or_check(OUT_FILE, render(), check=args.check, label=os.path.relpath(OUT_FILE, REPO_ROOT))


if __name__ == "__main__":
    sys.exit(main())

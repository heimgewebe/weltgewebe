#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys

from scripts.docmeta.docmeta import (
    REPO_ROOT,
    extract_depends_on,
    normalize_list_field,
    parse_frontmatter,
    parse_repo_index,
    parse_review_policy,
)
from scripts.docmeta.generated_check import write_or_check

OUT_FILE = os.path.join(REPO_ROOT, "docs", "_generated", "system-map.md")


def render() -> str:
    policy = parse_review_policy()
    strict_mode = policy.get("strict_manifest", False)
    repo_index = parse_repo_index(strict_manifest=strict_mode)

    output = [
        "---",
        "id: docs.generated.system-map",
        "title: System Map",
        "doc_type: generated",
        "status: active",
        "summary: Automatisch generierte System Map.",
        "---",
        "## Weltgewebe System Map\n\nGenerated automatically. Do not edit.\n\nSource: scripts/docmeta/generate_system_map.py\n",
    ]

    for zone_name, zone_data in sorted(repo_index.get("zones", {}).items()):
        output.append(f"## Zone: {zone_name}\n")
        docs = []
        for doc_file in zone_data.get("canonical_docs", []):
            rel_zone_path = zone_data.get("path", "")
            rel_file_path = os.path.join(rel_zone_path, doc_file)
            file_path = os.path.join(REPO_ROOT, rel_file_path)
            frontmatter = parse_frontmatter(file_path)
            if frontmatter:
                doc_id = frontmatter.get("id", "")
                docs.append((doc_id, frontmatter, rel_file_path))
            else:
                docs.append(("_Missing_", None, rel_file_path))

        docs.sort(key=lambda x: x[0])
        rows = []
        for doc_id, frontmatter, rel_file_path in docs:
            if frontmatter:
                status = frontmatter.get("status", "")
                organ = frontmatter.get("organ", "")
                role = frontmatter.get("role", "")
                last_reviewed_str = frontmatter.get("last_reviewed", "")
                depends_on_str = ", ".join(extract_depends_on(frontmatter))
                vw_list = normalize_list_field(frontmatter.get("verifies_with", []))
                vw_display = []
                missing_scripts = []
                for vw in sorted(vw_list):
                    vw_path = os.path.join(REPO_ROOT, vw)
                    if not os.path.exists(vw_path):
                        missing_scripts.append(vw)
                        vw_display.append(f"{vw} 🔴(Missing)")
                    else:
                        vw_display.append(vw)
                verifies_with_str = ", ".join(vw_display)
                missing_scripts_str = ", ".join(missing_scripts)
                file_link = rel_file_path
            else:
                role = "_Missing_"
                status = "_Missing_"
                organ = "_Missing_"
                last_reviewed_str = "_Missing_"
                depends_on_str = "_Missing_"
                verifies_with_str = "_Missing_"
                missing_scripts_str = "_Missing_"
                file_link = rel_file_path
            rows.append([
                doc_id,
                file_link,
                role,
                organ,
                status,
                last_reviewed_str,
                depends_on_str,
                verifies_with_str,
                missing_scripts_str,
            ])

        headers = [
            "id",
            "path",
            "role",
            "organ",
            "status",
            "last_reviewed",
            "depends_on",
            "verifies_with",
            "missing_scripts",
        ]
        output.append("|" + "|".join(headers) + "|")
        output.append("|" + "|".join(["---" for _ in headers]) + "|")
        for row in rows:
            output.append("|" + "|".join(row) + "|")
        output.append("")

    output.append("## Automated Checks\n")
    checks = repo_index.get("checks", [])
    if checks:
        for check in sorted(checks):
            output.append(f"- {check}")
        output.append("")
    return "\n".join(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare output without rewriting it")
    args = parser.parse_args([] if argv is None else argv)
    try:
        target = os.path.join(REPO_ROOT, "docs", "_generated", "system-map.md")
        return write_or_check(target, render(), check=args.check, label=os.path.relpath(target, REPO_ROOT))
    except ValueError as exc:
        print(f"Error parsing manifest/policy: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

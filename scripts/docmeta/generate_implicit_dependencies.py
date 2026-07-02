#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from scripts.docmeta.docmeta import REPO_ROOT
from scripts.docmeta.generated_check import write_or_check

OUT_FILE = os.path.join(REPO_ROOT, "docs", "_generated", "implicit-dependencies.md")


def collect_deps() -> list[dict[str, str]]:
    makefile_path = os.path.join(REPO_ROOT, "Makefile")
    deps: list[dict[str, str]] = []
    if not os.path.exists(makefile_path):
        return deps

    with open(makefile_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current_target = None
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith("#"):
            continue
        match = re.match(r"^([a-zA-Z0-9_.-]+):", line)
        if match:
            current_target = match.group(1).strip()
        elif current_target and line.startswith("\t"):
            if line_stripped.startswith("python3 -m "):
                module = line_stripped.split("python3 -m ")[1].split()[0]
                deps.append({
                    "source": "Makefile",
                    "target": current_target,
                    "dependency": module,
                    "evidence": line_stripped,
                    "documented": "*unclear*",
                })
            elif line_stripped.startswith("bash "):
                script = line_stripped.split("bash ")[1].split()[0]
                deps.append({
                    "source": "Makefile",
                    "target": current_target,
                    "dependency": script,
                    "evidence": line_stripped,
                    "documented": "*unclear*",
                })
    return deps


def render() -> str:
    deps = collect_deps()
    lines = [
        "---",
        "id: docs.generated.implicit-dependencies",
        "title: Implicit Dependencies",
        "doc_type: generated",
        "status: active",
        "summary: Heuristische Karte impliziter Abhängigkeiten.",
        "---",
        "",
        "## Weltgewebe Implicit Dependencies",
        "",
        "Generated automatically. Do not edit.",
        "",
        "> **Note:** This report uses Makefile-based heuristic inference to identify script execution dependencies. Documentation status validation is not yet fully automated here.",
        "",
        "| Source | Inferred Dependency | Evidence | Documented |",
        "| --- | --- | --- | --- |",
    ]
    if deps:
        for dep in deps:
            evidence_text = dep["evidence"].replace("|", "\\|")
            evidence = f"`{evidence_text}`"
            lines.append(f"| {dep['source']} ({dep['target']}) | {dep['dependency']} | {evidence} | {dep['documented']} |")
    else:
        lines.append("| Makefile | docs-guard | `make docs-guard` | *unclear* |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare output without rewriting it")
    args = parser.parse_args(argv)
    return write_or_check(OUT_FILE, render(), check=args.check, label=os.path.relpath(OUT_FILE, REPO_ROOT))


if __name__ == "__main__":
    sys.exit(main())

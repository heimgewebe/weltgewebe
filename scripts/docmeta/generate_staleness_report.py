#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from scripts.docmeta.docmeta import REPO_ROOT, parse_frontmatter
from scripts.docmeta.generated_check import write_or_check

OUT_FILE = os.path.join(REPO_ROOT, "docs", "_generated", "staleness-report.md")
SCAN_DIRS = ("docs", "architecture", "runtime", "runbooks")


def collect_stale(repo_root: str = REPO_ROOT) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for directory in SCAN_DIRS:
        base = Path(repo_root) / directory
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.md")):
            if "_generated" in path.parts:
                continue
            fm = parse_frontmatter(str(path)) or {}
            status = str(fm.get("status", ""))
            lifecycle = str(fm.get("lifecycle_state", ""))
            if status in {"deprecated", "superseded"} or lifecycle in {"superseded", "archived"}:
                rows.append((path.relative_to(repo_root).as_posix(), status or "—", lifecycle or "—"))
    return rows


def render() -> str:
    rows = collect_stale()
    lines = [
        "---",
        "id: docs.generated.staleness-report",
        "title: Staleness Report",
        "doc_type: generated",
        "status: active",
        "summary: Listet explizit abgelöste, veraltete oder archivierte Dokumente aus ihren Metadaten.",
        "---",
        "",
        "## Weltgewebe Staleness Report",
        "",
        "Generated automatically. Do not edit.",
        "",
        "> This report is metadata-based. It does not infer semantic staleness from prose.",
        "",
    ]
    if not rows:
        lines.append("_No explicitly stale documents found._")
    else:
        lines.extend([
            f"Explicitly stale documents: **{len(rows)}**",
            "",
            "| Document | status | lifecycle_state |",
            "| --- | --- | --- |",
        ])
        lines.extend(f"| `{path}` | {status} | {lifecycle} |" for path, status, lifecycle in rows)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare output without rewriting it")
    args = parser.parse_args(argv)
    return write_or_check(OUT_FILE, render(), check=args.check, label=os.path.relpath(OUT_FILE, REPO_ROOT))


if __name__ == "__main__":
    sys.exit(main())

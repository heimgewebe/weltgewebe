"""
Orphan Guard — identifies documents with no inbound or outbound relations.

Uses the centralized relations parser (no duplicate parsing logic).

Output: docs/_generated/orphans.md
"""

import os
import argparse
import sys
from collections import defaultdict

from scripts.docmeta.docmeta import REPO_ROOT
from scripts.docmeta.generated_check import write_or_check
from scripts.docmeta.relations_parser import collect_file_relations

OUT_FILE = os.path.join(REPO_ROOT, "docs", "_generated", "orphans.md")

HEADER = """\
---
id: docs.generated.orphans
title: Orphans
doc_type: generated
status: active
summary: Automatisch generierte Liste verwaister Dokumente.
---

## Weltgewebe Orphans

Generated automatically. Do not edit.

"""


def render_orphans() -> str:

    file_relations = collect_file_relations(["docs"], REPO_ROOT)

    # Build set of all docs and backlinks map
    all_docs = set()
    backlinks = defaultdict(list)
    for source_path, rels in file_relations.items():
        all_docs.add(source_path)
        for entry in rels:
            if isinstance(entry, dict):
                target = entry.get("target", "")
                if target:
                    backlinks[target].append(source_path)

    orphans = []
    for file_path in all_docs:
        if file_path.endswith("index.md") or file_path.endswith("README.md"):
            continue

        is_targeted = file_path in backlinks
        has_outgoing = any(
            isinstance(e, dict) and e.get("target")
            for e in file_relations.get(file_path, [])
        )

        if not is_targeted and not has_outgoing:
            orphans.append(file_path)

    if not orphans:
        body = "_No orphans found._\n"
    else:
        body = "".join(f"- {o}\n" for o in sorted(orphans))
    return HEADER + body


def generate_orphans() -> None:
    rc = write_or_check(OUT_FILE, render_orphans(), label=os.path.relpath(OUT_FILE, REPO_ROOT))
    if rc:
        raise SystemExit(rc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare output without rewriting it")
    args = parser.parse_args(argv)
    return write_or_check(
        OUT_FILE,
        render_orphans(),
        check=args.check,
        label=os.path.relpath(OUT_FILE, REPO_ROOT),
    )


if __name__ == "__main__":
    sys.exit(main())

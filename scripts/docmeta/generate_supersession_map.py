"""
Supersession Map Generator — maps which documents supersede others.

Uses the centralized relations parser (no duplicate parsing logic).

Output: docs/_generated/supersession-map.md
"""

import os
import argparse
import sys

from scripts.docmeta.docmeta import REPO_ROOT
from scripts.docmeta.generated_check import write_or_check
from scripts.docmeta.relations_parser import collect_file_relations

OUT_FILE = os.path.join(REPO_ROOT, "docs", "_generated", "supersession-map.md")

HEADER = """\
---
id: docs.generated.supersession-map
title: Supersession Map
doc_type: generated
status: active
summary: Automatisch generierte Karte der abgelösten Dokumente.
---

## Weltgewebe Supersession Map

Generated automatically. Do not edit.

"""


def render_supersession_map() -> str:

    file_relations = collect_file_relations(["docs"], REPO_ROOT)

    supersession_relations = []
    for source_path, rels in file_relations.items():
        for entry in rels:
            if isinstance(entry, dict):
                rel_type = entry.get("type", "")
                target = entry.get("target", "")
                if rel_type == "supersedes" and target:
                    supersession_relations.append((target, source_path))

    if not supersession_relations:
        body = "_No supersession relations found._\n"
    else:
        body = "".join(
            f"- {old_doc} → superseded by → {new_doc}\n"
            for old_doc, new_doc in sorted(supersession_relations)
        )
    return HEADER + body


def generate_supersession_map() -> None:
    rc = write_or_check(OUT_FILE, render_supersession_map(), label=os.path.relpath(OUT_FILE, REPO_ROOT))
    if rc:
        raise SystemExit(rc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare output without rewriting it")
    args = parser.parse_args(argv)
    return write_or_check(
        OUT_FILE,
        render_supersession_map(),
        check=args.check,
        label=os.path.relpath(OUT_FILE, REPO_ROOT),
    )


if __name__ == "__main__":
    sys.exit(main())

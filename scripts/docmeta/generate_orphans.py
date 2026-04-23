"""
Orphan Guard — identifies documents with no inbound or outbound relations.

Uses the centralized relations parser (no duplicate parsing logic).

Output: docs/_generated/orphans.md
"""

import os
import sys
from collections import defaultdict

from scripts.docmeta.docmeta import REPO_ROOT
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


def generate_orphans():
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)

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

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(HEADER)
        if not orphans:
            f.write("_No orphans found._\n")
        else:
            for o in sorted(orphans):
                f.write(f"- {o}\n")

    print(f"Generated {os.path.relpath(OUT_FILE, REPO_ROOT)}")


if __name__ == "__main__":
    generate_orphans()

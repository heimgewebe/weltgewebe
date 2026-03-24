"""
Supersession Map Generator — maps which documents supersede others.

Uses the centralized relations parser (no duplicate parsing logic).

Output: docs/_generated/supersession-map.md
"""

import os
import sys

from scripts.docmeta.docmeta import REPO_ROOT
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


def generate_supersession_map():
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)

    file_relations = collect_file_relations(["docs"], REPO_ROOT)

    supersession_relations = []
    for source_path, rels in file_relations.items():
        for entry in rels:
            if isinstance(entry, dict):
                rel_type = entry.get("type", "")
                target = entry.get("target", "")
                if rel_type == "supersedes" and target:
                    supersession_relations.append((target, source_path))

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(HEADER)
        if not supersession_relations:
            f.write("_No supersession relations found._\n")
        else:
            for old_doc, new_doc in sorted(supersession_relations):
                f.write(f"- {old_doc} → superseded by → {new_doc}\n")

    print(f"Generated {os.path.relpath(OUT_FILE, REPO_ROOT)}")


if __name__ == "__main__":
    generate_supersession_map()

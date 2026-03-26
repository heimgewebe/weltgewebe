"""
Backlinks Generator — builds a reverse-reference graph from document relations.

Uses the centralized relations parser (no duplicate parsing logic).

Output: docs/_generated/backlinks.md
"""

import os
import sys
from collections import defaultdict

from scripts.docmeta.docmeta import REPO_ROOT
from scripts.docmeta.relations_parser import (
    extract_relations_from_content,
    collect_file_relations,
)

OUT_FILE = os.path.join(REPO_ROOT, "docs", "_generated", "backlinks.md")

HEADER = """\
---
id: docs.generated.backlinks
title: Backlinks Graph
doc_type: generated
status: active
summary: Automatisch generierter Graph der Rückverweise.
---

## Weltgewebe Backlinks

Generated automatically. Do not edit.

"""


def generate_backlinks():
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)

    file_relations = collect_file_relations(["docs"], REPO_ROOT)

    backlinks = defaultdict(list)
    for source_path, rels in file_relations.items():
        for entry in rels:
            if isinstance(entry, dict):
                rel_type = entry.get("type", "")
                target = entry.get("target", "")
                if rel_type and target:
                    backlinks[target].append((source_path, rel_type))

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(HEADER)
        if not backlinks:
            f.write("_No relations found._\n")
        else:
            blocks = []
            for target in sorted(backlinks.keys()):
                block_lines = [f"## {target}"]
                for source, rel in sorted(backlinks[target]):
                    block_lines.append(f"- [{rel}] {source}")
                blocks.append("\n".join(block_lines))
            f.write("\n\n".join(blocks) + "\n")

    print(f"Generated {os.path.relpath(OUT_FILE, REPO_ROOT)}")


if __name__ == "__main__":
    generate_backlinks()

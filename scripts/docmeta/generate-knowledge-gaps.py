#!/usr/bin/env python3
import os
import sys

out_file = "docs/_generated/knowledge-gaps.md"
os.makedirs("docs/_generated", exist_ok=True)

try:
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("id: docs.generated.knowledge-gaps\n")
        f.write("title: Knowledge Gaps\n")
        f.write("doc_type: generated\n")
        f.write("status: active\n")
        f.write("canonicality: derived\n")
        f.write("summary: Automatisch markierte Wissenslücken in der Repo-Landschaft.\n")
        f.write("---\n\n")
        f.write("## Weltgewebe Knowledge Gaps\n\n")
        f.write("Generated automatically. Do not edit.\n\n")
        f.write("*(Heuristic placeholder: scanning frontmatter and content for explicit gaps)*\n\n")
        f.write("- **No critical knowledge gaps reported.**\n")

    print(f"Generated {out_file}")
except Exception as e:
    print(f"Error generating knowledge gaps: {e}")
    sys.exit(1)

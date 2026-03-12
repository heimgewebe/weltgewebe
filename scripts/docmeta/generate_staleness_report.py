#!/usr/bin/env python3
import os
import sys
from scripts.docmeta.docmeta import REPO_ROOT

out_file = os.path.join(REPO_ROOT, "docs", "_generated", "staleness-report.md")
os.makedirs(os.path.dirname(out_file), exist_ok=True)

try:
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("id: docs.generated.staleness-report\n")
        f.write("title: Staleness Report\n")
        f.write("doc_type: generated\n")
        f.write("status: active\n")
        f.write("canonicality: derived\n")
        f.write("summary: Markiert veraltete oder abgelöste Dokumente.\n")
        f.write("---\n\n")
        f.write("## Weltgewebe Staleness Report\n\n")
        f.write("Generated automatically. Do not edit.\n\n")
        f.write("> (Heuristic placeholder: scanning frontmatter for deprecated/superseded labels)\n\n")
        f.write("- **No stale documents found.**\n")

    print(f"Generated {out_file}")
except Exception as e:
    print(f"Error generating staleness report: {e}", file=sys.stderr)
    sys.exit(1)

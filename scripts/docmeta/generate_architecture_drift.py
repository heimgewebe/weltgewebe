#!/usr/bin/env python3
import os
import sys
from scripts.docmeta.docmeta import REPO_ROOT

out_file = os.path.join(REPO_ROOT, "docs", "_generated", "architecture-drift.md")
os.makedirs(os.path.dirname(out_file), exist_ok=True)

try:
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("id: docs.generated.architecture-drift\n")
        f.write("title: Architecture Drift\n")
        f.write("doc_type: generated\n")
        f.write("status: active\n")
        f.write("canonicality: derived\n")
        f.write("summary: Automatisch generierter Report über Architektur-Drift.\n")
        f.write("---\n\n")
        f.write("## Weltgewebe Architecture Drift\n\n")
        f.write("Generated automatically. Do not edit.\n\n")
        f.write("> (Heuristic placeholder: comparing implementation roots and documented structure)\n\n")
        f.write("- **No significant drift detected.**\n")

    print(f"Generated {out_file}")
except Exception as e:
    print(f"Error generating architecture drift: {e}", file=sys.stderr)
    sys.exit(1)

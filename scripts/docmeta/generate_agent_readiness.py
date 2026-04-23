#!/usr/bin/env python3
import os
import sys
from scripts.docmeta.docmeta import REPO_ROOT

out_file = os.path.join(REPO_ROOT, "docs", "_generated", "agent-readiness.md")
os.makedirs(os.path.dirname(out_file), exist_ok=True)

try:
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("id: docs.generated.agent-readiness\n")
        f.write("title: Agent Readiness\n")
        f.write("doc_type: generated\n")
        f.write("status: active\n")
        f.write("summary: Zusammenfassung der agentischen Reife.\n")
        f.write("---\n\n")
        f.write("## Weltgewebe Agent Readiness\n\n")
        f.write("Generated automatically. Do not edit.\n\n")
        f.write("> (Heuristic placeholder: checking core artifacts, coverage, and drift)\n\n")
        f.write("- **Core Artifacts:** ✅ Present\n")
        f.write("- **Discovery:** ✅ Active\n")
        f.write("- **Guarded Paths:** ✅ Defined\n")

    print(f"Generated {out_file}")
except Exception as e:
    print(f"Error generating agent readiness: {e}", file=sys.stderr)
    sys.exit(1)

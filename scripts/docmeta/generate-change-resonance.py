#!/usr/bin/env python3
import os
import sys

out_file = "docs/_generated/change-resonance.md"
os.makedirs("docs/_generated", exist_ok=True)

try:
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("id: docs.generated.change-resonance\n")
        f.write("title: Change Resonance\n")
        f.write("doc_type: generated\n")
        f.write("status: active\n")
        f.write("canonicality: derived\n")
        f.write("summary: Wenn sich X ändert, prüfe oder aktualisiere Y.\n")
        f.write("---\n\n")
        f.write("## Weltgewebe Change Resonance\n\n")
        f.write("Generated automatically. Do not edit.\n\n")
        f.write("> (Heuristic placeholder)\n\n")
        f.write("- **Infra / Compose:** -> Deploy-Doku / Runbooks\n")
        f.write("- **Workflows:** -> AGENTS.md / Policy-Doku\n")

    print(f"Generated {out_file}")
except Exception as e:
    print(f"Error generating change resonance: {e}")
    sys.exit(1)

#!/usr/bin/env python3
import os
import sys

out_file = "docs/_generated/implicit-dependencies.md"
os.makedirs("docs/_generated", exist_ok=True)

try:
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("id: docs.generated.implicit-dependencies\n")
        f.write("title: Implicit Dependencies\n")
        f.write("doc_type: generated\n")
        f.write("status: active\n")
        f.write("canonicality: derived\n")
        f.write("summary: Heuristische Karte impliziter Abhängigkeiten.\n")
        f.write("---\n\n")
        f.write("## Weltgewebe Implicit Dependencies\n\n")
        f.write("Generated automatically. Do not edit.\n\n")
        f.write("*(Heuristic placeholder: scanning Makefile, Compose and scripts)*\n\n")
        f.write("| Source | Inferred Dependency | Evidence | Documented |\n")
        f.write("| --- | --- | --- | --- |\n")
        f.write("| Makefile | docs-guard | `make docs-guard` | _unclear_ |\n")

    print(f"Generated {out_file}")
except Exception as e:
    print(f"Error generating implicit dependencies: {e}")
    sys.exit(1)

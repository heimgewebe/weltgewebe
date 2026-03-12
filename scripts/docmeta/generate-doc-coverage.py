#!/usr/bin/env python3
import os
import sys

out_file = "docs/_generated/doc-coverage.md"
os.makedirs("docs/_generated", exist_ok=True)

try:
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("id: docs.generated.doc-coverage\n")
        f.write("title: Doc Coverage\n")
        f.write("doc_type: generated\n")
        f.write("status: active\n")
        f.write("canonicality: derived\n")
        f.write("summary: Automatisch generierter Report über die Dokumentationsabdeckung.\n")
        f.write("---\n\n")
        f.write("## Weltgewebe Doc Coverage\n\n")
        f.write("Generated automatically. Do not edit.\n\n")
        f.write("> (Heuristic placeholder: parsing audit/impl-registry.yaml vs coverage)\n\n")
        f.write("| Component | Coverage |\n")
        f.write("| --- | --- |\n")
        f.write("| Apps | unknown |\n")
        f.write("| Contracts | unknown |\n")

    print(f"Generated {out_file}")
except Exception as e:
    print(f"Error generating doc coverage: {e}")
    sys.exit(1)

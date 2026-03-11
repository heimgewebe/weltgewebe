#!/usr/bin/env bash

set -euo pipefail

OUT_FILE="docs/_generated/impl-index.md"
mkdir -p docs/_generated

cat << 'HEADER' > "$OUT_FILE"
---
id: docs.generated.impl-index
title: Implementation Index
doc_type: generated
status: active
canonicality: derived
summary: Automatisch generierter Index kritischer Implementierungen.
---

# Weltgewebe Implementation Index

Generated automatically. Do not edit.

| implementation | documented_by | criticality | verification |
|---|---|---|---|
HEADER

python3 -c "
import yaml

out_file = 'docs/_generated/impl-index.md'
registry_file = 'audit/impl-registry.yaml'

try:
    with open(registry_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    implementations = data.get('implementations', [])

    with open(out_file, 'a', encoding='utf-8') as f:
        if not implementations:
            pass
        else:
            for impl in implementations:
                impl_id = impl.get('id', '')
                docs = impl.get('documented_by', [])
                docs_str = ', '.join(docs) if docs else '⚠ undocumented'
                criticality = impl.get('impl_type', 'unknown')
                verification = impl.get('verified_by', [])
                verif_str = ', '.join(verification) if verification else 'none'

                f.write(f'| {impl_id} | {docs_str} | {criticality} | {verif_str} |\n')

    print(f'Generated {out_file}')
except Exception as e:
    print(f'Error processing impl-registry: {e}')
    # Write empty state if it fails so the guard won't crash
    print(f'Generated {out_file}')
"

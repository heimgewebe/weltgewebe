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
summary: Automatisch generierter Index kritischer Implementierungen.
---

## Weltgewebe Implementation Index

Generated automatically. Do not edit.

| implementation | documented_by | criticality | verification |
| --- | --- | --- | --- |
HEADER

python3 -c "
import sys

out_file = 'docs/_generated/impl-index.md'
registry_file = 'audit/impl-registry.yaml'

try:
    implementations = []
    with open(registry_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Basic string parsing for the known schema of impl-registry.yaml
    lines = content.split('\n')
    current_impl = None
    current_list_field = None

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        if line.startswith('  - id:'):
            if current_impl:
                implementations.append(current_impl)
            current_impl = {'id': line_stripped.split('id:')[1].strip()}
            current_list_field = None
        elif current_impl is not None:
            if line_stripped.startswith('path:'):
                current_impl['path'] = line_stripped.split('path:')[1].strip()
                current_list_field = None
            elif line_stripped.startswith('impl_type:'):
                current_impl['impl_type'] = line_stripped.split('impl_type:')[1].strip()
                current_list_field = None
            elif line_stripped.startswith('status:'):
                current_impl['status'] = line_stripped.split('status:')[1].strip()
                current_list_field = None
            elif line_stripped.startswith('documented_by:'):
                current_list_field = 'documented_by'
                current_impl[current_list_field] = []
                val = line_stripped.split('documented_by:')[1].strip()
                if val == '[]':
                    current_list_field = None
            elif line_stripped.startswith('verified_by:'):
                current_list_field = 'verified_by'
                current_impl[current_list_field] = []
                val = line_stripped.split('verified_by:')[1].strip()
                if val == '[]':
                    current_list_field = None
            elif line_stripped.startswith('supersedes:'):
                current_list_field = None
            elif line_stripped.startswith('deprecated_by:'):
                current_list_field = None
            elif line_stripped.startswith('- ') and current_list_field:
                val = line_stripped[2:].strip()
                current_impl[current_list_field].append(val)

    if current_impl:
        implementations.append(current_impl)

    with open(out_file, 'a', encoding='utf-8') as f:
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
    print(f'Generated {out_file}')
"

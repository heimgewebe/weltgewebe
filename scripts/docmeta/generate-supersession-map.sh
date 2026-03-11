#!/usr/bin/env bash

set -euo pipefail

OUT_FILE="docs/_generated/supersession-map.md"
mkdir -p docs/_generated

cat << 'HEADER' > "$OUT_FILE"
---
id: docs.generated.supersession-map
title: Supersession Map
doc_type: generated
status: active
canonicality: derived
summary: Automatisch generierte Karte der abgelösten Dokumente.
---

# Weltgewebe Supersession Map

Generated automatically. Do not edit.

HEADER

python3 -c "
import os
import yaml

out_file = 'docs/_generated/supersession-map.md'
relations = []

for root, dirs, files in os.walk('docs'):
    if '_generated' in root:
        continue
    for file in files:
        if file.endswith('.md'):
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.startswith('---'):
                        parts = content.split('---', 2)
                        if len(parts) >= 3:
                            fm = yaml.safe_load(parts[1])
                            if isinstance(fm, dict):
                                if 'supersedes' in fm and fm['supersedes']:
                                    targets = fm['supersedes']
                                    if isinstance(targets, list):
                                        for t in targets:
                                            relations.append((t, file_path))
                                    elif isinstance(targets, str):
                                        relations.append((targets, file_path))
                                if 'deprecated_by' in fm and fm['deprecated_by']:
                                    targets = fm['deprecated_by']
                                    if isinstance(targets, list):
                                        for t in targets:
                                            relations.append((file_path, t))
                                    elif isinstance(targets, str):
                                        relations.append((file_path, targets))
            except Exception:
                pass

with open(out_file, 'a', encoding='utf-8') as f:
    if not relations:
        f.write('_No supersession relations found._\n')
    else:
        for old_doc, new_doc in sorted(relations):
            f.write(f'- {old_doc} → superseded by → {new_doc}\n')

print(f'Generated {out_file}')
"

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
summary: Automatisch generierte Karte der abgelösten Dokumente.
---

## Weltgewebe Supersession Map

Generated automatically. Do not edit.

HEADER

python3 -c "
import os

out_file = 'docs/_generated/supersession-map.md'
relations = []

def extract_relations(content):
    relations = {}
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            fm_str = parts[1]
            lines = fm_str.strip().split('\n')
            current_key = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if ':' in line and not line.startswith('- '):
                    key, val = line.split(':', 1)
                    key = key.strip()
                    val = val.strip()
                    current_key = key
                    if val and val != '[]':
                        if val.startswith('[') and val.endswith(']'):
                            items = [i.strip() for i in val[1:-1].split(',') if i.strip()]
                            relations[key] = items
                        else:
                            relations[key] = [val]
                    else:
                        relations[key] = []
                elif line.startswith('- ') and current_key:
                    val = line[2:].strip()
                    if current_key not in relations:
                        relations[current_key] = []
                    relations[current_key].append(val)
    return relations

for root, dirs, files in os.walk('docs'):
    if '_generated' in root:
        continue
    for file in files:
        if file.endswith('.md'):
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    fm = extract_relations(content)
                    if 'supersedes' in fm and fm['supersedes']:
                        targets = fm['supersedes']
                        for t in targets:
                            relations.append((t, file_path))
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

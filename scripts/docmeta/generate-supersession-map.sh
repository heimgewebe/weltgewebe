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
supersession_relations = []

def extract_relations(content):
    \"\"\"Parse structured relations[] from YAML frontmatter.\"\"\"
    relations = []
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            fm_str = parts[1]
            lines = fm_str.strip().split('\n')
            in_relations = False
            current_type = None
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                if not line[0:1] in (' ', '\t') and ':' in stripped:
                    key = stripped.split(':')[0].strip()
                    in_relations = (key == 'relations')
                    current_type = None
                    continue
                if in_relations:
                    if stripped.startswith('- type:'):
                        current_type = stripped.split(':', 1)[1].strip()
                    elif stripped.startswith('target:') and current_type:
                        target = stripped.split(':', 1)[1].strip()
                        relations.append((current_type, target))
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
                    rels = extract_relations(content)
                    for rel_type, target in rels:
                        if rel_type == 'supersedes':
                            supersession_relations.append((target, file_path))
            except Exception:
                pass

with open(out_file, 'a', encoding='utf-8') as f:
    if not supersession_relations:
        f.write('_No supersession relations found._\n')
    else:
        for old_doc, new_doc in sorted(supersession_relations):
            f.write(f'- {old_doc} → superseded by → {new_doc}\n')

print(f'Generated {out_file}')
"

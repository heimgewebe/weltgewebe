#!/usr/bin/env bash

set -euo pipefail

OUT_FILE="docs/_generated/orphans.md"
mkdir -p docs/_generated

cat << 'HEADER' > "$OUT_FILE"
---
id: docs.generated.orphans
title: Orphans
doc_type: generated
status: active
summary: Automatisch generierte Liste verwaister Dokumente.
---

## Weltgewebe Orphans

Generated automatically. Do not edit.

HEADER

python3 -c "
import os
from collections import defaultdict

out_file = 'docs/_generated/orphans.md'
backlinks = defaultdict(list)
all_docs = set()

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
            all_docs.add(os.path.join(root, file))

for file in all_docs:
    try:
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
            rels = extract_relations(content)
            for rel_type, target in rels:
                backlinks[target].append(file)
    except Exception:
        pass

orphans = []
for file in all_docs:
    if file.endswith('index.md') or file.endswith('README.md'):
        continue

    is_targeted = file in backlinks

    has_outgoing = False
    try:
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
            rels = extract_relations(content)
            has_outgoing = len(rels) > 0
    except Exception:
        pass

    if not is_targeted and not has_outgoing:
        orphans.append(file)

with open(out_file, 'a', encoding='utf-8') as f:
    if not orphans:
        f.write('_No orphans found._\n')
    else:
        for o in sorted(orphans):
            f.write(f'- {o}\n')

print(f'Generated {out_file}')
"

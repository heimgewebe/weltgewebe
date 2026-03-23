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
import re

out_file = 'docs/_generated/orphans.md'
backlinks = defaultdict(list)
all_docs = set()

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
            all_docs.add(os.path.join(root, file))

for file in all_docs:
    try:
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
            fm = extract_relations(content)
            for rel in ['relates_to', 'depends_on', 'supersedes']:
                if rel in fm and fm[rel]:
                    targets = fm[rel]
                    for t in targets:
                        backlinks[t].append(file)
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
            fm = extract_relations(content)
            for rel in ['relates_to', 'depends_on', 'supersedes']:
                if rel in fm and fm[rel]:
                    has_outgoing = True
                    break
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

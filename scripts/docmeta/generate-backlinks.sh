#!/usr/bin/env bash

set -euo pipefail

OUT_FILE="docs/_generated/backlinks.md"
mkdir -p docs/_generated

cat << 'HEADER' > "$OUT_FILE"
---
id: docs.generated.backlinks
title: Backlinks Graph
doc_type: generated
status: active
summary: Automatisch generierter Graph der Rückverweise.
---

## Weltgewebe Backlinks

Generated automatically. Do not edit.

HEADER

python3 -c "
import os
from collections import defaultdict
import re

out_file = 'docs/_generated/backlinks.md'
backlinks = defaultdict(list)

# Poor man's YAML frontmatter parser for basic relations
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
                # Match key: value or key:
                if ':' in line and not line.startswith('- '):
                    key, val = line.split(':', 1)
                    key = key.strip()
                    val = val.strip()
                    current_key = key
                    if val and val != '[]':
                        # Simplistic array parsing like [a, b]
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

doc_files = []
for root, dirs, files in os.walk('docs'):
    if '_generated' in root:
        continue
    for file in files:
        if file.endswith('.md'):
            doc_files.append(os.path.join(root, file))

for file in sorted(doc_files):
    try:
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
            fm = extract_relations(content)
            for rel in ['relates_to', 'supersedes', 'depends_on']:
                if rel in fm and fm[rel]:
                    targets = fm[rel]
                    for t in targets:
                        backlinks[t].append((file, rel))
    except Exception as e:
        pass

with open(out_file, 'a', encoding='utf-8') as f:
    if not backlinks:
        f.write('_No relations found._\n')
    else:
        for target in sorted(backlinks.keys()):
            f.write(f'## {target}\n\n')
            for source, rel in sorted(backlinks[target]):
                f.write(f'- [{rel}] {source}\n')
            f.write('\n')

print(f'Generated {out_file}')
"

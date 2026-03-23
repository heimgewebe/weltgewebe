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

out_file = 'docs/_generated/backlinks.md'
backlinks = defaultdict(list)

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
                # Detect top-level key
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
            rels = extract_relations(content)
            for rel_type, target in rels:
                backlinks[target].append((file, rel_type))
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

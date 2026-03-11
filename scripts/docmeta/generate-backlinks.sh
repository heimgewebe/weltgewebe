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
canonicality: derived
summary: Automatisch generierter Graph der Rückverweise.
---

# Weltgewebe Backlinks

Generated automatically. Do not edit.

HEADER

# A completely Python-based approach is safer and handles data gathering more cleanly than Bash associative arrays + pipes.
python3 -c "
import os
import glob
import yaml
from collections import defaultdict

out_file = 'docs/_generated/backlinks.md'
backlinks = defaultdict(list)

# Find all markdown files in docs/ except _generated/
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
            if content.startswith('---'):
                # Extract frontmatter
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    fm_str = parts[1]
                    fm = yaml.safe_load(fm_str)
                    if isinstance(fm, dict):
                        for rel in ['documents', 'implemented_by', 'related_docs', 'supersedes', 'depends_on']:
                            if rel in fm and fm[rel]:
                                targets = fm[rel]
                                if isinstance(targets, list):
                                    for t in targets:
                                        backlinks[t].append((file, rel))
                                elif isinstance(targets, str):
                                    backlinks[targets].append((file, rel))
    except Exception as e:
        # Ignore files that fail to parse
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

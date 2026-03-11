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
canonicality: derived
summary: Automatisch generierte Liste verwaister Dokumente.
---

# Weltgewebe Orphans

Generated automatically. Do not edit.

HEADER

python3 -c "
import os
import yaml
from collections import defaultdict

out_file = 'docs/_generated/orphans.md'
backlinks = defaultdict(list)
all_docs = set()

# Find all docs
for root, dirs, files in os.walk('docs'):
    if '_generated' in root:
        continue
    for file in files:
        if file.endswith('.md'):
            all_docs.add(os.path.join(root, file))

# Parse frontmatter to find related docs
for file in all_docs:
    try:
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    fm_str = parts[1]
                    fm = yaml.safe_load(fm_str)
                    if isinstance(fm, dict):
                        for rel in ['related_docs', 'documents', 'depends_on', 'supersedes']:
                            if rel in fm and fm[rel]:
                                targets = fm[rel]
                                if isinstance(targets, list):
                                    for t in targets:
                                        backlinks[t].append(file)
                                elif isinstance(targets, str):
                                    backlinks[targets].append(file)
    except Exception:
        pass

# Orphan detection: a doc is an orphan if it is not targeted by any backlink,
# and it is not an index file, and it does not define any outgoing relations.
orphans = []
for file in all_docs:
    if file.endswith('index.md') or file.endswith('README.md'):
        continue

    is_targeted = file in backlinks

    # Check if it has outgoing relations
    has_outgoing = False
    try:
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    fm_str = parts[1]
                    fm = yaml.safe_load(fm_str)
                    if isinstance(fm, dict):
                        for rel in ['related_docs', 'documents', 'depends_on', 'supersedes', 'implemented_by']:
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

# Currently, we do not exit 1 on orphans because it is just a warning/report
# but we could enforce it later.
"

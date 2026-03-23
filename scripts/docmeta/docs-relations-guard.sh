#!/usr/bin/env bash

set -euo pipefail

echo "Checking docs relations..."

FAIL=0

# Dynamic check for required frontmatter fields using a python parser for robustness
while IFS= read -r -d '' file; do
    # Use python to extract frontmatter
    python3 -c "
import sys
import os

file_path = sys.argv[1]

# Read lines instead of full read for large files
frontmatter = []
in_frontmatter = False

with open(file_path, 'r', encoding='utf-8') as f:
    first_line = f.readline().strip()
    if first_line != '---':
        print(f'ERROR: Missing frontmatter block in {file_path}')
        sys.exit(1)

    for line in f:
        line_stripped = line.strip()
        if line_stripped == '---':
            break
        frontmatter.append(line)

required_fields = ['id:', 'title:', 'doc_type:', 'status:', 'canonicality:', 'summary:']
fm_str = ''.join(frontmatter)

missing = []
for field in required_fields:
    found = False
    for line in frontmatter:
        if line.strip().startswith(field):
            found = True
            break
    if not found:
        missing.append(field.replace(':', ''))

if missing:
    print(f'ERROR: Frontmatter missing fields {missing} in {file_path}')
    sys.exit(1)

# Reject placeholder summaries that carry no real information
placeholder_patterns = [
    'Automatisch hinzugefügtes Frontmatter',
    'TODO',
    'FIXME',
    'PLACEHOLDER',
]
summary_value = ''
in_summary = False
for line in frontmatter:
    stripped = line.strip()
    if not in_summary:
        if stripped.startswith('summary:'):
            val = stripped[len('summary:'):].strip()
            if val == '>' or val == '|':
                in_summary = True
                continue
            summary_value = val.strip('\"').strip(\"'\")
            break
    else:
        # In YAML block scalars (> or |), continuation lines are indented.
        # An unindented line means the block ended.
        if line[0:1] in ('', ' ', '\t') and stripped:
            summary_value += (' ' if summary_value else '') + stripped
        else:
            break

for pattern in placeholder_patterns:
    if pattern.lower() in summary_value.lower():
        print(f'ERROR: Placeholder summary detected in {file_path}: \"{summary_value}\"')
        sys.exit(1)

sys.exit(0)
" "$file" || FAIL=1

done < <(find docs -type f -name "*.md" ! -path "docs/_generated/*" -print0)

if [ "$FAIL" -eq 1 ]; then
    exit 1
fi

echo "docs-relations-guard pass."

#!/usr/bin/env bash

set -euo pipefail

OUT_FILE="docs/_generated/doc-index.md"
mkdir -p docs/_generated

cat << 'HEADER' > "$OUT_FILE"
---
id: docs.generated.doc-index
title: Doc Index
doc_type: generated
status: active
canonicality: derived
summary: Automatisch generierter Dokumenten-Index.
---

## Weltgewebe Doc Index

Generated automatically. Do not edit.

| id | title | type | status | canonicality | path |
| --- | --- | --- | --- | --- | --- |
HEADER

find docs -type f -name "*.md" ! -path "docs/_generated/*" | sort | while read -r file; do
    # Skip files without frontmatter
    if ! head -n 1 "$file" | grep -q "^---$"; then
        continue
    fi

    # Extract fields with basic sed
    id=$(sed -n -e '/^---$/,/^---$/ p' "$file" | grep "^id:" | sed 's/^id: *//' | tr -d '"'\''')
    title=$(sed -n -e '/^---$/,/^---$/ p' "$file" | grep "^title:" | sed 's/^title: *//' | tr -d '"'\''')
    doc_type=$(sed -n -e '/^---$/,/^---$/ p' "$file" | grep "^doc_type:" | sed 's/^doc_type: *//' | tr -d '"'\''')
    status=$(sed -n -e '/^---$/,/^---$/ p' "$file" | grep "^status:" | sed 's/^status: *//' | tr -d '"'\''')
    canonicality=$(sed -n -e '/^---$/,/^---$/ p' "$file" | grep "^canonicality:" | sed 's/^canonicality: *//' | tr -d '"'\''')

    if [ -n "$id" ]; then
        echo "| $id | $title | $doc_type | $status | $canonicality | $file |" >> "$OUT_FILE"
    fi
done

echo "Generated $OUT_FILE"

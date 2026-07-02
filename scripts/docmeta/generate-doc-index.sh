#!/usr/bin/env bash

set -euo pipefail

CHECK_MODE=0
if [[ "${1:-}" == "--check" ]]; then
  CHECK_MODE=1
fi

TARGET_FILE="docs/_generated/doc-index.md"
if [[ "${CHECK_MODE}" == "1" ]]; then
  OUT_FILE="$(mktemp)"
  trap 'rm -f "${OUT_FILE}"' EXIT
else
  OUT_FILE="${TARGET_FILE}"
  mkdir -p docs/_generated
fi

cat << 'HEADER' > "$OUT_FILE"
---
id: docs.generated.doc-index
title: Doc Index
doc_type: generated
status: active
summary: Automatisch generierter Dokumenten-Index.
---

## Weltgewebe Doc Index

Generated automatically. Do not edit.

| id | title | type | status | path |
| --- | --- | --- | --- | --- |
HEADER

# Create a temporary file to hold entries before sorting
TEMP_ENTRIES=$(mktemp)

find docs -type f -name "*.md" ! -path "docs/_generated/*" -print0 | while IFS= read -r -d '' file; do
  # Skip files without frontmatter
  if ! head -n 1 "$file" | grep -q "^---$"; then
    continue
  fi

  # Extract fields with basic sed
  id=$(sed -n -e '/^---$/,/^---$/ p' "$file" | grep "^id:" | sed 's/^id: *//' | tr -d '"'\''')
  title=$(sed -n -e '/^---$/,/^---$/ p' "$file" | grep "^title:" | sed 's/^title: *//' | tr -d '"'\''')
  doc_type=$(sed -n -e '/^---$/,/^---$/ p' "$file" | grep "^doc_type:" | sed 's/^doc_type: *//' | tr -d '"'\''')
  status=$(sed -n -e '/^---$/,/^---$/ p' "$file" | grep "^status:" | sed 's/^status: *//' | tr -d '"'\''')

  if [ -n "$id" ]; then
    echo "| $id | $title | $doc_type | $status | $file |" >> "$TEMP_ENTRIES"
  fi
done

# Sort entries deterministically and append to output
LC_ALL=C sort "$TEMP_ENTRIES" >> "$OUT_FILE"
rm -f "$TEMP_ENTRIES"

if [[ "${CHECK_MODE}" == "1" ]]; then
  if cmp -s "${TARGET_FILE}" "${OUT_FILE}"; then
    echo "${TARGET_FILE} is up to date."
  else
    echo "ERROR: ${TARGET_FILE} is stale; regenerate it." >&2
    diff -u "${TARGET_FILE}" "${OUT_FILE}" >&2 || true
    exit 1
  fi
else
  echo "Generated $OUT_FILE"
fi

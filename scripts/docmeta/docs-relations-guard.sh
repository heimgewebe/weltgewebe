#!/usr/bin/env bash

set -euo pipefail

echo "Checking docs relations..."

FAIL=0

# Dynamic check for required frontmatter fields
for file in $(find docs -type f -name "*.md" ! -path "docs/_generated/*" ! -path "docs/index.md" ! -path "docs/README.md"); do
    # Skip files that don't look like they have frontmatter at all to avoid spamming
    if ! head -n 1 "$file" | grep -q "^---$"; then
        continue
    fi

    if ! head -n 10 "$file" | grep -q "^id:"; then
        echo "ERROR: Frontmatter 'id' missing in $file"
        FAIL=1
    fi
    if ! head -n 10 "$file" | grep -q "^title:"; then
        echo "ERROR: Frontmatter 'title' missing in $file"
        FAIL=1
    fi
    if ! head -n 10 "$file" | grep -q "^doc_type:"; then
        echo "ERROR: Frontmatter 'doc_type' missing in $file"
        FAIL=1
    fi
    if ! head -n 10 "$file" | grep -q "^status:"; then
        echo "ERROR: Frontmatter 'status' missing in $file"
        FAIL=1
    fi
    if ! head -n 10 "$file" | grep -q "^canonicality:"; then
        echo "ERROR: Frontmatter 'canonicality' missing in $file"
        FAIL=1
    fi
    if ! head -n 10 "$file" | grep -q "^summary:"; then
        echo "ERROR: Frontmatter 'summary' missing in $file"
        FAIL=1
    fi
done

if [ "$FAIL" -eq 1 ]; then
    exit 1
fi

echo "docs-relations-guard pass."

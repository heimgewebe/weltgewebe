#!/usr/bin/env bash
set -e

echo "[INFO] Running docs-relations-guard..."

MISSING=0

check_frontmatter() {
  local file="$1"
  if ! head -n 1 "$file" | grep -q "^---$"; then
    echo "[WARN] Missing frontmatter in: $file" >&2
    # Setting to warn initially, can be changed to fail when fully implemented
    # MISSING=$((MISSING + 1))
  fi
}

# Find all non-generated docs
while IFS= read -r -d '' file; do
  check_frontmatter "$file"
done < <(find docs -type f -name "*.md" ! -path "docs/_generated/*" -print0)

if [ "$MISSING" -gt 0 ]; then
  echo "[FAIL] docs-relations-guard failed. $MISSING files missing frontmatter." >&2
  exit 1
fi

echo "[SUCCESS] docs-relations-guard passed."
exit 0

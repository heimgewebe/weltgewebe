#!/usr/bin/env bash
set -e

echo "[INFO] Running generated-files-guard..."

MISSING=0

check_header() {
  local file="$1"
  if ! head -n 1 "$file" | grep -q "<!-- GENERATED FILE: DO NOT EDIT -->"; then
    echo "[ERROR] Missing generated header in: $file" >&2
    MISSING=$((MISSING + 1))
  fi
}

# Find all generated docs
if [ -d "docs/_generated" ]; then
  while IFS= read -r -d '' file; do
    check_header "$file"
  done < <(find docs/_generated -type f -name "*.md" -print0)
fi

if [ "$MISSING" -gt 0 ]; then
  echo "[FAIL] generated-files-guard failed. $MISSING files missing or modified." >&2
  exit 1
fi

echo "[SUCCESS] generated-files-guard passed."
exit 0

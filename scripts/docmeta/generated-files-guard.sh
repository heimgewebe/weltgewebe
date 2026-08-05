#!/usr/bin/env bash

set -euo pipefail

echo "Checking generated files guard..."

FAIL=0

if [ ! -d "docs/_generated" ]; then
  echo "ERROR: docs/_generated missing."
  FAIL=1
fi

# The expected generated-file surface is now declared in
# .wgx/generated-artifacts.yml and cross-checked against repo.meta.yaml by
# scripts.docmeta.validate_generated_artifacts. Keep this shell guard focused
# on lightweight file-shape checks; do not duplicate the file list here.

for file in docs/_generated/*.md; do
  if [ -f "$file" ]; then
    if ! grep -q "Generated automatically." "$file"; then
      echo "ERROR: Generated file $file missing 'Generated automatically.' string."
      FAIL=1
    fi
    if ! head -n 1 "$file" | grep -q "^---$"; then
      echo "ERROR: Generated file $file missing frontmatter block."
      FAIL=1
    fi
  fi
done

if [ ! -f ".wgx/generated-artifacts.yml" ]; then
  echo "ERROR: .wgx/generated-artifacts.yml missing."
  FAIL=1
else
  # Same repo-canonical tools/py environment as make validate / UV_RUN.
  if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv is required for generated artifact control (tools/py/uv.lock)."
    FAIL=1
  elif ! uv run --project tools/py --locked python -m scripts.docmeta.validate_generated_artifacts --check; then
    echo "ERROR: generated artifact control validation failed."
    FAIL=1
  fi
fi

if [ "$FAIL" -eq 1 ]; then
  exit 1
fi

echo "generated-files-guard pass."

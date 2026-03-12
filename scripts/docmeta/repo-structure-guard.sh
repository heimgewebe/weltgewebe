#!/usr/bin/env bash
set -e

echo "[INFO] Running repo-structure-guard..."

MISSING=0

check_file() {
  if [ ! -f "$1" ]; then
    echo "[ERROR] Missing required file: $1" >&2
    MISSING=$((MISSING + 1))
  else
    echo "[OK] Found $1"
  fi
}

check_dir() {
  if [ ! -d "$1" ]; then
    echo "[ERROR] Missing required directory: $1" >&2
    MISSING=$((MISSING + 1))
  else
    echo "[OK] Found $1"
  fi
}

check_file "repo.meta.yaml"
check_file "docs/index.md"
check_dir "docs/_generated"

if [ "$MISSING" -gt 0 ]; then
  echo "[FAIL] repo-structure-guard failed. $MISSING artifacts missing." >&2
  exit 1
fi

echo "[SUCCESS] repo-structure-guard passed."
exit 0

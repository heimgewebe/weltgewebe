#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." > /dev/null 2>&1 && pwd)}"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ -f "$REPO_ROOT/package.json" ]] || fail "root package.json missing"
[[ -f "$REPO_ROOT/pnpm-lock.yaml" ]] || fail "root pnpm-lock.yaml missing"
[[ -f "$REPO_ROOT/apps/web/package.json" ]] || fail "apps/web/package.json missing"
[[ -f "$REPO_ROOT/apps/web/pnpm-lock.yaml" ]] || fail "apps/web/pnpm-lock.yaml missing"

if ! grep -Fq '"packageManager": "pnpm@' "$REPO_ROOT/package.json"; then
  fail "root package.json must declare pnpm as packageManager"
fi
if ! grep -Fq '"packageManager": "pnpm@' "$REPO_ROOT/apps/web/package.json"; then
  fail "apps/web/package.json must declare pnpm as packageManager"
fi

if find "$REPO_ROOT" \
  \( -path "$REPO_ROOT/.git" -o -path "$REPO_ROOT/node_modules" -o -path "$REPO_ROOT/apps/web/node_modules" \) -prune \
  -o -name package-lock.json -print -quit | grep -q .; then
  fail "package-lock.json is not canonical; use pnpm-lock.yaml"
fi

printf 'PASS: pnpm lockfile contract is canonical\n'

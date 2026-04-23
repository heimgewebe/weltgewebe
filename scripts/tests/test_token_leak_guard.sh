#!/usr/bin/env bash
set -euo pipefail

# Test: scripts/guard/token-leak-guard.sh
# Verifies that the token leak guard correctly detects and rejects
# accidental secrets while allowing known-safe exclusions.
#
# Tests call the REAL guard script via REPO_ROOT override — no
# shadow reimplementation of guard logic.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
GUARD_SCRIPT="$REPO_ROOT/scripts/guard/token-leak-guard.sh"

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

PASS=0
FAIL=0

report() {
  if [ "$1" -eq 0 ]; then
    PASS=$((PASS + 1))
    echo "PASS: $2"
  else
    FAIL=$((FAIL + 1))
    echo "FAIL: $2"
  fi
}

# We need a git repository for git grep to work
setup_git_repo() {
  rm -rf "$TEMP_DIR/repo"
  mkdir -p "$TEMP_DIR/repo"
  cd "$TEMP_DIR/repo"
  git init -q
  git config user.email "test@test.com"
  git config user.name "test"
}

# Case 1: Clean repo — no leaks
setup_git_repo
echo "Hello world" > file.txt
git add . && git commit -q -m "clean"
if REPO_ROOT="$TEMP_DIR/repo" bash "$GUARD_SCRIPT" >/dev/null 2>&1; then
  report 0 "Clean repo passes"
else
  report 1 "Clean repo should pass"
fi

# Case 2: File with token= leak — must fail
setup_git_repo
echo "config token=abcdefghij1234567890" > config.txt
git add . && git commit -q -m "with leak"
if REPO_ROOT="$TEMP_DIR/repo" bash "$GUARD_SCRIPT" >/dev/null 2>&1; then
  report 1 "File with token= leak should fail"
else
  report 0 "File with token= leak correctly detected"
fi

# Case 3: File with password= leak — must fail
setup_git_repo
echo "database password=supersecret123password" > db.txt
git add . && git commit -q -m "with password"
if REPO_ROOT="$TEMP_DIR/repo" bash "$GUARD_SCRIPT" >/dev/null 2>&1; then
  report 1 "File with password= leak should fail"
else
  report 0 "File with password= leak correctly detected"
fi

# Case 4: File with Authorization Bearer leak — must fail
setup_git_repo
echo "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9" > api.txt
git add . && git commit -q -m "with bearer"
if REPO_ROOT="$TEMP_DIR/repo" bash "$GUARD_SCRIPT" >/dev/null 2>&1; then
  report 1 "File with Bearer token leak should fail"
else
  report 0 "File with Bearer token leak correctly detected"
fi

# Case 5: Short token (9 chars, under the 10-char threshold) should NOT trigger
setup_git_repo
echo "token=abc12345x" > short.txt
git add . && git commit -q -m "short token"
if REPO_ROOT="$TEMP_DIR/repo" bash "$GUARD_SCRIPT" >/dev/null 2>&1; then
  report 0 "Short token (9 chars, under threshold) correctly passes"
else
  report 1 "Short token (9 chars) should not trigger detection"
fi

echo ""
echo "test_token_leak_guard: $PASS passed, $FAIL failed"
if [ "$FAIL" -ne 0 ]; then
  exit 1
fi

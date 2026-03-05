#!/usr/bin/env bash
set -euo pipefail

# This is a STATIC preflight guard. It runs BEFORE docker compose up.
# It checks if the build artifacts contain an inline script, and if so,
# verifies that the target Caddyfile's CSP allows it.

ROOT="${ROOT:-/opt/weltgewebe}"
REQUIRE_WEB_BUILD="${REQUIRE_WEB_BUILD:-1}"

# Caddyfile detection (heuristic: prioritize user explicit env var, then root, then infra)
if [[ -n "${CADDYFILE_PATH:-}" ]] && [[ -f "$CADDYFILE_PATH" ]]; then
  CADDYFILE="$CADDYFILE_PATH"
elif [[ -f "$ROOT/Caddyfile" ]]; then
  CADDYFILE="$ROOT/Caddyfile"
elif [[ -f "$ROOT/infra/caddy/Caddyfile.heim" ]]; then
  CADDYFILE="$ROOT/infra/caddy/Caddyfile.heim"
elif [[ -f "$ROOT/infra/caddy/Caddyfile.prod" ]]; then
  CADDYFILE="$ROOT/infra/caddy/Caddyfile.prod"
elif [[ -f "$ROOT/infra/caddy/Caddyfile" ]]; then
  CADDYFILE="$ROOT/infra/caddy/Caddyfile"
else
  CADDYFILE=""
fi

if [[ "$REQUIRE_WEB_BUILD" != "1" ]]; then
  echo "csp_contract_static: Web build not required, skipping."
  exit 0
fi

if [[ -z "$CADDYFILE" || ! -f "$CADDYFILE" ]]; then
  echo "ERROR: csp_contract_static could not find the target Caddyfile." >&2
  echo "       This is a fail-closed check because the web build is required and Caddy is enabled." >&2
  exit 1
fi

INDEX_HTML="$ROOT/apps/web/build/index.html"

if [[ ! -f "$INDEX_HTML" ]]; then
  echo "csp_contract_static: No index.html found at $INDEX_HTML, skipping."
  exit 0
fi

# Detect inline script in HTML
# We must find a <script ...> tag that does NOT contain a src= attribute.
# Since HTML can be minified into a single line, we use grep -o to extract all script tags first.
HAS_INLINE_SCRIPT=0
SCRIPT_TAGS=$(grep -ioP '<script[^>]*>' "$INDEX_HTML" || true)

# If grep -P fails on some alpine environments, fallback to basic sed extraction
if [[ $? -ne 0 ]] || [[ -z "$SCRIPT_TAGS" ]]; then
  SCRIPT_TAGS=$(sed -n 's/.*\(<script[^>]*>\).*/\1/p' "$INDEX_HTML" | tr '<' '\n' | grep -i '^script' | sed 's/^/</' || true)
fi

while IFS= read -r tag; do
  if [[ -n "$tag" ]] && ! echo "$tag" | grep -qi "src="; then
    HAS_INLINE_SCRIPT=1
    break
  fi
done <<< "$SCRIPT_TAGS"


if [[ "$HAS_INLINE_SCRIPT" == "1" ]]; then

  # Extract CSP line from Caddyfile
  # Assuming standard format: Content-Security-Policy "..."
  CSP_LINES=$(grep -i "Content-Security-Policy" "$CADDYFILE" || true)

  if [[ -z "$CSP_LINES" ]]; then
     echo "csp_contract_static: No CSP found in $CADDYFILE, assuming safe (or no CSP)."
     exit 0
  fi

  # Handle multiple CSP lines (take the first one, warn if multiple)
  LINE_COUNT=$(echo "$CSP_LINES" | wc -l)
  if [[ "$LINE_COUNT" -gt 1 ]]; then
     echo "WARNING: csp_contract_static found multiple CSP lines in $CADDYFILE. Using the first one." >&2
  fi
  CSP_LINE=$(echo "$CSP_LINES" | head -n 1)

  # Check if script-src allows unsafe-inline or contains nonce/hash
  # Look specifically within the script-src directive
  if echo "$CSP_LINE" | grep -qi "script-src"; then
      # Extract just the script-src part (up to the next semicolon or end of string) using sed for portability
      SCRIPT_SRC=$(echo "$CSP_LINE" | sed -n 's/.*\([sS][cC][rR][iI][pP][tT]-[sS][rR][cC][^;]*\).*/\1/p')

      if echo "$SCRIPT_SRC" | grep -qF "'unsafe-inline'"; then
          echo "csp_contract_static: OK ('unsafe-inline' present in script-src)"
          exit 0
      fi

      if echo "$SCRIPT_SRC" | grep -qE "'nonce-|'sha256-"; then
          echo "csp_contract_static: OK (nonce/hash present in script-src)"
          exit 0
      fi

      echo "ERROR: Inline <script> detected in index.html, but CSP in $CADDYFILE lacks 'unsafe-inline' or nonce/hash in script-src." >&2
      echo "CSP Line: $CSP_LINE" >&2
      echo "Script-src part: $SCRIPT_SRC" >&2
      exit 1
  fi
fi

echo "csp_contract_static: OK (no inline script or valid CSP)"
exit 0

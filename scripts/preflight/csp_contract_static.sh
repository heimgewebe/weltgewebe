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
  echo "csp_contract_static: Caddyfile not found, skipping."
  exit 0
fi

if [[ "$REQUIRE_WEB_BUILD" != "1" ]]; then
  echo "csp_contract_static: Web build not required, skipping."
  exit 0
fi

INDEX_HTML="$ROOT/apps/web/build/index.html"

if [[ ! -f "$INDEX_HTML" ]]; then
  echo "csp_contract_static: No index.html found at $INDEX_HTML, skipping."
  exit 0
fi

# Detect inline script in HTML (simple heuristic: <script> without src)
if grep -qE '<script>|<script type="module">' "$INDEX_HTML"; then

  # Extract CSP line from Caddyfile
  # Assuming standard format: Content-Security-Policy "..."
  CSP_LINE=$(grep -i "Content-Security-Policy" "$CADDYFILE" || true)

  if [[ -z "$CSP_LINE" ]]; then
     echo "csp_contract_static: No CSP found in $CADDYFILE, assuming safe (or no CSP)."
     exit 0
  fi

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

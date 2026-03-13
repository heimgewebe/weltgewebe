#!/usr/bin/env bash
set -euo pipefail

# This is a STATIC preflight guard. It runs BEFORE docker compose up.
# It checks if the build artifacts contain an inline script, and if so,
# verifies that the target Caddyfile's CSP allows it.

ROOT="${ROOT:-/opt/weltgewebe}"
REQUIRE_FRONTEND="${REQUIRE_FRONTEND:-1}"
CADDY_TARGET_SITE="${CADDY_TARGET_SITE:-weltgewebe.home.arpa}"

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

if [[ "$REQUIRE_FRONTEND" != "1" ]]; then
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
  echo "ERROR: csp_contract_static could not find index.html at $INDEX_HTML." >&2
  echo "       This is a fail-closed check because REQUIRE_FRONTEND=1." >&2
  echo "       (Note: runtime_contract.sh also enforces this file's existence)." >&2
  exit 1
fi

# Detect inline script in HTML
# We must find a <script ...> tag that does NOT contain a src= attribute.
HAS_INLINE_SCRIPT=0
# Extract all script tags. grep -o is standard, but the regex needs to be simple.
# '<script[^>]*>' works in standard grep in many implementations, but to be 100% POSIX safe
# and handle minified files, we use sed to isolate the script tags by injecting newlines.
SCRIPT_TAGS=$(sed 's/<script/\n<script/g' "$INDEX_HTML" | grep -io '^<script[^>]*>' || true)

while IFS= read -r tag; do
  if [[ -z "$tag" ]]; then
    continue
  fi
  # If the script tag does not contain "src=", it's an inline script
  if ! echo "$tag" | grep -qi "src="; then
    HAS_INLINE_SCRIPT=1
    break
  fi
done <<< "$SCRIPT_TAGS"


if [[ "$HAS_INLINE_SCRIPT" == "1" ]]; then

  # Extract the configuration block for the target site.
  # This uses a simple awk script to count braces and extract only the relevant host block.
  TARGET_BLOCK=$(awk -v site="$CADDY_TARGET_SITE" '
    # Match the site name followed by a brace or space
    $0 ~ site"( *{| *$)" { in_block=1; braces=0 }
    in_block {
      print
      # Count opening and closing braces
      braces += gsub(/{/, "{") - gsub(/}/, "}")
      if (braces <= 0 && $0 ~ /}/) { in_block=0 }
    }
  ' "$CADDYFILE" || true)

  if [[ -z "$TARGET_BLOCK" ]]; then
     echo "ERROR: csp_contract_static could not find the host block for '$CADDY_TARGET_SITE' in $CADDYFILE." >&2
     exit 1
  fi

  # Extract CSP lines from the target block
  # Assuming standard format: Content-Security-Policy "..."
  CSP_LINES=$(echo "$TARGET_BLOCK" | grep -i "Content-Security-Policy" || true)

  if [[ -z "$CSP_LINES" ]]; then
     echo "csp_contract_static: No CSP found for $CADDY_TARGET_SITE in $CADDYFILE, assuming safe (or no CSP)."
     exit 0
  fi

  # Handle multiple CSP lines: If ANY line satisfies the requirement, we pass.
  # This prevents false positives in multi-site Caddyfiles without needing a full parser.
  while IFS= read -r CSP_LINE; do
      if [[ -z "$CSP_LINE" ]]; then
          continue
      fi

      # Look specifically within the script-src directive
      if echo "$CSP_LINE" | grep -qi "script-src"; then
          # Extract just the script-src part (up to the next semicolon or end of string) using sed for portability
          SCRIPT_SRC=$(echo "$CSP_LINE" | sed -n 's/.*\([sS][cC][rR][iI][pP][tT]-[sS][rR][cC][^;]*\).*/\1/p')

          if echo "$SCRIPT_SRC" | grep -qF "'unsafe-inline'"; then
              echo "csp_contract_static: OK ('unsafe-inline' present in script-src of $CADDYFILE)"
              exit 0
          fi

          if echo "$SCRIPT_SRC" | grep -qE "'nonce-|'sha256-"; then
              echo "csp_contract_static: OK (nonce/hash present in script-src of $CADDYFILE)"
              exit 0
          fi
      fi
  done <<< "$CSP_LINES"

  echo "ERROR: Inline <script> detected in INDEX_HTML ($INDEX_HTML), but no matching Content-Security-Policy in CADDYFILE_PATH ($CADDYFILE) allows 'unsafe-inline' or nonce/hash." >&2
  echo "Found CSP lines:" >&2
  echo "$CSP_LINES" >&2
  exit 1
fi

echo "csp_contract_static: OK (no inline script or valid CSP)"
exit 0

#!/usr/bin/env bash
set -euo pipefail

URL="${URL:-https://weltgewebe.home.arpa/}"

# Fetch CSP header
csp="$(curl -skI "$URL" | tr -d '\r' | awk 'BEGIN{IGNORECASE=1} /^content-security-policy:/{sub(/^content-security-policy:[[:space:]]*/,""); print; exit}')"

# If no CSP, we do nothing (contract not enforced).
if [[ -z "${csp:-}" ]]; then
  echo "csp_contract: no CSP header found (skip)"
  exit 0
fi

# Detect inline script in HTML
html="$(curl -sk "$URL")"
if echo "$html" | grep -q "<script>"; then
  # If script-src exists and does NOT include unsafe-inline AND does NOT include nonce/hash, fail.
  if echo "$csp" | grep -qi "script-src"; then
    if echo "$csp" | grep -qi "script-src[^;]*unsafe-inline"; then
      echo "csp_contract: OK (unsafe-inline present for inline script)"
      exit 0
    fi
    # Heuristic: allow nonce/hash based CSP too (future hardening).
    if echo "$csp" | grep -Eqi "script-src[^;]*'nonce-|script-src[^;]*'sha256-"; then
      echo "csp_contract: OK (nonce/hash present)"
      exit 0
    fi
    echo "ERROR: inline <script> present, but CSP script-src lacks unsafe-inline and lacks nonce/hash" >&2
    echo "CSP=$csp" >&2
    exit 1
  fi
fi

echo "csp_contract: OK"

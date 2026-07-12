#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
GUARD="$REPO_ROOT/scripts/guard/security-headers-guard.sh"

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

mkdir -p "$TEMP_DIR/policies" "$TEMP_DIR/infra/caddy"
cat >"$TEMP_DIR/policies/security.yml" <<'YAML'
strict_transport_security:
  max_age_seconds: 31536000
csp_exceptions:
  - "script-src 'unsafe-inline'"
YAML

write_caddy() {
  local file="$1"
  cat >"$file" <<'CADDY'
example.test {
  header {
    Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data: blob:; object-src 'none';"
    Strict-Transport-Security "max-age=31536000; includeSubDomains"
    X-Frame-Options "DENY"
    Referrer-Policy "no-referrer"
    X-Content-Type-Options "nosniff"
    X-Weltgewebe-Build "{$WELTGEWEBE_BUILD}"
  }
}
CADDY
}

write_caddy "$TEMP_DIR/infra/caddy/Caddyfile.vps"
write_caddy "$TEMP_DIR/infra/caddy/Caddyfile.heim"
write_caddy "$TEMP_DIR/infra/caddy/Caddyfile.prod"

REPO_ROOT="$TEMP_DIR" bash "$GUARD" >/dev/null

sed -i '/Strict-Transport-Security/d' "$TEMP_DIR/infra/caddy/Caddyfile.vps"
if REPO_ROOT="$TEMP_DIR" bash "$GUARD" >/dev/null 2>&1; then
  echo "security headers guard should fail without HSTS" >&2
  exit 1
fi

echo "PASS: security headers guard"

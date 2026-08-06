#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" > /dev/null 2>&1 && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
GUARD="$REPO_ROOT/scripts/guard/security-headers-guard.sh"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT
mkdir -p "$TEMP_DIR/policies" "$TEMP_DIR/infra/caddy" "$TEMP_DIR/apps/web"

cat > "$TEMP_DIR/policies/security.yml" << 'YAML'
content_security_policy:
  script-src: "'self' plus build-generated sha256 hashes"
  script_mode: hash
  style-src: "'self' 'unsafe-inline'"
csp_exceptions:
  - directive: "style-src 'unsafe-inline'"
strict_transport_security:
  max_age_seconds: 31536000
YAML

cat > "$TEMP_DIR/apps/web/svelte.config.js" << 'JS'
export default {
  kit: {
    csp: {
      mode: "hash",
      directives: {
        "script-src": ["self"],
      },
    },
  },
};
JS

write_static_caddy() {
  local file="$1"
  local connect="$2"
  local strict_matcher="apiResponse"
  local strict_paths="/api/*"
  if [[ "$(basename "$file")" == "Caddyfile.vps" ]]; then
    strict_matcher="nonDocumentResponse"
    strict_paths="/api/* /health/*"
  fi
  cat > "$file" << CADDY
example.test {
  @magicLinkConfirm {
    method GET
    path /api/auth/magic-link/consume
  }
  header @magicLinkConfirm >Content-Security-Policy "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none';"
  @${strict_matcher} {
    path ${strict_paths}
    not {
      method GET
      path /api/auth/magic-link/consume
    }
  }
  header @${strict_matcher} >Content-Security-Policy "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none';"
  header {
    Content-Security-Policy "style-src 'self' 'unsafe-inline'; connect-src $connect; img-src 'self' data: blob:; worker-src 'self' blob:; font-src 'self'; media-src 'self'; manifest-src 'self'; child-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none';"
    Strict-Transport-Security "max-age=31536000; includeSubDomains"
    X-Frame-Options "DENY"
    Referrer-Policy "no-referrer"
    X-Content-Type-Options "nosniff"
    X-Weltgewebe-Build "{\$WELTGEWEBE_BUILD}"
  }
}
CADDY
}

write_prod_caddy() {
  local file="$1"
  cat > "$file" << 'CADDY'
example.test {
  header {
    Strict-Transport-Security "max-age=31536000; includeSubDomains"
    X-Frame-Options "DENY"
    Referrer-Policy "no-referrer"
    X-Content-Type-Options "nosniff"
    X-Weltgewebe-Build "{$WELTGEWEBE_BUILD}"
  }
}
CADDY
}

write_static_caddy "$TEMP_DIR/infra/caddy/Caddyfile" "'self' ws: wss:"
write_static_caddy "$TEMP_DIR/infra/caddy/Caddyfile.vps" "'self'"
write_static_caddy "$TEMP_DIR/infra/caddy/Caddyfile.heim" "'self'"
write_prod_caddy "$TEMP_DIR/infra/caddy/Caddyfile.prod"

REPO_ROOT="$TEMP_DIR" bash "$GUARD" > /dev/null

sed -i '/Strict-Transport-Security/d' "$TEMP_DIR/infra/caddy/Caddyfile.vps"
if REPO_ROOT="$TEMP_DIR" bash "$GUARD" > /dev/null 2>&1; then
  echo "security headers guard should fail without HSTS" >&2
  exit 1
fi
write_static_caddy "$TEMP_DIR/infra/caddy/Caddyfile.vps" "'self'"

# Same repo-canonical tools/py environment as make validate / UV_RUN.
if ! command -v uv > /dev/null 2>&1; then
  echo "ERROR: uv is required for security headers guard tests (tools/py/uv.lock)." >&2
  exit 1
fi
uv run --project "$REPO_ROOT/tools/py" --locked python - "$TEMP_DIR/infra/caddy/Caddyfile.vps" << 'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace(
    "  @magicLinkConfirm {\n    method GET\n    path /api/auth/magic-link/consume\n  }",
    "  @magicLinkConfirm {\n    path /api/auth/magic-link/consume\n  }\n  @other {\n    method GET\n    path /other\n  }",
    1,
)
path.write_text(text, encoding="utf-8")
PY
if REPO_ROOT="$TEMP_DIR" bash "$GUARD" > /dev/null 2>&1; then
  echo "security headers guard should fail when GET exists outside the magic-link matcher" >&2
  exit 1
fi
write_static_caddy "$TEMP_DIR/infra/caddy/Caddyfile.vps" "'self'"

sed -i 's/header @magicLinkConfirm >Content-Security-Policy/header @magicLinkConfirm Content-Security-Policy/' "$TEMP_DIR/infra/caddy/Caddyfile.vps"
if REPO_ROOT="$TEMP_DIR" bash "$GUARD" > /dev/null 2>&1; then
  echo "security headers guard should fail when magic-link CSP is not deferred" >&2
  exit 1
fi
write_static_caddy "$TEMP_DIR/infra/caddy/Caddyfile.vps" "'self'"

sed -i "s/style-src 'self' 'unsafe-inline';/script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';/" "$TEMP_DIR/infra/caddy/Caddyfile.vps"
if REPO_ROOT="$TEMP_DIR" bash "$GUARD" > /dev/null 2>&1; then
  echo "security headers guard should fail with script-src unsafe-inline" >&2
  exit 1
fi

echo "PASS: security headers guard"

#!/usr/bin/env bash
set -euo pipefail

# Guard: DOMAIN-PG-002 single-instance boundary for the domain PostgreSQL path
#
# Background (see docs/reports/domain-postgres-instance-coherence-decision.md
# and docs/blueprints/domain-data-postgres-cutover.md § Instance Coherence
# Boundary):
#
# The API keeps domain state (nodes, edges, accounts) and parts of the auth
# state (tokens, step-up tokens, challenges, passkeys) in process-local
# in-memory caches. There is no tested cross-instance invalidation mechanism.
# Running more than one API instance would therefore create a silent cache
# split-brain: instance B does not observe instance A's writes through its
# local cache until it restarts.
#
# This guard is a fence, not a distributed system. It blocks the obvious
# static drift that would quietly enable API scale-out:
#   1. compose `replicas: N` (N > 1) on the `api` service
#   2. `docker compose --scale api=N` (N > 1) in docs/scripts/infra
#   3. multiple API upstreams on a single Caddy `reverse_proxy` directive line
#
# It is deliberately narrow and API-specific: a `replicas`/`--scale` for any
# other service (e.g. `caddy=0`, a future `db` replica) is NOT flagged, because
# DOMAIN-PG-002 only constrains the API domain read/write path.
#
# Non-goals: this guard does not prove a single container runs in production,
# does not implement cross-instance coherence, and does not detect every
# conceivable scale-out config — only the obvious, robustly-detectable ones.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd -- "${SCRIPT_DIR}/../.." >/dev/null 2>&1 && pwd)}"

FAILED=0

fail() {
  echo "DOMAIN-SINGLE-INSTANCE-GUARD: $*" >&2
  FAILED=1
}

# ---------------------------------------------------------------------------
# Check 1 — compose `replicas: N` (N > 1) on the `api` service.
#
# Parsed per file with a small, scope-limited awk state machine that tracks the
# current top-level service block, so a `replicas` under any non-api service is
# not flagged. Covers both top-level `replicas:` and `deploy:\n  replicas:`.
# ---------------------------------------------------------------------------
check_compose_replicas() {
  local compose_dir="${REPO_ROOT}/infra/compose"
  [ -d "$compose_dir" ] || return 0

  local f
  for f in "$compose_dir"/*.yml "$compose_dir"/*.yaml; do
    [ -e "$f" ] || continue
    local hits
    hits="$(awk '
      BEGIN { in_api = 0 }
      # A top-level key (0 indent) ends any service block.
      /^[^ ]/ { in_api = 0 }
      # A service declaration is a 2-space-indented bare key ("  <name>:").
      /^  [^ ].*:[[:space:]]*$/ {
        name = $0
        sub(/^  /, "", name)
        sub(/:.*$/, "", name)
        in_api = (name == "api")
        next
      }
      # Any other 2-space-indented key ends the current service block.
      /^  [^ ]/ { in_api = 0 }
      in_api && /replicas:/ {
        val = $0
        sub(/^.*replicas:[[:space:]]*"?/, "", val)
        sub(/[^0-9].*$/, "", val)
        if (val != "" && val + 0 >= 2) {
          printf "%s:%d: %s\n", FILENAME, NR, $0
        }
      }
    ' "$f")"
    if [ -n "$hits" ]; then
      echo "$hits" >&2
      fail "api service declares replicas > 1 (forbidden for the domain PostgreSQL transition)"
    fi
  done
}

# ---------------------------------------------------------------------------
# Check 2 — `docker compose --scale api=N` (N > 1) in docs/scripts/infra.
#
# Matches `--scale api=N` and `--scale api N` for N >= 2. Deliberately does not
# match `--scale api=1`, `--scale api=0`, or scaling of other services such as
# the existing `--scale caddy=0`.
# ---------------------------------------------------------------------------
check_scale_flag() {
  local scan_dirs=()
  local d
  for d in docs scripts infra; do
    [ -d "${REPO_ROOT}/${d}" ] && scan_dirs+=("${REPO_ROOT}/${d}")
  done
  [ "${#scan_dirs[@]}" -gt 0 ] || return 0

  local pattern='--scale[[:space:]]+api[=[:space:]]+([2-9]|[1-9][0-9]+)'
  local hits
  # Exclude this guard and its test: their source legitimately carries the
  # forbidden pattern as documentation and as test fixtures.
  if hits="$(grep -RInE \
    --exclude='domain-single-instance-guard.sh' \
    --exclude='test_domain_single_instance_guard.sh' \
    -- "$pattern" "${scan_dirs[@]}" 2>/dev/null)"; then
    echo "$hits" >&2
    fail "docker compose --scale api=N (N>1) is forbidden by the single-instance boundary"
  fi
}

# ---------------------------------------------------------------------------
# Check 3 — multiple API upstreams on a single Caddy `reverse_proxy` line.
#
# Counts host:port upstream tokens on each reverse_proxy directive line; flags
# only lines that carry an api upstream together with a second upstream (the
# obvious "load-balance across api replicas" drift). A single `reverse_proxy
# api:8080` and a `reverse_proxy /* web:5173` both stay valid.
# ---------------------------------------------------------------------------
check_caddy_upstreams() {
  local caddy_dir="${REPO_ROOT}/infra/caddy"
  [ -d "$caddy_dir" ] || return 0

  local f
  for f in "$caddy_dir"/*; do
    [ -f "$f" ] || continue
    local hits
    hits="$(awk '
      /reverse_proxy/ {
        rest = $0
        sub(/^.*reverse_proxy/, "", rest)
        n = split(rest, toks, /[[:space:]]+/)
        ups = 0
        api_up = 0
        for (i = 1; i <= n; i++) {
          if (toks[i] ~ /^[A-Za-z0-9_.-]+:[0-9]+$/) {
            ups++
            if (toks[i] ~ /api/) api_up = 1
          }
        }
        if (api_up && ups >= 2) {
          printf "%s:%d: %s\n", FILENAME, NR, $0
        }
      }
    ' "$f")"
    if [ -n "$hits" ]; then
      echo "$hits" >&2
      fail "multiple api upstreams on a reverse_proxy line are forbidden by the single-instance boundary"
    fi
  done
}

check_compose_replicas
check_scale_flag
check_caddy_upstreams

if [ "$FAILED" -ne 0 ]; then
  echo "" >&2
  echo "DOMAIN-SINGLE-INSTANCE-GUARD: single-instance boundary violated." >&2
  echo "  See docs/reports/domain-postgres-instance-coherence-decision.md (DOMAIN-PG-002)." >&2
  echo "  Horizontal API scale-out requires a new task plus a tested cross-instance" >&2
  echo "  cache invalidation/coherence mechanism — it is not enabled by config drift." >&2
  exit 1
fi

echo "DOMAIN-SINGLE-INSTANCE-GUARD: ok"

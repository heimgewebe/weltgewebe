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
# in-memory caches with no tested cross-instance invalidation mechanism. Running
# more than one API instance would create a silent cache split-brain: instance B
# does not observe instance A's writes through its local cache until it restarts.
#
# This is a scope-limited static guard, not a runtime proof and not a full
# YAML/Caddy parser. It is a fence against the obvious static drift that would
# quietly enable API scale-out:
#   1. compose `replicas` on the `api` service with a value that is not clearly
#      0 or 1 (numeric >= 2, or a non-literal/`$`-expanded value -> fail-closed)
#   2. `docker compose --scale api=<value>` where <value> is not clearly 0 or 1
#      (numeric >= 2, or a non-literal/`$`-expanded value -> fail-closed)
#   3. an API upstream together with any additional upstream on the same Caddy
#      `reverse_proxy`/`to` directive line
#
# It is deliberately API-specific: `--scale caddy=0`, a single API instance
# (`replicas: 1`, `--scale api=1`) and `replicas` on a non-API service are not
# flagged. A bare non-numeric token without `$` (e.g. a prose placeholder like
# `N`) is treated as documentation, not a live value, so the guard does not eat
# its own explanation.
#
# Known limitations (tracked as future work, not blockers for DOMAIN-PG-002):
#   - multi-line Caddy `to` blocks (one upstream per line across several lines)
#   - a real YAML/Caddy AST check (would need yq/caddy in CI as a hard dep)

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd -- "${SCRIPT_DIR}/../.." >/dev/null 2>&1 && pwd)}"

GUARD_SELF="domain-single-instance-guard.sh"
GUARD_TEST="test_domain_single_instance_guard.sh"
DECISION_REF="docs/reports/domain-postgres-instance-coherence-decision.md"

FAILED=0

# Print one finding block per offending location: reason, file:line:content,
# and a pointer to the decision record.
report_hits() {
  local hits="$1" reason="$2" line
  [ -n "$hits" ] || return 0
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    echo "DOMAIN-SINGLE-INSTANCE-GUARD: ${reason}" >&2
    echo "  ${line}" >&2
    echo "  api scale-out is forbidden by DOMAIN-PG-002 single-instance boundary; see ${DECISION_REF}" >&2
    FAILED=1
  done <<<"$hits"
}

# --- awk programs (quoted heredocs: single/double quotes used freely) ---------

# Check 1 — `replicas` on the `api` service in compose files.
# Scope-limited static guard, fail-closed for ambiguous API replicas. The
# `services:` child indentation is detected dynamically (not bound to exactly
# two spaces); both top-level `replicas:` and `deploy:`/`replicas:` are covered.
REPLICAS_AWK=$(cat <<'AWK'
BEGIN { in_services=0; services_indent=0; svc_indent=-1; in_api=0; rc=0 }
/^[[:space:]]*($|#)/ { next }
{ match($0, /^ */); ind = RLENGTH }
$0 ~ /^[[:space:]]*services:[[:space:]]*$/ { in_services=1; services_indent=ind; svc_indent=-1; in_api=0; next }
{
  if (in_services && ind <= services_indent) { in_services=0; in_api=0 }
  else if (in_services) {
    if (svc_indent == -1) svc_indent = ind
    if (ind == svc_indent) { name=$0; sub(/^[[:space:]]+/,"",name); sub(/[[:space:]]*:.*$/,"",name); in_api=(name=="api") }
  }
}
(in_services && in_api && ind > svc_indent && /replicas:[[:space:]]*/) {
  val=$0
  sub(/^.*replicas:[[:space:]]*/,"",val)
  sub(/[[:space:]]*#.*$/,"",val)
  gsub(/['"]/,"",val)
  gsub(/[[:space:]]/,"",val)
  blocked=0
  if (val ~ /^[0-9]+$/) { if (val+0 >= 2) blocked=1 }
  else if (val ~ /\$/) blocked=1
  else if (val == "") blocked=1
  if (blocked) { printf "%s:%d:%s\n", FILENAME, FNR, $0; rc=1 }
}
END { exit rc }
AWK
)

# Check 2 — `docker compose --scale api=<value>`.
# Quotes and '=' are normalised to spaces so api=2, "api=2", 'api=2', --scale=api=2
# and `--scale api 2` collapse to the same token stream. A value is blocked when
# it is numeric >= 2 or contains `$` (non-literal -> fail-closed).
SCALE_AWK=$(cat <<'AWK'
BEGIN { rc=0 }
{
  line=$0
  gsub(/['"]/," ",line); gsub(/=/," ",line); gsub(/[[:space:]]+/," ",line)
  n=split(line, t, " ")
  for (i=1; i+2<=n; i++) {
    if (t[i]=="--scale" && t[i+1]=="api") {
      val=t[i+2]; blocked=0
      if (val ~ /^[0-9]+$/) { if (val+0>=2) blocked=1 }
      else if (val ~ /\$/) blocked=1
      if (blocked) { printf "%s:%d:%s\n", FILENAME, FNR, $0; rc=1 }
    }
  }
}
END { exit rc }
AWK
)

# Check 3 — an API upstream plus any additional upstream on one Caddy
# `reverse_proxy`/`to` directive line.
# Strips an optional http(s):// scheme, ignores path matchers and `{`, counts
# host:port upstream tokens, and flags only lines that carry an API upstream
# together with a second upstream (single-line drift).
CADDY_AWK=$(cat <<'AWK'
BEGIN { rc=0 }
{
  is_rp=($0 ~ /reverse_proxy/); is_to=($0 ~ /^[[:space:]]*to[[:space:]]/)
  if (!is_rp && !is_to) next
  rest=$0
  if (is_rp) sub(/^.*reverse_proxy/,"",rest); else sub(/^[[:space:]]*to[[:space:]]+/," ",rest)
  n=split(rest, toks, /[[:space:]]+/); ups=0; api_up=0
  for (i=1;i<=n;i++){
    tok=toks[i]; sub(/^https?:\/\//,"",tok); gsub(/[{}]/,"",tok)
    if (tok ~ /^[A-Za-z0-9_.-]+:[0-9]+$/){ ups++; if (tok ~ /api/) api_up=1 }
  }
  if (api_up && ups>=2){ printf "%s:%d:%s\n", FILENAME, FNR, $0; rc=1 }
}
END { exit rc }
AWK
)

# --- checks -------------------------------------------------------------------

check_compose_replicas() {
  local f hits
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    hits="$(awk "$REPLICAS_AWK" "$f" 2>/dev/null || true)"
    report_hits "$hits" "api service declares replicas that are not clearly 0 or 1 (fail-closed for non-literal/>=2 values)"
  done < <(find "$REPO_ROOT" \( -name .git -o -name node_modules \) -prune -o \
    -type f \( -name 'compose*.yml' -o -name 'compose*.yaml' \
    -o -name 'docker-compose*.yml' -o -name 'docker-compose*.yaml' \) -print 2>/dev/null)
}

check_scale_flag() {
  local surfaces=() s f hits
  for s in docs scripts infra .github/workflows .devcontainer Makefile Justfile; do
    [ -e "${REPO_ROOT}/${s}" ] && surfaces+=("${REPO_ROOT}/${s}")
  done
  [ "${#surfaces[@]}" -gt 0 ] || return 0
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    hits="$(awk "$SCALE_AWK" "$f" 2>/dev/null || true)"
    report_hits "$hits" "docker compose --scale api with a value that is not clearly 0 or 1 (fail-closed for non-literal/>=2 values)"
  done < <(grep -rIlE --exclude="$GUARD_SELF" --exclude="$GUARD_TEST" -- '--scale' "${surfaces[@]}" 2>/dev/null || true)
}

check_caddy_upstreams() {
  local caddy_dir="${REPO_ROOT}/infra/caddy" f hits
  [ -d "$caddy_dir" ] || return 0
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    hits="$(awk "$CADDY_AWK" "$f" 2>/dev/null || true)"
    report_hits "$hits" "an API upstream together with any additional upstream on the same reverse_proxy/to directive line"
  done < <(find "$caddy_dir" -type f -print 2>/dev/null)
}

check_compose_replicas
check_scale_flag
check_caddy_upstreams

if [ "$FAILED" -ne 0 ]; then
  echo "" >&2
  echo "DOMAIN-SINGLE-INSTANCE-GUARD: single-instance boundary violated." >&2
  echo "  Horizontal API scale-out requires a new task plus a tested cross-instance" >&2
  echo "  cache invalidation/coherence mechanism — it is not enabled by config drift." >&2
  exit 1
fi

echo "DOMAIN-SINGLE-INSTANCE-GUARD: ok"

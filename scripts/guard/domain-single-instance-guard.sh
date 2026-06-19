#!/usr/bin/env bash
# Intentionally no `set -e`: scanner failures must map to a dedicated internal
# exit code (2), not abort the script with an arbitrary status. See the exit
# code contract below.
set -uo pipefail

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
#
#   1. compose api scaling — only `services.api.scale` and
#      `services.api.deploy.replicas` are inspected, and only literal `0` or `1`
#      (optionally quoted) are accepted. A direct `services.api.replicas` key, an
#      inline/alias/merge shape on the api service or its deploy block, and any
#      non-literal value are blocked (fail-closed). Same-named keys nested under
#      `environment`, `labels`, `annotations` or `x-*` are ignored.
#   2. `docker compose --scale api=<value>` / `docker compose scale api=<value>`
#      on executable surfaces — only literal `0` or `1` pass; missing or any
#      other value is blocked. Under `docs/` the abstract placeholders `N` and
#      `<value>` are additionally allowed.
#   3. an API upstream together with any additional upstream on the same Caddy
#      `reverse_proxy`/`to` directive line.
#
# The API host family for Caddy is `api`, `weltgewebe-api`, and their numbered
# variants `api-<n>` / `weltgewebe-api-<n>`. Hosts that merely contain the
# substring "api" (e.g. `myapi`, `api-gateway`, `capital-api`) are not API hosts.
#
# Exit code contract:
#   0 = no violation
#   1 = single-instance policy violation
#   2 = internal error (scanner failure / guard could not complete a check)
# Priority: internal error (2) outranks policy violation (1) outranks ok (0).
#
# Known limitations (tracked as future work, not blockers for DOMAIN-PG-002):
#   - multi-line Caddy `reverse_proxy`/`to` blocks (one upstream per line)
#   - dynamic Caddy upstream placeholders (e.g. `{env.WEB_UPSTREAM_URL}`) are not
#     statically resolved
#   - individual compose files are inspected, not the rendered multi-file model
#   - shell line continuations of a `docker compose --scale` command
#   - a real YAML/Caddy AST check (would need yq/caddy in CI as a hard dep)

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd -- "${SCRIPT_DIR}/../.." >/dev/null 2>&1 && pwd)}"

GUARD_SELF="domain-single-instance-guard.sh"
GUARD_TEST="test_domain_single_instance_guard.sh"
DECISION_REF="docs/reports/domain-postgres-instance-coherence-decision.md"

# Configurable scanners so tests can inject failing fakes (see exit code 2).
FIND_BIN="${FIND_BIN:-find}"
GREP_BIN="${GREP_BIN:-grep}"
AWK_BIN="${AWK_BIN:-awk}"

VIOLATION=0
INTERNAL_ERR=0

internal_error() {
  echo "DOMAIN-SINGLE-INSTANCE-GUARD: internal error: $*" >&2
  INTERNAL_ERR=1
}

# Print one finding block per offending location with a single shared reason.
report_hits() {
  local hits="$1" reason="$2" line
  [ -n "$hits" ] || return 0
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    echo "DOMAIN-SINGLE-INSTANCE-GUARD: ${reason}" >&2
    echo "  ${line}" >&2
    echo "  api scale-out is forbidden by DOMAIN-PG-002 single-instance boundary; see ${DECISION_REF}" >&2
    VIOLATION=1
  done <<<"$hits"
}

# Print one finding block per offending location; the reason is selected from a
# leading TAG (TAG<TAB>file:line:content), so the compose check can speak to the
# specific drift class it detected.
report_tagged() {
  local hits="$1" tag rest reason
  [ -n "$hits" ] || return 0
  while IFS=$'\t' read -r tag rest; do
    [ -n "$tag" ] || continue
    case "$tag" in
      VALUE) reason="api service declares scale/replicas that is not literal 0 or 1 (fail-closed)" ;;
      DIRECT) reason="api service uses unsupported direct replicas key; use api.scale or api.deploy.replicas with literal 0 or 1" ;;
      SHAPE) reason="api service uses an unsupported inline, alias or merge shape; single-instance safety cannot be proven statically" ;;
      *) reason="api single-instance violation" ;;
    esac
    echo "DOMAIN-SINGLE-INSTANCE-GUARD: ${reason}" >&2
    echo "  ${rest}" >&2
    echo "  api scale-out is forbidden by DOMAIN-PG-002 single-instance boundary; see ${DECISION_REF}" >&2
    VIOLATION=1
  done <<<"$hits"
}

# --- awk programs (quoted heredocs: single/double quotes used freely) ---------

# Check 1 — api scaling in a single compose file.
# Indentation-based state machine (mawk-portable). Only the direct child key
# `services.api.scale` and the direct child key `services.api.deploy.replicas`
# are evaluated; a direct `services.api.replicas`, inline/alias/merge shapes and
# any non-literal value are flagged. environment/labels/annotations/x-* subtrees
# under api are skipped so same-named keys there do not trigger.
REPLICAS_AWK=$(cat <<'AWK'
function bad_value(v) {
  sub(/[[:space:]]*#.*$/, "", v)
  gsub(/['"]/, "", v)
  gsub(/[[:space:]]/, "", v)
  if (v == "0" || v == "1") return 0
  return 1
}
BEGIN {
  in_services=0; services_indent=-1
  svc_indent=-1; in_api=0; api_child_indent=-1
  in_deploy=0; deploy_indent=-1; deploy_child_indent=-1
  ignore_indent=-1; rc=0
}
/^[[:space:]]*($|#)/ { next }
{
  line=$0
  match(line, /^[ ]*/); ind=RLENGTH

  # inside an ignored subtree (environment/labels/annotations/x-*)
  if (ignore_indent >= 0) {
    if (ind > ignore_indent) next
    ignore_indent=-1
  }

  # dedent context resets
  if (in_deploy && ind <= deploy_indent) { in_deploy=0; deploy_child_indent=-1 }
  if (in_api && ind <= svc_indent) { in_api=0; in_deploy=0; api_child_indent=-1; deploy_child_indent=-1 }
  if (in_services && services_indent >= 0 && ind <= services_indent && line !~ /^[[:space:]]*services:/) {
    in_services=0; in_api=0; in_deploy=0
  }

  if (line ~ /^[[:space:]]*services:[[:space:]]*($|#)/) {
    in_services=1; services_indent=ind; svc_indent=-1; in_api=0; in_deploy=0
    api_child_indent=-1; deploy_child_indent=-1
    next
  }

  if (!in_services) next
  if (ind <= services_indent) next

  if (svc_indent == -1) svc_indent=ind

  if (ind == svc_indent) {
    in_deploy=0; deploy_child_indent=-1; api_child_indent=-1
    rest=line; sub(/^[[:space:]]+/, "", rest)
    name=rest; sub(/[[:space:]]*:.*$/, "", name)
    in_api=(name == "api")
    if (in_api) {
      after=rest; sub(/^api[[:space:]]*:[[:space:]]*/, "", after)
      sub(/[[:space:]]*#.*$/, "", after); gsub(/[[:space:]]+$/, "", after)
      if (after ~ /^\{/ || after ~ /^\*/) { printf "SHAPE\t%s:%d:%s\n", FILENAME, FNR, $0; rc=1 }
    }
    next
  }

  if (!in_api) next

  if (api_child_indent == -1) api_child_indent=ind

  if (ind == api_child_indent) {
    in_deploy=0; deploy_child_indent=-1
    key=line; sub(/^[[:space:]]+/, "", key)
    kname=key; sub(/[[:space:]]*:.*$/, "", kname)
    if (kname == "environment" || kname == "labels" || kname == "annotations" || kname ~ /^x-/) {
      ignore_indent=ind; next
    }
    if (kname == "<<") { printf "SHAPE\t%s:%d:%s\n", FILENAME, FNR, $0; rc=1; next }
    if (kname == "scale") {
      val=key; sub(/^scale[[:space:]]*:[[:space:]]*/, "", val)
      if (val ~ /^\*/) { printf "SHAPE\t%s:%d:%s\n", FILENAME, FNR, $0; rc=1 }
      else if (bad_value(val)) { printf "VALUE\t%s:%d:%s\n", FILENAME, FNR, $0; rc=1 }
      next
    }
    if (kname == "replicas") { printf "DIRECT\t%s:%d:%s\n", FILENAME, FNR, $0; rc=1; next }
    if (kname == "deploy") {
      after=key; sub(/^deploy[[:space:]]*:[[:space:]]*/, "", after)
      sub(/[[:space:]]*#.*$/, "", after); gsub(/[[:space:]]+$/, "", after)
      if (after ~ /^\{/ || after ~ /^\*/) { printf "SHAPE\t%s:%d:%s\n", FILENAME, FNR, $0; rc=1; next }
      in_deploy=1; deploy_indent=ind; deploy_child_indent=-1; next
    }
    next
  }

  if (in_deploy && ind > deploy_indent) {
    if (deploy_child_indent == -1) deploy_child_indent=ind
    if (ind == deploy_child_indent) {
      key=line; sub(/^[[:space:]]+/, "", key)
      kname=key; sub(/[[:space:]]*:.*$/, "", kname)
      if (kname == "replicas") {
        val=key; sub(/^replicas[[:space:]]*:[[:space:]]*/, "", val)
        if (val ~ /^\*/) { printf "SHAPE\t%s:%d:%s\n", FILENAME, FNR, $0; rc=1 }
        else if (bad_value(val)) { printf "VALUE\t%s:%d:%s\n", FILENAME, FNR, $0; rc=1 }
      }
    }
    next
  }
}
END { exit rc }
AWK
)

# Check 2 — `docker compose --scale api=<value>` / `docker compose scale api=...`.
# Comments are stripped first. A line is only considered when it actually carries
# a `docker compose` / `docker-compose` invocation, so unrelated tools and prose
# do not trigger. Quotes/backticks and `=` are normalised to spaces so the
# equals, space and quoted forms collapse to one token stream. The value policy
# depends on the surface mode (exec: only 0/1; docs: also N and <value>).
SCALE_AWK=$(cat <<'AWK'
function val_blocks(v, mode) {
  gsub(/['"`]/, "", v)
  if (v == "0" || v == "1") return 0
  if (mode == "docs") {
    if (v ~ /^[0-9]+$/ && (v + 0) >= 2) return 1
    if (v ~ /\$/) return 1
    if (v == "two" || v == "many" || v == "auto" || v == "<N>") return 1
    return 0
  }
  return 1
}
BEGIN { rc=0 }
{
  line=$0
  sub(/^[[:space:]]*#.*/, "", line)
  sub(/[[:space:]]#.*/, "", line)
  has_compose=(line ~ /docker[ -]compose/)
  norm=line
  gsub(/['"`]/, " ", norm); gsub(/=/, " ", norm); gsub(/[[:space:]]+/, " ", norm)
  n=split(norm, t, " ")
  for (i=1; i<=n; i++) {
    if (has_compose && t[i] == "--scale" && t[i+1] == "api") {
      if (i + 2 > n) { printf "%s:%d:%s\n", FILENAME, FNR, $0; rc=1 }
      else if (val_blocks(t[i+2], mode)) { printf "%s:%d:%s\n", FILENAME, FNR, $0; rc=1 }
    }
    if (t[i] == "scale" && i > 1 && t[i-1] == "compose" && t[i+1] == "api") {
      if (i + 2 > n) { printf "%s:%d:%s\n", FILENAME, FNR, $0; rc=1 }
      else if (val_blocks(t[i+2], mode)) { printf "%s:%d:%s\n", FILENAME, FNR, $0; rc=1 }
    }
  }
}
END { exit rc }
AWK
)

# Check 3 — an API upstream plus any additional upstream on one Caddy
# `reverse_proxy`/`to` directive line. Comments are removed first, the directive
# keyword is anchored at line start, an optional http(s):// scheme and `{}` are
# stripped, bracketed IPv6 hosts are recognised, path/named matchers are ignored
# (they are not host:port), and only the strict API host family counts as api.
CADDY_AWK=$(cat <<'AWK'
function is_api_host(h) {
  return (h == "api" || h == "weltgewebe-api" || h ~ /^api[-_.][0-9]+$/ || h ~ /^weltgewebe-api[-_.][0-9]+$/)
}
BEGIN { rc=0 }
{
  cline=$0
  sub(/^[[:space:]]*#.*/, "", cline)
  sub(/[[:space:]]#.*/, "", cline)
  is_rp=(cline ~ /^[[:space:]]*reverse_proxy([[:space:]]|$)/)
  is_to=(cline ~ /^[[:space:]]*to([[:space:]]|$)/)
  if (!is_rp && !is_to) next
  rest=cline
  if (is_rp) sub(/^[[:space:]]*reverse_proxy[[:space:]]*/, "", rest)
  else sub(/^[[:space:]]*to[[:space:]]+/, "", rest)
  n=split(rest, toks, /[[:space:]]+/); ups=0; api_up=0
  for (i=1; i<=n; i++) {
    tok=toks[i]
    sub(/^https?:\/\//, "", tok)
    gsub(/[{}]/, "", tok)
    if (tok ~ /^([A-Za-z0-9_.-]+|\[[0-9A-Fa-f:.%_-]+\]):[0-9]+$/) {
      ups++
      host=tok; sub(/:[0-9]+$/, "", host)
      if (is_api_host(host)) api_up=1
    }
  }
  if (api_up && ups >= 2) { printf "%s:%d:%s\n", FILENAME, FNR, $0; rc=1 }
}
END { exit rc }
AWK
)

# --- scanners (fail-visible: surface errors as internal error / exit 2) --------

SCAN_FILES=()

# run_find <find-args...> ; appends `-print0`. Writes the NUL-delimited list to a
# temp file, checks the exit status, then loads it into SCAN_FILES. A find
# failure is an internal error, never a silently-empty result.
run_find() {
  SCAN_FILES=()
  local tmp rc f
  tmp="$(mktemp 2>/dev/null)" || { internal_error "mktemp failed"; return 1; }
  "$FIND_BIN" "$@" -print0 >"$tmp" 2>/dev/null
  rc=$?
  if [ "$rc" -ne 0 ]; then
    rm -f "$tmp"
    internal_error "find failed (exit ${rc})"
    return 1
  fi
  while IFS= read -r -d '' f; do SCAN_FILES+=("$f"); done <"$tmp"
  rm -f "$tmp"
  return 0
}

# awk_scan <out-var-name> <file> [extra awk args...] <program>
# Runs awk on a single file, distinguishing rc 0/1 (clean/violations) from
# rc > 1 (internal error). Sets the named variable to the awk stdout.
awk_scan() {
  local __outvar="$1" __file="$2"
  shift 2
  local __out __rc
  __out="$("$AWK_BIN" "$@" "$__file" 2>/dev/null)"
  __rc=$?
  if [ "$__rc" -gt 1 ]; then
    internal_error "awk failed (exit ${__rc}) on ${__file}"
    return 1
  fi
  printf -v "$__outvar" '%s' "$__out"
  return 0
}

check_compose_replicas() {
  run_find "$REPO_ROOT" \( -name .git -o -name node_modules -o -name target -o -name .venv \) -prune -o \
    -type f \( -name 'compose*.yml' -o -name 'compose*.yaml' \
    -o -name 'docker-compose*.yml' -o -name 'docker-compose*.yaml' \) || return 0
  local f out
  for f in "${SCAN_FILES[@]}"; do
    [ -n "$f" ] || continue
    awk_scan out "$f" "$REPLICAS_AWK" || continue
    report_tagged "$out"
  done
}

# scan_scale <mode> <surface...> — grep is a pre-filter (rc 1 = no match is
# normal; rc > 1 is an internal error); awk does the precise, mode-aware check.
scan_scale() {
  local mode="$1"
  shift
  local surfaces=() s
  for s in "$@"; do [ -e "$s" ] && surfaces+=("$s"); done
  [ "${#surfaces[@]}" -gt 0 ] || return 0
  local out rc f ao reason
  out="$("$GREP_BIN" -rIlE --exclude="$GUARD_SELF" --exclude="$GUARD_TEST" -- 'scale' "${surfaces[@]}" 2>/dev/null)"
  rc=$?
  if [ "$rc" -gt 1 ]; then internal_error "grep (scale) failed (exit ${rc})"; return 0; fi
  [ "$rc" -eq 0 ] || return 0
  if [ "$mode" = "docs" ]; then
    reason="docker compose api scaling example uses a disallowed value (only 0, 1 or the N / <value> placeholders are allowed under docs/)"
  else
    reason="docker compose api scaling on an executable surface must be literal 0 or 1 (fail-closed)"
  fi
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    awk_scan ao "$f" -v mode="$mode" "$SCALE_AWK" || continue
    report_hits "$ao" "$reason"
  done <<<"$out"
}

check_scale_flag() {
  scan_scale exec \
    "${REPO_ROOT}/scripts" "${REPO_ROOT}/infra" "${REPO_ROOT}/.github/workflows" \
    "${REPO_ROOT}/.devcontainer" "${REPO_ROOT}/Makefile" "${REPO_ROOT}/Justfile"
  scan_scale docs "${REPO_ROOT}/docs"
}

check_caddy_upstreams() {
  local caddy_dir="${REPO_ROOT}/infra/caddy" f out
  [ -d "$caddy_dir" ] || return 0
  run_find "$caddy_dir" -type f || return 0
  for f in "${SCAN_FILES[@]}"; do
    [ -n "$f" ] || continue
    awk_scan out "$f" "$CADDY_AWK" || continue
    report_hits "$out" "an API upstream together with any additional upstream on the same reverse_proxy/to directive line"
  done
}

check_compose_replicas
check_scale_flag
check_caddy_upstreams

if [ "$INTERNAL_ERR" -ne 0 ]; then
  echo "" >&2
  echo "DOMAIN-SINGLE-INSTANCE-GUARD: internal error — a check could not be completed." >&2
  echo "  The single-instance boundary was NOT proven; treat as inconclusive, not as a pass." >&2
  exit 2
fi

if [ "$VIOLATION" -ne 0 ]; then
  echo "" >&2
  echo "DOMAIN-SINGLE-INSTANCE-GUARD: single-instance boundary violated." >&2
  echo "  Horizontal API scale-out requires a new task plus a tested cross-instance" >&2
  echo "  cache invalidation/coherence mechanism — it is not enabled by config drift." >&2
  exit 1
fi

echo "DOMAIN-SINGLE-INSTANCE-GUARD: ok"
exit 0

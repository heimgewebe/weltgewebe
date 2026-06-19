#!/usr/bin/env bash
set -euo pipefail

# DOMAIN-PG-002: static single-instance boundary for the API.
#
# The API still has process-local domain/auth state without tested cross-instance
# invalidation. This guard blocks obvious static scale-out drift. It is not a
# runtime proof and not a complete YAML/Caddy parser.
#
# Exit codes: 0 = no violation, 1 = single-instance policy violation,
# 2 = internal error (a find/grep/awk scanner failed or a check could not run).
# Internal error outranks a policy violation.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" > /dev/null 2>&1 && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd -- "${SCRIPT_DIR}/../.." > /dev/null 2>&1 && pwd)}"

GUARD_SELF="domain-single-instance-guard.sh"
GUARD_TEST="test_domain_single_instance_guard.sh"
DECISION_REF="docs/reports/domain-postgres-instance-coherence-decision.md"
FAILED=0
INTERNAL=0

# Configurable scanners so tests can inject failing fakes. A scanner failure is
# an internal error (exit 2), never a silent pass.
FIND_BIN="${FIND_BIN:-find}"
GREP_BIN="${GREP_BIN:-grep}"
AWK_BIN="${AWK_BIN:-awk}"

report_hits() {
  local hits="$1" reason="$2" line
  [ -n "$hits" ] || return 0
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    echo "DOMAIN-SINGLE-INSTANCE-GUARD: ${reason}" >&2
    echo "  ${line}" >&2
    echo "  api scale-out is forbidden by DOMAIN-PG-002; see ${DECISION_REF}" >&2
    FAILED=1
  done <<< "$hits"
}

report_scan_error() {
  local detail="$1"
  echo "DOMAIN-SINGLE-INSTANCE-GUARD: scan failed" >&2
  echo "  ${detail}" >&2
  echo "  refusing to pass with incomplete evidence; see ${DECISION_REF}" >&2
  INTERNAL=1
}

run_awk_check() {
  local program="$1" file="$2" reason="$3" mode="${4:-}" hits status

  if hits="$("$AWK_BIN" ${mode:+-v mode="$mode"} "$program" "$file" 2>&1)"; then
    status=0
  else
    status=$?
  fi

  if [ "$status" -gt 1 ]; then
    report_scan_error "awk failed for ${file}: ${hits}"
    return 0
  fi

  report_hits "$hits" "$reason"
}

# Block-style Compose parser. It checks only structurally relevant keys:
# - direct api.scale
# - direct api.replicas (always forbidden)
# - direct api.deploy.replicas
# Count values fail closed: only exact literal 0/1, optionally fully quoted,
# are accepted. Non-provable shapes on the api service or its deploy block also
# fail closed: inline flow mappings, aliases and merge keys. Pure block anchors
# are allowed, and their child keys are still checked.
REPLICAS_AWK=$(
  cat << 'AWK'
function trim(v) {
  sub(/^[[:space:]]+/, "", v)
  sub(/[[:space:]]+$/, "", v)
  return v
}
function unquote_key(v) {
  v=trim(v)
  if ((v ~ /^"[^"]*"$/) || (v ~ /^'[^']*'$/)) {
    return substr(v, 2, length(v)-2)
  }
  return v
}
function parse_mapping(src, body, pos) {
  body=trim(src)
  pos=index(body, ":")
  if (pos == 0) return 0
  map_key=unquote_key(substr(body, 1, pos-1))
  map_value=trim(substr(body, pos+1))
  return 1
}
function strip_value_comment(v) {
  if (v ~ /^#/) return ""
  sub(/[[:space:]]+#.*$/, "", v)
  return trim(v)
}
function allowed_count(v) {
  v=strip_value_comment(v)
  return v == "0" || v == "1" || v == "\"0\"" || v == "\"1\"" || v == "'0'" || v == "'1'"
}
function unprovable_inline_value(v) {
  v=strip_value_comment(v)
  if (v == "") return 0
  if (v ~ /^\*/) return 1
  if (index(v, "{") > 0) return 1
  if (v ~ /^&[A-Za-z0-9_.-]+$/) return 0
  return 1
}
function finding() { printf "%s:%d:%s\n", FILENAME, FNR, raw; rc=1 }
BEGIN {
  in_services=0; services_indent=-1; service_indent=-1
  in_api=0; api_child_indent=-1
  in_deploy=0; deploy_indent=-1; deploy_child_indent=-1
  rc=0
}
{
  raw=$0
  line=$0
  if (line ~ /^[[:space:]]*($|#)/) next
  match(line, /^ */); ind=RLENGTH
  if (!parse_mapping(line)) next

  if (map_key == "services" && strip_value_comment(map_value) == "") {
    in_services=1; services_indent=ind; service_indent=-1
    in_api=0; api_child_indent=-1; in_deploy=0
    next
  }
  if (!in_services) next
  if (ind <= services_indent) {
    in_services=0; in_api=0; in_deploy=0
    next
  }

  if (service_indent == -1) service_indent=ind
  if (ind == service_indent) {
    name=map_key
    in_api=(name == "api")
    api_child_indent=-1; in_deploy=0; deploy_indent=-1; deploy_child_indent=-1
    if (in_api) {
      if (unprovable_inline_value(map_value)) finding()
    }
    next
  }

  if (!in_api || ind <= service_indent) next
  if (api_child_indent == -1) api_child_indent=ind

  if (ind == api_child_indent) {
    in_deploy=0; deploy_indent=-1; deploy_child_indent=-1

    # YAML merge key under api (<<: *anchor): unprovable -> fail closed.
    if (map_key == "<<") { finding(); next }
    if (map_key == "deploy") {
      if (unprovable_inline_value(map_value)) { finding(); next }
      in_deploy=1; deploy_indent=ind
      next
    }
    if (map_key == "scale") {
      if (!allowed_count(map_value)) finding()
      next
    }
    if (map_key == "replicas") {
      finding()
      next
    }
  }

  if (in_deploy) {
    if (ind <= deploy_indent) {
      in_deploy=0
    } else {
      if (deploy_child_indent == -1) deploy_child_indent=ind
      if (ind == deploy_child_indent) {
        if (map_key == "<<") { finding(); next }
        if (map_key == "replicas" && !allowed_count(map_value)) finding()
      }
    }
  }
}
END { exit rc }
AWK
)

# Docker Compose CLI parser.
# It recognizes only token sequences starting at docker-compose or docker compose,
# then checks API scale arguments after that command. Executable surfaces accept
# only literal 0/1. Documentation additionally accepts the abstract placeholders
# N and <value>; concrete or malformed values, including <N>, still fail.
SCALE_AWK=$(
  cat << 'AWK'
function safe_value(v) { return v == "0" || v == "1" }
function doc_placeholder(v) { return v == "N" || v == "<value>" }
function permitted(v) { return safe_value(v) || (mode == "docs" && doc_placeholder(v)) }
function finding() { printf "%s:%d:%s\n", FILENAME, FNR, raw; rc=1 }
function check_value(v) {
  if (v == "" || !permitted(v)) finding()
}
function value_after_api(pos, v) {
  if (pos+1 > n) return ""
  if (t[pos+1] == "=") {
    if (pos+2 > n) return ""
    return t[pos+2]
  }
  return t[pos+1]
}
function scale_api_pos(pos, p) {
  p=pos+1
  if (p <= n && t[p] == "=") p++
  if (p > n || t[p] != "api") return 0
  return p
}
BEGIN { rc=0 }
{
  raw=$0
  line=$0
  if (mode == "exec") {
    if (line ~ /^[[:space:]]*#/) next
    sub(/[[:space:]]+#.*$/, "", line)
  }

  gsub(/[`'"]/, " ", line)
  gsub(/=/, " = ", line)
  gsub(/[[:space:]]+/, " ", line)
  sub(/^ /, "", line); sub(/ $/, "", line)
  if (line == "") next

  n=split(line, t, " ")
  start=0
  for (j=1; j<=n; j++) {
    if (t[j] == "docker-compose") { start=j+1; break }
    if (j < n && t[j] == "docker" && t[j+1] == "compose") { start=j+2; break }
  }
  if (start == 0) next

  for (i=start; i<=n; i++) {
    if (t[i] == "--scale") {
      api_pos=scale_api_pos(i)
      if (api_pos == 0) {
        if (i+1 > n) finding()
        continue
      }
      check_value(value_after_api(api_pos))
      continue
    }

    if (t[i] == "scale") {
      for (k=i+1; k<=n; k++) {
        if (t[k] == "api") check_value(value_after_api(k))
      }
    }
  }
}
END { exit rc }
AWK
)

# Caddy line heuristic. Comments are removed before directive recognition. API
# identity is deliberately narrow: api, weltgewebe-api, or those with a numeric
# instance suffix (-, _ or . separator, e.g. api-2 / weltgewebe-api-1). Names
# such as api-gateway, capital-api or myapi are not treated as the protected API.
CADDY_AWK=$(
  cat << 'AWK'
BEGIN { rc=0 }
{
  raw=$0
  line=$0
  sub(/#.*/, "", line)

  is_rp=(line ~ /^[[:space:]]*reverse_proxy([[:space:]]|$)/)
  is_to=(line ~ /^[[:space:]]*to([[:space:]]|$)/)
  if (!is_rp && !is_to) next

  rest=line
  if (is_rp) sub(/^[[:space:]]*reverse_proxy[[:space:]]*/, "", rest)
  else sub(/^[[:space:]]*to[[:space:]]*/, "", rest)

  n=split(rest, toks, /[[:space:]]+/); ups=0; api_up=0
  for (i=1; i<=n; i++) {
    tok=toks[i]
    sub(/^https?:\/\//, "", tok)
    gsub(/[{}]/, "", tok)
    if (tok ~ /^([A-Za-z0-9_.-]+|\[[0-9A-Fa-f:.%_-]+\]):[0-9]+$/) {
      ups++
      host=tok
      sub(/:[0-9]+$/, "", host)
      if (host ~ /^api([-_.][0-9]+)?$/ || host ~ /^weltgewebe-api([-_.][0-9]+)?$/) api_up=1
    }
  }
  if (api_up && ups >= 2) {
    printf "%s:%d:%s\n", FILENAME, FNR, raw
    rc=1
  }
}
END { exit rc }
AWK
)

check_compose_counts() {
  local files f
  if ! files="$("$FIND_BIN" "$REPO_ROOT" \
    \( -name .git -o -name node_modules -o -name target -o -name .venv \) -prune -o \
    -type f \( -name 'compose*.yml' -o -name 'compose*.yaml' \
    -o -name 'docker-compose*.yml' -o -name 'docker-compose*.yaml' \) -print 2>&1)"; then
    report_scan_error "find failed while locating Compose files: ${files}"
    return
  fi

  while IFS= read -r f; do
    [ -n "$f" ] || continue
    run_awk_check "$REPLICAS_AWK" "$f" \
      "api Compose scale/replicas is not a literal 0 or 1, or uses an unprovable inline/alias/merge shape"
  done <<< "$files"
}

scan_scale_surface() {
  local mode="$1"
  shift
  local files status f

  if files="$("$GREP_BIN" -rIlE \
    --exclude="$GUARD_SELF" --exclude="$GUARD_TEST" \
    --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=target \
    --exclude-dir=.venv --exclude-dir=_generated --exclude-dir=docs/_generated \
    -- 'docker-compose|docker[[:space:]]+compose|--scale' "$@" 2>&1)"; then
    status=0
  else
    status=$?
  fi

  if [ "$status" -eq 1 ]; then
    return 0
  fi
  if [ "$status" -ne 0 ]; then
    report_scan_error "grep failed while scanning ${mode} scale surfaces: ${files}"
    return 0
  fi

  while IFS= read -r f; do
    [ -n "$f" ] || continue
    run_awk_check "$SCALE_AWK" "$f" \
      "docker compose --scale api value is malformed or not permitted for this surface" "$mode"
  done <<< "$files"
}

check_scale_flags() {
  local docs=() exec_surfaces=() s

  [ -d "${REPO_ROOT}/docs" ] && docs+=("${REPO_ROOT}/docs")
  for s in scripts infra .github/workflows .devcontainer Makefile Justfile; do
    [ -e "${REPO_ROOT}/${s}" ] && exec_surfaces+=("${REPO_ROOT}/${s}")
  done

  [ "${#docs[@]}" -eq 0 ] || scan_scale_surface docs "${docs[@]}"
  [ "${#exec_surfaces[@]}" -eq 0 ] || scan_scale_surface exec "${exec_surfaces[@]}"
}

check_caddy_upstreams() {
  local caddy_dir="${REPO_ROOT}/infra/caddy" files f
  [ -d "$caddy_dir" ] || return 0

  if ! files="$("$FIND_BIN" "$caddy_dir" -type f -print 2>&1)"; then
    report_scan_error "find failed while locating Caddy files: ${files}"
    return
  fi

  while IFS= read -r f; do
    [ -n "$f" ] || continue
    run_awk_check "$CADDY_AWK" "$f" \
      "an API upstream appears with another upstream on one reverse_proxy/to directive line"
  done <<< "$files"
}

check_compose_counts
check_scale_flags
check_caddy_upstreams

# Exit-code contract: 0 = no violation, 1 = policy violation, 2 = internal error.
# Internal error outranks a policy violation, so a crashed/failed scanner is
# reported as inconclusive (2), never as a silent pass.
if [ "$INTERNAL" -ne 0 ]; then
  echo "" >&2
  echo "DOMAIN-SINGLE-INSTANCE-GUARD: internal error — a check could not be completed." >&2
  echo "  Treat as inconclusive (exit 2), not as a pass." >&2
  exit 2
fi

if [ "$FAILED" -ne 0 ]; then
  echo "" >&2
  echo "DOMAIN-SINGLE-INSTANCE-GUARD: single-instance boundary violated." >&2
  echo "  Horizontal API scale-out requires a new task and tested cross-instance coherence." >&2
  exit 1
fi

echo "DOMAIN-SINGLE-INSTANCE-GUARD: ok"

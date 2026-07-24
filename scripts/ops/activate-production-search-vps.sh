#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE_CHECKOUT="${WELTGEWEBE_SOURCE_CHECKOUT:-/opt/weltgewebe}"
RELEASE_ROOT="${WELTGEWEBE_RELEASE_ROOT:-/opt/weltgewebe-releases}"
RUNTIME_ENV="${WELTGEWEBE_RUNTIME_ENV:-/etc/weltgewebe/weltgewebe.env}"
STATE_ROOT="${WELTGEWEBE_DEPLOY_STATE_ROOT:-/var/lib/weltgewebe-main-reconciler}"
FRONTEND_VERSION_URL="${WELTGEWEBE_FRONTEND_VERSION_URL:-https://weltgewebe.net/_app/version.json}"
API_VERSION_URL="${WELTGEWEBE_API_VERSION_URL:-https://weltgewebe.net/api/version}"
SEARCH_URL="${WELTGEWEBE_SEARCH_URL:-https://weltgewebe.net/api/search}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-weltgewebe}"

readonly LOCK_DOMAIN="weltgewebe-production-deployment-v1"
readonly LOCK_FILE="$STATE_ROOT/production-deployment.lock"
readonly PROVIDER="local:ollama"
readonly MODEL_ID="qwen3-embedding:4b"
readonly MODEL_REVISION="sha256:df5bd2e3c74cd8d069d21dc038f1b359fcdc9458fce1c99bd43c9eb1518ff907"
readonly RUNTIME_IDENTITY="ollama:0.12.6@http://127.0.0.1:11434"
readonly OLLAMA_URL="http://127.0.0.1:11434"
readonly DIMENSION="2560"
readonly GENERATION_ID="search-gen-2e8358273aa6d41e6a59025985a99738614aba725b8f369b3a54f390f8752e5c"
readonly OLLAMA_IMAGE="ollama/ollama:0.12.6@sha256:352e045b937ac29d3d9550c22fb85525f60a89e064df34c26579bee5a93b3a16"
readonly MIN_DISK_BYTES="${WELTGEWEBE_SEARCH_MIN_DISK_BYTES:-8589934592}"
readonly MIN_MEMORY_BYTES="${WELTGEWEBE_SEARCH_MIN_MEMORY_BYTES:-5368709120}"
readonly MIN_CPU_COUNT="${WELTGEWEBE_SEARCH_MIN_CPU_COUNT:-3}"
readonly MAX_BATCHES="${WELTGEWEBE_SEARCH_MAX_BATCHES:-100}"
readonly BATCH_SIZE="${WELTGEWEBE_SEARCH_BACKFILL_MAX_JOBS:-200}"

COMMIT=""
release_dir=""
started_at=""
receipt_terminal=false
aggregate_status="unobserved"

usage() {
  echo "Usage: activate-production-search-vps.sh --commit <40-char-main-sha>" >&2
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" > /dev/null 2>&1 || fail "required command not found: $1"
}

PREVIOUS_GENERATION_ID=""
semantic_probe_status="unobserved"
rollback_status="not_attempted"

write_receipt() {
  local result="$1"
  local completed_at="$2"
  local receipt_dir="$STATE_ROOT/search-activation"
  local receipt="$receipt_dir/$GENERATION_ID.json"
  local temporary
  install -d -o root -g root -m 0700 "$receipt_dir"
  temporary="$(mktemp "$receipt_dir/.${GENERATION_ID}.XXXXXX")"
  jq -n \
    --arg result "$result" \
    --arg commit "$COMMIT" \
    --arg generation_id "$GENERATION_ID" \
    --arg previous_generation_id "$PREVIOUS_GENERATION_ID" \
    --arg semantic_probe_status "$semantic_probe_status" \
    --arg rollback_status "$rollback_status" \
    --arg provider "$PROVIDER" \
    --arg model_id "$MODEL_ID" \
    --arg model_revision "$MODEL_REVISION" \
    --arg runtime_identity "$RUNTIME_IDENTITY" \
    --arg dimension "$DIMENSION" \
    --arg started_at "$started_at" \
    --arg completed_at "$completed_at" \
    --arg aggregate_status "$aggregate_status" \
    '{schema_version:1,kind:"weltgewebe_search_activation",result:$result,commit:$commit,generation_id:$generation_id,previous_generation_id:(if ($previous_generation_id|length)>0 then $previous_generation_id else null end),semantic_probe_status:$semantic_probe_status,rollback_status:$rollback_status,provider:$provider,model_id:$model_id,model_revision:$model_revision,runtime_identity:$runtime_identity,dimension:($dimension|tonumber),started_at:(if ($started_at|length)>0 then $started_at else null end),completed_at:(if ($completed_at|length)>0 then $completed_at else null end),aggregate_status:$aggregate_status,does_not_establish:["private content disclosure","SemantAH retirement","domain data mutation authority"]}' \
    > "$temporary"
  chmod 0600 "$temporary"
  chown root:root "$temporary"
  mv -fT "$temporary" "$receipt"
  ln -sfn "search-activation/$GENERATION_ID.json" "$STATE_ROOT/search-activation-current.json"
  echo "$receipt"
}

cleanup() {
  local rc=$?
  trap - EXIT
  if ((rc != 0)) && [[ -n "$started_at" && "$receipt_terminal" == false ]]; then
    write_receipt "failed" "$(date --utc +%Y-%m-%dT%H:%M:%SZ 2> /dev/null || true)" > /dev/null || true
  fi
  exit "$rc"
}
trap cleanup EXIT

while (($#)); do
  case "$1" in
    --commit)
      [[ $# -ge 2 ]] || fail "--commit requires a value"
      COMMIT="$2"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *) fail "unknown argument: $1" ;;
  esac
done

[[ "$EUID" -eq 0 ]] || fail "this helper must run as root"
[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]] || fail "commit must be a full lowercase Git SHA"
for bounded_value in "$MIN_DISK_BYTES" "$MIN_MEMORY_BYTES" "$MIN_CPU_COUNT" "$MAX_BATCHES" "$BATCH_SIZE"; do
  [[ "$bounded_value" =~ ^[0-9]+$ ]] || fail "numeric activation limits are invalid"
done
((MIN_DISK_BYTES > 0 && MIN_MEMORY_BYTES > 0 && MIN_CPU_COUNT > 0)) || fail "resource limits must be positive"
((MAX_BATCHES >= 1 && MAX_BATCHES <= 1000)) || fail "WELTGEWEBE_SEARCH_MAX_BATCHES must be 1..=1000"
((BATCH_SIZE >= 1 && BATCH_SIZE <= 10000)) || fail "WELTGEWEBE_SEARCH_BACKFILL_MAX_JOBS must be 1..=10000"
for command_name in git docker curl jq flock install realpath readlink stat find awk grep date mktemp mv ln df rm chmod chown sleep getconf; do
  require_command "$command_name"
done
[[ -d "$SOURCE_CHECKOUT" && ! -L "$SOURCE_CHECKOUT" ]] || fail "source checkout is missing or unsafe"
[[ -f "$RUNTIME_ENV" && ! -L "$RUNTIME_ENV" ]] || fail "runtime environment is missing or unsafe"
[[ "$(stat --format=%u "$RUNTIME_ENV")" == "0" ]] || fail "runtime environment is not root-owned"
(((8#$(stat --format=%a "$RUNTIME_ENV") & 022) == 0)) || fail "runtime environment is group- or world-writable"
[[ -f "$LOCK_FILE" && ! -L "$LOCK_FILE" ]] || fail "production lock is missing or unsafe"
[[ "$(stat --format=%u "$LOCK_FILE")" == "0" ]] || fail "production lock is not root-owned"
exec 9<> "$LOCK_FILE"
flock -n 9 || fail "production deployment lock is busy"

release_dir="$(readlink -f "$STATE_ROOT/current-release")"
release_root_real="$(realpath "$RELEASE_ROOT")"
case "$release_dir" in "$release_root_real"/*) ;; *) fail "current release escaped release root" ;; esac
[[ "$(git -C "$release_dir" rev-parse HEAD)" == "$COMMIT" ]] || fail "current release is not the requested commit"
remote_main="$(git -C "$SOURCE_CHECKOUT" ls-remote origin refs/heads/main | awk '{print $1}')"
[[ "$remote_main" == "$COMMIT" ]] || fail "requested commit is no longer current origin/main"
[[ "$(curl -fsS "$API_VERSION_URL" | jq -er '.commit')" == "$COMMIT" ]] || fail "public API commit mismatch"
[[ "$(curl -fsS "$FRONTEND_VERSION_URL" | jq -er '.commit')" == "$COMMIT" ]] || fail "public frontend commit mismatch"

available_disk="$(df -B1 --output=avail / | awk 'NR==2 {print $1}')"
available_memory="$(awk '/^MemAvailable:/ {print $2 * 1024}' /proc/meminfo)"
available_cpus="$(getconf _NPROCESSORS_ONLN)"
[[ "$available_disk" =~ ^[0-9]+$ && "$available_memory" =~ ^[0-9]+$ && "$available_cpus" =~ ^[0-9]+$ ]] || fail "resource preflight could not be measured"
((available_disk >= MIN_DISK_BYTES)) || fail "insufficient free disk for pinned Ollama image and model"
((available_memory >= MIN_MEMORY_BYTES)) || fail "insufficient available memory for qwen3-embedding:4b"
((available_cpus >= MIN_CPU_COUNT)) || fail "insufficient online CPUs for qwen3-embedding:4b"

compose=(docker compose --env-file "$RUNTIME_ENV" -p "$COMPOSE_PROJECT" -f "$release_dir/infra/compose/compose.prod.yml")
override="$release_dir/infra/compose/compose.vps.override.yml"
[[ -f "$override" && ! -L "$override" ]] && compose+=(-f "$override")
"${compose[@]}" config --services | grep -qFx ollama || fail "canonical compose has no Ollama service"
for service in api db nats ollama search-worker; do
  cid="$("${compose[@]}" ps -q "$service")"
  [[ -n "$cid" ]] || fail "required service is not running: $service"
  [[ "$(docker inspect --format '{{.State.Running}}' "$cid")" == "true" ]] || fail "required service is not running: $service"
done
ollama_cid="$("${compose[@]}" ps -q ollama)"
[[ "$(docker inspect --format '{{.Config.Image}}' "$ollama_cid")" == "$OLLAMA_IMAGE" ]] || fail "Ollama image identity mismatch"
api_cid="$("${compose[@]}" ps -q api)"
worker_cid="$("${compose[@]}" ps -q search-worker)"
[[ "$(docker inspect --format '{{.Image}}' "$worker_cid")" == "$(docker inspect --format '{{.Image}}' "$api_cid")" ]] || fail "search worker image is not commit-bound to API image"
[[ "$(docker inspect --format '{{json .Config.Cmd}}' "$worker_cid")" == '["/usr/local/bin/search-worker-loop"]' ]] || fail "search worker command mismatch"

started_at="$(date --utc +%Y-%m-%dT%H:%M:%SZ)"
write_receipt "preparing" "" > /dev/null

"${compose[@]}" exec -T ollama ollama pull "$MODEL_ID"
version_body="$("${compose[@]}" exec -T api wget -qO- "$OLLAMA_URL/api/version")"
[[ "$(jq -er '.version' <<< "$version_body")" == "0.12.6" ]] || fail "Ollama runtime version mismatch"
tags_body="$("${compose[@]}" exec -T api wget -qO- "$OLLAMA_URL/api/tags")"
observed_digest="$(jq -er --arg model "$MODEL_ID" '.models[] | select(.name == $model) | .digest' <<< "$tags_body")"
[[ "$observed_digest" == "$MODEL_REVISION" ]] || fail "Ollama model digest mismatch"

[[ "$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$api_cid" | awk -F= '$1=="WELTGEWEBE_SEARCH_OLLAMA_URL" {print $2}')" == "$OLLAMA_URL/" ]] || fail "API search provider URL is not literal loopback"

db_cid="$("${compose[@]}" ps -q db)"
postgres_user="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$db_cid" | awk -F= '$1=="POSTGRES_USER" {print substr($0,index($0,"=")+1)}')"
postgres_db="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$db_cid" | awk -F= '$1=="POSTGRES_DB" {print substr($0,index($0,"=")+1)}')"
[[ -n "$postgres_user" && -n "$postgres_db" ]] || fail "PostgreSQL identity could not be resolved"
psql_exec() {
  "${compose[@]}" exec -T db psql -v ON_ERROR_STOP=1 -U "$postgres_user" -d "$postgres_db" "$@"
}

if ! PREVIOUS_GENERATION_ID="$(psql_exec -Atc "SELECT generation_id FROM search_index_generations WHERE state = 'active' ORDER BY activated_at DESC LIMIT 1;")"; then
  fail "failed to capture previous active search generation"
fi

for ((batch = 1; batch <= MAX_BATCHES; batch++)); do
  "${compose[@]}" exec -T \
    -e WELTGEWEBE_SEARCH_GENERATION_ID="$GENERATION_ID" \
    -e WELTGEWEBE_SEARCH_BACKFILL_MAX_JOBS="$BATCH_SIZE" \
    -e WELTGEWEBE_SEARCH_OLLAMA_URL="$OLLAMA_URL/" \
    -e WELTGEWEBE_SEARCH_PROVIDER="$PROVIDER" \
    -e WELTGEWEBE_SEARCH_MODEL_ID="$MODEL_ID" \
    -e WELTGEWEBE_SEARCH_MODEL_REVISION="$MODEL_REVISION" \
    -e WELTGEWEBE_SEARCH_RUNTIME_IDENTITY="$RUNTIME_IDENTITY" \
    -e WELTGEWEBE_SEARCH_DIMENSION="$DIMENSION" \
    api /app/search-backfill
  aggregate_status="$(psql_exec -Atc "SELECT concat_ws('|',g.expected_nodes,g.completed_nodes,count(*) FILTER (WHERE j.state='pending'),count(*) FILTER (WHERE j.state='claimed'),count(*) FILTER (WHERE j.state='retry'),count(*) FILTER (WHERE j.state='failed')) FROM search_index_generations g LEFT JOIN search_projection_jobs j ON j.generation_id=g.generation_id WHERE g.generation_id='$GENERATION_ID' GROUP BY g.expected_nodes,g.completed_nodes;")"
  IFS='|' read -r expected completed pending claimed retry failed <<< "$aggregate_status"
  for count in "$expected" "$completed" "$pending" "$claimed" "$retry" "$failed"; do
    [[ "$count" =~ ^[0-9]+$ ]] || fail "search projection aggregate is malformed"
  done
  [[ "$failed" == "0" ]] || fail "search projection contains failed jobs"
  if [[ "$pending" == "0" && "$claimed" == "0" && "$retry" == "0" ]]; then
    break
  fi
  ((batch < MAX_BATCHES)) || fail "bounded backfill did not converge"
  sleep 2
done

[[ "$expected" =~ ^[0-9]+$ && "$completed" == "$expected" ]] || fail "search generation is incomplete"

probe_json="$(psql_exec -At -v gen="$GENERATION_ID" -c "SELECT json_build_object('id', p.node_id, 'title', p.title)::text FROM search_node_projections p JOIN domain_nodes n ON n.id=p.node_id WHERE p.generation_id=:'gen' AND n.search_visibility='public' AND p.status='active' AND p.semantic_state='ready' AND cardinality(p.embedding)=$DIMENSION ORDER BY p.node_id LIMIT 1;")"

probe_node_id=""
probe_title=""
if [[ -n "$probe_json" ]]; then
  probe_node_id="$(jq -er '.id | select(type == "string" and length > 0)' <<< "$probe_json")" || fail "semantic probe node id is malformed"
  probe_title="$(jq -er '.title | select(type == "string" and length > 0)' <<< "$probe_json")" || fail "semantic probe title is malformed"
  semantic_probe_status="candidate_bound"
else
  semantic_probe_status="not_applicable"
  echo "Notice: active generation has no public semantic probe candidate"
fi

gate_ready="$(psql_exec -At -v gen="$GENERATION_ID" -c "SELECT weltgewebe_search_generation_activation_ready(:'gen');")"
[[ "$gate_ready" == "t" ]] || fail "database activation gate rejected generation"
psql_exec -v gen="$GENERATION_ID" -c "SELECT weltgewebe_activate_search_generation(:'gen');" > /dev/null

verify_activation() {
  identity_ok="$(psql_exec -v gen="$GENERATION_ID" -v prov="$PROVIDER" -v model="$MODEL_ID" -v rev="$MODEL_REVISION" -v rid="$RUNTIME_IDENTITY" -v dim="$DIMENSION" -Atc "SELECT count(*)=1 FROM search_index_generations WHERE generation_id=:'gen' AND state='active' AND provider=:'prov' AND model_id=:'model' AND model_revision=:'rev' AND runtime_identity=:'rid' AND dimension=:'dim'::integer AND completed_nodes=expected_nodes;")"
  [[ "$identity_ok" == "t" ]] || return 1

  if [[ "$semantic_probe_status" == "candidate_bound" ]]; then
    search_body="$(mktemp)"
    curl -fsS --get --data-urlencode "q=$probe_title" --data-urlencode 'limit=10' "$SEARCH_URL" > "$search_body" || {
      rm -f "$search_body"
      return 1
    }
    jq -e --arg generation "$GENERATION_ID" --arg probe_id "$probe_node_id" '.generation_id == $generation and .mode == "hybrid" and (.items | type == "array") and any(.items[]?; .id == $probe_id)' "$search_body" > /dev/null || {
      rm -f "$search_body"
      return 1
    }
    rm -f "$search_body"
    semantic_probe_status="verified"
  fi

  worker_cid="$("${compose[@]}" ps -q search-worker)"
  if [[ -z "$worker_cid" || "$(docker inspect --format '{{.State.Running}}' "$worker_cid")" != "true" ]]; then
    echo "ERROR: search worker stopped or was replaced after activation" >&2
    return 1
  fi
  if [[ "$(docker inspect --format '{{.Image}}' "$worker_cid")" != "$(docker inspect --format '{{.Image}}' "$api_cid")" ]]; then
    echo "ERROR: search worker image drifted after activation" >&2
    return 1
  fi
  if [[ "$(docker inspect --format '{{json .Config.Cmd}}' "$worker_cid")" != '["/usr/local/bin/search-worker-loop"]' ]]; then
    echo "ERROR: search worker command drifted after activation" >&2
    return 1
  fi
  return 0
}

rollback_activation() {
  local rollback_ok
  if [[ -n "$PREVIOUS_GENERATION_ID" ]]; then
    if [[ "$PREVIOUS_GENERATION_ID" != "$GENERATION_ID" ]]; then
      psql_exec -v prev_gen="$PREVIOUS_GENERATION_ID" -c "SELECT weltgewebe_activate_search_generation(:'prev_gen');" > /dev/null || return 1
    fi
    rollback_ok="$(psql_exec -At -v prev_gen="$PREVIOUS_GENERATION_ID" -v gen="$GENERATION_ID" -c "SELECT count(*)=1 FROM search_index_generations WHERE generation_id=:'prev_gen' AND state='active' AND (:'prev_gen'=:'gen' OR NOT EXISTS (SELECT 1 FROM search_index_generations WHERE generation_id=:'gen' AND state='active'));")" || return 1
  else
    psql_exec -v gen="$GENERATION_ID" -c "BEGIN; SELECT pg_advisory_xact_lock(hashtextextended('weltgewebe.search.generation.activation', 0)); UPDATE search_index_generations SET state='ready', activated_at=NULL WHERE generation_id=:'gen' AND state='active'; COMMIT;" > /dev/null || return 1
    rollback_ok="$(psql_exec -At -v gen="$GENERATION_ID" -c "SELECT count(*)=1 FROM search_index_generations WHERE generation_id=:'gen' AND state='ready' AND NOT EXISTS (SELECT 1 FROM search_index_generations WHERE state='active');")" || return 1
  fi
  [[ "$rollback_ok" == "t" ]]
}

if ! verify_activation; then
  echo "ERROR: post-activation verification failed, initiating rollback..." >&2
  semantic_probe_status="failed"
  if rollback_activation; then
    rollback_status="verified"
  else
    rollback_status="failed"
  fi
  aggregate_status="post_activation_verification_failed|rollback=$rollback_status"
  write_receipt "failed" "$(date --utc +%Y-%m-%dT%H:%M:%SZ)" > /dev/null
  receipt_terminal=true
  if [[ "$rollback_status" != "verified" ]]; then
    fail "post-activation verification failed and rollback could not be verified"
  fi
  fail "post-activation verification failed; rollback verified"
fi

aggregate_status="active|expected=$expected|completed=$completed|failed=$failed|worker=running"
receipt="$(write_receipt "verified" "$(date --utc +%Y-%m-%dT%H:%M:%SZ)")"
receipt_terminal=true
echo "search_activation=verified commit=$COMMIT generation=$GENERATION_ID receipt=$receipt lock_domain=$LOCK_DOMAIN"

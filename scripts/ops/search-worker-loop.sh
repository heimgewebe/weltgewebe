#!/usr/bin/env bash
set -Eeuo pipefail

readonly OLLAMA_URL="${WELTGEWEBE_SEARCH_OLLAMA_URL:?WELTGEWEBE_SEARCH_OLLAMA_URL is required}"
readonly MODEL_ID="${WELTGEWEBE_SEARCH_MODEL_ID:?WELTGEWEBE_SEARCH_MODEL_ID is required}"
readonly MODEL_REVISION="${WELTGEWEBE_SEARCH_MODEL_REVISION:?WELTGEWEBE_SEARCH_MODEL_REVISION is required}"
readonly INTERVAL_SECONDS="${WELTGEWEBE_SEARCH_WORKER_INTERVAL_SECONDS:-15}"

[[ "$OLLAMA_URL" == "http://127.0.0.1:11434/" ]] || {
  echo "search_worker=blocked reason=provider_not_literal_loopback" >&2
  exit 1
}
if [[ ! "$INTERVAL_SECONDS" =~ ^[0-9]+$ ]] || ((INTERVAL_SECONDS < 5 || INTERVAL_SECONDS > 300)); then
  echo "search_worker=blocked reason=invalid_interval" >&2
  exit 1
fi

provider_ready() {
  local body observed
  body="$(wget -qO- "${OLLAMA_URL}api/tags" 2> /dev/null)" || return 1
  observed="$(jq -er --arg model "$MODEL_ID" '.models[] | select(.name == $model) | .digest' <<< "$body" 2> /dev/null)" || return 1
  [[ "$observed" == "$MODEL_REVISION" ]]
}

while true; do
  if provider_ready; then
    if /app/search-backfill; then
      echo "search_worker=batch_complete"
    else
      echo "search_worker=batch_failed" >&2
    fi
  else
    echo "search_worker=waiting_for_pinned_model"
  fi
  sleep "$INTERVAL_SECONDS"
done

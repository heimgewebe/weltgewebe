      echo "WARNING: Frontend artifact missing and build disabled."
  fi
fi

# --- Failure Bundle Logic ---
generate_failure_bundle() {
  local error_msg="$1"
  local err_log_file="${2:-}"
  local timestamp=$(date +"%Y%m%d-%H%M%S")
  local bundle_dir=".ops/failures/${timestamp}"

  mkdir -p "$bundle_dir"

  # 1. git_state.txt
  {
    local branch
    branch=$(git symbolic-ref -q --short HEAD 2>/dev/null || echo "DETACHED")
    local head_commit
    head_commit=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    local remote_main
    remote_main=$(git rev-parse --short "refs/remotes/${REMOTE}/main" 2>/dev/null || echo "unknown")

    echo "branch: $branch"
    echo "head: $head_commit"
    echo "remote main: $remote_main"
    echo "fetch attempted: $GIT_FETCH_ATTEMPTED"
    echo "pull attempted: $GIT_PULL_ATTEMPTED"

    if [[ -n "$GIT_PULL_SKIPPED_REASON" ]]; then
       echo "pull skipped reason: $GIT_PULL_SKIPPED_REASON"
    fi
    echo "autofix applied: $GIT_AUTOFIX_APPLIED"
  } > "${bundle_dir}/git_state.txt"

  # 2. compose_ps.txt
  docker compose "${BASE_ARGS[@]}" ps > "${bundle_dir}/compose_ps.txt" 2>&1 || true

  # 3. unhealthy_containers.txt & 4. / 5. details
  local ps_format
  ps_format=$(docker compose "${BASE_ARGS[@]}" ps --format '{{.Name}} {{.State}} {{.Health}}' 2>/dev/null || true)

  local unhealthy_containers=()
  while IFS= read -r line; do
    if [[ -z "$line" ]]; then continue; fi
    local name
    name=$(echo "$line" | awk '{print $1}')
    local state
    state=$(echo "$line" | awk '{print $2}')
    local health
    health=$(echo "$line" | awk '{print $3}')

    if [[ "$state" == "exited" || "$health" == "unhealthy" || "$state" == "dead" || "$state" == "created" ]]; then
       unhealthy_containers+=("$name")
    fi
  done <<< "$ps_format"

  if [[ ${#unhealthy_containers[@]} -gt 0 ]]; then
      for c in "${unhealthy_containers[@]}"; do
          echo "$c" >> "${bundle_dir}/unhealthy_containers.txt"
          docker inspect --format '{{json .State.Health}}' "$c" > "${bundle_dir}/health_details_${c}.json" 2>/dev/null || true
          docker logs --tail=100 "$c" > "${bundle_dir}/container_logs_${c}.log" 2>&1 || true
      done
  else
      echo "No specific unhealthy/exited containers detected." > "${bundle_dir}/unhealthy_containers.txt"
  fi

  # 6. Compose Configuration Source
  {
    echo "Base Compose File: $BASE_COMPOSE_FILE"
    if [[ -f "$OVERRIDE_FILE" ]]; then
        echo "Override File: $OVERRIDE_FILE"
    else
        echo "Override File: None"
    fi
  } > "${bundle_dir}/compose_files.txt"

  # 7. api_network_aliases.txt
  local api_cid=$(docker compose "${BASE_ARGS[@]}" ps -q api 2>/dev/null || true)
  if [[ -n "$api_cid" ]]; then
      docker inspect --format '{{range .NetworkSettings.Networks}}{{println .NetworkID}} {{println .Aliases}}{{end}}' "$api_cid" > "${bundle_dir}/api_network_aliases.txt" 2>/dev/null || true
  fi

  # 8. docker compose up stderr log (if provided)
  if [[ -n "$err_log_file" && -f "$err_log_file" ]]; then
      cp "$err_log_file" "${bundle_dir}/compose_up.stderr.log"
  fi

  # Print failure summary (exact requested format)
  echo
  echo "ERROR: Deploy failed."
  if [[ -n "$error_msg" ]]; then
      echo "$error_msg"
  fi
  echo
  echo "Git state:"
  cat "${bundle_dir}/git_state.txt"
  echo
  echo "Compose state:"

  # Compose state summary
  while IFS= read -r line; do
    if [[ -z "$line" ]]; then continue; fi
    local srv_name
    srv_name=$(echo "$line" | awk '{print $1}')
    local srv
    srv=$(docker inspect --format '{{ index .Config.Labels "com.docker.compose.service"}}' "$srv_name" 2>/dev/null || echo "unknown")
    local state
    state=$(echo "$line" | awk '{print $2}')
    local health
    health=$(echo "$line" | awk '{print $3}')

    local display_state="$state"
    if [[ "$health" == "healthy" || "$health" == "unhealthy" ]]; then
        display_state="$health"
    elif [[ -z "$health" || "$health" == "<nil>" || "$health" == "starting" ]]; then
        display_state="$state"
    fi
    echo "${srv}: ${display_state}"
  done <<< "$ps_format"

  echo
  echo "Diagnostics saved:"
  echo "${bundle_dir}/"
  echo
}

# 7. Deploy
echo
echo
echo ">> Preflight: Validating runtime contract..."
if [[ -x "scripts/preflight/runtime_contract.sh" ]]; then

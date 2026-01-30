#!/usr/bin/env bash
set -euo pipefail

# -----------------------------
# Configuration (sane defaults)
# -----------------------------
SNAPSHOT_MODE="${SNAPSHOT_MODE:-dry}"          # dry | live
COMPOSE_FILE="${COMPOSE_FILE:-infra/compose/compose.prod.yml}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-compose}"
HEALTH_MODE="${HEALTH_MODE:-container}"        # container | url
HEALTH_URL="${HEALTH_URL:-}"
OUT_DIR="${OUT_DIR:-artifacts}"
OUT_FILE="${OUT_DIR}/deploy.snapshot.json"

# -----------------------------
# Helpers
# -----------------------------
iso_ts() { date -Is; }
sha256() { sha256sum "$1" | awk '{print $1}'; }

have() { command -v "$1" >/dev/null 2>&1; }

json_escape() {
  python3 - <<'PY'
import json,sys
print(json.dumps(sys.stdin.read()))
PY
}

collect_compose_config() {
  local out
  if have docker && docker compose version >/dev/null 2>&1; then
    set +e
    out="$(docker compose -f "$COMPOSE_FILE" config 2>&1)"
    rc=$?
    set -e
    echo "$out"
    return $rc
  else
    return 127
  fi
}

mkdir -p "$OUT_DIR"

# -----------------------------
# Repo info
# -----------------------------
REPO_PATH="$(pwd)"
REPO_SHA=""
REPO_DIRTY="null"

if have git && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  REPO_SHA="$(git rev-parse --short HEAD)"
  if git diff --quiet; then
    REPO_DIRTY="false"
  else
    REPO_DIRTY="true"
  fi
else
  REPO_SHA=""
  REPO_DIRTY="null"
fi

# -----------------------------
# Compose file hash
# -----------------------------
if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Compose file not found: $COMPOSE_FILE" >&2
  exit 1
fi

COMPOSE_FILE_SHA="$(sha256 "$COMPOSE_FILE")"

# -----------------------------
# Compose render (best effort)
# -----------------------------
RENDER_DEGRADED="false"
CONFIG_SHA="null"
WARNINGS=()

if cfg_out="$(collect_compose_config)"; then
  CONFIG_SHA="$(printf "%s" "$cfg_out" | sha256sum | awk '{print $1}')"
else
  RENDER_DEGRADED="true"
fi

while IFS= read -r line; do
  if [[ "$line" =~ WARN ]]; then
    RENDER_DEGRADED="true"
    WARNINGS+=("$(printf "%s" "$line")")
  fi
done <<< "$cfg_out"

WARNINGS_JSON="[]"
if [ ${#WARNINGS[@]} -gt 0 ]; then
  WARNINGS_JSON=$(python3 -c "import sys, json; print(json.dumps(sys.argv[1:]))" "${WARNINGS[@]}")
fi

# -----------------------------
# Containers / Volumes / Mounts
# -----------------------------
CONTAINERS_JSON="[]"
VOLUMES_JSON="[]"
MOUNTS_JSON="[]"
HEALTH_JSON='{ "mode": null, "url": null, "ok": null, "http_code": null, "reason": null }'

if [[ "$SNAPSHOT_MODE" == "live" ]]; then
  if ! have docker; then
    echo "Live mode requires docker" >&2
    exit 2
  fi

  mapfile -t RUNNING < <(docker ps --format '{{.Names}}')

  declare -A SERVICES=(
    ["api"]="compose-api-1"
    ["caddy"]="compose-caddy-1"
    ["db"]="compose-db-1"
  )

  CONTAINERS_JSON="$(python3 - <<PY
import json,subprocess
services = {
    "api": "compose-api-1",
    "caddy": "compose-caddy-1",
    "db": "compose-db-1"
}
out=[]
for svc,name in services.items():
    try:
        insp = subprocess.check_output(
          ["docker","inspect",name], stderr=subprocess.DEVNULL
        )
        data=json.loads(insp)[0]
        ports=[]
        if data.get("NetworkSettings",{}).get("Ports"):
            for k,v in data["NetworkSettings"]["Ports"].items():
                if v:
                    for e in v:
                        ports.append(f'{e["HostIp"]}:{e["HostPort"]}->{k}')
        out.append({
          "service": svc,
          "name": name,
          "image": data["Config"]["Image"],
          "digest": None,
          "status": data["State"]["Status"],
          "health": data["State"].get("Health",{}).get("Status"),
          "ports": ports
        })
    except Exception:
        pass
print(json.dumps(out, indent=2))
PY
)"

  VOLUMES_JSON="$(python3 - <<PY
import json,subprocess
logical = {
  "pg_data_prod":"compose_pg_data_prod",
  "nats_js":"compose_nats_js",
  "gewebe_fs_data":"compose_gewebe_fs_data",
  "caddy_data":"compose_caddy_data",
  "caddy_config":"compose_caddy_config"
}
out=[]
for l,c in logical.items():
    try:
        subprocess.check_output(["docker","volume","inspect",c], stderr=subprocess.DEVNULL)
        ex=True
    except Exception:
        ex=False
    out.append({"logical":l,"compose_name":c,"exists":ex})
print(json.dumps(out, indent=2))
PY
)"

  MOUNTS_JSON="$(python3 - <<PY
import json,subprocess
out=[]
for c in ["compose-caddy-1","compose-api-1","compose-db-1"]:
    try:
        insp=json.loads(subprocess.check_output(["docker","inspect",c]))[0]
        for m in insp.get("Mounts",[]):
            if m.get("Type")=="bind":
                out.append({
                  "container": c,
                  "type": m["Type"],
                  "source": m["Source"],
                  "destination": m["Destination"]
                })
    except Exception:
        pass
print(json.dumps(out, indent=2))
PY
)"

  if [[ "$HEALTH_MODE" == "container" ]]; then
    if docker exec compose-api-1 sh -c 'command -v curl' >/dev/null 2>&1; then
      if docker exec compose-api-1 curl -fsS http://127.0.0.1:8080/health/ready >/dev/null 2>&1; then
        HEALTH_JSON='{ "mode":"container","url":null,"ok":true,"http_code":200,"reason":null }'
      else
        HEALTH_JSON='{ "mode":"container","url":null,"ok":false,"http_code":500,"reason":"health endpoint failed" }'
      fi
    else
      HEALTH_JSON='{ "mode":"container","url":null,"ok":null,"http_code":null,"reason":"curl not available in container" }'
    fi
  fi
fi

# -----------------------------
# Emit snapshot
# -----------------------------
ISO_TS="$(iso_ts)"
HOSTNAME="$(hostname)"

python3 - <<PY > "$OUT_FILE"
import json,sys
snapshot = {
  "ts": "${ISO_TS}",
  "host": "${HOSTNAME}",
  "repo": {
    "path": "$REPO_PATH",
    "sha_short": "$REPO_SHA" if "$REPO_SHA" else None,
    "dirty": True if "$REPO_DIRTY" == "true" else (False if "$REPO_DIRTY" == "false" else None)
  },
  "compose": {
    "file": "$COMPOSE_FILE",
    "file_sha256": "$COMPOSE_FILE_SHA",
    "config_sha256": "$CONFIG_SHA" if "$CONFIG_SHA"!="null" else None,
    "render_degraded": True if "$RENDER_DEGRADED" == "true" else False,
    "warnings": json.loads('''$WARNINGS_JSON''')
  },
  "containers": json.loads('''$CONTAINERS_JSON'''),
  "volumes": json.loads('''$VOLUMES_JSON'''),
  "mounts": json.loads('''$MOUNTS_JSON'''),
  "health": json.loads('''$HEALTH_JSON''')
}
print(json.dumps(snapshot, indent=2))
PY

echo "Snapshot written to $OUT_FILE"

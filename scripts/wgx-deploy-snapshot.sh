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
  # Robust dirty check: staged + unstaged changes
  # git diff-index --quiet HEAD -- returns 1 if dirty, 0 if clean
  if git diff-index --quiet HEAD -- 2>/dev/null; then
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

  # Dynamic container names based on project prefix
  # Typical compose naming: <project>-<service>-<index>
  API_CONTAINER="${COMPOSE_PROJECT}-api-1"
  CADDY_CONTAINER="${COMPOSE_PROJECT}-caddy-1"
  DB_CONTAINER="${COMPOSE_PROJECT}-db-1"

  # Pass service mapping to python via environment to avoid injection
  export SVC_MAP_JSON=$(python3 -c "import json; print(json.dumps({'api': '$API_CONTAINER', 'caddy': '$CADDY_CONTAINER', 'db': '$DB_CONTAINER'}))")

  CONTAINERS_JSON="$(python3 - <<'PY'
import json, subprocess, os

service_map = json.loads(os.environ['SVC_MAP_JSON'])
out = []

for svc, name in service_map.items():
    try:
        insp = subprocess.check_output(
            ["docker", "inspect", name], stderr=subprocess.DEVNULL
        )
        data = json.loads(insp)[0]

        # Ports
        ports = []
        if data.get("NetworkSettings", {}).get("Ports"):
            for k, v in data["NetworkSettings"]["Ports"].items():
                if v:
                    for e in v:
                        ports.append(f'{e["HostIp"]}:{e["HostPort"]}->{k}')

        # Digest (try to get it from image inspect if needed, or from Config.Image)
        # docker inspect output usually contains RepoDigests in the Image struct,
        # but here we are inspecting the container.
        # Container inspect -> Image is the ID. We'd need to inspect the image ID to get RepoDigests.
        # For simplicity, we leave digest null here unless we add a second call.
        # Let's try a lightweight attempt if feasible, else null.
        digest = None
        try:
             image_id = data["Image"]
             img_insp = subprocess.check_output(["docker", "inspect", image_id], stderr=subprocess.DEVNULL)
             img_data = json.loads(img_insp)[0]
             if img_data.get("RepoDigests"):
                 digest = img_data["RepoDigests"][0]
        except:
             pass

        out.append({
            "service": svc,
            "name": name,
            "image": data["Config"]["Image"],
            "digest": digest,
            "status": data["State"]["Status"],
            "health": data["State"].get("Health", {}).get("Status"),
            "ports": ports
        })
    except Exception:
        pass
print(json.dumps(out, indent=2))
PY
)"

  # Dynamic Volume Discovery
  # List all volumes starting with project prefix
  export PROJ_PREFIX="${COMPOSE_PROJECT}_"
  VOLUMES_JSON="$(python3 - <<'PY'
import json, subprocess, os

prefix = os.environ['PROJ_PREFIX']
out = []

try:
    # List volumes filtering by name is not strictly supported by 'docker volume ls --filter name=...'
    # in all versions the same way (regex vs substring). We list all and filter in python.
    ls_out = subprocess.check_output(["docker", "volume", "ls", "--format", "{{.Name}}"], stderr=subprocess.DEVNULL)
    volumes = ls_out.decode().strip().split('\n')

    for v in volumes:
        if v.startswith(prefix):
            logical = v[len(prefix):]
            out.append({
                "logical": logical,
                "compose_name": v,
                "exists": True
            })
except Exception:
    pass

print(json.dumps(out, indent=2))
PY
)"

  # Mounts for specific containers
  # We use the same service map to inspect mounts
  MOUNTS_JSON="$(python3 - <<'PY'
import json, subprocess, os

service_map = json.loads(os.environ['SVC_MAP_JSON'])
out = []
# We only care about specific containers for mounts usually, or all in the map.
# Let's check all in the map.
containers = list(service_map.values())

for c in containers:
    try:
        insp = json.loads(subprocess.check_output(["docker", "inspect", c], stderr=subprocess.DEVNULL))[0]
        for m in insp.get("Mounts", []):
            if m.get("Type") == "bind":
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

  # Health Check
  if [[ "$HEALTH_MODE" == "container" ]]; then
    # Use fallback logic: wget -> curl inside container
    # We check API container usually
    TARGET_CONTAINER="${COMPOSE_PROJECT}-api-1"

    HEALTH_CMD="
      if command -v wget >/dev/null 2>&1; then
        wget -qO- http://127.0.0.1:8080/health/ready >/dev/null 2>&1 && echo ok || echo fail
      elif command -v curl >/dev/null 2>&1; then
        curl -fsS http://127.0.0.1:8080/health/ready >/dev/null 2>&1 && echo ok || echo fail
      else
        echo unknown
      fi
    "

    if docker ps -q -f name="$TARGET_CONTAINER" | grep -q .; then
       RES=$(docker exec "$TARGET_CONTAINER" sh -c "$HEALTH_CMD" 2>/dev/null || echo "exec_fail")
       if [[ "$RES" == "ok" ]]; then
         HEALTH_JSON='{ "mode":"container","url":null,"ok":true,"http_code":200,"reason":null }'
       elif [[ "$RES" == "unknown" ]]; then
         HEALTH_JSON='{ "mode":"container","url":null,"ok":null,"http_code":null,"reason":"neither wget nor curl available" }'
       else
         HEALTH_JSON='{ "mode":"container","url":null,"ok":false,"http_code":500,"reason":"health endpoint failed or exec error" }'
       fi
    else
       HEALTH_JSON='{ "mode":"container","url":null,"ok":false,"http_code":null,"reason":"container not running" }'
    fi
  elif [[ "$HEALTH_MODE" == "url" ]]; then
      if [[ -n "$HEALTH_URL" ]]; then
          if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
             HEALTH_JSON='{ "mode":"url","url":"'"$HEALTH_URL"'","ok":true,"http_code":200,"reason":null }'
          else
             HEALTH_JSON='{ "mode":"url","url":"'"$HEALTH_URL"'","ok":false,"http_code":null,"reason":"connection failed" }'
          fi
      fi
  fi
fi

# -----------------------------
# Emit snapshot
# -----------------------------
ISO_TS="$(iso_ts)"
HOSTNAME="$(hostname)"

# Export variables for python
export ISO_TS HOSTNAME REPO_PATH REPO_SHA REPO_DIRTY
export COMPOSE_FILE COMPOSE_FILE_SHA CONFIG_SHA RENDER_DEGRADED
export WARNINGS_JSON CONTAINERS_JSON VOLUMES_JSON MOUNTS_JSON HEALTH_JSON

python3 - <<'PY' > "$OUT_FILE"
import json, sys, os

# Safe boolean parsing
def parse_bool(val):
    return True if val == "true" else (False if val == "false" else None)

snapshot = {
  "ts": os.environ['ISO_TS'],
  "host": os.environ['HOSTNAME'],
  "repo": {
    "path": os.environ['REPO_PATH'],
    "sha_short": os.environ['REPO_SHA'] if os.environ['REPO_SHA'] else None,
    "dirty": parse_bool(os.environ['REPO_DIRTY'])
  },
  "compose": {
    "file": os.environ['COMPOSE_FILE'],
    "file_sha256": os.environ['COMPOSE_FILE_SHA'],
    "config_sha256": os.environ['CONFIG_SHA'] if os.environ['CONFIG_SHA'] != "null" else None,
    "render_degraded": parse_bool(os.environ['RENDER_DEGRADED']),
    "warnings": json.loads(os.environ['WARNINGS_JSON'])
  },
  "containers": json.loads(os.environ['CONTAINERS_JSON']),
  "volumes": json.loads(os.environ['VOLUMES_JSON']),
  "mounts": json.loads(os.environ['MOUNTS_JSON']),
  "health": json.loads(os.environ['HEALTH_JSON'])
}
print(json.dumps(snapshot, indent=2))
PY

echo "Snapshot written to $OUT_FILE"

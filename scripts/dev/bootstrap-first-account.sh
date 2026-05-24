#!/usr/bin/env bash
set -euo pipefail

# Bootstrap the first real account with a public map position.
#
# Reads account data from environment variables. Required:
#   ACCOUNT_TITLE   Display name
#   PUBLIC_LAT      Latitude (decimal degrees, e.g. 53.5503)
#   PUBLIC_LON      Longitude (decimal degrees, e.g. 9.9932)
#
# Optional:
#   ACCOUNT_ID      UUID (default: auto-generated via uuidgen or sha256 fallback)
#   ACCOUNT_SUMMARY Short description (default: empty)
#   ACCOUNT_TYPE    garnrolle|ron (default: garnrolle)
#   ACCOUNT_ROLE    weber|admin (default: weber)
#   ACCOUNT_TAGS    Comma-separated tags (default: real)
#   ACCOUNT_EMAIL   Email address (operational field, not in domain contract)
#
# Flags:
#   --round-location  Round lat/lon to 3 decimal places (~111 m per 0.001 deg)
#   --clean-demo      Remove known demo sample IDs from the dataset
#   --force           Re-run even if bootstrap metadata file already exists
#   -h|--help         Show this help
#
# The TARGET_DIR can be passed as a positional argument (default: .gewebe/in).
# The metadata file .gewebe/in/bootstrap-first-account.env is created on success.
#
# Privacy notice:
#   PUBLIC_LAT/PUBLIC_LON are written to the JSONL seed and served as public_pos
#   via /api/accounts. This position is intentionally public on the map.
#   Use --round-location to reduce precision (~111 m per 0.001 deg).
#   The script does NOT prevent exact coordinates — use your own judgment.
#
# Examples:
#   ACCOUNT_TITLE="Alice" PUBLIC_LAT="53.55" PUBLIC_LON="9.99" \
#     ./scripts/dev/bootstrap-first-account.sh
#
#   ACCOUNT_TITLE="Alice" PUBLIC_LAT="53.55" PUBLIC_LON="9.99" \
#     ACCOUNT_SUMMARY="Gründerin" ACCOUNT_TAGS="real,gründung" \
#     ./scripts/dev/bootstrap-first-account.sh --round-location

DIR=".gewebe/in"
CLEAN_DEMO=0
FORCE=0
ROUND_LOCATION=0

for arg in "$@"; do
  case "$arg" in
    --clean-demo) CLEAN_DEMO=1 ;;
    --force) FORCE=1 ;;
    --round-location) ROUND_LOCATION=1 ;;
    -h | --help)
      sed -n '3,50p' "$0"
      exit 0
      ;;
    -*)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
    *) DIR="$arg" ;;
  esac
done

# --- Dependency check ---
if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required. Install with: apt-get install jq" >&2
  exit 1
fi

# --- Required env ---
if [ -z "${ACCOUNT_TITLE:-}" ]; then
  echo "Error: ACCOUNT_TITLE is required." >&2
  echo "  ACCOUNT_TITLE=\"Alice\" PUBLIC_LAT=\"53.55\" PUBLIC_LON=\"9.99\" $0" >&2
  exit 1
fi
if [ -z "${PUBLIC_LAT:-}" ]; then
  echo "Error: PUBLIC_LAT is required (latitude of your public map position)." >&2
  exit 1
fi
if [ -z "${PUBLIC_LON:-}" ]; then
  echo "Error: PUBLIC_LON is required (longitude of your public map position)." >&2
  exit 1
fi

# --- Validate coordinates are numeric ---
_validate_coord() {
  local val="$1"
  local name="$2"
  if ! printf '%s' "$val" | grep -qE '^-?[0-9]+(\.[0-9]+)?$'; then
    echo "Error: $name must be a decimal number (e.g. 53.55), got: $val" >&2
    exit 1
  fi
}
_validate_coord "$PUBLIC_LAT" "PUBLIC_LAT"
_validate_coord "$PUBLIC_LON" "PUBLIC_LON"

# --- Defaults ---
ACCOUNT_ROLE="${ACCOUNT_ROLE:-weber}"
ACCOUNT_TYPE="${ACCOUNT_TYPE:-garnrolle}"
ACCOUNT_SUMMARY="${ACCOUNT_SUMMARY:-}"
ACCOUNT_TAGS="${ACCOUNT_TAGS:-real}"

# --- Location ---
LAT="$PUBLIC_LAT"
LON="$PUBLIC_LON"
if [ "$ROUND_LOCATION" -eq 1 ]; then
  LAT="$(printf '%.3f' "$LAT")"
  LON="$(printf '%.3f' "$LON")"
fi

# --- Account ID ---
if [ -z "${ACCOUNT_ID:-}" ]; then
  if command -v uuidgen >/dev/null 2>&1; then
    ACCOUNT_ID="$(uuidgen | tr '[:upper:]' '[:lower:]')"
  else
    _hash="$(printf '%s' "${ACCOUNT_TITLE}${LAT}${LON}" | sha256sum | cut -c1-32)"
    ACCOUNT_ID="${_hash:0:8}-${_hash:8:4}-4${_hash:13:3}-8${_hash:17:3}-${_hash:20:12}"
  fi
fi

mkdir -p "$DIR"
META_FILE="$DIR/bootstrap-first-account.env"
ACCOUNTS_FILE="$DIR/demo.accounts.jsonl"
NODES_FILE="$DIR/demo.nodes.jsonl"
EDGES_FILE="$DIR/demo.edges.jsonl"

# --- Idempotency ---
if [ -f "$META_FILE" ] && [ "$FORCE" -eq 0 ]; then
  # shellcheck source=/dev/null
  . "$META_FILE"
  echo "→ Metadaten bereits vorhanden: $META_FILE"
  echo "  Account-ID: ${BOOTSTRAP_ACCOUNT_ID:-?}"
  echo "  Verwende --force zum Neuanlegen."
  exit 0
fi

# --- Privacy notice ---
printf '\n'
printf 'HINWEIS: Die Position (%s, %s) wird als öffentliche Kartenposition\n' "$LAT" "$LON"
printf '(public_pos) gespeichert und über /api/accounts abrufbar.\n'
if [ "$ROUND_LOCATION" -eq 0 ]; then
  printf 'Die Koordinaten sind exakt. Verwende --round-location für ~111 m Unschärfe.\n'
fi
printf '\n'

# --- Helpers ---
TMP_FILE=""
cleanup() {
  if [ -n "$TMP_FILE" ] && [ -f "$TMP_FILE" ]; then
    rm -f "$TMP_FILE"
  fi
}
trap cleanup EXIT

remove_line_by_id() {
  local file="$1"
  local id="$2"
  local match_pattern="^{\"id\":\"$id\""
  if [ -s "$file" ] && grep -q "$match_pattern" "$file"; then
    echo "→ removing $id from $(basename "$file")"
    TMP_FILE=$(mktemp)
    grep -v "$match_pattern" "$file" >"$TMP_FILE" || true
    mv "$TMP_FILE" "$file"
    chmod 644 "$file"
    TMP_FILE=""
  fi
}

ensure_jsonl_line() {
  local file="$1"
  local id="$2"
  local canonical_json="$3"
  local match_pattern="^{\"id\":\"$id\""

  if [ ! -s "$file" ]; then
    echo "→ seeds: $(basename "$file") (neu)"
    printf '%s\n' "$canonical_json" >"$file"
    return 0
  fi

  local count
  count=$(grep -c "$match_pattern" "$file" || true)

  if [ "$count" -eq 0 ]; then
    echo "→ adding $id to $(basename "$file")"
    printf '%s\n' "$canonical_json" >>"$file"
  elif [ "$count" -gt 1 ]; then
    echo "→ deduplicating $id in $(basename "$file")"
    TMP_FILE=$(mktemp)
    grep -v "$match_pattern" "$file" >"$TMP_FILE" || true
    printf '%s\n' "$canonical_json" >>"$TMP_FILE"
    mv "$TMP_FILE" "$file"
    chmod 644 "$file"
    TMP_FILE=""
  fi
}

# --- Demo IDs (kept in sync with generate-demo-data.sh) ---
DEMO_ACCOUNT_IDS=(
  "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8"
)
DEMO_NODE_IDS=(
  "00000000-0000-0000-0000-000000000001"
  "00000000-0000-0000-0000-000000000002"
  "00000000-0000-0000-0000-000000000003"
  "00000000-0000-0000-0000-000000000004"
  "00000000-0000-0000-0000-000000000005"
  "b52be17c-4ab7-4434-98ce-520f86290cf0"
)
DEMO_EDGE_IDS=(
  "00000000-0000-0000-0000-000000000101"
  "00000000-0000-0000-0000-000000000102"
  "00000000-0000-0000-0000-000000000103"
  "00000000-0000-0000-0000-000000000104"
  "00000000-0000-0000-0000-00000000E001"
)

if [ "$CLEAN_DEMO" -eq 1 ]; then
  echo "→ cleaning demo sample IDs from $DIR"
  touch "$ACCOUNTS_FILE" "$NODES_FILE" "$EDGES_FILE"
  for id in "${DEMO_ACCOUNT_IDS[@]}"; do remove_line_by_id "$ACCOUNTS_FILE" "$id"; done
  for id in "${DEMO_NODE_IDS[@]}"; do remove_line_by_id "$NODES_FILE" "$id"; done
  for id in "${DEMO_EDGE_IDS[@]}"; do remove_line_by_id "$EDGES_FILE" "$id"; done
fi

# --- Build account JSON ---
# type=garnrolle + mode=verortet requires location (domain contract).
# radius_m=0 → calculate_jittered_pos returns exact coords as public_pos.
TAGS_JSON="$(jq -Rn --arg tags "$ACCOUNT_TAGS" \
  '$tags | split(",") | map(gsub("^[[:space:]]+|[[:space:]]+$"; "")) | map(select(. != ""))')"

ACCOUNT_JSON="$(jq -n \
  --arg id "$ACCOUNT_ID" \
  --arg type "$ACCOUNT_TYPE" \
  --arg title "$ACCOUNT_TITLE" \
  --arg summary "$ACCOUNT_SUMMARY" \
  --argjson tags "$TAGS_JSON" \
  --arg role "$ACCOUNT_ROLE" \
  --argjson lat "$LAT" \
  --argjson lon "$LON" \
  '{id: $id, type: $type, mode: "verortet", title: $title, summary: $summary,
    tags: $tags, role: $role,
    location: {lat: $lat, lon: $lon}, radius_m: 0}' \
  | jq -c .)"

if [ -n "${ACCOUNT_EMAIL:-}" ]; then
  ACCOUNT_JSON="$(printf '%s' "$ACCOUNT_JSON" | \
    jq -c --arg email "$ACCOUNT_EMAIL" '. + {email: $email}')"
fi

touch "$ACCOUNTS_FILE"
ensure_jsonl_line "$ACCOUNTS_FILE" "$ACCOUNT_ID" "$ACCOUNT_JSON"

# --- Save metadata ---
{
  printf 'BOOTSTRAP_ACCOUNT_ID="%s"\n' "$ACCOUNT_ID"
  printf 'BOOTSTRAP_ACCOUNT_TITLE="%s"\n' "$ACCOUNT_TITLE"
  printf 'BOOTSTRAP_PUBLIC_LAT="%s"\n' "$LAT"
  printf 'BOOTSTRAP_PUBLIC_LON="%s"\n' "$LON"
} >"$META_FILE"
echo "→ Metadaten gespeichert: $META_FILE"

printf '\n'
printf '✓ Bootstrap abgeschlossen in %s\n' "$DIR"
printf '  Account:  %s (%s)\n' "$ACCOUNT_ID" "$ACCOUNT_TITLE"
printf '  Typ:      %s / verortet\n' "$ACCOUNT_TYPE"
printf '  Position: %s, %s (öffentlich auf der Karte)\n' "$LAT" "$LON"
printf '  Rolle:    %s\n' "$ACCOUNT_ROLE"
printf '\n'
printf 'Dev-Login (AUTH_DEV_LOGIN=1 vorausgesetzt):\n'
printf '  POST /api/auth/dev/login  {\"account_id\":\"%s\"}\n' "$ACCOUNT_ID"

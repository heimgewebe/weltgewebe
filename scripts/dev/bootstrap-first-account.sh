#!/usr/bin/env bash
set -euo pipefail

# Bootstrap the first real account with a public map position.
#
# The bootstrap account is always a verortete Garnrolle: the whole point is a
# visible account with a public position on the map. (RoN accounts have no
# public_pos by contract and are therefore not produced by this path.)
#
# Reads account data from environment variables. See usage() below.
#
# No external JSON tools required: uses only bash, grep, awk, sed, and printf.

usage() {
  cat << 'EOF'
Usage:
  ACCOUNT_TITLE="Alice" PUBLIC_LAT="53.5503" PUBLIC_LON="9.9932" \
    ./scripts/dev/bootstrap-first-account.sh [TARGET_DIR] [FLAGS]

Required environment variables:
  ACCOUNT_TITLE   Display name (non-empty)
  PUBLIC_LAT      Latitude in [-90, 90]   (decimal degrees, e.g. 53.5503)
  PUBLIC_LON      Longitude in [-180, 180] (decimal degrees, e.g. 9.9932)

Optional environment variables:
  ACCOUNT_ID      UUID (default: generated via uuidgen or sha256 fallback)
  ACCOUNT_SUMMARY Short description (omitted if empty)
  ACCOUNT_ROLE    weber|admin (default: admin; first real bootstrap should be admin)
  ACCOUNT_TAGS    Comma-separated tags (default: real)
  ACCOUNT_EMAIL   Email address (operational field, omitted if empty)

Flags:
  --round-location  Round lat/lon to 3 decimals (~111 m per 0.001 deg)
  --clean-demo      Remove known demo sample IDs from the dataset
  --force           Re-run even if the bootstrap metadata file exists
  -h, --help        Show this help

The created account is type=garnrolle, mode=verortet, radius_m=0 (exact
public_pos). The TARGET_DIR positional arg defaults to .gewebe/in. On success
the metadata file <TARGET_DIR>/bootstrap-first-account.env is written.

Privacy: PUBLIC_LAT/PUBLIC_LON become public_pos via /api/accounts. This
position is intentionally public on the map. Use --round-location to reduce
precision. .gewebe/in/ is git-ignored; no coordinates are written to the repo.
EOF
}

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
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $arg" >&2
      usage >&2
      exit 1
      ;;
    *) DIR="$arg" ;;
  esac
done

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

# --- Required env ---
if [ -z "${ACCOUNT_TITLE:-}" ]; then
  echo "Error: ACCOUNT_TITLE is required (non-empty)." >&2
  usage >&2
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

# --- Validate coordinates: numeric and within geographic range ---
# Uses grep for format check and awk for float range comparison (no jq).
_validate_coord() {
  local val="$1" lo="$2" hi="$3" name="$4"
  if ! printf '%s' "$val" | grep -qE '^-?[0-9]+(\.[0-9]+)?$'; then
    echo "Error: $name must be a decimal number in [$lo, $hi], got: $val" >&2
    exit 1
  fi
  if ! awk -v v="$val" -v lo="$lo" -v hi="$hi" 'BEGIN { exit !(v >= lo && v <= hi) }'; then
    echo "Error: $name must be in range [$lo, $hi], got: $val" >&2
    exit 1
  fi
}
_validate_coord "$PUBLIC_LAT" -90 90 "PUBLIC_LAT"
_validate_coord "$PUBLIC_LON" -180 180 "PUBLIC_LON"

# --- Defaults & allowlists ---
ACCOUNT_ROLE="${ACCOUNT_ROLE:-admin}"
case "$ACCOUNT_ROLE" in
  weber | admin) ;;
  *)
    echo "Error: ACCOUNT_ROLE must be 'weber' or 'admin', got: $ACCOUNT_ROLE" >&2
    exit 1
    ;;
esac
ACCOUNT_SUMMARY="${ACCOUNT_SUMMARY:-}"
ACCOUNT_TAGS="${ACCOUNT_TAGS:-real}"

# --- Location (validation already done above on raw input) ---
LAT="$PUBLIC_LAT"
LON="$PUBLIC_LON"
if [ "$ROUND_LOCATION" -eq 1 ]; then
  LAT="$(LC_ALL=C printf '%.3f' "$LAT")"
  LON="$(LC_ALL=C printf '%.3f' "$LON")"
fi

# --- Account ID ---
if [ -z "${ACCOUNT_ID:-}" ]; then
  if command -v uuidgen > /dev/null 2>&1; then
    ACCOUNT_ID="$(uuidgen | tr '[:upper:]' '[:lower:]')"
  else
    _hash="$(printf '%s' "${ACCOUNT_TITLE}${LAT}${LON}" | sha256sum | cut -c1-32)"
    ACCOUNT_ID="${_hash:0:8}-${_hash:8:4}-4${_hash:13:3}-8${_hash:17:3}-${_hash:20:12}"
  fi
fi
# Validate ID is a UUID: contract requires format uuid, and the ID is used in a
# grep regex below, so reject anything that is not a plain UUID.
if ! printf '%s' "$ACCOUNT_ID" |
  grep -qiE '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'; then
  echo "Error: ACCOUNT_ID must be a UUID, got: $ACCOUNT_ID" >&2
  exit 1
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
    grep -v "$match_pattern" "$file" > "$TMP_FILE" || true
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
    printf '%s\n' "$canonical_json" > "$file"
    return 0
  fi

  local count
  count=$(grep -c "$match_pattern" "$file" || true)

  if [ "$count" -eq 0 ]; then
    echo "→ adding $id to $(basename "$file")"
    printf '%s\n' "$canonical_json" >> "$file"
  elif [ "$count" -gt 1 ]; then
    echo "→ deduplicating $id in $(basename "$file")"
    TMP_FILE=$(mktemp)
    grep -v "$match_pattern" "$file" > "$TMP_FILE" || true
    printf '%s\n' "$canonical_json" >> "$TMP_FILE"
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

# --- JSON helpers (pure shell/sed/awk; no jq required) ---

# Escape a string value for embedding in a JSON string literal.
# Handles the critical JSON special characters: backslash (must be first),
# double-quote. Newlines and carriage-returns are stripped to preserve the
# single-line JSONL format required by the data store.
json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr -d '\r\n'
}

# Convert a comma-separated tag list to a JSON array of quoted strings.
# Trims surrounding whitespace from each tag and skips empty tokens.
tags_to_json_array() {
  local input="$1" result="[" first=1 rest tag
  rest="$input"
  while true; do
    case "$rest" in
      *,*)
        tag="${rest%%,*}"
        rest="${rest#*,}"
        ;;
      *)
        tag="$rest"
        rest=""
        ;;
    esac
    # trim leading whitespace
    while [ "${tag#[[:space:]]}" != "$tag" ]; do tag="${tag#[[:space:]]}"; done
    # trim trailing whitespace
    while [ "${tag%[[:space:]]}" != "$tag" ]; do tag="${tag%[[:space:]]}"; done
    if [ -n "$tag" ]; then
      [ "$first" -eq 0 ] && result="${result},"
      result="${result}\"$(json_escape "$tag")\""
      first=0
    fi
    [ -z "$rest" ] && break
  done
  printf '%s' "${result}]"
}

# --- Build account JSON (pure shell; no jq required) ---
# Always type=garnrolle / mode=verortet with location + radius_m=0 so the API
# computes an exact public_pos. summary/email are omitted when empty
# (contract requires summary minLength 1; additionalProperties is projected out
# by verify-demo-data.ts so operational fields role/email are allowed in JSONL).
TAGS_JSON="$(tags_to_json_array "$ACCOUNT_TAGS")"
TITLE_ESC="$(json_escape "$ACCOUNT_TITLE")"
ACCOUNT_JSON="{\"id\":\"${ACCOUNT_ID}\",\"type\":\"garnrolle\",\"mode\":\"verortet\""
ACCOUNT_JSON="${ACCOUNT_JSON},\"title\":\"${TITLE_ESC}\",\"tags\":${TAGS_JSON}"
ACCOUNT_JSON="${ACCOUNT_JSON},\"role\":\"${ACCOUNT_ROLE}\""
ACCOUNT_JSON="${ACCOUNT_JSON},\"location\":{\"lat\":${LAT},\"lon\":${LON}}"
ACCOUNT_JSON="${ACCOUNT_JSON},\"radius_m\":0}"
if [ -n "$ACCOUNT_SUMMARY" ]; then
  SUMMARY_ESC="$(json_escape "$ACCOUNT_SUMMARY")"
  ACCOUNT_JSON="${ACCOUNT_JSON%\}},\"summary\":\"${SUMMARY_ESC}\"}"
fi
if [ -n "${ACCOUNT_EMAIL:-}" ]; then
  EMAIL_ESC="$(json_escape "${ACCOUNT_EMAIL}")"
  ACCOUNT_JSON="${ACCOUNT_JSON%\}},\"email\":\"${EMAIL_ESC}\"}"
fi

touch "$ACCOUNTS_FILE"
ensure_jsonl_line "$ACCOUNTS_FILE" "$ACCOUNT_ID" "$ACCOUNT_JSON"

# --- Save metadata ---
# Values are %q-quoted so the file is safe to `source` even if the title
# contains spaces, quotes or shell metacharacters.
{
  printf 'BOOTSTRAP_ACCOUNT_ID=%q\n' "$ACCOUNT_ID"
  printf 'BOOTSTRAP_ACCOUNT_TITLE=%q\n' "$ACCOUNT_TITLE"
  printf 'BOOTSTRAP_PUBLIC_LAT=%q\n' "$LAT"
  printf 'BOOTSTRAP_PUBLIC_LON=%q\n' "$LON"
} > "$META_FILE"
echo "→ Metadaten gespeichert: $META_FILE"

printf '\n'
printf '✓ Bootstrap abgeschlossen in %s\n' "$DIR"
printf '  Account:  %s (%s)\n' "$ACCOUNT_ID" "$ACCOUNT_TITLE"
printf '  Typ:      garnrolle / verortet\n'
printf '  Position: %s, %s (öffentlich auf der Karte)\n' "$LAT" "$LON"
printf '  Rolle:    %s\n' "$ACCOUNT_ROLE"
printf '\n'
printf 'Dev-Login (AUTH_DEV_LOGIN=1 vorausgesetzt):\n'
printf '  POST /api/auth/dev/login  {"account_id":"%s"}\n' "$ACCOUNT_ID"

#!/usr/bin/env bash
set -euo pipefail

# Seeds the first REAL account plus real initial nodes/edges as JSONL.
#
# This is deliberately separate from scripts/dev/generate-demo-data.sh:
# - generate-demo-data.sh  -> throwaway demo sample
# - seed-real-data.sh      -> the real starting dataset for an actual operation
#
# Privacy: the committed records are intentionally privacy-safe.
# - The founding account is a "Rolle ohne Namen" (RoN): no location at all.
# - Real public places use rounded (~100 m) public coordinates only.
# - No emails, secrets or precise private coordinates are committed here.
#   Precise/private data belongs into the (git-ignored) .gewebe/in/*.jsonl
#   on the target machine only — never into the repository.
#
# All records validate against contracts/domain/{account,node,edge}.schema.json
# after projection to the schema's domain keys (operational fields such as
# "role" are read by the API but are not part of the domain contract).
#
# Usage:
#   ./scripts/dev/seed-real-data.sh [TARGET_DIR] [--clean-demo]
#
# Arguments:
#   TARGET_DIR     Destination directory (default: .gewebe/in)
#   --clean-demo   Remove the known demo sample IDs so the dataset stays
#                  cleanly "real only" (non-destructive otherwise).

DIR=".gewebe/in"
CLEAN_DEMO=0

for arg in "$@"; do
  case "$arg" in
    --clean-demo) CLEAN_DEMO=1 ;;
    -h | --help)
      sed -n '3,33p' "$0"
      exit 0
      ;;
    -*)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
    *) DIR="$arg" ;;
  esac
done

mkdir -p "$DIR"

# --- Helpers (mirrors generate-demo-data.sh idempotency contract) ---

TMP_FILE=""
cleanup() {
  if [ -n "$TMP_FILE" ] && [ -f "$TMP_FILE" ]; then
    rm -f "$TMP_FILE"
  fi
}
trap cleanup EXIT

# remove_line_by_id <file> <id>
# Removes all lines whose JSON starts with the exact ID from the JSONL file.
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

# ensure_jsonl_line <file> <id> <canonical_json>
# Ensures exactly one entry for the given ID exists. An existing single entry
# is left untouched so local edits on the target machine survive re-runs.
ensure_jsonl_line() {
  local file="$1"
  local id="$2"
  local canonical_json="$3"
  local match_pattern="^{\"id\":\"$id\""

  if [ ! -s "$file" ]; then
    echo "→ seeds: $(basename "$file") (new)"
    echo "$canonical_json" > "$file"
    return 0
  fi

  local count
  count=$(grep -c "$match_pattern" "$file" || true)

  if [ "$count" -eq 0 ]; then
    echo "→ adding $id to $(basename "$file")"
    echo "$canonical_json" >> "$file"
  elif [ "$count" -gt 1 ]; then
    echo "→ deduplicating $id in $(basename "$file")"
    TMP_FILE=$(mktemp)
    grep -v "$match_pattern" "$file" > "$TMP_FILE" || true
    echo "$canonical_json" >> "$TMP_FILE"
    mv "$TMP_FILE" "$file"
    chmod 644 "$file"
    TMP_FILE=""
  fi
}

# Known demo sample IDs (kept in sync with generate-demo-data.sh).
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

ACCOUNTS_FILE="$DIR/demo.accounts.jsonl"
NODES_FILE="$DIR/demo.nodes.jsonl"
EDGES_FILE="$DIR/demo.edges.jsonl"

if [ "$CLEAN_DEMO" -eq 1 ]; then
  echo "→ cleaning demo sample IDs from $DIR"
  for id in "${DEMO_ACCOUNT_IDS[@]}"; do remove_line_by_id "$ACCOUNTS_FILE" "$id"; done
  for id in "${DEMO_NODE_IDS[@]}"; do remove_line_by_id "$NODES_FILE" "$id"; done
  for id in "${DEMO_EDGE_IDS[@]}"; do remove_line_by_id "$EDGES_FILE" "$id"; done
fi

# --- REAL ACCOUNT (founding role) ---
# RoN: no location, no public position. role=weber so it may use write paths.
ACCOUNT_ID="a0000001-0000-4000-8000-000000000001"
ACCOUNT_JSON='{"id":"a0000001-0000-4000-8000-000000000001","type":"ron","mode":"ron","title":"Gründungsrolle","summary":"Erste reale Rolle ohne Namen (RoN) des Weltgewebe-Betriebs.","tags":["real","ron"],"role":"weber"}'

touch "$ACCOUNTS_FILE"
ensure_jsonl_line "$ACCOUNTS_FILE" "$ACCOUNT_ID" "$ACCOUNT_JSON"

# --- REAL NODES (public places, rounded coordinates) ---
NODE1_ID="b0000001-0000-4000-8000-000000000001"
NODE1_JSON='{"id":"b0000001-0000-4000-8000-000000000001","kind":"ort","title":"Rathausmarkt","summary":"Öffentlicher Platz im Zentrum Hamburgs.","info":"Realer öffentlicher Ort (Seed). Koordinaten gerundet (~100 m).","tags":["real","ort","öffentlich"],"created_at":"2026-05-24T00:00:00Z","updated_at":"2026-05-24T00:00:00Z","location":{"lat":53.55,"lon":9.992}}'

NODE2_ID="b0000002-0000-4000-8000-000000000002"
NODE2_JSON='{"id":"b0000002-0000-4000-8000-000000000002","kind":"ort","title":"Planten un Blomen","summary":"Öffentliche Parkanlage in Hamburg.","info":"Realer öffentlicher Ort (Seed). Koordinaten gerundet (~100 m).","tags":["real","ort","öffentlich"],"created_at":"2026-05-24T00:00:00Z","updated_at":"2026-05-24T00:00:00Z","location":{"lat":53.559,"lon":9.985}}'

touch "$NODES_FILE"
ensure_jsonl_line "$NODES_FILE" "$NODE1_ID" "$NODE1_JSON"
ensure_jsonl_line "$NODES_FILE" "$NODE2_ID" "$NODE2_JSON"

# --- REAL EDGES (founding faden + connection) ---
EDGE1_ID="c0000001-0000-4000-8000-000000000001"
EDGE1_JSON='{"id":"c0000001-0000-4000-8000-000000000001","source_type":"account","source_id":"a0000001-0000-4000-8000-000000000001","target_type":"node","target_id":"b0000001-0000-4000-8000-000000000001","edge_kind":"reference","created_at":"2026-05-24T00:00:00Z","note":"Gründungsrolle verweist auf Rathausmarkt"}'

EDGE2_ID="c0000002-0000-4000-8000-000000000002"
EDGE2_JSON='{"id":"c0000002-0000-4000-8000-000000000002","source_type":"node","source_id":"b0000001-0000-4000-8000-000000000001","target_type":"node","target_id":"b0000002-0000-4000-8000-000000000002","edge_kind":"reference","created_at":"2026-05-24T00:00:00Z","note":"Verbindung Rathausmarkt – Planten un Blomen"}'

touch "$EDGES_FILE"
ensure_jsonl_line "$EDGES_FILE" "$EDGE1_ID" "$EDGE1_JSON"
ensure_jsonl_line "$EDGES_FILE" "$EDGE2_ID" "$EDGE2_JSON"

echo "✓ Real seed ensured in $DIR"
echo "  account: $ACCOUNT_ID (RoN, role=weber)"
echo "  nodes:   $NODE1_ID, $NODE2_ID"
echo "  edges:   $EDGE1_ID, $EDGE2_ID"

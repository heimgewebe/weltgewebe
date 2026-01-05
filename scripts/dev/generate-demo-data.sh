#!/usr/bin/env bash
set -euo pipefail

# Erzeugt Demo-Daten falls nicht vorhanden.
mkdir -p .gewebe/in

# Helper function to migrate a single JSONL line based on ID
# Usage: ensure_jsonl_line <file> <id> <canonical_json> [check_field]
# - file: path to .jsonl file
# - id: UUID to manage
# - canonical_json: The full JSON line that should exist
# - check_field: optional field name (e.g. "location") to check for semantic correctness (via jq or grep)
ensure_jsonl_line() {
  local file="$1"
  local id="$2"
  local canonical_json="$3"
  local check_field="${4:-}" # Optional semantic check

  # Use regex anchor to match start of line for robustness
  local match_pattern="^{\"id\":\"$id\""
  local needs_migration=0

  if [ -s "$file" ]; then
    # Check if ID exists (anchored)
    if grep -q "$match_pattern" "$file"; then
       # Deduplication Check: If ID appears more than once, force migration
       local count
       count=$(grep -c "$match_pattern" "$file" || true)

       if [ "$count" -gt 1 ]; then
          echo "→ migrating: deduplicating $id in $(basename "$file")"
          needs_migration=1
       else
          # Exact one match found. Check semantics if requested.
          local existing_line
          existing_line=$(grep "$match_pattern" "$file")

          if [ -n "$check_field" ]; then
             if command -v jq >/dev/null 2>&1; then
               # Use jq for semantic check
               if echo "$existing_line" | jq -e "has(\"$check_field\") | not" >/dev/null 2>&1; then
                  echo "→ migrating: fixing stale entry (missing $check_field) $id in $(basename "$file")"
                  needs_migration=1
               fi
             else
               # Fallback: anchored grep check for field
               if ! echo "$existing_line" | grep -q "\"$check_field\"[[:space:]]*:"; then
                  echo "→ migrating: fixing stale entry (missing $check_field) $id in $(basename "$file")"
                  needs_migration=1
               fi
             fi
          fi

          # Special check for edges: verify target_id matches (if provided in canonical)
          # This handles the specific case of E001 edge migration
          if [[ "$file" == *"edges.jsonl"* ]] && [[ "$canonical_json" == *"target_id"* ]]; then
             # Extract target_id from canonical using grep/sed simply for this specific check
             # Note: This is a specific heuristics for the known edge migration case
             if ! echo "$existing_line" | grep -q "target_id"; then
                 : # Missing target, covered by check_field logic usually, or migration
             else
                 # Compare the line content roughly. If specific target ID is missing in existing line but present in canonical
                 # It's stale. (Simplification: if the canonical line is NOT the existing line)
                 # We simply check if canonical is exact match or not?
                 # Better: For simplicity in this script, let's trust the "check_field" or dedupe.
                 # But specifically for the E001 edge case mentioned in original script:
                 if [[ "$id" == *"E001"* ]]; then
                    # Check if it points to the new target "b52be17c..."
                    if ! echo "$existing_line" | grep -q "b52be17c-4ab7-4434-98ce-520f86290cf0"; then
                        echo "→ migrating: fixing stale edge target for $id"
                        needs_migration=1
                    fi
                 fi
             fi
          fi
       fi
    else
       # ID not present, simply needs adding
       echo "→ updating: adding $id to $(basename "$file")"
       echo "$canonical_json" >> "$file"
       return 0
    fi
  else
    # File empty or missing
    echo "→ seeds: $(basename "$file") (new)"
    echo "$canonical_json" > "$file"
    return 0
  fi

  if [ "$needs_migration" -eq 1 ]; then
    # Atomic update: remove all occurrences of the ID, then append the correct line
    local tmp_file
    tmp_file=$(mktemp)

    # Copy all lines EXCEPT the ones matching our ID
    grep -v "$match_pattern" "$file" > "$tmp_file" || true

    # Append the canonical line
    echo "$canonical_json" >> "$tmp_file"

    # Move back atomically
    mv "$tmp_file" "$file"
    chmod 644 "$file"
  fi
}

# --- ACCOUNTS ---
ACCOUNT_ID="7d97a42e-3704-4a33-a61f-0e0a6b4d65d8"
ACCOUNT_JSON='{"id":"7d97a42e-3704-4a33-a61f-0e0a6b4d65d8","type":"garnrolle","title":"gewebespinnerAYE","summary":"Persönlicher Account (Garnrolle), am Wohnsitz verortet. Ursprung von Fäden ins Gewebe.","location":{"lat":53.5604148,"lon":10.0629844},"visibility":"public","tags":["account","garnrolle","wohnort"]}'

# Ensure file exists to avoid "no such file" in grep inside function if empty
touch .gewebe/in/demo.accounts.jsonl
ensure_jsonl_line ".gewebe/in/demo.accounts.jsonl" "$ACCOUNT_ID" "$ACCOUNT_JSON" "location"


# --- NODES ---
NODE_ID="b52be17c-4ab7-4434-98ce-520f86290cf0"
NODE_LINE='{"id":"b52be17c-4ab7-4434-98ce-520f86290cf0","kind":"Knoten","title":"fairschenkbox","summary":"Öffentliche Fair-Schenk-Box","info":"Dies ist eine **Demo-Info** für den Test.","created_at":"2025-12-22T00:00:00Z","updated_at":"2025-12-22T00:00:00Z","location":{"lat":53.558894813662505,"lon":10.060228407382967}}'

# Pre-seed if missing entirely
if [ ! -s .gewebe/in/demo.nodes.jsonl ]; then
  echo "→ seeds: nodes"
  cat > .gewebe/in/demo.nodes.jsonl <<EOF
{"id":"00000000-0000-0000-0000-000000000001","kind":"Ort","title":"Marktplatz Hamburg","created_at":"2025-01-01T12:00:00Z","updated_at":"2025-11-01T09:00:00Z","location":{"lon":9.9937,"lat":53.5511}}
{"id":"00000000-0000-0000-0000-000000000002","kind":"Initiative","title":"Nachbarschaftshaus","created_at":"2025-01-01T12:00:00Z","updated_at":"2025-11-02T12:15:00Z","location":{"lon":10.0002,"lat":53.5523}}
{"id":"00000000-0000-0000-0000-000000000003","kind":"Projekt","title":"Tauschbox Altona","created_at":"2025-01-01T12:00:00Z","updated_at":"2025-10-30T18:45:00Z","location":{"lon":9.9813,"lat":53.5456}}
{"id":"00000000-0000-0000-0000-000000000004","kind":"Ort","title":"Gemeinschaftsgarten","created_at":"2025-01-01T12:00:00Z","updated_at":"2025-11-05T10:00:00Z","location":{"lon":10.0184,"lat":53.5631}}
{"id":"00000000-0000-0000-0000-000000000005","kind":"Initiative","title":"Reparaturcafé","created_at":"2025-01-01T12:00:00Z","updated_at":"2025-11-03T16:20:00Z","location":{"lon":9.9708,"lat":53.5615}}
EOF
fi

# 1. Clean up old legacy node if present (one-off cleanup)
if grep -q "00000000-0000-0000-0000-000000000006" .gewebe/in/demo.nodes.jsonl; then
   echo "→ migrating: removing legacy node 0000...0006"
   grep -v "00000000-0000-0000-0000-000000000006" .gewebe/in/demo.nodes.jsonl > .gewebe/in/demo.nodes.jsonl.tmp || true
   mv .gewebe/in/demo.nodes.jsonl.tmp .gewebe/in/demo.nodes.jsonl
fi

# 2. Ensure new correct node exists
ensure_jsonl_line ".gewebe/in/demo.nodes.jsonl" "$NODE_ID" "$NODE_LINE"


# --- EDGES ---
EDGE_ID="00000000-0000-0000-0000-00000000E001"
EDGE_LINE='{"id":"00000000-0000-0000-0000-00000000E001","source_type":"account","source_id":"7d97a42e-3704-4a33-a61f-0e0a6b4d65d8","target_type":"node","target_id":"b52be17c-4ab7-4434-98ce-520f86290cf0","edge_kind":"reference","note":"faden","created_at":"2025-12-22T00:00:00Z"}'

# Pre-seed if missing
if [ ! -s .gewebe/in/demo.edges.jsonl ]; then
  echo "→ seeds: edges"
  cat > .gewebe/in/demo.edges.jsonl <<EOF
{"id":"00000000-0000-0000-0000-000000000101","source_type":"node","source_id":"00000000-0000-0000-0000-000000000001","target_type":"node","target_id":"00000000-0000-0000-0000-000000000002","edge_kind":"reference","note":"Kooperation Marktplatz ↔ Nachbarschaftshaus","created_at":"2025-01-01T12:00:00Z"}
{"id":"00000000-0000-0000-0000-000000000102","source_type":"node","source_id":"00000000-0000-0000-0000-000000000002","target_type":"node","target_id":"00000000-0000-0000-0000-000000000004","edge_kind":"reference","note":"Gemeinschaftsaktion Gartenpflege","created_at":"2025-01-01T12:00:00Z"}
{"id":"00000000-0000-0000-0000-000000000103","source_type":"node","source_id":"00000000-0000-0000-0000-000000000001","target_type":"node","target_id":"00000000-0000-0000-0000-000000000003","edge_kind":"reference","note":"Tauschbox liefert Material","created_at":"2025-01-01T12:00:00Z"}
{"id":"00000000-0000-0000-0000-000000000104","source_type":"node","source_id":"00000000-0000-0000-0000-000000000005","target_type":"node","target_id":"00000000-0000-0000-0000-000000000001","edge_kind":"reference","note":"Reparaturcafé hilft Marktplatz","created_at":"2025-01-01T12:00:00Z"}
EOF
fi

# Ensure correct edge exists (handles dedupe and target_id fix internally in function)
ensure_jsonl_line ".gewebe/in/demo.edges.jsonl" "$EDGE_ID" "$EDGE_LINE"

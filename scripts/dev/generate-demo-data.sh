#!/usr/bin/env bash
set -euo pipefail

# Erzeugt Demo-Daten falls nicht vorhanden.
mkdir -p .gewebe/in

# Accounts
ACCOUNT_ID="7d97a42e-3704-4a33-a61f-0e0a6b4d65d8"
ACCOUNT_JSON='{"id":"7d97a42e-3704-4a33-a61f-0e0a6b4d65d8","type":"garnrolle","title":"gewebespinnerAYE","summary":"Persönlicher Account (Garnrolle), am Wohnsitz verortet. Ursprung von Fäden ins Gewebe.","location":{"lat":53.5604148,"lon":10.0629844},"visibility":"public","tags":["account","garnrolle","wohnort"]}'

if [ -s .gewebe/in/demo.accounts.jsonl ]; then
  NEEDS_MIGRATION=0
  # Strict matching: look for the ID key structure to avoid false positives in summary/text
  # We escape quotes for grep: "id":"UUID"
  MATCH_PATTERN="\"id\":\"$ACCOUNT_ID\""

  EXISTING_LINE=$(grep -F "$MATCH_PATTERN" .gewebe/in/demo.accounts.jsonl || true)

  if [ -n "$EXISTING_LINE" ]; then
     # Deduplication Check: If ID appears more than once, force migration to cleanup
     COUNT=$(echo "$EXISTING_LINE" | wc -l)
     if [ "$COUNT" -gt 1 ]; then
        NEEDS_MIGRATION=1
     else
        # Check for location field
        if command -v jq >/dev/null 2>&1; then
          if echo "$EXISTING_LINE" | jq -e 'has("location") | not' >/dev/null 2>&1; then
            NEEDS_MIGRATION=1
          fi
        else
          # Fallback: simple grep for "location": pattern
          if ! echo "$EXISTING_LINE" | grep -q '"location"[[:space:]]*:'; then
            NEEDS_MIGRATION=1
          fi
        fi
     fi
  else
     # ID not present, simply needs adding
     :
  fi

  if [ "$NEEDS_MIGRATION" -eq 1 ]; then
    echo "→ migrating: fixing/deduping account $ACCOUNT_ID"
    # Atomic update: remove old (all occurrences), add new, move
    grep -vF "$MATCH_PATTERN" .gewebe/in/demo.accounts.jsonl > .gewebe/in/demo.accounts.jsonl.tmp || true
    echo "$ACCOUNT_JSON" >> .gewebe/in/demo.accounts.jsonl.tmp
    mv .gewebe/in/demo.accounts.jsonl.tmp .gewebe/in/demo.accounts.jsonl
  elif [ -z "$EXISTING_LINE" ]; then
    echo "→ updating: adding account $ACCOUNT_ID"
    echo "$ACCOUNT_JSON" >> .gewebe/in/demo.accounts.jsonl
  fi
else
  echo "→ seeds: accounts"
  echo "$ACCOUNT_JSON" > .gewebe/in/demo.accounts.jsonl
fi

# Nodes
# Define the correct new node line
NODE_LINE='{"id":"b52be17c-4ab7-4434-98ce-520f86290cf0","kind":"Knoten","title":"fairschenkbox","summary":"Öffentliche Fair-Schenk-Box","info":"Dies ist eine **Demo-Info** für den Test.","created_at":"2025-12-22T00:00:00Z","updated_at":"2025-12-22T00:00:00Z","location":{"lat":53.558894813662505,"lon":10.060228407382967}}'

if [ ! -s .gewebe/in/demo.nodes.jsonl ]; then
  echo "→ seeds: nodes"; cat > .gewebe/in/demo.nodes.jsonl <<EOF
{"id":"00000000-0000-0000-0000-000000000001","kind":"Ort","title":"Marktplatz Hamburg","created_at":"2025-01-01T12:00:00Z","updated_at":"2025-11-01T09:00:00Z","location":{"lon":9.9937,"lat":53.5511}}
{"id":"00000000-0000-0000-0000-000000000002","kind":"Initiative","title":"Nachbarschaftshaus","created_at":"2025-01-01T12:00:00Z","updated_at":"2025-11-02T12:15:00Z","location":{"lon":10.0002,"lat":53.5523}}
{"id":"00000000-0000-0000-0000-000000000003","kind":"Projekt","title":"Tauschbox Altona","created_at":"2025-01-01T12:00:00Z","updated_at":"2025-10-30T18:45:00Z","location":{"lon":9.9813,"lat":53.5456}}
{"id":"00000000-0000-0000-0000-000000000004","kind":"Ort","title":"Gemeinschaftsgarten","created_at":"2025-01-01T12:00:00Z","updated_at":"2025-11-05T10:00:00Z","location":{"lon":10.0184,"lat":53.5631}}
{"id":"00000000-0000-0000-0000-000000000005","kind":"Initiative","title":"Reparaturcafé","created_at":"2025-01-01T12:00:00Z","updated_at":"2025-11-03T16:20:00Z","location":{"lon":9.9708,"lat":53.5615}}
${NODE_LINE}
EOF
else
  # Migration: Remove legacy node with old ID if present
  if grep -q "00000000-0000-0000-0000-000000000006" .gewebe/in/demo.nodes.jsonl; then
     echo "→ migrating: removing stale node 0000...0006"
     # Use a temporary file to delete the line safely
     grep -v "00000000-0000-0000-0000-000000000006" .gewebe/in/demo.nodes.jsonl > .gewebe/in/demo.nodes.jsonl.tmp || true
     mv .gewebe/in/demo.nodes.jsonl.tmp .gewebe/in/demo.nodes.jsonl
  fi

  # Ensure correct node exists
  MATCH_PATTERN="\"id\":\"b52be17c-4ab7-4434-98ce-520f86290cf0\""
  if ! grep -Fq "$MATCH_PATTERN" .gewebe/in/demo.nodes.jsonl; then
     echo "→ updating: adding node b52be17c..."
     echo "${NODE_LINE}" >> .gewebe/in/demo.nodes.jsonl
  fi
fi

# Edges
EDGE_LINE='{"id":"00000000-0000-0000-0000-00000000E001","source_type":"account","source_id":"7d97a42e-3704-4a33-a61f-0e0a6b4d65d8","target_type":"node","target_id":"b52be17c-4ab7-4434-98ce-520f86290cf0","edge_kind":"reference","note":"faden","created_at":"2025-12-22T00:00:00Z"}'

if [ ! -s .gewebe/in/demo.edges.jsonl ]; then
  echo "→ seeds: edges"; cat > .gewebe/in/demo.edges.jsonl <<EOF
{"id":"00000000-0000-0000-0000-000000000101","source_type":"node","source_id":"00000000-0000-0000-0000-000000000001","target_type":"node","target_id":"00000000-0000-0000-0000-000000000002","edge_kind":"reference","note":"Kooperation Marktplatz ↔ Nachbarschaftshaus","created_at":"2025-01-01T12:00:00Z"}
{"id":"00000000-0000-0000-0000-000000000102","source_type":"node","source_id":"00000000-0000-0000-0000-000000000002","target_type":"node","target_id":"00000000-0000-0000-0000-000000000004","edge_kind":"reference","note":"Gemeinschaftsaktion Gartenpflege","created_at":"2025-01-01T12:00:00Z"}
{"id":"00000000-0000-0000-0000-000000000103","source_type":"node","source_id":"00000000-0000-0000-0000-000000000001","target_type":"node","target_id":"00000000-0000-0000-0000-000000000003","edge_kind":"reference","note":"Tauschbox liefert Material","created_at":"2025-01-01T12:00:00Z"}
{"id":"00000000-0000-0000-0000-000000000104","source_type":"node","source_id":"00000000-0000-0000-0000-000000000005","target_type":"node","target_id":"00000000-0000-0000-0000-000000000001","edge_kind":"reference","note":"Reparaturcafé hilft Marktplatz","created_at":"2025-01-01T12:00:00Z"}
${EDGE_LINE}
EOF
else
   # Migration: Check if edge exists but with wrong target (stale)
   # We define "wrong" as having the ID but NOT the new target ID on the same line.
   MATCH_PATTERN="\"id\":\"00000000-0000-0000-0000-00000000E001\""
   if grep -Fq "$MATCH_PATTERN" .gewebe/in/demo.edges.jsonl; then
      if ! grep -q "b52be17c-4ab7-4434-98ce-520f86290cf0" .gewebe/in/demo.edges.jsonl; then
          echo "→ migrating: removing stale edge E001 (wrong target)"
          grep -vF "$MATCH_PATTERN" .gewebe/in/demo.edges.jsonl > .gewebe/in/demo.edges.jsonl.tmp || true
          mv .gewebe/in/demo.edges.jsonl.tmp .gewebe/in/demo.edges.jsonl
      fi
   fi

   if ! grep -Fq "$MATCH_PATTERN" .gewebe/in/demo.edges.jsonl; then
     echo "→ updating: adding edge E001"
     echo "${EDGE_LINE}" >> .gewebe/in/demo.edges.jsonl
  fi
fi

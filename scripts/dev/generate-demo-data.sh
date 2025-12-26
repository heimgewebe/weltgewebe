#!/usr/bin/env bash
set -euo pipefail

# Erzeugt Demo-Daten falls nicht vorhanden.
mkdir -p .gewebe/in

# Accounts
test -s .gewebe/in/demo.accounts.jsonl || { echo "→ seeds: accounts"; cat > .gewebe/in/demo.accounts.jsonl <<-'JSONL'
{"id":"7d97a42e-3704-4a33-a61f-0e0a6b4d65d8","type":"garnrolle","title":"gewebespinnerAYE","summary":"Persönlicher Account (Garnrolle), am Wohnsitz verortet. Ursprung von Fäden ins Gewebe.","location":{"lat":53.5604148,"lon":10.0629844},"visibility":"public","tags":["account","garnrolle","wohnort"]}
JSONL
}

# Nodes (Append new node if file exists, or create full list if not)
if [ ! -s .gewebe/in/demo.nodes.jsonl ]; then
  echo "→ seeds: nodes"; cat > .gewebe/in/demo.nodes.jsonl <<-'JSONL'
{"id":"00000000-0000-0000-0000-000000000001","kind":"Ort","title":"Marktplatz Hamburg","created_at":"2025-01-01T12:00:00Z","updated_at":"2025-11-01T09:00:00Z","location":{"lon":9.9937,"lat":53.5511}}
{"id":"00000000-0000-0000-0000-000000000002","kind":"Initiative","title":"Nachbarschaftshaus","created_at":"2025-01-01T12:00:00Z","updated_at":"2025-11-02T12:15:00Z","location":{"lon":10.0002,"lat":53.5523}}
{"id":"00000000-0000-0000-0000-000000000003","kind":"Projekt","title":"Tauschbox Altona","created_at":"2025-01-01T12:00:00Z","updated_at":"2025-10-30T18:45:00Z","location":{"lon":9.9813,"lat":53.5456}}
{"id":"00000000-0000-0000-0000-000000000004","kind":"Ort","title":"Gemeinschaftsgarten","created_at":"2025-01-01T12:00:00Z","updated_at":"2025-11-05T10:00:00Z","location":{"lon":10.0184,"lat":53.5631}}
{"id":"00000000-0000-0000-0000-000000000005","kind":"Initiative","title":"Reparaturcafé","created_at":"2025-01-01T12:00:00Z","updated_at":"2025-11-03T16:20:00Z","location":{"lon":9.9708,"lat":53.5615}}
{"id":"00000000-0000-0000-0000-000000000006","kind":"Knoten","title":"fairschenkbox","summary":"Fairschenken-Box","created_at":"2025-12-22T00:00:00Z","updated_at":"2025-12-22T00:00:00Z","location":{"lat":53.558894813662505,"lon":10.060228407382967}}
JSONL
else
  # Ensure fairschenkbox exists if file already exists but might be missing it
  if ! grep -q "00000000-0000-0000-0000-000000000006" .gewebe/in/demo.nodes.jsonl; then
     echo '{"id":"00000000-0000-0000-0000-000000000006","kind":"Knoten","title":"fairschenkbox","summary":"Fairschenken-Box","created_at":"2025-12-22T00:00:00Z","updated_at":"2025-12-22T00:00:00Z","location":{"lat":53.558894813662505,"lon":10.060228407382967}}' >> .gewebe/in/demo.nodes.jsonl
  fi
fi

# Edges
if [ ! -s .gewebe/in/demo.edges.jsonl ]; then
  echo "→ seeds: edges"; cat > .gewebe/in/demo.edges.jsonl <<-'JSONL'
{"id":"00000000-0000-0000-0000-000000000101","source_type":"node","source_id":"00000000-0000-0000-0000-000000000001","target_type":"node","target_id":"00000000-0000-0000-0000-000000000002","edge_kind":"reference","note":"Kooperation Marktplatz ↔ Nachbarschaftshaus","created_at":"2025-01-01T12:00:00Z"}
{"id":"00000000-0000-0000-0000-000000000102","source_type":"node","source_id":"00000000-0000-0000-0000-000000000002","target_type":"node","target_id":"00000000-0000-0000-0000-000000000004","edge_kind":"reference","note":"Gemeinschaftsaktion Gartenpflege","created_at":"2025-01-01T12:00:00Z"}
{"id":"00000000-0000-0000-0000-000000000103","source_type":"node","source_id":"00000000-0000-0000-0000-000000000001","target_type":"node","target_id":"00000000-0000-0000-0000-000000000003","edge_kind":"reference","note":"Tauschbox liefert Material","created_at":"2025-01-01T12:00:00Z"}
{"id":"00000000-0000-0000-0000-000000000104","source_type":"node","source_id":"00000000-0000-0000-0000-000000000005","target_type":"node","target_id":"00000000-0000-0000-0000-000000000001","edge_kind":"reference","note":"Reparaturcafé hilft Marktplatz","created_at":"2025-01-01T12:00:00Z"}
{"id":"00000000-0000-0000-0000-00000000E001","source_type":"account","source_id":"7d97a42e-3704-4a33-a61f-0e0a6b4d65d8","target_type":"node","target_id":"00000000-0000-0000-0000-000000000006","edge_kind":"reference","note":"faden","created_at":"2025-12-22T00:00:00Z"}
JSONL
else
   if ! grep -q "00000000-0000-0000-0000-00000000E001" .gewebe/in/demo.edges.jsonl; then
     echo '{"id":"00000000-0000-0000-0000-00000000E001","source_type":"account","source_id":"7d97a42e-3704-4a33-a61f-0e0a6b4d65d8","target_type":"node","target_id":"00000000-0000-0000-0000-000000000006","edge_kind":"reference","note":"faden","created_at":"2025-12-22T00:00:00Z"}' >> .gewebe/in/demo.edges.jsonl
   fi
fi

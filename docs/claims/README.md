---
id: docs.claims.readme
title: Claim-Registry
doc_type: reference
status: active
summary: Minimal machine-readable Claim-Evidence registry for AGENT-SAFE-003.
relations:
  - type: relates_to
    target: docs/blueprints/blueprint-agent-safety-control-layer.md
  - type: relates_to
    target: docs/tasks/index.json
  - type: relates_to
    target: scripts/docmeta/validate_claim_registry.py
---

# Claim-Registry

## Zweck

Die Claim-Registry bindet zentrale Claims an konkrete Evidence-Pfade und
Validierungskommandos. Sie ist maschinenlesbar und deterministisch pruefbar.

Die Registry entscheidet nicht final ueber Wahrheit oder Produktstatus.
Sie liefert nur eine pruefbare Belegstruktur fuer Review, CI und Task-Control.

## Verhaeltnis zu anderen Flaechen

- Roadmap und Task-Control bleiben die Arbeitssteuerung.
- Agent-Readiness bleibt ein diagnostischer Statusreport.
- CI und menschliches Review treffen die finalen Freigabeentscheidungen.

## Datei und Format

Die Registry liegt unter `docs/claims/registry.yml`.

Wegen fehlender Projektabhaengigkeit fuer YAML-Parsing wird ein strenger
JSON-kompatibler YAML-Subset genutzt. Das heisst: Die Datei hat `.yml`,
enthaelt aber JSON-Struktur, damit die Validierung ohne externe Dependency
stabil bleibt.

## Statuswerte

Erlaubte Claim-Statuswerte:

- `proposed`
- `established`
- `superseded`
- `rejected`

Nicht erlaubt sind Done-Semantiken wie `done`, `verified` oder `proven`.

## Evidence-Kinds

Typische `kind`-Werte:

- `implementation`
- `test`
- `ci`
- `documentation`
- `generated-report`
- `registry`

## Evidence-Pfade

- Evidence-`path` muss relativ zum Repository-Root sein.
- Absolute Pfade (zum Beispiel `/etc/hosts`) sind unzulaessig.
- Parent-Traversal (zum Beispiel `../foo`) ist unzulaessig.
- Bei `status: established` muessen repo-interne Evidence-Pfade zusaetzlich
  existieren.

## Nicht-Ziele dieses Slices

Dieser Slice fuehrt nicht ein:

- Agent-Contract-Suite
- Handoff-Validator
- Non-Ideal-Guard
- Dry-Run-Runner
- Write-Mode
- Blocking-CI
- Vollstaendige Proof-Engine

AGENT-SAFE-004 bleibt offen.

## Freshness Registry (Lenskit Bridge)

`docs/doc-freshness-registry.yml` ist der Lenskit-kompatible Bridge-Contract.
Er exponiert die Claim-Evidence-Bindung aus `docs/claims/registry.yml` im
Format `lenskit.doc_freshness_registry` v1.0.

`docs/claims/registry.yml` bleibt die kanonische Claim-Quelle.
Die Bridge beweist keine Claims; sie macht die Claim-Evidence-Bindung fuer
Lenskit sichtbar.

`last_verified` belegt nur die Bridge-Validierung gegen die Claim-Registry
und repo-lokale Evidence-Pfade. Es beweist nicht, dass ein Claim wahr ist.

Evidence-Kinds werden explizit gemappt:

- `implementation`, `documentation`, `ci`, `generated-report`, `registry` -> Lenskit `file`
- `test` -> Lenskit `test`

- Validierung: `python3 scripts/docmeta/validate_doc_freshness_registry.py`
- Generierte Uebersicht (report-only):
  - `docs/_generated/claim-evidence-map.md`

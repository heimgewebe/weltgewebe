---
id: docs.security.agent-write-scope-baseline
title: "Agent Write Scope Baseline"
doc_type: security
status: active
summary: >
  Definiert die erlaubten Schreibbereiche und Verbotspfade für agentische Änderungen
  sowie die Fehlercodes des Safety-Preflight Guards (AGENT-SAFE-001).
relations:
  - type: relates_to
    target: agent-policy.yaml
  - type: relates_to
    target: AGENTS.md
  - type: relates_to
    target: docs/blueprints/blueprint-agent-safety-control-layer.md
  - type: relates_to
    target: docs/tasks/board.md
---

# Agent Write Scope Baseline

> Sicherheits-Basisdokument für agentische Schreiboperationen.
> Kanonisch für den Safety-Preflight Guard (`AGENT-SAFE-001`).

## Zweck

Dieses Dokument legt fest, welche Pfade Agenten beschreiben dürfen, welche Pfade
verboten sind und welche Fehlercodes der Safety-Preflight Guard (`scripts/agent/check_agent_preflight.py`)
erzeugt, wenn Grenzen verletzt werden.

Die Guard-Implementierung ist deterministisch und report-only (Stufe 1 gemaess Blueprint-Ratchet).
Kein automatisches Blockieren und kein Write-Mode. Claim-Registry,
Agent-Contracts, Handoff-Validierung und Dry-Run-Runner sind separate
Agent-Safety-Slices und ersetzen diesen Preflight-Guard nicht.

## Erlaubte Schreibpfade

Agenten dürfen nur Pfade beschreiben, die explizit als `allowed_paths` in der Task-Datei
deklariert sind.

## Verbotene Pfade (immer)

| Pfad | Begründung |
|---|---|
| `docs/_generated/*` | Automatisch generierte Diagnoseartefakte; niemals direkt editieren |
| `secrets/` | Credentials und Geheimnisse |
| `snapshots/` | Deploy-Snapshots; kein direkter Agent-Zugriff |

Quelle: `agent-policy.yaml` → `forbidden_write_paths`

## Pfadgruppen mit erhöhtem Anforderungsniveau

| Pfadgruppe | Anforderung |
|---|---|
| `.github/workflows/` | `task_type: ci_change` erforderlich |
| `infra/` | `task_type: infra_change` und `expected_evidence` oder `proof_ref` erforderlich |
| `infra/compose/` | Zusätzlich Deploy-Drift-Guard-Konvention beachten (siehe `deploy-drift-guard.yml`) |
| `apps/` | Target-Proof erforderlich (siehe `agent-policy.yaml`) |
| `src/` | Target-Proof erforderlich |
| `deployment/` | Menschliche Review + Target-Proof erforderlich |
| `security/` | Menschliche Review erforderlich |

Quelle: `agent-policy.yaml` → `requires_target_proof_for`, `human_review_required_for`

## Pflichtfelder in Task-Metadaten

Jede agentische Änderung muss vor der Ausführung folgende Felder in der Task-Datei
aufweisen:

| Feld | Beschreibung |
|---|---|
| `task_id` | Eindeutige Task-ID (Format: `^[A-Z]+(-[A-Z]+)*-[0-9]{3}$`) |
| `task_type` | Art der Änderung (z. B. `doc_change`, `ci_change`, `infra_change`) |
| `allowed_paths` | Liste erlaubter Schreibpfade |
| `validation` oder `validation_commands` | Ausführbare Prüfschritte |
| `expected_evidence` oder `evidence` | Erwartete Belege für die Änderung |

## Fehlercodes

Der Preflight Guard erzeugt maschinenlesbare Fehlercodes:

| Code | Beschreibung |
|---|---|
| `MISSING_TASK_ID` | `task_id` fehlt/ist leer oder entspricht nicht dem Format `^[A-Z]+(-[A-Z]+)*-[0-9]{3}$` |
| `MISSING_TASK_TYPE` | `task_type` fehlt oder ist leer |
| `MISSING_ALLOWED_PATHS` | `allowed_paths` fehlt oder ist leer |
| `MISSING_VALIDATION` | Weder `validation` noch `validation_commands` vorhanden |
| `MISSING_EXPECTED_EVIDENCE` | Weder `expected_evidence` noch `evidence` vorhanden |
| `GENERATED_DIRECT_EDIT` | Direkte Änderung an `docs/_generated/*` erkannt |
| `ROADMAP_DONE_WITHOUT_CLAIM` | Roadmap-Haken `[x]` oder Done-Status ohne Claim-/Proof-Bezug |
| `STATUS_DONE_WITHOUT_PROOF` | Status auf `done` gesetzt ohne `proof_ref` oder Claim |
| `PATH_OUT_OF_SCOPE` | Geänderter Pfad liegt außerhalb von `allowed_paths` |
| `WORKFLOW_CHANGE_WITHOUT_TASK_TYPE` | Änderung an `.github/workflows/` ohne `task_type: ci_change` |
| `INFRA_CHANGE_WITHOUT_PROOF` | Änderung an Infra-Pfaden ohne passenden Task-Typ und Proof-Erwartung |
| `DELETE_WITHOUT_PERMISSION` | Dateilöschung ohne explizites `delete_allowed: true` |

## Modus: Report-Only (Stufe 1)

Der Guard befindet sich in Stufe 1 (report-only / warn).
Er erkennt und meldet Verletzungen, blockiert aber keinen PR automatisch.

Stufe 3 (blocking) bleibt deaktiviert, bis ein separater Ratchet-Slice die
Claim-, Contract-, Handoff- und Runner-Belege in eine blockierende Policy
ueberfuehrt.

### Dateibasiertes Scanning

Der Guard (`AGENT-SAFE-001`) scannt vollständige Dateien, nicht einzelne Diff-Hunks.
Geänderte Dateien werden komplett gelesen. Dadurch können bestehende `[x]`-Einträge
oder `status: done`-Felder in noch nicht bereinigten Dateien als Befund erscheinen,
auch wenn der aktuelle PR diese Zeilen nicht eingeführt hat (Altbefunde).

Das ist der Grund, warum Blocking explizit nicht aktiviert ist.
Diff-hunk-basiertes Scanning ist für einen späteren Slice vorgesehen.

## Residual Gaps

Folgende Punkte sind bekannt und werden in späteren Slices adressiert:

| Gap | Slice |
|---|---|
| Blocking-Modus (Stufe 3) ist noch nicht aktiviert | Spaeterer Ratchet-Slice |
| Run-Evidence und unabhaengige Run-Attestierung fehlen noch | Folge-Slice nach `AGENT-SAFE-006` |
| Write-Mode nicht implementiert | Spaeterer gated Write-Mode-Slice |

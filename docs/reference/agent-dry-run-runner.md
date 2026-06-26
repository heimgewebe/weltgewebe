---
id: docs.reference.agent-dry-run-runner
title: "Agent Dry-Run Runner"
doc_type: reference
status: active
summary: "Read-only Runner fuer Agent-Task-Contracts mit funktionalem Readiness-Smoke."
relations:
  - type: relates_to
    target: docs/blueprints/blueprint-agent-safety-control-layer.md
  - type: relates_to
    target: contracts/agent/task.schema.json
  - type: relates_to
    target: contracts/agent/handoff.schema.json
  - type: relates_to
    target: scripts/agent/run_task.py
  - type: relates_to
    target: scripts/docmeta/generate_agent_readiness.py
---

# Agent Dry-Run Runner

## Zweck

`scripts/agent/run_task.py` fuehrt Agent-Task-Contracts im read-only Dry-Run
aus. Der Runner prueft den Task bis unmittelbar vor die Schreib- und
Ausfuehrungsgrenze, bilanziert Claims, Evidence und Validierungen und erzeugt
ein gueltiges `incomplete`-Handoff.

Der Runner fuehrt keine Task-Kommandos aus und aendert keine Repository-Dateien.

## CLI

```bash
python3 -m scripts.agent.run_task \
  --dry-run \
  tests/fixtures/agent/valid-doc-drift-task.json
```

`--dry-run` ist optional, weil Dry Run der einzige Modus ist. `--write` ist kein
gueltiges Flag.

Mit externem Output:

```bash
python3 -m scripts.agent.run_task \
  --dry-run \
  --output-dir /tmp/weltgewebe-agent-run \
  tests/fixtures/agent/valid-doc-drift-task.json
```

## Exit-Codes

| Code | Bedeutung |
|---:|---|
| 0 | Gueltiger Dry Run wurde geplant und bilanziert |
| 1 | Task ist syntaktisch lesbar, wird aber durch Schema- oder Non-Ideal-Regeln blockiert |
| 2 | Aufruf-, JSON-, Pfad-, Git-, Contract-, Output- oder interner Betriebsfehler |

Betriebsfehler werden auf stderr als JSON mit `code` und `message` ausgegeben.
Regulaere Ergebnisse erscheinen als genau ein JSON-Dokument auf stdout.

## Stage-Modell

Der Runner nutzt diese feste Reihenfolge:

```text
load_task
validate_task_schema
load_claim_registry
run_non_ideal_guard
resolve_source_revision
capture_repository_state
prepare_execution_plan
account_expected_evidence
build_handoff
validate_handoff
verify_repository_unchanged
emit_result
```

Bei fruehem Blockieren bleiben spaetere Stufen `not_run`.

## Task-Laden

Die Task-Datei muss repository-relativ sein. Absolute Pfade,
Parent-Traversal und Symlinks aus dem Repository werden abgewiesen.

Der Runner liest die Task-Datei genau als Bytes, bildet daraus den SHA-256,
dekodiert danach strikt als UTF-8 und laedt den Inhalt mit dem vorhandenen
Strict-JSON-Parser. Duplicate Keys, `NaN`, `Infinity`, `-Infinity`, malformed
JSON und ungueltiges UTF-8 werden abgewiesen.

## Raw-Byte-Digest

`task_contract_sha256` ist:

```python
hashlib.sha256(raw_task).hexdigest()
```

Es gibt keine Normalisierung, keine erneute Serialisierung und keine
Zeilenendenkonvertierung.

## Source Revision

Die CLI ermittelt die Revision mit:

```bash
git rev-parse --verify HEAD
```

Der Core akzeptiert die Revision als explizite Abhaengigkeit, damit Tests ohne
Fake-CLI-Flag deterministisch bleiben. In diesem Slice wird nur der lokale
aktuelle `HEAD` syntaktisch gebunden. Es wird keine Remote-Erreichbarkeit,
Main-Ancestry oder Diff-Bindung behauptet.

## Execution-Plan-v1

Der aktuelle Task-Contract beschreibt keine konkreten Aenderungen. Deshalb ist
`execution_plan` nur eine Scope- und Berechtigungsbilanz:

```json
{
  "allowed_paths": [],
  "forbidden_paths": [],
  "delete_allowed": false,
  "planned_changed_paths": [],
  "planned_deleted_paths": []
}
```

Der Plan enthaelt keinen Patch, keinen Dateiinhaltsentwurf, keine automatisch
gewaehlten Zieldateien und keine Shell-Kommandos.

## Handoff-Semantik

Ein erfolgreicher Dry Run erzeugt ein Handoff mit:

- `outcome: incomplete`
- `changed_paths: []`
- `deleted_paths: []`
- `claims_addressed`: alle Task-Claims
- `evidence_produced: []`
- `missing_evidence`: alle `expected_evidence`
- `validation_results`: alle Task-Kommandos mit `not_run`
- `residual_gaps`: keine Task-Kommandos ausgefuehrt, keine Repository-Aenderung angewendet

`claims_addressed` bedeutet bilanziert, nicht bewiesen. `missing_evidence`
bedeutet in diesem Run nicht erzeugt oder bestaetigt, nicht zwingend auf der
Festplatte abwesend. `not_run` bedeutet bewusst nicht ausgefuehrt.

## Evidence-Bilanz

Jede erwartete Evidence muss entweder produziert oder als fehlend bilanziert
sein. Im Runner-v1 wird keine Evidence produziert; daher wird jede erwartete
Evidence unter `missing_evidence` gefuehrt.

## Output-Vertrag

Ohne `--output-dir` schreibt der Runner nichts und gibt das vollstaendige
Run-Result inklusive Handoff auf stdout aus.

Mit `--output-dir` erzeugt der Runner ausserhalb des Repositorys genau:

```text
handoff.json
run-result.json
```

Die Inhalte enthalten keine temp-spezifischen absoluten Output-Pfade.

## Externe Output-Verzeichnisregeln

Das Output-Ziel muss ausserhalb des Repository-Roots liegen, neu oder leer sein
und darf weder selbst ein Symlink sein noch ueber Symlink-Eltern aufgeloest
werden. Repository-Root, Unterverzeichnisse des Repositories, vorhandene
Zieldateien, nicht leere Verzeichnisse und nicht aufloesbare Elternstrukturen
werden abgewiesen.

## No-Write-Invariante

Der Runner erfasst vor und nach der planenden Verarbeitung:

```bash
git status --porcelain=v1 --untracked-files=all
```

Die Byteausgaben muessen identisch bleiben. Ein bereits schmutziger
Ausgangszustand ist erlaubt, solange er unveraendert bleibt.

Tests und CI vergleichen den Git-Status zusaetzlich von aussen, damit der
Runner nicht alleiniger Zeuge seiner No-Write-Eigenschaft ist.

## Readiness-Smoke

`scripts/docmeta/generate_agent_readiness.py` markiert `dry_run_runner` nur als
`pass`, wenn ein funktionaler Smoke erfolgreich ist:

```bash
python3 -m scripts.agent.run_task \
  --dry-run \
  tests/fixtures/agent/valid-doc-drift-task.json
```

Der Smoke prueft Exit-Code, Strict-JSON-Output, `mode`, `status`,
`repository_unchanged`, Handoff-Semantik, `not_run`-Validierungen,
Handoff-Validator und unveraenderten Git-Status.

## Trust Boundary

Ein erfolgreicher Dry Run belegt read-only Contract- und Planungsfaehigkeit. Er
belegt keine fachliche Task-Erledigung, keine Ausfuehrung der
Validierungskommandos, keine Run-Attestierung, keine Producer-Authentizitaet,
keinen Patch und keine Merge-Reife.

## Non-Goals

Nicht Teil dieses Slices:

- Command-Schema
- rekursive Kontextakquise
- Dateiinhalte als Agent-Kontext
- Patch-Erzeugung
- Task-Command-Ausfuehrung
- persistentes Run-Archiv
- Run-Evidence
- Git-Ancestry- oder Diff-Bindung
- Write Mode
- autonome PR- oder Merge-Ausfuehrung

## Folge-Slices

Folgearbeiten koennen Run-Evidence, persistente Run-Artefakte,
Command-Ausfuehrung, Patch-Planung und spaeter gated Write Mode entwerfen. Diese
Funktionen brauchen eigene Contracts und duerfen nicht aus diesem Runner-v1
abgeleitet werden.

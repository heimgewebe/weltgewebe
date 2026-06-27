---
id: docs.reference.agent-run-evidence-lite
title: "Agent Run Evidence Lite"
doc_type: reference
status: active
summary: "Minimaler, atomar publizierter Evidenzsatz fuer erfolgreich geplante Agent-Dry-Runs."
relations:
  - type: relates_to
    target: docs/blueprints/blueprint-agent-safety-control-layer.md
  - type: relates_to
    target: docs/reference/agent-dry-run-runner.md
  - type: relates_to
    target: contracts/agent/validation.schema.json
  - type: relates_to
    target: contracts/agent/run-result.schema.json
  - type: relates_to
    target: scripts/agent/run_task.py
---

# Agent Run Evidence Lite

## Zweck

Run Evidence Lite macht einen **erfolgreich geplanten** Dry-Run nachtraeglich
pruefbar. Der Runner fuehrt weiterhin keine Task-Kommandos aus und veraendert
keine Task-Zieldateien. Seine einzige neue persistente Wirkung ist ein lokales,
von Git ignoriertes Evidenzbuendel.

Standardpfad:

```text
artifacts/agent-runs/<run-id>/
├── task.yml
├── handoff.json
├── validation.json
└── run-result.json
```

`task.yml` enthaelt die exakten Eingabebytes. Die aktuellen Task-Contracts sind
striktes JSON; JSON ist zugleich eine gueltige YAML-1.2-Teilmenge. Die Endung
`.yml` bezeichnet hier deshalb die kanonische Bundle-Rolle, nicht eine
Neuformatierung der Eingabe.

## Run-ID

Das Format ist:

```text
RUN-YYYYMMDDTHHMMSSZ-<12 hex characters>
```

Der Zeitanteil ist UTC. Der Hex-Suffix wird kryptografisch zufaellig erzeugt.
Die Run-ID ist absichtlich eindeutig und **nicht deterministisch**. Die
Task-Bindung erfolgt separat ueber `task_contract_sha256`.

## Artefaktbindung

`run-result.json` verwendet zwei bewusst getrennte Aussagen:
`status = planned` bedeutet, dass der read-only Plan erfolgreich erstellt wurde;
`outcome = incomplete` uebernimmt die Handoff-Wahrheit, dass keine
Task-Ausfuehrung und keine erwartete Task-Evidence abgeschlossen wurde.

`run-result.json` bindet mindestens:

- `run_id`, Task-ID und Dry-Run-Modus,
- `started_at` und `completed_at` als UTC-Zeitpunkte mit Mikrosekunden,
- `status: planned` fuer den erfolgreich erstellten Plan und
  `outcome: incomplete` fuer das bewusst nicht ausgefuehrte Handoff,
- den SHA-256 der exakten Task-Eingabebytes,
- den beobachteten Git-`HEAD`,
- einen SHA-256-Fingerabdruck des Git-sichtbaren Repositoryzustands,
- relative Artefaktpfade und SHA-256-Werte fuer `task.yml`, `handoff.json` und
  `validation.json`,
- die weiterhin offenen Grenzen des Lite-Slices.

`validation.json` bezeichnet ausschliesslich die vor der Ausfuehrungsgrenze
geprueften Contracts und Guards. Die im Task verlangten
`validation_commands` bleiben im Handoff weiterhin `not_run`.

`run-result.json` kann seinen eigenen endgueltigen Hash nicht ohne
Selbstreferenz enthalten. Es fuehrt deshalb fuer sich selbst nur den relativen
Pfad. Eine externe Manifest- oder Attestierungsschicht bleibt Folgearbeit.

## Publikationsverfahren

Der Runner schreibt alle vier Dateien zunaechst in ein zufaellig benanntes
Staging-Verzeichnis unter demselben Elternverzeichnis. Er validiert die beiden
neuen JSON-Artefakte gegen ihre Contracts und prueft zusaetzlich die
felduebergreifenden Bindungen zwischen Task, Handoff, Validation und Run Result.
Unmittelbar vor der Publikation werden Git-`HEAD` und Repository-Fingerabdruck
erneut geprueft. Erst danach wird das vollstaendige Staging-Verzeichnis mit
`renameat2(RENAME_NOREPLACE)` auf das Ziel umbenannt. Fehlt diese
Linux-Faehigkeit, schlaegt die Publikation geschlossen fehl.

Alle Pfadoperationen nach der Vorpruefung sind an bereits geoeffnete
Verzeichnis-Deskriptoren gebunden. `O_NOFOLLOW` verhindert, dass ein nachtraeglich
ausgetauschter Symlink-Elternpfad das Bundle an einen anderen Ort umlenkt. Ein
bestehendes Ziel wird atomar nicht ersetzt. Parent-Traversal, Pfad-Ausbruch und
ein benutzerdefiniertes Ziel innerhalb des Repositorys werden abgewiesen.
Bundle-Dateien werden mit Modus `0600` erzeugt. Bei einem Fehler vor der
Umbenennung bleibt kein sichtbares Zielbuendel zurueck.

Nach der Umbenennung ist das Bundle logisch vollstaendig und sichtbar. Schlaegt
die anschliessende Synchronisierung des Elternverzeichnisses fehl, wird es nicht
als vermeintlich ungueltiges Bundle entfernt. Stattdessen meldet der Runner
`OUTPUT_DURABILITY_UNCONFIRMED` und weist ausdruecklich darauf hin, dass das
Bundle publiziert wurde, seine Crash-Dauerhaftigkeit aber nicht bestaetigt ist.

## CLI

Standardmaessig wird Evidence persistiert:

```bash
python3 -m scripts.agent.run_task \
  --dry-run \
  tests/fixtures/agent/valid-doc-drift-task.json
```

Nur stdout, ohne Persistenz:

```bash
python3 -m scripts.agent.run_task \
  --dry-run \
  --no-persist \
  tests/fixtures/agent/valid-doc-drift-task.json
```

Explizites einzelnes Ziel ausserhalb des Repositorys:

```bash
python3 -m scripts.agent.run_task \
  --dry-run \
  --output-dir /tmp/weltgewebe-agent-run \
  tests/fixtures/agent/valid-doc-drift-task.json
```

`--no-persist` und `--output-dir` sind gegenseitig ausgeschlossen.

## Bewusste Grenzen

Dieser Slice persistiert nur Runs mit dem Status `planned`. Schema-blockierte,
Non-Ideal-blockierte und betriebsfehlerhafte Runs bleiben strukturierte
stdout-/stderr-Ergebnisse. Das ist eine ausdrueckliche Restluecke, keine
vollstaendige Run-Attestierung.

Run Evidence Lite beweist insbesondere nicht:

- dass Task-Kommandos ausgefuehrt wurden,
- dass ein Patch angewendet oder getestet wurde,
- dass Write Mode freigegeben ist,
- dass CI oder eine vertrauenswuerdige externe Instanz attestiert hat,
- dass ein Pull Request mergebar ist.

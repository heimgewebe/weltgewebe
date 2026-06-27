---
id: docs.reference.generated-artifact-control
title: "Generated Artifact Control"
doc_type: reference
status: active
summary: "Maschinenlesbarer Minimalvertrag für zwei generierte Diagnoseartefakte und den kuratierten Task-Index."
relations:
  - type: relates_to
    target: docs/blueprints/blueprint-agent-safety-control-layer.md
---

# Generated Artifact Control

## Zweck

`.wgx/generated-artifacts.yml` beschreibt den ersten blockierenden
Kontrollumfang für besonders sensible Dokumentationsartefakte. Der Vertrag
benennt für jedes Artefakt seine Rolle, Kanonizität, Quellen sowie die
zulässigen Generator- und Prüfkommandos.

Der Kontrollvertrag macht abgeleitete Dateien nicht zur Wahrheit. Er stellt nur
sicher, dass ihre Herkunft und ihre Driftprüfung maschinenlesbar und
reproduzierbar sind.

## Minimaler Umfang

| Pfad | Art | Kanonizität | Kontrolle |
|---|---|---|---|
| `docs/_generated/agent-readiness.md` | generated | derived | Generator und schreibfreier `--check` |
| `docs/_generated/claim-evidence-map.md` | generated | derived | Generator und schreibfreier `--check` |
| `docs/tasks/index.json` | curated_index | canonical | Schema- und Cross-Artifact-Driftprüfung |

Der kontrollierte Claim-Pfad ist
`docs/_generated/claim-evidence-map.md`. Ein JSON-Begleitartefakt gehört nicht
zum Minimalumfang dieses Slices.

## Generated und Curated Index

Ein `generated`-Artefakt wird vollständig aus deklarierten Quellen erzeugt. Es
muss einen repository-eigenen Generator und mindestens einen schreibfreien
Check besitzen. Direkte Inhaltsänderungen scheitern, sobald der Check den
committeten Inhalt mit der deterministisch berechneten Ausgabe vergleicht.

`docs/tasks/index.json` ist dagegen kein Generator-Output. Es ist die
maschinenlesbare, kuratierte Task-Control-Quelle. Deshalb behauptet das Manifest
keinen erfundenen Generator. Die Kontrolle besteht aus Schema-Validierung und
dem vorhandenen Driftvergleich mit `docs/tasks/board.md` und
`docs/reports/optimierungsstatus.json`.

## Ausführung

Nur die Manifeststruktur prüfen:

```bash
python3 -m scripts.docmeta.validate_generated_artifacts
```

Struktur und alle blockierenden Artefaktchecks prüfen:

```bash
python3 -m scripts.docmeta.validate_generated_artifacts --check
```

Der zweite Befehl wird durch `scripts/docmeta/generated-files-guard.sh` und
damit über `make validate-guards` ausgeführt.

## Fail-closed-Regeln

Der Validator blockiert unter anderem:

- fehlende oder doppelte kritische Artefakte,
- unbekannte Manifestfelder,
- absolute Pfade, Parent-Traversal und Symlinks,
- fehlende Quellen oder repository-fremde Prüfkommandos,
- Generated-Artefakte ohne `derived`-Kanonizität,
- einen fälschlich deklarierten Generator für den kuratierten Task-Index,
- fehlende `commit_required`- oder `blocking`-Flags,
- Drift eines registrierten Artefakts.

## Grenzen

Der Kontrollvertrag beweist weder fachliche Richtigkeit noch Vollständigkeit
der generierten Inhalte. Er attestiert keine Claims und ersetzt keine Reviews.
Eine spätere Vollausbaustufe kann weitere Dateien aufnehmen; eine Erweiterung
des Minimalumfangs ist bis dahin absichtlich blockiert.

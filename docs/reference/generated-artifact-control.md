---
id: docs.reference.generated-artifact-control
title: "Generated Artifact Control"
doc_type: reference
status: active
summary: "Maschinenlesbarer Kontrollvertrag für alle docs/_generated/*-Diagnosen und den kuratierten Task-Index."
relations:
  - type: relates_to
    target: docs/blueprints/blueprint-agent-safety-control-layer.md
---

# Generated Artifact Control

## Zweck

`.wgx/generated-artifacts.yml` beschreibt den blockierenden
Kontrollumfang für generierte Dokumentationsdiagnosen und den kuratierten Task-Index. Der Vertrag
benennt für jedes Artefakt seine Rolle, Kanonizität, Quellen sowie die
zulässigen Generator- und Prüfkommandos.

Der Kontrollvertrag macht abgeleitete Dateien nicht zur Wahrheit. Er stellt nur
sicher, dass ihre Herkunft und ihre Kontrollfläche maschinenlesbar und
reproduzierbar sind.

## Kontrollumfang

Der Vollausbau umfasst alle aktuell getrackten Dateien unter
`docs/_generated/*.md` sowie `docs/tasks/index.json`.

Die erwartete `docs/_generated/*`-Oberfläche wird nicht mehr in
`scripts/docmeta/generated-files-guard.sh` dupliziert. Der Validator gleicht
stattdessen drei Flächen ab:

1. reale Dateien in `docs/_generated/*.md`,
2. Einträge in `.wgx/generated-artifacts.yml`,
3. `repo.meta.yaml.generated_artifacts`.

Damit entsteht eine einzige prüfbare Manifestfläche; `repo.meta.yaml` bleibt
weiter sichtbar, darf aber nicht still davon abweichen.

## Generated und Curated Index

Ein `generated`-Artefakt wird aus deklarierten Quellen erzeugt. Es muss einen
repository-eigenen Generator besitzen. Wo der Generator einen schreibfreien
`--check` anbietet, nutzt das Manifest diesen direkten Driftcheck. Ältere
Generatoren ohne schreibfreien Einzelcheck bleiben trotzdem kontrolliert:
Manifest-Coverage, `repo.meta.yaml`-Abgleich, Quellenvalidierung,
Generator-Whitelist, Marker- und Frontmatter-Prüfung laufen blockierend.

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

- fehlende oder doppelte Artefakte,
- reale `docs/_generated/*.md`-Dateien ohne Manifest-Eintrag,
- Manifest-Einträge, die nicht zu `repo.meta.yaml.generated_artifacts` passen,
- unbekannte Manifestfelder,
- absolute Pfade, Parent-Traversal und Symlinks,
- fehlende Quellen oder repository-fremde Prüfkommandos,
- nicht geprüfte Shell-Kommandos außerhalb `scripts/docmeta/generate-*.sh`,
- Generated-Artefakte ohne `derived`-Kanonizität,
- einen fälschlich deklarierten Generator für den kuratierten Task-Index,
- fehlende `commit_required`- oder `blocking`-Flags,
- Drift eines registrierten Artefakts.

## Grenzen

Der Kontrollvertrag beweist weder fachliche Richtigkeit noch Vollständigkeit der
generierten Inhalte. Er attestiert keine Claims und ersetzt keine Reviews. Für
Generatoren ohne schreibfreien Einzelcheck beweist der Vertrag zunächst die
registrierte Kontrollfläche, nicht die inhaltliche Deterministik jedes einzelnen
Outputs.

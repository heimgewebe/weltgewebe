# Bash-Tooling-Richtlinien

Diese Richtlinien beschreiben, wie wir Shell-Skripte im Projekt entwickeln, prüfen und ausführen.

## Ziele

- Einheitliche Formatierung der Skripte.
- Automatisierte Qualitätssicherung mit statischer Analyse.
- Gute Developer Experience für wiederkehrende Aufgaben.

## Kernwerkzeuge

### shfmt

- Formatierung gemäß POSIX-kompatiblen Standards.
- Nutze `shfmt -w` für automatische Formatierung.
- Setze `shfmt -d` in CI-Checks ein, um Formatierungsabweichungen aufzuzeigen.

### ShellCheck

- Analysiert Skripte auf Fehler, Portabilitätsprobleme und Stilfragen.
- Lokaler Aufruf: `shellcheck <skript>`.
- In CI-Pipelines verpflichtend.

### Bash Language Server (optional)

- Bietet Editor-Unterstützung wie Autocompletion und Inlay-Hints.
- Installiere z. B. via `npm install -g bash-language-server`.
- Konfiguriere dein LSP im Editor deiner Wahl.

## Arbeitsweise

1. Skripte mit `#!/usr/bin/env bash` beginnen und `set -euo pipefail` verwenden.
2. Vor Commit `shfmt` und `shellcheck` lokal laufen lassen.
3. Falls neue Tools nötig sind, Dokumentation hier ergänzen.
4. Ergebnisse der Checks im Pull Request verlinken, falls relevant.

## Troubleshooting

- Bei nicht kompatiblen Legacy-Skripten markieren wir die entsprechenden Abschnitte mit `# shellcheck disable=...` und begründen die Ausnahme.
- Für Plattformunterschiede (Linux vs. macOS) halten wir Workarounds im Skript kommentiert fest.
- Prüfe bei `shfmt`-Fehlern, ob das Skript mit Tabs arbeitet; wir verwenden ausschließlich Leerzeichen.

[Zurück zum Prozessindex](README.md)

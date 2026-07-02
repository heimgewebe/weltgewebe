---
id: reports.repo-audit-r12-lychee-config-decision-2026-07-02
title: "REPO-AUDIT-001 / R-12: Lychee-Konfigurationsentscheidung"
doc_type: report
status: active
lifecycle_state: active
lifecycle: audit
owner_task: REPO-AUDIT-001
review_after: 2026-10-31
canonicality: evidence
created: 2026-07-02
lang: de
relations:
  - type: relates_to
    target: docs/reports/repo-audit-2026-07-02.md
  - type: relates_to
    target: docs/tasks/board.md
---

# REPO-AUDIT-001 / R-12: Lychee-Konfigurationsentscheidung

## Entscheidung

Die bevorzugte R-12-Lösung ist **Entfernen statt Laden**.

Begründung: Die Linkcheck-Workflows konfigurieren Lychee bereits explizit über Action-Argumente. Ein zusätzlich geladener TOML-Kanal würde eine zweite Wahrheitsschicht einführen und könnte bestehendes CI-Verhalten unbeabsichtigt ändern. Die richtige Korrektur ist daher nicht, die Dotfile-Konfiguration zu aktivieren, sondern die ungenutzte Konfigurationsfläche zu entfernen.

## Abgrenzung

Dieser Bericht ist der Entscheidungsbeleg. Die physische Entfernung der Dotfile und die anschließende Aktualisierung von Board/Index bleiben Teil desselben R-12-Schnitts, falls der Schreibkanal Dateilöschung zulässt.

## Status

- R-12-Diagnose: bestätigt.
- Zielpfad: Dotfile entfernen, nicht laden.
- Keine Änderung an App-Logik, Datenmodell, Runtime oder Linkcheck-Zielmenge beabsichtigt.

## Risiko

Laden der vorhandenen Dotfile hätte ein höheres Regressionsrisiko, weil bestehende Action-Argumente und Dateiwerte nicht vollständig deckungsgleich sind. Entfernen ist verhaltensärmer: weniger Magie, weniger Schattenregierung.

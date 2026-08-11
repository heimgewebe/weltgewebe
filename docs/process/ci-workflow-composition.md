---
id: process.ci-workflow-composition
title: "CI-Workflow-Komposition"
doc_type: process
status: active
created: 2026-08-11
lang: de
summary: >
  Vertrag zur Reduktion von GitHub-Actions-Redundanz durch einen wiederverwendbaren
  Web-/Playwright-Workflow und einen blockierenden Struktur-Guard.
relations:
  - type: relates_to
    target: docs/reports/optimierungsstatus.md
  - type: relates_to
    target: .github/workflows/reusable-web-check.yml
---

# CI-Workflow-Komposition

## Ziel

Wiederholte Runner-Einrichtung ist Wartungsarbeit ohne fachlichen Mehrwert. Der gemeinsame
Web-/Playwright-Pfad liegt deshalb in `.github/workflows/reusable-web-check.yml` und wird
über `workflow_call` von `ci.yml`, `web.yml` und `heavy.yml` verwendet.

## Redundanzkriterium

Ein Workflow-Abschnitt wird zentralisiert, wenn dieselbe technische Aufgabe in mindestens
zwei Workflow-Lanes wiederholt wird und keine unterschiedliche Berechtigung, Service-Topologie
oder Beweissemantik die Trennung verlangt. Dazu gehören insbesondere Checkout, pnpm/Node-Setup,
Dependency-Installation, Playwright-Browserinstallation und die Standard-Suite-Ausführung.

Nicht zentralisiert werden fachlich eigenständige Beweis-Lanes. PostgreSQL-Proofs,
Web-Runtime-Performance-Proofs, Dokumentationsprüfungen und API-spezifische Jobs behalten ihre
eigenen Jobs, weil ihre Dienste, Artefakte oder Akzeptanzbedingungen verschieden sind.

## Caller-Vertrag

- `ci.yml` bleibt die kanonische Required-Merge-Lane. `web-e2e` ruft den wiederverwendbaren
  Workflow mit Demo-API und `ci`-Suite auf; `required-merge-gate` hängt weiterhin von
  `web-e2e` ab.
- `web.yml` bleibt der pfadbegrenzte Web-Gate. Typecheck, Lint und Build laufen dort über
  denselben wiederverwendbaren Job; Unit-Tests bleiben der Fallback für Nicht-`main`-Pushes.
- `heavy.yml` bleibt ausschließlich manuell oder durch das Label `full-ci` wirksam. Es ruft
  die `full`-Suite auf und wird nicht in den Required-Merge-Gate aufgenommen.

## Rückfall verhindern

`scripts/ci/check_ci_workflow_structure.py` prüft, dass alle drei Caller den gemeinsamen
Workflow benutzen, keine direkte Playwright-Browserinstallation oder gemeinsame Suite wieder
einführen und die wichtigen Gate-Semantiken erhalten bleiben. `scripts/guard/run.sh` führt
diesen Strukturcheck als Core Guard aus. Die Regressionstests liegen in
`scripts/ci/tests/test_ci_workflow_structure.py`.

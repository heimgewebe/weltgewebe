---
id: reports.github-actions-node24-readiness
title: "GitHub Actions Node-24 Runtime Readiness — OPT-CI-005"
doc_type: report
status: active
lifecycle_state: active
lifecycle: audit
owner_task: OPT-CI-005
review_after: 2026-09-29
created: 2026-06-29
lang: de
summary: >
  Abschluss- und Auditbericht zu OPT-CI-005. Stage A war abgeschlossen; ein
  frischer Readback vom 2026-08-08 zeigt jedoch neue Missing-Force-Findings in
  zwei direkten Workflows. Stage B klassifiziert die wiederverwendbaren
  externen Workflows nach Pinning-Policy.
relations:
  - type: relates_to
    target: scripts/ci/check_actions_node24_readiness.py
  - type: relates_to
    target: scripts/ci/tests/test_check_actions_node24_readiness.py
  - type: relates_to
    target: .github/workflows/opt-arc-001-db-proof-matrix.yml
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: docs/tasks/index.json
---

# GitHub Actions Node-24 Runtime Readiness — OPT-CI-005

## Kurzurteil

OPT-CI-005 war im definierten Stage-A-Scope abgeschlossen. Der aktive Audit ist
jedoch nicht mehr vollständig grün: Ein frischer Lauf von
`scripts/ci/check_actions_node24_readiness.py` am 2026-08-08 meldet fehlendes
`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` in zwei direkten Workflows:

- `.github/workflows/germany-basemap-rollout.yml`
- `.github/workflows/kubernetes-proof-oci-mirror.yml`

Diese Baseline-Regression ist unabhängig vom WGX→Metarepo-Cutover. Die dabei
geänderten Guard-/Smoke-Caller werden vom selben Scanner korrekt als
SHA-gepinnte reusable Workflows klassifiziert.

## Was ursprünglich geändert wurde

`.github/workflows/opt-arc-001-db-proof-matrix.yml` setzt ebenfalls:

```yaml
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"
```

Dieser Workflow war zum damaligen Abschlusszeitpunkt die letzte vom Scanner
gemeldete direkte Workflow-Lücke. Der neue Auditbefund vom 2026-08-08 zeigt,
dass dieser historische Abschluss nicht als dauerhafte Grün-Garantie gelesen
werden darf.

## Was belegt ist

- `scripts/ci/check_actions_node24_readiness.py` erkennt direkt ausgeführte bekannte JavaScript-Actions.
- `scripts/ci/tests/test_check_actions_node24_readiness.py` deckt positive und negative Fälle ab.
- Der frische Scannerlauf vom 2026-08-08 reproduziert Missing-Force-Findings in genau den beiden oben genannten Workflows.
- Die WGX-Kompatibilitätscaller für Guard und Smoke werden nach dem Boundary-v2-Cutover als `pinned-sha` auf Metarepo erkannt.
- Mehrere frühere PR-CI-Läufe wurden unter erzwungener Node-24-Action-Runtime ausgeführt und GitHub hat die Merges akzeptiert.

## Stage-B-Audit

Der Scanner klassifiziert wiederverwendbare Workflows explizit nach
Referenztyp und Policy. Ein Caller-`env` beweist weiterhin nicht, dass der
aufgerufene externe Workflow intern Node-24-ready ist; Stage B ist daher ein
lokaler Risiko- und Pinning-Audit, kein Runtime-Beweis für fremde Repositories.

Aktueller Befund:

| Caller | Job | Reusable workflow | Ref | Policy |
| --- | --- | --- | --- | --- |
| `.github/workflows/metrics.yml` | `metrics` | `heimgewebe/metarepo/.github/workflows/wgx-metrics.yml@5c86ca69c0e2ae78a736c151f8d851e5cdda811e` | sha | pinned-sha |
| `.github/workflows/pr-heimgewebe-commands.yml` | `dispatch` | `heimgewebe/metarepo/.github/workflows/heimgewebe-command-dispatch.yml@a1984186a98a1e4214769f87649c5affc9686a53` | sha | pinned-sha |
| `.github/workflows/wgx-guard.yml` | `guard` | `heimgewebe/metarepo/.github/workflows/reusable-repo-verify.yml@fe6950616b2d06343e284a56a8944e0a36f1f972` | sha | pinned-sha |
| `.github/workflows/wgx-smoke.yml` | `smoke` | `heimgewebe/metarepo/.github/workflows/reusable-repo-verify.yml@fe6950616b2d06343e284a56a8944e0a36f1f972` | sha | pinned-sha |

Bewertung:

- Alle vier reusable Workflow Calls sind SHA-gepinnt.
- Der Scanner bleibt nicht-blockierend für reusable Workflows, weil die
  Semantik fremder Workflows nicht aus dem Caller-Repository bewiesen werden
  kann.
- Die gepinnten SHAs wurden gegen den vorhandenen Workflow-Pfad in den
  jeweiligen Callee-Repositories geprüft; Guard und Smoke delegieren die
  Verifikations-Policy revisionsfest an Metarepo.
- Stage B ist grün; Stage A hat aktuell die separat zu behebende
  Missing-Force-Regression in zwei direkten Workflows.

Damit bleibt Stage B als lokaler Audit und Pinning-Härtung belastbar. Nicht
behauptet wird eine inhaltliche Node-24-Readiness der externen
Callee-Workflows oder ein aktuell vollständig grüner Stage-A-Scan.

## Nicht-Ziele

- keine flächige Third-Party-SHA-Pinning-Änderung,
- keine Änderung an wiederverwendbaren externen Workflows,
- keine Deaktivierung von GitHub-Warnungen,
- kein `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION`.

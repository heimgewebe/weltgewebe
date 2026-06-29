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
  Abschlussbericht zu OPT-CI-005: Direkt ausgeführte Workflows mit bekannten
  JavaScript-Actions setzen FORCE_JAVASCRIPT_ACTIONS_TO_NODE24; der lokale
  Scanner findet keine fehlende Force-Variable mehr. Verbleibende Warnungen
  durch Action-Metadaten und wiederverwendbare externe Workflows bleiben Stage B.
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

OPT-CI-005 ist im definierten Stage-A-Scope abgeschlossen.

Direkt ausgeführte Workflows mit bekannten JavaScript-Actions setzen
`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`. Der Scanner meldet nach diesem Slice:

```text
rc 0
missing_force False
reusable_calls True
```

Damit ist die harte Readiness-Lücke geschlossen: Es gibt keinen bekannten direkt
ausgeführten JavaScript-Action-Schritt mehr, dem die Force-Variable fehlt.

## Was geändert wurde

`.github/workflows/opt-arc-001-db-proof-matrix.yml` setzt nun ebenfalls:

```yaml
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"
```

Dieser Workflow war die letzte vom Scanner gemeldete direkte Workflow-Lücke.

## Was belegt ist

- `scripts/ci/check_actions_node24_readiness.py` erkennt direkt ausgeführte bekannte JavaScript-Actions.
- `scripts/ci/tests/test_check_actions_node24_readiness.py` deckt positive und negative Fälle ab.
- Der Scanner läuft lokal gegen `.github/workflows` ohne Missing-Force-Finding.
- Mehrere aktuelle PR-CI-Läufe wurden unter erzwungener Node-24-Action-Runtime ausgeführt und GitHub hat die Merges akzeptiert.

## Stage-B-Restfläche

Der Scanner meldet weiterhin wiederverwendbare Workflows. Diese sind bewusst
nicht durch Stage A bewiesen, weil ein Caller-`env` nicht automatisch belegt,
dass der aufgerufene externe Workflow selbst Node-24-ready ist.

Stage B umfasst daher:

- wiederverwendbare externe Workflows prüfen oder ersetzen,
- verbleibende Node-20-Metadatenwarnungen der referenzierten Actions bewerten,
- bei Bedarf Action-Refs modernisieren oder auf SHA-/Versionen mit Node-24-Metadaten aktualisieren.

Diese Stage-B-Arbeit ist nicht Teil von OPT-CI-005. OPT-CI-005 schließt den
aktuellen Readiness-Schutz für direkt ausgeführte Workflows.

## Nicht-Ziele

- keine flächige Third-Party-SHA-Pinning-Änderung,
- keine Änderung an wiederverwendbaren externen Workflows,
- keine Deaktivierung von GitHub-Warnungen,
- kein `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION`.

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
  Scanner findet keine fehlende Force-Variable mehr. Stage B klassifiziert die
  wiederverwendbaren externen Workflows nach Pinning-Policy.
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

## Stage-B-Audit

Der Scanner klassifiziert wiederverwendbare Workflows jetzt explizit nach
Referenztyp und Policy. Ein Caller-`env` beweist weiterhin nicht, dass der
aufgerufene externe Workflow intern Node-24-ready ist; Stage B ist daher ein
lokaler Risiko- und Pinning-Audit, kein Runtime-Beweis für fremde Repositories.

Aktueller Befund:

| Caller | Job | Reusable workflow | Ref | Policy |
| --- | --- | --- | --- | --- |
| `.github/workflows/metrics.yml` | `metrics` | `heimgewebe/metarepo/.github/workflows/wgx-metrics.yml@5c86ca69c0e2ae78a736c151f8d851e5cdda811e` | sha | pinned-sha |
| `.github/workflows/pr-heimgewebe-commands.yml` | `dispatch` | `heimgewebe/metarepo/.github/workflows/heimgewebe-command-dispatch.yml@main` | named-ref | mutable-default-branch |
| `.github/workflows/wgx-guard.yml` | `guard` | `heimgewebe/wgx/.github/workflows/wgx-guard.yml@17e349d872e16f927bdd8e0d770d2295f8b6e663` | sha | pinned-sha |
| `.github/workflows/wgx-smoke.yml` | `smoke` | `heimgewebe/wgx/.github/workflows/wgx-smoke.yml@main` | named-ref | mutable-default-branch |

Bewertung:

- Zwei reusable Workflow Calls sind SHA-gepinnt.
- Zwei reusable Workflow Calls nutzen `main` und bleiben bewusst als mutable
  Default-Branch-Risiko sichtbar.
- Der Scanner bleibt nicht-blockierend für reusable Workflows, weil die
  Semantik fremder Workflows nicht aus dem Caller-Repository bewiesen werden
  kann.
- Ein späterer Härtungsschnitt kann die beiden `main`-Refs auf geprüfte SHAs
  anheben, sobald das jeweilige Callee-Repository als Quelle geprüft wurde.

Damit ist Stage B als lokaler Audit abgeschlossen. Nicht behauptet wird eine
inhaltliche Node-24-Readiness der externen Callee-Workflows.

## Nicht-Ziele

- keine flächige Third-Party-SHA-Pinning-Änderung,
- keine Änderung an wiederverwendbaren externen Workflows,
- keine Deaktivierung von GitHub-Warnungen,
- kein `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION`.

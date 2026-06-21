---
id: reports.planning-registration-findings
title: Planning Registration Findings Triage
doc_type: report
status: deprecated
lifecycle_state: archived
lifecycle: audit
owner_task: TASK-CTL-005
summary: >
  Evidenzbericht zu TASK-CTL-005: Triage der acht bestehenden
  planning-registration-Findings und Beleg für den Strict-Ratchet des Guards.
relations:
  - type: relates_to
    target: docs/tasks/index.json
  - type: relates_to
    target: scripts/docmeta/check_planning_registration.py
---

# Planning Registration Findings Triage

> Diagnostischer Evidenzbericht für `TASK-CTL-005`. Keine Wahrheitsschicht —
> er belegt, warum der `planning-registration`-Guard von `--mode warn` auf
> `--mode strict` umgestellt werden durfte.

## Lifecycle-Einordnung

Dieser Report bleibt am bestehenden Pfad als historische Evidenz für den
abgeschlossenen Strict-Ratchet aus `TASK-CTL-005` erhalten. Ein ablösendes
Report-Artefakt existiert nicht. Er wird daher ohne `superseded_by` fachlich
archiviert.

## Source command

- command: `python3 -m scripts.docmeta.check_planning_registration --format json`
- date: 2026-06-03
- branch: `claude/dreamy-thompson-DMy6t`
- base commit: `75169f7` (`75169f712c939f704e808ce28173263e81c046eb`)

## Summary

- initial finding count: 8
- final finding count: 0
- strict mode before: failed (exit 1)
- strict mode after: passed (exit 0)
- guard / config changed: no (the guard correctly flagged eight genuine
  planning artifacts; the fix is in the documents, not the guard)
- new tasks created: no

Triage outcome: six active/canonical strand documents were registered via a
frontmatter `relates_to` relation; two orphaned, already-executed deployment
planning artifacts were marked terminal (`status: deprecated`) and pointed at
the canonical, realized deployment documentation.

## Initial guard output

```text
--- Planning Artifact Registration Drift (8) ---
[UNREGISTERED_PLANNING_ARTIFACT] docs/blueprints/doc-structure-task-control-examples.md
[UNREGISTERED_PLANNING_ARTIFACT] docs/blueprints/kartenklarheit.md
[UNREGISTERED_PLANNING_ARTIFACT] docs/blueprints/map-blaupause.md
[UNREGISTERED_PLANNING_ARTIFACT] docs/blueprints/ui-blaupause.md
[UNREGISTERED_PLANNING_ARTIFACT] docs/blueprints/ui-state-machine.md
[UNREGISTERED_PLANNING_ARTIFACT] docs/blueprints/weltgewebe.auth-and-ui-routing.md
[UNREGISTERED_PLANNING_ARTIFACT] docs/blueprints/weltgewebe.config.diff.md
[UNREGISTERED_PLANNING_ARTIFACT] docs/blueprints/weltgewebe.deploy.plan.md
Check finished with 8 issue(s).
```

- report mode: exit 0, 8 findings
- JSON mode: `finding_count: 8`, `ok: false`, deterministic
- strict mode: exit 1
- no `CONFIG_MISSING` / `CONFIG_INVALID` findings

## Finding table

| # | Path | Code | Reason | Classification | Action | Evidence |
|---|---|---|---|---|---|---|
| 1 | `docs/blueprints/doc-structure-task-control-examples.md` | UNREGISTERED_PLANNING_ARTIFACT | Flagged because path is under `docs/blueprints/`; `doc_type: reference`, `status: draft`. Active example material for the task-control layer. | frontmatter_relation_added | Added `relates_to: docs/tasks/index.json`. | Siblings `doc-structure-task-control.md` / `-roadmap.md` are registered; this file exemplifies the task-index/board structures; the `task-index` workflow already watches `docs/blueprints/doc-structure-task-control*`. |
| 2 | `docs/blueprints/kartenklarheit.md` | UNREGISTERED_PLANNING_ARTIFACT | `doc_type: blueprint`, `status: draft`. Foundational blueprint of the Kartenklarheit strand. | frontmatter_relation_added | Added `relates_to: docs/roadmap.md`. | Master roadmap coordinates the "Strang Karte" (Kartenklarheit); sub-roadmaps `kartenklarheit-roadmap.md` / `kartenklarheit-phase6.md` are registered, this base blueprint was the gap. |
| 3 | `docs/blueprints/map-blaupause.md` | UNREGISTERED_PLANNING_ARTIFACT | `doc_type: blueprint`, `status: draft`. Normative Basemap architecture. | frontmatter_relation_added | Added `relates_to: docs/roadmap.md`. | Master roadmap coordinates the Basemap strand; the doc itself states "Blueprint und Roadmap sind als Paket zu verstehen" with the registered `map-roadmap.md`. |
| 4 | `docs/blueprints/ui-blaupause.md` | UNREGISTERED_PLANNING_ARTIFACT | `doc_type: blueprint`, `status: canonical`. Canonical UI design. | frontmatter_relation_added | Added `relates_to: docs/roadmap.md`. | Master roadmap "Strang UI" coordinates the UI work; registered `ui-roadmap.md` is the executive path, this canonical design doc was the gap. |
| 5 | `docs/blueprints/ui-state-machine.md` | UNREGISTERED_PLANNING_ARTIFACT | `doc_type: blueprint`, `status: canonical`. Canonical UI state machine (PR series done). | frontmatter_relation_added | Added `relates_to: docs/roadmap.md`. | Master roadmap "Strang UI" references the UI-State-Machine tests; the canonical state-machine doc itself was unregistered. |
| 6 | `docs/blueprints/weltgewebe.auth-and-ui-routing.md` | UNREGISTERED_PLANNING_ARTIFACT | `doc_type: reference`, `status: active`. Active auth-strand bridge / routing-diagnostic blueprint. | frontmatter_relation_added | Added `relates_to: docs/roadmap.md`. | `auth-roadmap.md` (line 134) and `auth-status-matrix.md` (line 41) explicitly classify it as an active "Brückendokument, nicht Endarchitektur" and cite it as documentation evidence; the auth strand is roadmap-coordinated. Not terminal. |
| 7 | `docs/blueprints/weltgewebe.config.diff.md` | UNREGISTERED_PLANNING_ARTIFACT | `doc_type: reference`, `status: active`. Phase-0 config-diff. | terminal_status | Set `status: deprecated`; added `relates_to: docs/deploy/heim-first-phase0.md` + deprecation note. | Orphaned (zero inbound references); the described config changes are realized in `infra/caddy/Caddyfile.heim` and `infra/compose/compose.prod.yml`; canonical deployment truth lives in `docs/deploy/` (`README.md` is normative, `heim-first-phase0.md` acknowledges the change). |
| 8 | `docs/blueprints/weltgewebe.deploy.plan.md` | UNREGISTERED_PLANNING_ARTIFACT | `doc_type: reference`, `status: active`. Phase-0 migration plan. | terminal_status | Set `status: deprecated`; added `relates_to: docs/deploy/heim-first-phase0.md` + deprecation note. | Orphaned (zero inbound references); Phase 0 is realized (`docs/deploy/heim-first-phase0.md`); the document's "404/405" auth-route claims are stale — auth routes are implemented and proven per `auth-status-matrix.md`. |

### Classification tally

- frontmatter_relation_added: 6 (rows 1–6)
- terminal_status: 2 (rows 7–8)
- false_positive_guard_fix / false_positive_config_fix: 0
- needs_followup_not_fixed: 0

No finding was classified as a false positive, so no guard or config code was
changed and no regression test was required. The registration mechanisms used
(frontmatter relation to `docs/roadmap.md` / `docs/tasks/...` and terminal
`status: deprecated`) are already covered by
`scripts/docmeta/tests/test_check_planning_registration.py`.

## Final guard output

```text
Agent-planning registration check passed (0 issues).
```

```text
{
  "finding_count": 0,
  "findings": [],
  "format": "json",
  "mode": "report",
  "ok": true
}
```

- report mode: exit 0, 0 findings
- JSON mode: `finding_count: 0`, `ok: true`
- strict mode: exit 0

## Workflow ratchet

`.github/workflows/task-index.yml` now runs the guard blocking:

```yaml
      - name: Check planning registration drift (strict)
        run: python3 -m scripts.docmeta.check_planning_registration --mode strict
```

`TASK-CTL-004` built the guard mechanism (modes report/warn/strict, JSON
output, YAML config, tests). `TASK-CTL-005` cleared the eight pre-existing
findings and ratcheted the CI guard to `--mode strict`, so new unregistered
planning artifacts are now blocked at PR time.

---
id: reports.github-action-ref-pinning-audit
title: "GitHub Action Reference Pinning Audit — OPT-INF-002"
doc_type: report
status: active
lifecycle_state: active
lifecycle: audit
owner_task: OPT-INF-002
created: 2026-07-03
review_after: 2026-09-30
lang: de
summary: >
  Reproduzierbarer Audit zu GitHub-Actions-`uses:`-Referenzen. Der Scanner
  klassifiziert lokale Actions, GitHub Actions und reusable Workflows nach
  Referenztyp und Pinning-Policy; er pinnt nicht automatisch und behauptet keine
  Runtime-Semantik externer Actions.
relations:
  - type: relates_to
    target: scripts/ci/check_github_action_pinning.py
  - type: relates_to
    target: scripts/ci/tests/test_check_github_action_pinning.py
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: docs/tasks/index.json
---

# GitHub Action Reference Pinning Audit — OPT-INF-002

## Kurzurteil

OPT-INF-002 ist wieder aufnahmefähig, weil die Dependency-Update-Automation
(`OPT-CI-004`) bereits abgeschlossen ist. Ein direktes Repo-weites Blind-Pinning
wäre trotzdem zu riskant: das Repo enthält viele wiederholte Action-Uses und
mehrere Action-Familien mit unterschiedlichen Update- und Wartungswegen.

Dieser Slice schließt daher die erste belastbare Stufe: eine reproduzierbare
Pinning-Inventur.

## Scanner

Ausführen:

```bash
python3 scripts/ci/check_github_action_pinning.py
```

Der Scanner liest `.github/workflows/*.yml` und `.github/workflows/*.yaml`,
klassifiziert jede `uses:`-Referenz und schreibt keine Dateien.

## Befund am 2026-07-03

```text
total=162
kind.github-action=158
kind.reusable-workflow=4
policy.named-ref=105
policy.pinned-sha=57
```

Unique named refs:

```text
DavidAnson/markdownlint-cli2-action@v16
Swatinem/rust-cache@v2
actions/cache@v4
actions/download-artifact@v8
actions/setup-python@v5
actions/upload-artifact@v4
anchore/sbom-action@v0
astral-sh/setup-uv@v7
docker/setup-buildx-action@v4
dorny/paths-filter@v4
dtolnay/rust-toolchain@v1
extractions/setup-just@v2
lycheeverse/lychee-action@v2
pnpm/action-setup@v6
softprops/action-gh-release@v2
```

## Pinning Slice 1 — actions/checkout

| Action-Familie | Ursprungstag | Ziel-SHA | Vorkommen | Prüfung |
| --- | --- | --- | ---: | --- |
| `actions/checkout` | `v4` | `34e114876b0b11c390a56381ad16ebd13914f8d5` | 41 | GitHub tag ref `actions/checkout@v4` zeigte auf Commit-SHA `34e114876b0b11c390a56381ad16ebd13914f8d5`. |

Alle ersetzten Workflow-Zeilen behalten den Ursprungstag als Inline-Kommentar:

```yaml
uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # tag: v4
```

`.github/workflows/api.yml` bleibt in diesem Slice ausgenommen, weil diese Datei die OPT-ARC-001-DB-Proof-Harnesses trägt. Ein Checkout-Pin dort macht die Proof-Matrix-Evidence formal stale und braucht einen separaten Proof-Refresh-Schnitt.

## Bewertung

- Alle reusable Workflows sind nach #1331 SHA-gepinnt.
- `actions/checkout` ist außerhalb der OPT-ARC-001-DB-Proof-Harness-Datei SHA-gepinnt.
- Die verbleibende Pinning-Fläche liegt bei direkt verwendeten GitHub Actions
  mit named refs. Größte verbleibende Familien sind `actions/upload-artifact`,
  `dtolnay/rust-toolchain`, `Swatinem/rust-cache`, `pnpm/action-setup`,
  `actions/setup-python` und `actions/cache`.
- Der Audit bleibt bewusst nicht-blockierend. Er ist die Grundlage für spätere
  kontrollierte Pinning-Slices.

## Grenzen

Der Scanner beweist nicht, dass eine Action intern sicher oder Node-24-ready ist.
Er beweist nur, ob die Caller-Referenz auf einen SHA, einen benannten Ref, keinen
Ref, eine lokale Action oder eine Docker-Referenz zeigt.

## Nächster Schnitt

Nicht alle Actions in einem PR pinnen. Sinnvoller ist ein ratcheted Vorgehen:

1. Als nächstes entweder `actions/upload-artifact` pinnen oder einen separaten Proof-Refresh-Schnitt für `.github/workflows/api.yml` planen.
2. Ursprungstag und Ziel-SHA pro Familie dokumentieren.
3. Nach jedem Slice prüfen, dass Dependabot/Update-Pfad weiterhin verständlich
   bleibt.

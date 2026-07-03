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
policy.named-ref=49
policy.pinned-sha=113
```

Unique named refs:

```text
DavidAnson/markdownlint-cli2-action@v16
Swatinem/rust-cache@v2
anchore/sbom-action@v0
docker/setup-buildx-action@v4
dorny/paths-filter@v4
dtolnay/rust-toolchain@v1
extractions/setup-just@v2
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

## Pinning Slice 2 — actions/upload-artifact

| Action-Familie | Ursprungstag | Ziel-SHA | Vorkommen | Prüfung |
| --- | --- | --- | ---: | --- |
| `actions/upload-artifact` | `v4` | `ea165f8d65b6e75b540449e92b4886f43607fa02` | 22 | GitHub tag ref `actions/upload-artifact@v4` zeigte auf Commit-SHA `ea165f8d65b6e75b540449e92b4886f43607fa02`. |

Alle ersetzten Workflow-Zeilen behalten den Ursprungstag als Inline-Kommentar:

```yaml
uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # tag: v4
```

## Pinning Slice 3 — pnpm/action-setup

| Action-Familie | Ursprungstag | Ziel-SHA | Vorkommen | Prüfung |
| --- | --- | --- | ---: | --- |
| `pnpm/action-setup` | `v6` | `b0f76dfb45f55f8421693e4803ac7bb65143bd34` | 11 | GitHub tag ref `pnpm/action-setup@v6` zeigte auf Commit-SHA `b0f76dfb45f55f8421693e4803ac7bb65143bd34`. |

Alle ersetzten Workflow-Zeilen behalten den Ursprungstag als Inline-Kommentar:

```yaml
uses: pnpm/action-setup@b0f76dfb45f55f8421693e4803ac7bb65143bd34 # tag: v6
```

## Pinning Slice 4 — actions/setup-python

| Action-Familie | Ursprungstag | Ziel-SHA | Vorkommen | Prüfung |
| --- | --- | --- | ---: | --- |
| `actions/setup-python` | `v5` | `a26af69be951a213d495a4c3e4e4022e16d87065` | 10 | GitHub tag ref `actions/setup-python@v5` zeigte auf Commit-SHA `a26af69be951a213d495a4c3e4e4022e16d87065`. |

Alle ersetzten Workflow-Zeilen behalten den Ursprungstag als Inline-Kommentar:

```yaml
uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # tag: v5
```

## Pinning Slice 5 — actions/cache

| Action-Familie | Ursprungstag | Ziel-SHA | Vorkommen | Prüfung |
| --- | --- | --- | ---: | --- |
| `actions/cache` | `v4` | `0057852bfaa89a56745cba8c7296529d2fc39830` | 7 | GitHub tag ref `actions/cache@v4` zeigte auf Commit-SHA `0057852bfaa89a56745cba8c7296529d2fc39830`. |

Alle ersetzten Workflow-Zeilen behalten den Ursprungstag als Inline-Kommentar:

```yaml
uses: actions/cache@0057852bfaa89a56745cba8c7296529d2fc39830 # tag: v4
```

## Pinning Slice 6 — lycheeverse/lychee-action

| Action-Familie | Ursprungstag | Ziel-SHA | Vorkommen | Prüfung |
| --- | --- | --- | ---: | --- |
| `lycheeverse/lychee-action` | `v2` | `8646ba30535128ac92d33dfc9133794bfdd9b411` | 3 | GitHub tag ref `lycheeverse/lychee-action@v2` zeigte auf Commit-SHA `8646ba30535128ac92d33dfc9133794bfdd9b411`. |

Alle ersetzten Workflow-Zeilen behalten den Ursprungstag als Inline-Kommentar:

```yaml
uses: lycheeverse/lychee-action@8646ba30535128ac92d33dfc9133794bfdd9b411 # tag: v2
```

## Pinning Slice 7 — astral-sh/setup-uv

| Action-Familie | Ursprungstag | Ziel-SHA | Vorkommen | Prüfung |
| --- | --- | --- | ---: | --- |
| `astral-sh/setup-uv` | `v7` | `37802adc94f370d6bfd71619e3f0bf239e1f3b78` | 2 | GitHub tag ref `astral-sh/setup-uv@v7` war ein annotierter Tag und wurde auf Commit-SHA `37802adc94f370d6bfd71619e3f0bf239e1f3b78` dereferenziert. |

Alle ersetzten Workflow-Zeilen behalten den Ursprungstag als Inline-Kommentar:

```yaml
uses: astral-sh/setup-uv@37802adc94f370d6bfd71619e3f0bf239e1f3b78 # tag: v7
```

## Pinning Slice 8 — actions/download-artifact

| Action-Familie | Ursprungstag | Ziel-SHA | Vorkommen | Prüfung |
| --- | --- | --- | ---: | --- |
| `actions/download-artifact` | `v8` | `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c` | 1 | GitHub tag ref `actions/download-artifact@v8` zeigte auf Commit-SHA `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`. |

```yaml
uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # tag: v8
```

## Bewertung

- Alle reusable Workflows sind nach #1331 SHA-gepinnt.
- `actions/checkout` ist außerhalb der OPT-ARC-001-DB-Proof-Harness-Datei SHA-gepinnt.
- `actions/upload-artifact` ist repo-weit SHA-gepinnt.
- `pnpm/action-setup` ist repo-weit SHA-gepinnt.
- `actions/setup-python` ist repo-weit SHA-gepinnt.
- Die verbleibende Pinning-Fläche liegt bei direkt verwendeten GitHub Actions
  mit named refs. Größte verbleibende Familien sind `dtolnay/rust-toolchain` und
  `Swatinem/rust-cache`.
- Der Audit bleibt bewusst nicht-blockierend. Er ist die Grundlage für spätere
  kontrollierte Pinning-Slices.

## Grenzen

Der Scanner beweist nicht, dass eine Action intern sicher oder Node-24-ready ist.
Er beweist nur, ob die Caller-Referenz auf einen SHA, einen benannten Ref, keinen
Ref, eine lokale Action oder eine Docker-Referenz zeigt.

## Nächster Schnitt

Nicht alle Actions in einem PR pinnen. Sinnvoller ist ein ratcheted Vorgehen:

1. Als nächstes eine verbleibende nicht-api.yml-Action-Familie prüfen; `dtolnay/rust-toolchain` und `Swatinem/rust-cache` berühren überwiegend `.github/workflows/api.yml` und bleiben eher Proof-Refresh-Schnitt.
2. Ursprungstag und Ziel-SHA pro Familie dokumentieren.
3. Nach jedem Slice prüfen, dass Dependabot/Update-Pfad weiterhin verständlich
   bleibt.

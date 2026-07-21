---
id: docs.proofs.repoground-agent-utility-v1-t003-vertical-pilot
title: RepoGround Agent Utility V1 T003 Vertical Pilot
doc_type: proof
status: active
summary: Revisionsgebundener Weltgewebe-Pilot für RepoGround Change Capsules; der Kompaktheits-Gate besteht, die Default-Promotion bleibt wegen eines zu großen Call-Graph-Artefakts blockiert.
relations:
  - type: relates_to
    target: scripts/ci/fixtures/repoground_vertical_pilot.v1.json
  - type: relates_to
    target: scripts/ci/validate_repoground_vertical_pilot.py
  - type: relates_to
    target: scripts/ci/tests/test_repoground_vertical_pilot.py
  - type: relates_to
    target: docs/policies/agent-reading-protocol.md
---

# RepoGround Agent Utility V1 T003 Vertical Pilot

## Zweck

Dieser Proof misst eine RepoGround Change Capsule gegen denselben heutigen Grabowski-/RepoGround-Kontextweg ohne Capsule. Er verändert weder Produktion noch Compose/Kubernetes-Runtime.

Die Baseline ist `repoground_context_pack`; die Capsule ist `repoground_context_compose`. Beide verwenden je Fall dieselbe Query und das Task-Profil `change_impact`. Die Capsule ist zusätzlich an exakte Basis-/Ziel-Commits und den daraus berechneten `git_tree_delta_v1`-SHA-256 gebunden.

## Gebundene Identitäten

- Weltgewebe-Pilotbasis / beim Messlauf aktueller `main`: `929dc002c5317e0d85abb24811cf11d5e330d41b`
- RepoGround-Bundle: `heimgewebe__weltgewebe__main-max-260721-0745`
- Bundle-Manifest SHA-256: `34f6ac4682db840efba13e56164d0847a6d3099d16cfb2a6047e8eac6c19f31f`
- Bundle-Frische beim Lauf: `fresh_exact`
- Gemessene Grabowski-Runtime: `e5ec3f699499efcfd36d4b320fb9339988e18368`
- Kontextbudget der Capsule: `12000` Byte
- Maschinenlesbare Evidenz: `scripts/ci/fixtures/repoground_vertical_pilot.v1.json`

## Goldfälle und kontrollierter Livefall

| Profil | Referenz | Baseline | Capsule | Reduktion | Kritische Direktpfade | Status |
|---|---|---:|---:|---:|---:|---|
| Datenbank/Auth | PR #1295, PostgreSQL Passkey Store | 42.848 B | 11.738 B | 72,606 % | 5/5 | degraded |
| Web/Karte | PR #1514, Map Fan Surfaces | 7.713 B | 1.449 B | 81,214 % | 3/3 | degraded |
| Deployment/Kubernetes | PR #1458, exakte Workflow-Proof-Bindung | 16.781 B | 6.091 B | 63,703 % | 5/5 | degraded |
| kontrolliert live | beim Messlauf aktueller `main` `929dc002…` | 7.739 B | 1.449 B | 81,277 % | 3/3 | degraded |

Alle vier Fälle waren diff-gebunden und nutzten eine frische RepoGround-Publikation. Die vorher festgelegten kritischen Direktpfade blieben vollständig enthalten. Die mechanische T003-Schwelle von mindestens 20 Prozent Kontextreduktion in mindestens zwei Goldfällen wird damit in allen drei Goldfällen erreicht.

Die Laufzeit wurde **nicht** verbessert: Die Baseline-Läufe lagen bei rund 394–435 ms, die Capsule-Läufe bei rund 627–694 ms. Der gemessene Nutzen liegt damit derzeit in der Kontextverdichtung, nicht in geringerer Berechnungszeit.

## Gefundener Blocker

Alle vier Capsules melden denselben Impact-Blocker:

- Artefaktrolle: `python_call_graph_json`
- Artefaktgröße: `22.127.878` Byte
- sichere Grenze des Read-only-Adapters: `16.777.216` Byte (16 MiB)
- Überschreitung: `5.350.662` Byte
- Fehlercode: `artifact_too_large`

Es existiert nur eine gesunde aktuelle Weltgewebe-Publikation; ein kleineres alternatives gesundes Bundle steht nicht zur Auswahl. Deshalb ist der Fehler kein Auswahlproblem.

Folge: Die Capsule bleibt `degraded`; automatische `related_tests`, `target_symbols` und die Call-Graph-Lane sind nicht belastbar verfügbar. Die Lücke wird explizit ausgegeben und nicht als Vollständigkeit geglättet.

## Bewertung der T003-Akzeptanz

- **Drei Änderungsklassen:** bestanden. Je ein revisionsgebundener Goldfall für Datenbank/Auth, Web/Karte und Deployment/Kubernetes liegt vor.
- **Gepaarte Baseline:** bestanden. Jeder Fall wurde mit identischer Query und identischem Task-Profil gegen `repoground_context_pack` gemessen.
- **Qualität/Freshness:** begrenzt bestanden. Kritische Direktpfade: 100 %, Diff-Bindung: verifiziert, Bundle-Frische: `fresh`. Die fehlende Impact-Tiefe bleibt ausdrücklich als Gap sichtbar.
- **Mechanischer Promotion-Gate:** bestanden. Kontextreduktion beträgt in allen drei Goldfällen deutlich mehr als 20 Prozent.
- **Delivery Chain:** **blockiert**. Die automatische Kette über betroffene Symbole und Related Tests ist wegen des übergroßen Call-Graphs nicht vollständig belegt.
- **Delivery/PR/CI:** nicht durch die Messfixture selbst bewiesen. PR-Head, vollständiger Diff, Review und CI werden separat als delivery-gebundene Evidenz geführt; auch deren Erfolg autorisiert keine Default-Promotion.

## Entscheidung

**Default-Promotion wird zurückgehalten.**

Der Pilot belegt einen deutlichen Kompaktheitsvorteil ohne Verlust der vorher festgelegten kritischen Direktpfade. Er belegt aber noch nicht die vollständige Änderungsauswirkungskette, die T003 für eine Generalisierung voraussetzt. Der Call-Graph-Skalierungsbruch muss separat behoben und der Pilot danach erneut ausgeführt werden.

## Nicht bewiesen

- semantische Vollständigkeit der Capsule
- automatische Vollständigkeit verwandter Tests
- automatische Vollständigkeit betroffener Symbole
- Patch-Korrektheit oder Merge-Reife einer beliebigen Änderung
- Runtime-Korrektheit oder Regressionsfreiheit
- Berechtigung, RepoGround standardmäßig zu routen
- Berechtigung, Phase 3 allein aufgrund der Kontextreduktion zu starten

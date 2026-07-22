---
id: docs.proofs.repoground-agent-utility-v1-t003-vertical-pilot
title: RepoGround Agent Utility V1 T003 Vertical Pilot
doc_type: proof
status: active
summary: Aktuelle revisionsgebundene Drei-Fälle-Neumessung für den begrenzten RepoGround-change-impact-Handoff; Promotion besteht bei expliziten Grenzen für Vollständigkeit, Testabdeckung und Merge-Autorität.
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

## Entscheidung

**Für die begrenzte Zielsetzung besteht der Pilot:** RepoGround darf im gemessenen `change_impact`-Handoff als Standardkontext verwendet werden, wenn der Consumer die expliziten Nichtaussagen respektiert.

**Für die stärkere Zielsetzung besteht kein Beweis:** Die Messung etabliert weder semantische Vollständigkeit noch vollständige Related-Test- oder Symbolabdeckung, Patch-Korrektheit, Merge-Reife oder Runtime-Korrektheit.

Die alternative, konservativere Entscheidung wäre, die Promotion bis zu vollständiger automatischer Related-Test- und Symbolabdeckung in allen Änderungsklassen zurückzuhalten. Das senkt das Fehlinterpretationsrisiko, setzt aber ein stärkeres Kriterium als den T003-Pilotvertrag voraus und verwirft den bereits belegten Nutzen der revisionsgebundenen Verdichtung.

## Warum erneut gemessen wurde

Der historische Pilot aus PR #1520 hielt die Promotion wegen eines damals blockierenden übergroßen Python-Call-Graphs zurück. Dieser Zustand ist überholt und wurde anschließend mehrfach gehärtet:

- RepoGround PR #1070, Merge `c12e6e867c0de3315b250ce5818f4331f6dbbb63`, machte den optionalen Call-Graph degradierbar statt Core-Impact-blockierend.
- Grabowski T006 PR #351, Merge `eaaf8307009df70bba549c571ec376a4fc7743e0`, korrigierte die Call-Graph-Lane-Wahrheit.
- Grabowski-Härtung PR #356, Merge `de799bbded2d1c09de9b29153325516539a805e2`, bindet Retrieval-Lanes an tatsächlich ausgelieferte Evidenz.
- Die aktuelle Grabowski-Runtime `acf29382784c1541b930b8068c58aac4497da5e4` enthält beide Grabowski-Merges.
- Der aktuelle RepoGround-Generator `131c843a2a0c3e995e879e71286bd21a169e0650` ist in der GitHub-Historie 23 Commits weiter als #1070 und enthält diesen Merge.

Während des Abschlussreviews wurde außerdem eine methodisch schwache Web-Baseline mit null Suchtreffern verworfen. Die aktuelle Web-Messung verwendet die Query `map` und enthält fünf aufgelöste Baseline-Snippets, fünf Bereiche und fünf Zitate.

## Gebundene Identitäten

- Weltgewebe-Publikationscommit: `a7f8c490095d907a26ba637f739ca423b8bba180`
- RepoGround-Bundle: `heimgewebe__weltgewebe__main-max-260722-0641`
- Bundle-Manifest SHA-256: `c24a45375b8751813a70857580568f5746346367c1278d62127bab790ebf5f94`
- Bundle-Frische: `fresh_exact`
- Post-Emit-Health: `pass`
- Output-Health: `pass`
- Bundle-Surface-Validation: `pass`
- RepoGround-Generator: `131c843a2a0c3e995e879e71286bd21a169e0650`
- Grabowski-Runtime: `acf29382784c1541b930b8068c58aac4497da5e4`
- Capsule-Budget: `12000` Byte

Alle drei Capsules wurden mit dem erwarteten `git_tree_delta_v1`-SHA-256 als harte Eingabe erneut ausgeführt. Eine falsche Diff-Identität hätte damit fail-closed abgebrochen.

## Drei-Fälle-Messung

| Klasse | Basis → Ziel | Baseline | Capsule | Reduktion | Direktpfade | Related Tests | Status |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| DB/Auth | `691f663a…` → `4b9b0507…` | 34.306 B | 8.478 B | 75,287 % | 14/14 | 5 | degraded: Budget |
| Web/Karte | `c18ef20b…` → `d7c1fb9c…` | 43.180 B | 11.711 B | 72,879 % | 4/4 | 2 | degraded: Budget |
| Deployment/Kubernetes | `5d11513e…` → `7a1b5943…` | 34.369 B | 11.998 B | 65,091 % | 9/9 | 1 | degraded: Budget |

Die gepaarten Baselines wurden auf demselben frischen Bundle direkt über `repoground_context_pack` geprüft. Ihr `resolved_evidence_status` ist in allen drei Fällen `available`; die Baseline-Evidenz enthält 3/3/3, 5/5/5 und 3/3/3 Snippets/Bereiche/Zitate.

Die in der Fixture gespeicherten Baseline-Bytewerte stammen aus `repoground_context_compose.compactness.general_context_pack_bytes`. Damit ist die Bytebilanz an genau die Vergleichsgröße gebunden, die der Composer für denselben allgemeinen Kontextpfad ausweist.

Alle drei Fälle überschreiten die T003-Schwelle von 20 Prozent deutlich. Sämtliche direkt geänderten Pfade sind enthalten. Der aktuelle Generator liefert zusätzlich fünf, zwei und einen direkt diff-gebundenen Related-Test.

`degraded` bedeutet in diesen drei Läufen ausschließlich Budgeterschöpfung in nachrangigen Lanes. `impact_context_blocked` tritt in keinem Fall auf.

## Retrieval-Lane-Wahrheit

Der aktuelle optionale Python-Call-Graph ist vorhanden:

- Größe: `22.437.645` Byte
- SHA-256: `c9256ca8bd55a567d0e9a6d1fc6b0b44872c5476d2819674e331a90ffe94613b`

Seine bloße Existenz zählt nicht als Nutzung:

- **DB/Auth:** keine ausgelieferte kohärente Call-Graph-Relation → `call_graph=skipped`.
- **Web/Karte:** keine ausgelieferte kohärente Call-Graph-Relation → `call_graph=skipped`.
- **Deployment/Kubernetes:** eine ausgelieferte Relation ist mit `python_call_graph_json`, `status=coherent`, Call-Site und Peer-Definition provenance-gebunden → `call_graph=used`.

Damit ist die T006-Regel live sichtbar: Eine Retrieval-Lane gilt nur dann als benutzt, wenn ihre vertrauenswürdige Evidenz tatsächlich im ausgelieferten Kontext vorkommt.

## Begrenzte Delivery Chain

Der Deployment-Fall enthält:

- alle 9 direkten Änderungen,
- den geänderten Produktions-Reconciler-Contract-Test als Related-Test,
- 8 ausgelieferte Zielsymbole,
- 7 ausgelieferte Kausalrelationen,
- darunter 1 kohärente Call-Graph-Relation,
- 1 ausgelieferten Live-Range des Produktions-Reconcilers.

Drei direkte Shell-Pfade (`activate-production-reconciler-from-release.sh`, `install-production-reconciler.sh`, `weltgewebe-up`) sind im Architecture Graph weiterhin nicht als Graph-Knoten vorhanden. Diese Lücke bleibt explizit. Sie blockiert den begrenzten Pilot nicht, weil die Pfade selbst als direkte Änderungen ausgeliefert werden; sie verhindert aber jede Behauptung einer vollständigen Architektur- oder Kausalabdeckung.

## Dirty-State-Grenze

Der aktuelle T003-Arbeitsbranch stand beim Nachmesslauf auf dem Publikationscommit `a7f8c490…` und war ausschließlich durch die vier T003-Evidenzdateien dirty. Diese Evidence-Edits gehören nicht zu den historischen Basis-/Zielrevisionen und sind nicht Teil der gemessenen Revisionsdiffs.

Zusätzlich meldet der aliasbasierte Composer einen fremden Dirty-Overlay des kanonischen Weltgewebe-Hauptcheckouts mit 33 Einträgen. Auch dieser Overlay ist ausdrücklich mit `included_in_revision_diff=false` ausgeschlossen. Beide Grenzen werden in der Fixture getrennt dokumentiert statt geglättet.

## Akzeptanz

- **Drei Änderungsklassen:** bestanden.
- **Gepaarte Baseline:** bestanden; alle Baselines frisch und mit aufgelöster Evidenz.
- **Kompaktheit:** bestanden; 75,287 %, 72,879 % und 65,091 % Reduktion.
- **Direktpfadabdeckung:** bestanden; 100 Prozent in jedem Fall.
- **Related-Test-Evidenz:** bestanden; mindestens ein diff-gebundener Related-Test in jedem Fall.
- **Diff-Bindung:** bestanden; alle drei erwarteten Diff-SHA-256 wurden verifiziert.
- **Frische:** bestanden; `fresh_exact` plus drei Health-Gates `pass`.
- **Retrieval-Lane-Wahrheit:** bestanden.
- **Delivery Chain:** begrenzt bestanden im Deployment-Fall.
- **Promotion-Gate:** bestanden.

## Promotion

**Empfehlung: `promote_default` ausschließlich für `bounded_change_impact_context_for_agent_handoff`.**

Gilt, wenn Budget-Degradierung nicht als Vollständigkeit interpretiert wird und die bestehenden `does_not_establish`-Grenzen erhalten bleiben. Die Promotion autorisiert weder Merge noch Deployment und ersetzt keine Tests oder Reviews.

## Nicht bewiesen

- semantische Vollständigkeit der Capsule
- vollständige automatische Related-Test-Ermittlung
- vollständige automatische Symbol-Impact-Ermittlung
- vollständige Architektur- oder Kausalabdeckung
- Patch-Korrektheit
- Test-Suffizienz oder vollständige Testabdeckung
- Review-Vollständigkeit
- Merge-Reife
- Runtime-Korrektheit
- Regressionsfreiheit
- globale RepoGround-Routing-Autorität außerhalb des gemessenen `change_impact`-Handoff-Pfads

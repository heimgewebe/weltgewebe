---
id: docs.proofs.repoground-agent-utility-v1-t003-vertical-pilot
title: RepoGround Agent Utility V1 T003 Vertical Pilot
doc_type: proof
status: active
summary: Revisionsgebundene Neumessung mit drei Goldfällen und einem kontrollierten Livefall für den begrenzten RepoGround-change-impact-Handoff; Promotion ist an explizite Contract-, CI-, Deployment-, Runtime-Readback- und Recovery-Evidenz gebunden.
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

**Für die stärkere Zielsetzung besteht kein Beweis:** Die Messung etabliert weder semantische Vollständigkeit noch vollständige Related-Test- oder Symbolabdeckung, Patch-Korrektheit, Merge-Reife, allgemeine Runtime-Korrektheit oder einen automatisch erfolgreichen Rollback.

Die Promotion gilt ausschließlich für `bounded_change_impact_context_for_agent_handoff`. Sie ersetzt weder Tests noch Review, Deployment-Gates oder Recovery-Verfahren. Alle drei Goldfälle bleiben wegen Budgeterschöpfung in nachrangigen Lanes `degraded`; der Bestand ist deshalb ausdrücklich ein begrenzter Qualitätsnachweis und kein Vollständigkeitsnachweis.

## Warum erneut gemessen wurde

Der historische Pilot aus PR #1520 hielt die Promotion wegen eines damals blockierenden übergroßen Python-Call-Graphs zurück. Dieser Zustand ist überholt:

- RepoGround PR #1070 machte den optionalen Call-Graph degradierbar statt Core-Impact-blockierend.
- Grabowski T006 PR #351 korrigierte die Call-Graph-Lane-Wahrheit.
- Grabowski-Härtung PR #356 bindet Retrieval-Lanes an tatsächlich ausgelieferte Evidenz.
- RepoGround PR #1075 diversifizierte die begrenzte Target-Symbol-Auswahl über geänderte Python-Pfade.
- RepoGround PR #1076 härtete exakte Target-Symbol-Treffer pro Pfad und schloss den verbliebenen Starvation-Randfall.
- Der gemessene RepoGround-Generator `131c843a2a0c3e995e879e71286bd21a169e0650` enthält diese Härtungen.

Methodisch schwache Baselines mit null aufgelösten Treffern wurden verworfen. Jeder hier akzeptierte Fall besitzt eine frisch aufgelöste gepaarte Baseline.

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

Alle vier Fälle sind an `git_tree_delta_v1`-Digests gebunden. Eine falsche Diff-Identität bricht fail-closed ab.

## Drei Goldfälle plus kontrollierter Livefall

| Klasse | Basis → Ziel | Baseline | Capsule | Reduktion | Direktpfade | Related Tests | Call-Graph | Status |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| DB/Auth | `691f663a…` → `4b9b0507…` | 34.306 B | 8.478 B | 75,287 % | 14/14 | 5 geänderte Testpfade | skipped | degraded: Budget |
| Web/Karte | `c18ef20b…` → `d7c1fb9c…` | 43.180 B | 11.711 B | 72,879 % | 4/4 | 2 geänderte Testpfade | skipped | degraded: Budget |
| Deployment/Kubernetes | `5d11513e…` → `7a1b5943…` | 34.369 B | 11.998 B | 65,091 % | 9/9 | 1 geänderter Testpfad | 1 kohärente Contract-Test-Relation | degraded: Budget |
| Kontrollierter Livefall | `24b74dab…` → `a7f8c490…` | 14.073 B | 5.095 B | 63,796 % | 1/1 | 1 Navigationstreffer | skipped | available |

Die drei Goldfälle decken `database_auth`, `web_map` und `deployment_kubernetes` ab. Der vierte Fall ist der von T003 zusätzlich verlangte kontrollierte Livefall und bindet sein Ziel exakt an den frischen Source-Bundle-Commit `a7f8c490…`.

Der Livefall verwendet die Query `metrics_path_label`. Die gepaarte Baseline enthält 2 Snippets, 2 Bereiche und 2 Zitate mit `resolved_evidence_status=available`. Der kanonische Revisionsdigest lautet `53750d3df0d4535ada0591d6fd0d85b0f62bfd4481f4dcf08c86343362f06e32`.

Alle vier Fälle haben vollständige Direktpfadabdeckung. Die drei Goldfälle enthalten jeweils mindestens einen direkt diff-gebundenen Testpfad. Beim kontrollierten Livefall liegt der relevante Test im geänderten Rust-Modul; RepoGround liefert zusätzlich einen aufgelösten Test-Navigationstreffer. Dieser Treffer wird nicht als direkt geänderter Test ausgegeben.

`degraded` bedeutet in den drei Goldfällen Budgeterschöpfung in nachrangigen Lanes. `impact_context_blocked` tritt in keinem Fall auf. Der kontrollierte Livefall ist `available` und hat keine ausgelösten Stop-Kriterien. Er ist der sauberste einzelne Lauf, ersetzt wegen seines kleineren Änderungsschnitts aber nicht die drei domänenspezifischen Goldfälle.

## Retrieval-Lane-Wahrheit

Der optionale Python-Call-Graph ist vorhanden:

- Größe: `22.437.645` Byte
- SHA-256: `c9256ca8bd55a567d0e9a6d1fc6b0b44872c5476d2819674e331a90ffe94613b`

Seine bloße Existenz zählt nicht als Nutzung:

- **DB/Auth:** keine ausgelieferte kohärente Call-Graph-Relation → `call_graph=skipped`.
- **Web/Karte:** keine ausgelieferte kohärente Call-Graph-Relation → `call_graph=skipped`.
- **Deployment/Kubernetes:** eine provenance-gebundene kohärente Call-Graph-Relation innerhalb der Contract-Tests wird ausgeliefert → `call_graph=used`.
- **Kontrollierter Livefall:** keine konsumierte Call-Graph-Relation → `call_graph=skipped`.

Damit gilt weiter: Eine Retrieval-Lane ist nur benutzt, wenn ihre vertrauenswürdige Evidenz tatsächlich im ausgelieferten Kontext vorkommt.

## Evidenzgebundene Delivery Chain

Der Deployment-Goldfall bindet die Änderung selbst, direkte Pfade, einen geänderten Testpfad, 8 Zielsymbole, einen gemeldeten Gesamtumfang von 7 Kausalrelationen, davon eine mit expliziter Call-Graph-Provenienz materialisierte kohärente Relation innerhalb der Contract-Tests, sowie einen Live-Range des Produktions-Reconcilers. Zusätzlich werden die bisher fehlenden operativen Glieder explizit geprüft:

- **Contract:** PR #1499; GitHub-Run `29806103267`, Job `88556854305` `Production reconciler contract tests` = `success`.
- **CI vor Merge:** Required Merge Gate Run `29805241044`, Job `88555418515` = `success`; Review Evidence Gate Run `29805240373`, Job `88556686625` = `success`.
- **Deployment:** Post-Merge-Run `29806103267` ist ein erfolgreicher `push`-Lauf auf exakt `7a1b5943524affd90b79cd8769f5e48b3f1d4b22`.
- **Ausgeführter Runtime-Readback:** Job `88556905034` `Exact main commit is live` = `success`; `Verify public frontend and API identity` = `success`; ein Produktions-Receipt wurde hochgeladen.
- **Recovery:** `docs/deploy/merge-to-live.md#L162-L171` bindet direkten Recovery-Aufruf, gemeinsame `flock`-Sperre, wirkungslose Konkurrenzablehnung und `EX_TEMPFAIL 75`.
- **Installationsschutz:** `test_installer_deferred_update_is_atomic_and_non_recursive` bindet atomare Installation sowie Erhalt des enabled/active Produktions-Timers.

Explizit modellierte Risiken sind parallele Recovery-Konkurrenz, partielle Reconciler-Installation, Verlust des Timerzustands und Post-Deploy-Supersession beziehungsweise Fehler. Die zugehörigen Mitigationen sind in der Fixture strukturiert hinterlegt.

Diese Kette belegt einen erfolgreichen exakten Produktions-Readback für den gebundenen Deploymentfall und vorhandene Recovery-Invarianten. Sie beweist **nicht** allgemeine Runtime-Korrektheit und **nicht** den Erfolg eines automatischen Rollbacks.

## Dirty-State-Grenze

Die Messungen sind revisionsgebunden. Evidence-Edits des T003-Arbeitsbranches und der fremde Dirty-Overlay des kanonischen Hauptcheckouts sind mit `included_in_revision_diff=false` ausgeschlossen. Die gespeicherten Overlay-Daten dokumentieren den Zustand zum Messzeitpunkt; der Validator fordert keinen identischen aktuellen lokalen Dirty-State eines späteren CI- oder Entwicklerlaufs. Entscheidend ist ausschließlich, dass Overlay-Inhalte nicht in die revisionsgebundenen historischen Diffs eingehen.

## Akzeptanz

- **Drei Änderungsklassen:** bestanden.
- **Kontrollierter Livefall:** bestanden und exakt an den frischen Source-Bundle-Commit gebunden.
- **Gepaarte Baseline:** bestanden; alle vier Baselines frisch und mit aufgelöster Evidenz.
- **Kompaktheit:** bestanden; alle vier Fälle liegen deutlich über 20 Prozent Reduktion.
- **Direktpfadabdeckung:** bestanden; 100 Prozent in jedem Fall.
- **Testpfad-Evidenz:** alle drei Goldfälle enthalten direkt diff-gebundene geänderte Testpfade; der Livefall besitzt zusätzlich einen aufgelösten Test-Navigationstreffer. Dies ist kein Beweis vollständiger automatischer Related-Test-Ermittlung.
- **Diff-Bindung und Frische:** bestanden.
- **Retrieval-Lane-Wahrheit:** bestanden.
- **Delivery Chain:** begrenzt bestanden und explizit an Contract, CI, Deployment, Runtime-Readback und Recovery/Risikoevidenz gebunden.
- **Promotion-Gate:** bestanden.

Der Validator berechnet die promotionsrelevanten Truth-, Acceptance- und Delivery-Gates aus der Detail-Evidenz neu. Deklarierte PASS-Zustände können einen gebrochenen Detailbeleg nicht überstimmen. Fehlt der kontrollierte Livefall oder einer der Pflichtbelege für Contract, CI, Deployment, Runtime-Readback, Recovery oder Rückfallrisiken, kann `promote_default` nicht bestehen.

## Promotion

**Empfehlung: begrenzte Default-Promotion für den gemessenen `change_impact`-Handoff.**

Der maschinenlesbare Scope bleibt `bounded_change_impact_context_for_agent_handoff`. Gilt, wenn Budget-Degradierung nicht als Vollständigkeit interpretiert wird und die bestehenden `does_not_establish`-Grenzen erhalten bleiben. Die Promotion autorisiert weder Merge noch Deployment und ersetzt keine Tests, Reviews oder Recovery-Verfahren.

## Nicht bewiesen

- semantische Vollständigkeit der Capsule
- vollständige automatische Related-Test-Ermittlung
- vollständige automatische Symbol-Impact-Ermittlung
- vollständige Architektur- oder Kausalabdeckung
- Patch-Korrektheit
- Test-Suffizienz oder vollständige Testabdeckung
- Review-Vollständigkeit
- Merge-Reife
- allgemeine Runtime-Korrektheit
- automatisch erfolgreicher Rollback
- Regressionsfreiheit
- globale RepoGround-Routing-Autorität außerhalb des gemessenen `change_impact`-Handoff-Pfads

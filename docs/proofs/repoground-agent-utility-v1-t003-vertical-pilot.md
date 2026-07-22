---
id: docs.proofs.repoground-agent-utility-v1-t003-vertical-pilot
title: RepoGround Agent Utility V1 T003 Vertical Pilot
doc_type: proof
status: active
summary: Revisionsgebundene Neumessung mit drei vollständigen Goldfällen und einem budgetbegrenzten kontrollierten Livefall für den RepoGround-change-impact-Handoff; Pilot-Delivery-Evidenz und aktueller T003-PR-Delivery-State sind ausdrücklich getrennt.
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

Die Promotion gilt ausschließlich für `bounded_change_impact_context_for_agent_handoff`. Sie ersetzt weder Tests noch Review, Deployment-Gates oder Recovery-Verfahren. Die drei Goldfälle liefern alle revisionsgebundenen Direktänderungen aus. Der kontrollierte Livefall prüft dagegen bei einem größeren Diff Frische **zum Messzeitpunkt**, Diff-Bindung, deterministische Budgetbegrenzung und Regressionen; er erhebt ausdrücklich **keinen** Anspruch auf vollständige Direktpfadauslieferung.

## Warum erneut gemessen wurde

Der historische Pilot aus PR #1520 hielt die Promotion wegen eines damals blockierenden übergroßen Python-Call-Graphs zurück. Dieser Zustand ist überholt:

- RepoGround PR #1070 machte den optionalen Call-Graph degradierbar statt Core-Impact-blockierend.
- Grabowski T006 PR #351 korrigierte die Call-Graph-Lane-Wahrheit.
- Grabowski-Härtung PR #356 bindet Retrieval-Lanes an tatsächlich ausgelieferte Evidenz.
- RepoGround PR #1075 diversifizierte die begrenzte Target-Symbol-Auswahl über geänderte Python-Pfade.
- RepoGround PR #1076 härtete exakte Target-Symbol-Treffer pro Pfad und schloss den verbliebenen Starvation-Randfall.
- Der gemessene RepoGround-Generator `dea8e61ace8bc45a32ec32bff3f79eccaa9c9f19` enthält den heute verwendeten Runtime-Stand.

Methodisch schwache Baselines mit null aufgelösten Treffern wurden verworfen. Jeder hier akzeptierte Fall besitzt eine frisch aufgelöste gepaarte Baseline.

## Gebundene Identitäten

- Weltgewebe-Publikationscommit: `e14944fb149c0b66b8a1ca4e1e1b26a8603c5067`
- RepoGround-Bundle: `heimgewebe__weltgewebe__main-max-260722-1548`
- Bundle-Manifest SHA-256: `04e84e1af3bf9a52b30fe412549fcb0bf5663967a3c85fb890c01c16a67f1b92`
- Frische-Evidenz: Publisher-Source-Commit und beobachteter `origin/main`-Commit waren beim Readback `2026-07-22T16:07:36Z` identisch mit `e14944fb149c0b66b8a1ca4e1e1b26a8603c5067`; Publisher-State SHA-256 `86351444ebafea5b9673924f26777248980ebac34833fd6a3efc08dc8a2ee882`.
- Post-Emit-Health: `pass`
- Output-Health: `pass`
- Bundle-Surface-Validation: `pass`
- RepoGround-Generator: `dea8e61ace8bc45a32ec32bff3f79eccaa9c9f19`
- Grabowski-Runtime: `acf29382784c1541b930b8068c58aac4497da5e4`
- Capsule-Budget: `12000` Byte

Alle vier Fälle sind an `git_tree_delta_v1`-Digests gebunden. Eine falsche Diff-Identität bricht fail-closed ab. Der kontrollierte Livefall bindet sein Ziel exakt an den Source-Bundle-Commit, der beim eingefrorenen Mess-Readback frisch gegen `origin/main` war.

## Drei Goldfälle plus kontrollierter Livefall

| Klasse | Basis → Ziel | Baseline | Capsule | Reduktion | Direktänderungen | Related Tests | Call-Graph | Status |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| DB/Auth | `691f663a…` → `4b9b0507…` | 34.306 B | 8.478 B | 75,287 % | 14/14 ausgeliefert | 5/5 geänderte Testpfade | skipped | degraded: nur `query_snippets` |
| Web/Karte | `c18ef20b…` → `d7c1fb9c…` | 43.206 B | 11.716 B | 72,883 % | 4/4 ausgeliefert | 2/2 geänderte Testpfade | skipped | degraded: nur `query_snippets` |
| Deployment/Kubernetes | `5d11513e…` → `7a1b5943…` | 34.369 B | 11.998 B | 65,091 % | 9/9 ausgeliefert | 1/1 geänderter Testpfad | 1 kohärente Contract-Test-Relation | degraded: policy- und budgetbegrenzt |
| Kontrollierter Livefall | `0cd3699c…` → `e14944fb…` | 51.900 B | 11.993 B | 76,892 % | 16/95 ausgeliefert; 79 policy-omitted | 8/34 ausgeliefert; 26 policy-omitted | skipped | degraded: policy- und budgetbegrenzt |

Die drei Goldfälle decken `database_auth`, `web_map` und `deployment_kubernetes` ab. In ihnen gilt `delivery_completeness_required=true`; alle revisionsgebundenen Direktänderungen wurden ausgeliefert und jeder Goldfall enthält mindestens einen direkt diff-gebundenen geänderten Testpfad.

Der kontrollierte Livefall verwendet die Query `guest`. Seine gepaarte Baseline enthält 5 Snippets, 5 Bereiche und 5 Zitate mit `resolved_evidence_status=available`. Der kanonische Revisionsdigest lautet `587369a65eb6b98fe70c13752f5fad95b71228b2475e2674e1e4eb741979c158`.

Für diesen Livefall gilt `delivery_completeness_required=false`: Der Revisionsdiff kennt 95 Direktänderungen, die Capsule berücksichtigt wegen des deterministischen Lane-Caps 16 davon und liefert diese 16 aus; 79 werden als `policy_omitted` ausgewiesen. Entsprechend wird keine `critical_path_coverage=1.0` behauptet. Das Modell trennt damit die vollständige Revisionsinventarisierung von der tatsächlich ausgelieferten, budgetbegrenzten Capsule.

`controlled_live` bedeutet hier **live gemessen und danach revisionsgebunden eingefroren**, nicht „muss für immer dem jeweils neuesten `main` entsprechen“. Ein späterer Main-Commit widerlegt die dokumentierte Frische zum Messzeitpunkt nicht. Eine zusätzliche „ist beim Merge immer noch aktuell?“-Prüfung ist dynamische CI-/Runtime-Evidenz und gehört in einen separaten Online-Validator; sie wird nicht durch fortlaufendes Umschreiben der kanonischen Fixture simuliert.

Auch die Test- und Symbol-Lanes sind im Livefall sichtbar begrenzt: 34 Related Tests sind verfügbar, 8 werden ausgeliefert; 11 Zielsymbole sind verfügbar, 8 werden ausgeliefert. Die ausgelieferten Related Tests sind echte `changed_test_path`-Belege mit `direct_diff`-Provenienz, keine bloßen Navigationstreffer.

Policy-Begrenzung und Budgetdegradierung sind getrennt modelliert. DB/Auth und Web/Karte sind nicht policy-begrenzt und erschöpfen nur `query_snippets`. Beim Deployment begrenzt die Sampling-Policy `target_symbols` und `causal_relations`; zusätzlich erschöpft das Byte-Budget `causal_relations`, `live_ranges`, `citations`, `entry_manifest` und `query_snippets`. Im Livefall begrenzt die Policy `direct_changes`, `related_tests` und `target_symbols`; das Byte-Budget erschöpft anschließend `live_ranges`, `citations`, `entry_manifest` und `query_snippets`. Für jede beobachtete Lane gilt rechnerisch `policy_omitted = available - considered` und `budget_omitted = considered - included`. Ob erforderliche Evidenz fehlt, wird nicht durch ein gespeichertes `required_lane_loss`-Urteil behauptet, sondern aus den konkreten Goldfall-, Direktänderungs-, Related-Test- und Lane-Regeln berechnet. `impact_context_blocked` tritt in keinem Fall auf.

## Retrieval-Lane-Wahrheit

Der optionale Python-Call-Graph ist vorhanden:

- Größe: `22.485.322` Byte
- SHA-256: `6e5292dd074e6d5e44b9588c1438f9c2acf23b9f7e0836787d64efc45fa476b9`

Seine bloße Existenz zählt nicht als Nutzung:

- **DB/Auth:** keine ausgelieferte kohärente Call-Graph-Relation → `call_graph=skipped`.
- **Web/Karte:** keine ausgelieferte kohärente Call-Graph-Relation → `call_graph=skipped`.
- **Deployment/Kubernetes:** eine provenance-gebundene kohärente Call-Graph-Relation innerhalb der Contract-Tests wird ausgeliefert → `call_graph=used`.
- **Kontrollierter Livefall:** keine konsumierte kohärente Call-Graph-Relation → `call_graph=skipped`.

Damit gilt weiter: Eine Retrieval-Lane ist nur benutzt, wenn ihre vertrauenswürdige Evidenz tatsächlich im ausgelieferten Kontext vorkommt.

## Historische `pilot_delivery_chain_evidence`

Die in der Fixture so benannte `pilot_delivery_chain_evidence` gehört ausschließlich zum Deployment-Goldfall. Sie belegt den historischen Nutzen des RepoGround-Kontexts entlang eines real ausgeführten Deploymentpfads. Sie ist **keine** Freigabe des aktuellen T003-PR.

Der Deployment-Goldfall bindet die Änderung selbst, direkte Pfade, einen geänderten Testpfad, 8 Zielsymbole, einen gemeldeten Gesamtumfang von 7 Kausalrelationen, davon eine mit expliziter Call-Graph-Provenienz materialisierte kohärente Relation innerhalb der Contract-Tests, sowie einen Live-Range des Produktions-Reconcilers. Zusätzlich werden die operativen Glieder strukturell und untereinander gebunden:

- **Contract:** PR #1499, PR-Head `c6d7bbc2dbec97ee0223a9c22cd1e331b7a21993`; GitHub-Run `29806103267`, Job `88556854305` `Production reconciler contract tests` = `success`.
- **CI vor Merge:** Required Merge Gate Run `29805241044`, Job `88555418515` = `success`; Review Evidence Gate Run `29805240373`, Job `88556686625` = `success`; beide binden den PR-Head `c6d7bbc2…`.
- **Deployment:** Post-Merge-Run `29806103267` ist ein erfolgreicher `push`-Lauf auf exakt `7a1b5943524affd90b79cd8769f5e48b3f1d4b22`.
- **Ausgeführter Runtime-Readback:** Job `88556905034` `Exact main commit is live` = `success`; `Verify public frontend and API identity` = `success`.
- **Produktions-Receipt:** GitHub-Artefakt `8485749581`, Name `production-live-7a1b5943524affd90b79cd8769f5e48b3f1d4b22`, Digest `sha256:c253bacc2bcb0791edbbb820959b10a6f124b60587254c73d5baa64de2687996`, gebunden an denselben Deployment-Commit und Workflow-Run.
- **Recovery:** `docs/deploy/merge-to-live.md#L162-L171` bindet direkten Recovery-Aufruf, gemeinsame `flock`-Sperre, wirkungslose Konkurrenzablehnung und `EX_TEMPFAIL 75`.
- **Installationsschutz:** `test_installer_deferred_update_is_atomic_and_non_recursive` bindet atomare Installation sowie Erhalt des enabled/active Produktions-Timers.

Die genannten PR-, Run-, Job- und Artefaktidentitäten wurden bei dieser Härtung gegen GitHub live gelesen. Der lokale Fixture-Validator prüft ihre Form und ihre gegenseitige Commit-/PR-/Run-Bindung fail-closed; er fragt GitHub derzeit **nicht selbst** erneut ab. Ein separater Live-/CI-Evidence-Validator mit content-addressed Receipt bleibt deshalb ein sinnvoller weiterer Härtungsschritt.

Diese Kette belegt einen erfolgreichen exakten Produktions-Readback für den gebundenen historischen Deploymentfall und vorhandene Recovery-Invarianten. Sie beweist **nicht** allgemeine Runtime-Korrektheit und **nicht** den Erfolg eines automatischen Rollbacks.

## Aktueller `t003_pr_delivery_state`

Der aktuelle Delivery-State von PR #1533 wird bewusst **nicht** aus `pilot_delivery_chain_evidence` abgeleitet. Er muss separat und auf dem jeweils neuesten PR-Head durch aktuelle CI, Diff-Identität, Review-Evidenz und die geltenden Merge-Gates belegt werden.

Daraus folgt: Selbst eine vollständig gültige `pilot_delivery_chain_evidence` und ein vom Validator berechnetes `promotion_ready=true` für den gemessenen Handoff bedeuten nicht, dass PR #1533 mergefähig oder mergefreigegeben ist. Jede Änderung an Fixture, Validator, Tests oder Proof erzeugt einen neuen PR-Head und macht ältere headgebundene Reviews für den Merge unbrauchbar.

## Dirty-State-Grenze

Die Messungen sind revisionsgebunden. Der verwendete RepoGround-Publikationscheckout war beim finalen 15:48-Lauf sauber und stand exakt auf `e14944fb149c0b66b8a1ca4e1e1b26a8603c5067`. `included_in_revision_diff=false` wird sowohl für den Messcheckout als auch pro Fall explizit geprüft.

Historische oder fremde Dirty-States sind keine dauerhafte Eigenschaft des Promotionsvertrags. Entscheidend ist ausschließlich, dass ein Dirty-Overlay niemals in den revisionsgebundenen Diff einfließt. Der Validator blockiert deshalb auch dann, wenn ein einzelner Fall `included_in_revision_diff=true` behauptet.

## Akzeptanz

- **Drei Änderungsklassen:** bestanden.
- **Kontrollierter Livefall:** bestanden und exakt an den frischen Source-Bundle-Commit gebunden.
- **Gepaarte Baseline:** bestanden; alle vier Baselines frisch und mit aufgelöster Evidenz.
- **Kompaktheit:** bestanden; alle vier Fälle liegen deutlich über 20 Prozent Reduktion.
- **Goldfall-Direktpfadabdeckung:** bestanden; 100 Prozent in allen drei Goldfällen.
- **Livefall-Budgetierung:** bestanden; 95 Direktänderungen inventarisiert, 16 deterministisch berücksichtigt und ausgeliefert, 79 explizit `policy_omitted`; keine Vollständigkeitsbehauptung.
- **Testpfad-Evidenz:** alle drei Goldfälle und der eingefrorene Livefall enthalten direkt diff-gebundene geänderte Testpfade; dies ist kein Beweis vollständiger automatischer Related-Test-Ermittlung.
- **Diff-Bindung und Frische:** bestanden.
- **Retrieval-Lane-Wahrheit:** bestanden.
- **Pilot-Delivery-Evidenz:** begrenzt bestanden und explizit an Contract, CI, Deployment, Runtime-Readback, Produktions-Receipt und Recovery/Risikoevidenz gebunden.
- **Promotion-Gate für den gemessenen Handoff:** bestanden.

Der Validator berechnet die promotionsrelevanten Truth-, Kompaktheits-, Qualitäts- und Delivery-Gates ausschließlich aus der Detail-Evidenz. Die Fixture enthält keine manuellen Verdict-Felder wie `truth_gate.passed`, `acceptance`, `mechanical_promotion_gate`, `overall_status` oder `promotion_recommendation`. Zusätzlich gilt fail-closed: Jeder Validierungsfehler setzt den berechneten Promotionszustand auf `promotion_ready=false`, auch wenn eine neu hinzugefügte Einzelprüfung versehentlich keinem separaten Gate-Bool zugeordnet wurde.

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
- automatische Online-Validierung der GitHub-Run-/Job-/Artefaktidentitäten durch den lokalen Fixture-Validator
- globale RepoGround-Routing-Autorität außerhalb des gemessenen `change_impact`-Handoff-Pfads

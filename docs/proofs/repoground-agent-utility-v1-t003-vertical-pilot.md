---
id: docs.proofs.repoground-agent-utility-v1-t003-vertical-pilot
title: RepoGround Agent Utility V1 T003 Vertical Pilot
doc_type: proof
status: active
summary: Revisionsgebundener Weltgewebe-Pilot nach T007; der Kompaktheits-Gate besteht und der große Call-Graph ist begrenzt nutzbar, die Default-Promotion bleibt wegen fehlender Contract-, Runtime-Proof- und Rollback-Evidenz blockiert.
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

Dieser Proof misst eine RepoGround Change Capsule gegen denselben Grabowski-/RepoGround-Kontextweg ohne Capsule. Er verändert weder Produktion noch Compose- oder Kubernetes-Runtime.

Die Baseline ist `repoground_context_pack`; die Capsule ist `repoground_context_compose`. Beide verwenden je Fall dieselbe Query und das Task-Profil `change_impact`. Die Capsule ist zusätzlich an exakte Basis-/Ziel-Commits und den daraus berechneten `git_tree_delta_v1`-SHA-256 gebunden.

Diese Nachmessung wurde nach den T007-Härtungen für großen Call-Graph-Zugriff, begrenzte Relationsquellen und evidenzgebundene `related_tests` ausgeführt.

## Gebundene Identitäten

- Weltgewebe-`main` beim Messlauf: `2959e2725c3b2e27e7d1b97f7040aac205d103f7`
- RepoGround-Bundle: `heimgewebe__weltgewebe__main-max-260721-2115`
- Bundle-Manifest SHA-256: `03d811956a34e1f925075fe69f4accd730711b8df047db64fe0393cf1d4e8b30`
- Bundle-Frische beim Lauf: `fresh_exact`
- RepoGround-Generator-Commit: `733443de4aa63d5d2480e6c3fade469ba3303b34`
- Gemessene Grabowski-Runtime: `1d37e67a6f3f2270a8e754a6d25a809448a0e2de`
- Kontextbudget der Capsule: `12000` Byte
- Rohmessung SHA-256: `0bc11f61085410b0d46256b59ed12e45be8b65e633c30b734654a195e0b90567`
- Maschinenlesbare Evidenz: `scripts/ci/fixtures/repoground_vertical_pilot.v1.json`

## Goldfälle und kontrollierter Livefall

| Profil | Referenz | Baseline | Capsule | Reduktion | Kritische Direktpfade | Status |
|---|---|---:|---:|---:|---:|---|
| Datenbank/Auth | PR #1295, PostgreSQL Passkey Store | 16.359 B | 6.377 B | 61,018 % | 5/5 | available |
| Web/Karte | PR #1514, Map Fan Surfaces | 7.759 B | 1.446 B | 81,364 % | 3/3 | available |
| Deployment/Kubernetes | PR #1458, exakte Workflow-Proof-Bindung | 7.819 B | 5.207 B | 33,406 % | 5/5 | degraded: budget only |
| kontrolliert live | `6dd58674…` → `2959e272…`, aktuelle Kartenänderungen | 7.759 B | 1.804 B | 76,750 % | 7/7 | available |

Alle vier Fälle sind diff-gebunden und nutzen eine frische RepoGround-Publikation. Die vorher festgelegten kritischen Direktpfade bleiben vollständig enthalten. Die mechanische T003-Schwelle von mindestens 20 Prozent Kontextreduktion in mindestens zwei Goldfällen wird in allen drei Goldfällen erreicht.

Die Capsule ist weiterhin langsamer zu erzeugen als das allgemeine Kontextpaket; der gemessene Nutzen liegt in der Kontextverdichtung, nicht in geringerer Berechnungszeit.

## T007-Nachweis: großer Call-Graph ist begrenzt nutzbar

Der aktuelle Weltgewebe-Call-Graph ist weiterhin größer als die frühere sichere Vollartefakt-Lesegrenze:

- Artefaktrolle: `python_call_graph_json`
- Artefaktgröße: `22.411.587` Byte
- frühere Read-only-Grenze: `16.777.216` Byte (16 MiB)
- Überschreitung: `5.634.371` Byte
- Artefakt-SHA-256: `96e213bddb538ca0ae183879ec3924d356fb08d5172b9be2653af5eab15e3c30`

Trotz dieser Größe tritt in keinem der vier Pilotfälle `artifact_too_large` auf. Der Zugriff bleibt begrenzt und hash-/manifestgebunden. Der Deployment/Kubernetes-Fall liefert sechs Ziel-Symbole. Reine Namensvermutungen werden nicht mehr als `related_tests` ausgegeben; der Heuristikzähler ist in allen vier Fällen null.

Damit ist der frühere T007-Skalierungsblocker für diesen Größenbereich beseitigt. Das beweist jedoch weder vollständige Call-Graph-Abdeckung noch, dass jeder Änderungstyp Call-Graph-Evidenz haben muss.

## Verbleibende Delivery-Chain-Lücke

T003 fordert mehr als Kompaktheit. Die Capsule soll Änderung, betroffene Pfade/Symbole, Tests, Contracts, CI, Deployment, Runtime-Proof und Rückfallrisiken verbinden, ohne Repository- und Runtime-Wahrheit zu vermischen.

**Belegt:**

- exakte Änderungsidentität und Diff-Bindung;
- 100 Prozent Abdeckung der vorab festgelegten kritischen Direktpfade;
- reale Testdateien in den gewählten Goldfällen;
- CI- und Deployment-Oberflächen in den revisionsgebundenen Änderungen;
- Ziel-Symbole im Python-basierten Deployment/Kubernetes-Fall;
- frische RepoGround-Publikation und bestandene Bundle-Gates;
- keine erneute `artifact_too_large`-Lücke;
- keine heuristischen `related_tests`.

**Noch nicht durch die Capsule etabliert:**

- eine explizite Kette zu normativen Contracts;
- ein ausgeführter Runtime-Proof;
- evidenzgebundene Rückfall-, Recovery- oder Rollback-Risiken.

Ein Workflow, Runbook oder Proof-Dokument im Repository ist Repository-Wahrheit. Seine bloße Auffindbarkeit beweist nicht, dass ein Runtime-Proof tatsächlich ausgeführt wurde. Diese Trennung bleibt absichtlich erhalten.

## Bewertung der T003-Akzeptanz

- **Drei Änderungsklassen:** bestanden.
- **Gepaarte Baseline:** bestanden.
- **Qualität/Freshness:** bestanden innerhalb der expliziten Nicht-Vollständigkeitsgrenzen; kritische Direktpfade 100 %, Diff-Bindung verifiziert, Bundle-Frische `fresh`.
- **Mechanischer Promotion-Gate:** bestanden; alle drei Goldfälle reduzieren den Kontext um mindestens 20 Prozent.
- **Delivery Chain:** **blockiert**. Contract-Evidenz, ausgeführter Runtime-Proof und Rollback-/Risikoevidenz sind noch nicht durch die Capsule verbunden.
- **Delivery/PR/CI:** wird für diesen Proof-Branch separat an Head, Diff, Review und CI gebunden; selbst ein erfolgreicher Merge autorisiert keine Default-Promotion.

## Entscheidung

**Default-Promotion wird zurückgehalten.**

T007 ist technisch wirksam: Der 22,4-MB-Call-Graph blockiert den Pilot nicht mehr, und unbelegte Testpfade werden nicht mehr als verwandte Tests ausgegeben. T003 bleibt dennoch blockiert, weil die geforderte Delivery Chain noch nicht vollständig belegt ist.

Der nächste Schritt ist deshalb kein breiter Plattformausbau, sondern ein enger Folgeschnitt für Contract-, ausgeführte Runtime-Proof- und Rollback-/Risikoevidenz. Erst danach darf T003 erneut über Abschluss und eine mögliche Phase-3-Generalisation entscheiden.

## Nicht bewiesen

- semantische Vollständigkeit der Capsule
- automatische Test-Suffizienz
- vollständige Symbol- oder Call-Graph-Abdeckung
- Runtime-Korrektheit oder tatsächlich ausgeführter Runtime-Proof allein aus Repository-Artefakten
- Rollback-Sicherheit
- Patch-Korrektheit oder Merge-Reife einer beliebigen Änderung
- Berechtigung, RepoGround standardmäßig zu routen
- Berechtigung, Phase 3 allein aufgrund der Kontextreduktion zu starten

---
id: proofs.weltgewebe-os-v1-t036-documentation-drift-reconciliation
title: WELTGEWEBE-OS-V1-T036 Dokumentationsdrift-Reconciliation
doc_type: proof
status: active
summary: Revisionsgebundene Einzeldisposition aller 52 historischen Ox-Dokumentationsdrift-Findings gegen den aktuellen Ausgangshead und ihre T036-Bereinigung.
relations:
  - type: relates_to
    target: docs/roadmap.md
---

# WELTGEWEBE-OS-V1-T036 — Dokumentationsdrift-Reconciliation

## Bindung und Semantik

Dieser Nachweis reconciliert das historische Ox-/Bestandsinventar **einzeln** gegen
den exakt geprüften Ausgangshead
`e34a27a160a37b86e06ba906e320ff24e871db0d` vom 24. August 2026.

Das historische Inventar ist Recovery-Evidenz, keine heutige Wahrheit. Seine
Identität ist durch Audit-Head `39d5a8f5fa637ba9f8a487074c86856e6a6b897c`
und SHA-256
`56e4a159d8b3dc79d6275ac46248f845337dbbe124b9f26f695a6a9ccfff8c0b`
gebunden. Die byte-identische historische Inventarquelle ist dauerhaft unter
`docs/proofs/sources/weltgewebe-os-v1-t036-documentation-drift-audit.json`
versioniert; Tests binden ihre 52 IDs und P1/P2-Schweregrade an die Tabelle unten.
Die damalige Aggregation lautete 11 P1 + 41 P2; sie wird hier nicht ungeprüft
fortgeschrieben.

**Disposition** bezeichnet den Zustand auf dem Ausgangshead vor der T036-
Bereinigung:

- **weiterhin gültig** — der Altbefund war auf dem Ausgangshead materiell noch
  wahr und brauchte T036-Remediation;
- **bereits behoben** — die Ursache war vor T036 auf `main` bereits korrigiert;
- **superseded** — die betroffene Quelle war bereits ausdrücklich
  deprecated/superseded und damit keine aktive Statuswahrheit mehr;
- **falsch-positiv** — der Altbefund verwechselte etwa dokument-relative,
  externe commitgebundene, historische, verbotene oder ausdrücklich geplante
  Ziele mit aktuellen lokalen Pfad-/Statusbehauptungen.

## Abgeleitete Matrix

| historisch | aktuell gültig | behoben | superseded | false positive |
|---:|---:|---:|---:|---:|
| 52 | 16 | 5 | 8 | 23 |

Die Summe der vier Dispositionsklassen ist 52. Die Zahlen werden ausschließlich
aus den 52 Tabellenzeilen unten abgeleitet.

## Einzeldisposition DRIFT-001 bis DRIFT-052

| ID | Sev. | Disposition | aktuelle Primärevidenz / Begründung | T036-Remediation |
|---|---|---|---|---|
| DRIFT-001 | P1 | weiterhin gültig | `docs/runbook.md` nannte den Release-Zustand repoähnlich; `scripts/ops/install-web-artifact.sh` setzt den Default tatsächlich auf den absoluten Runtime-Pfad `/opt/weltgewebe/apps/web/releases`. | Runbook bindet die Aussage jetzt an `WEB_RELEASES_DIR` und den absoluten Runtime-Pfad. |
| DRIFT-002 | P1 | falsch-positiv | Der Link `deploy/README.md` in `docs/runbook.md` ist dokument-relativ und löst nach `docs/deploy/README.md` auf. | Keine Inhaltsmutation. Der bestehende Link-Resolver bleibt dokument-relativ. |
| DRIFT-003 | P1 | falsch-positiv | Der Link `deploy/vps-db-initialization-boundary.md` in `docs/runbook.md` löst dokument-relativ nach `docs/deploy/vps-db-initialization-boundary.md` auf. | Keine Inhaltsmutation. |
| DRIFT-004 | P1 | falsch-positiv | Der Link `deploy/vps.md` in `docs/runbook.md` löst dokument-relativ nach `docs/deploy/vps.md` auf. | Keine Inhaltsmutation. |
| DRIFT-005 | P1 | bereits behoben | `CONTRIBUTING.md` kennzeichnet die Worker-Zielstruktur inzwischen ausdrücklich als noch nicht reale Repositorystruktur. | Keine erneute Umschreibung. |
| DRIFT-006 | P1 | bereits behoben | `CONTRIBUTING.md` kennzeichnet die Search-Zielstruktur inzwischen ausdrücklich als Zielbild und nicht als vorhandenen Pfad. | Keine erneute Umschreibung. |
| DRIFT-007 | P1 | bereits behoben | `CONTRIBUTING.md` trennt die Domain-/Repo-/Events-Unterstruktur inzwischen ausdrücklich als Zielmodell von der aktuellen realen Struktur. | Keine erneute Umschreibung. |
| DRIFT-008 | P1 | falsch-positiv | Die Deploy-Links in `docs/index.md` sind dokument-relativ zu `docs/` und ihre Ziele existieren. | Keine Inhaltsmutation. |
| DRIFT-009 | P1 | falsch-positiv | Die Runbook-Links in `docs/index.md` sind dokument-relativ und ihre Ziele unter `docs/runbooks/` existieren. | Keine Inhaltsmutation. |
| DRIFT-010 | P1 | bereits behoben | Der veraltete Convergence-HEAD wurde vor T036 durch Commit `579d7ef` auf den damaligen aktuellen Protokollhead rebasiert. | Keine historische Rebase-Aussage erneut verändern. |
| DRIFT-011 | P1 | bereits behoben | Das zugehörige JSON-/Beispiel-HEAD wurde im selben Convergence-Fix vor T036 korrigiert. | Keine erneute Umschreibung. |
| DRIFT-012 | P2 | weiterhin gültig | `docs/reports/domain-account-write-path-proof.md` war auf dem Ausgangshead aktiv und sein `review_after: 2026-07-16` war am 24.08.2026 fällig. | Als deprecated/archived markiert, `review_after` entfernt und sichtbarer Point-in-Time-Hinweis ergänzt; historische Aussagen bleiben unverändert. |
| DRIFT-013 | P2 | weiterhin gültig | `docs/reports/auth-persistence-runtime-target-reconciliation.md` war aktiv und mit `review_after: 2026-08-22` fällig; sein Heimserver-Runtime-Slice ist keine heutige Produktionswahrheit mehr. | Als deprecated/archived Point-in-Time-Abgleich markiert; ADR-0007 bleibt normative Gegenwartsquelle, Runtime muss frisch gelesen werden. |
| DRIFT-014 | P2 | weiterhin gültig | `docs/reports/domain-backfill-proof.md` war aktiv und mit `review_after: 2026-07-16` fällig. | Als deprecated/archived Point-in-Time-Beleg markiert; historischer Inhalt bleibt unverändert. |
| DRIFT-015 | P2 | superseded | `docs/reports/domain-edge-write-path-proof.md` war bereits deprecated und `lifecycle_state: superseded`; Nachfolger ist der Faden-Lifecycle-Proof. | Keine Reaktivierung durch altes Reviewdatum. Der neue Lifecycle-Check ignoriert retired/superseded Dokumente. |
| DRIFT-016 | P2 | weiterhin gültig | `docs/reports/domain-read-path-proof.md` war aktiv und mit `review_after: 2026-07-16` fällig. | Als deprecated/archived Point-in-Time-Beleg markiert. |
| DRIFT-017 | P2 | weiterhin gültig | `docs/reports/domain-account-email-uniqueness-audit.md` war aktiv und mit `review_after: 2026-07-13` fällig. | Als deprecated/archived Point-in-Time-Beleg markiert. |
| DRIFT-018 | P2 | weiterhin gültig | `docs/reports/domain-node-write-path-proof.md` war aktiv und mit `review_after: 2026-07-16` fällig. | Als deprecated/archived Point-in-Time-Beleg markiert. |
| DRIFT-019 | P2 | weiterhin gültig | `docs/reports/domain-edge-reference-audit.md` war aktiv und mit `review_after: 2026-07-16` fällig. | Als deprecated/archived Point-in-Time-Beleg markiert. |
| DRIFT-020 | P2 | superseded | Die UI-Blueprint-Quelle des ActionBar-Befunds ist bereits deprecated und damit keine aktive Implementierungswahrheit. | Keine historische Blueprint-Umschreibung. |
| DRIFT-021 | P2 | superseded | Die Kartenklarheit-Quelle für den alten load.ts-Befund ist bereits deprecated. | Keine Mutation. |
| DRIFT-022 | P2 | superseded | Die Kartenklarheit-Quelle für den alten scene.types-Befund ist bereits deprecated. | Keine Mutation. |
| DRIFT-023 | P2 | superseded | Die Kartenklarheit-Quelle für den alten MapDiagnostics-Befund ist bereits deprecated. | Keine Mutation. |
| DRIFT-024 | P2 | falsch-positiv | `docs/blueprints/blueprint-agent-safety-control-layer.md` ist Draft; die betroffene Stelle beschreibt ausdrücklich neue/geänderte Artefakte einer geplanten Welle. | Keine geplante Datei als aktuelle Wahrheit erfinden. |
| DRIFT-025 | P2 | falsch-positiv | Dieselbe Draft-/Plan-Semantik wie DRIFT-024. | Keine Mutation. |
| DRIFT-026 | P2 | falsch-positiv | Dieselbe Draft-/Plan-Semantik wie DRIFT-024. | Keine Mutation. |
| DRIFT-027 | P2 | falsch-positiv | Dieselbe Draft-/Plan-Semantik wie DRIFT-024. | Keine Mutation. |
| DRIFT-028 | P2 | falsch-positiv | Dieselbe Draft-/Plan-Semantik wie DRIFT-024. | Keine Mutation. |
| DRIFT-029 | P2 | falsch-positiv | Dieselbe Draft-/Plan-Semantik wie DRIFT-024. | Keine Mutation. |
| DRIFT-030 | P2 | falsch-positiv | Dieselbe Draft-/Plan-Semantik wie DRIFT-024. | Keine Mutation. |
| DRIFT-031 | P2 | falsch-positiv | Dieselbe Draft-/Plan-Semantik wie DRIFT-024. | Keine Mutation. |
| DRIFT-032 | P2 | falsch-positiv | Dieselbe Draft-/Plan-Semantik wie DRIFT-024. | Keine Mutation. |
| DRIFT-033 | P2 | falsch-positiv | Dieselbe Draft-/Plan-Semantik wie DRIFT-024. | Keine Mutation. |
| DRIFT-034 | P2 | falsch-positiv | `docs/runbooks/weltgewebe-ddns-runtime-verification.md` bindet die Implementierung ausdrücklich an Fremdrepository `heimgewebe/heimserver` und Commit `15dfbd6cc1c8899ec030ac6666464db4bc132c71`; der dort genannte Installationspfad ist kein lokaler Weltgewebe-Pfad. | Inline-Pfad-Gate erkennt externe commitgebundene Evidenz als legitimen Sonderfall. |
| DRIFT-035 | P2 | falsch-positiv | Die beanstandete Pfadangabe steht im Changelog als historische Änderungsbeschreibung, nicht als aktuelle Repository-Pfadzusage. | Changelog-Klasse wird nicht als aktuelle Inline-Pfad-Wahrheit behandelt. |
| DRIFT-036 | P2 | falsch-positiv | `docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md` kennzeichnet denselben DDNS-Pfad ausdrücklich als historischen Implementierungsbesitz im Fremdrepository/Commit. | Externe commitgebundene Evidenz bleibt unverändert. |
| DRIFT-037 | P2 | superseded | Das betroffene Overview-Dokument zur Ethik ist deprecated. | Keine historische Inhaltsmutation. |
| DRIFT-038 | P2 | superseded | Das betroffene Overview-Dokument zur UX ist deprecated. | Keine historische Inhaltsmutation. |
| DRIFT-039 | P2 | superseded | Der Auth-Diagnosebericht ist deprecated und lifecycle-seitig superseded; sein Nachfolger ist `docs/reports/optimierungsstatus.md`. | Keine Reaktivierung. |
| DRIFT-040 | P2 | falsch-positiv | `docs/reports/optimierungsbericht.md` sagt ausdrücklich, dass die Worker-Spezifikation **vor** einer Implementierung erstellt werden soll; der fehlende Pfad ist Zukunftsziel, keine Ist-Behauptung. | Inline-Pfad-Gate behandelt expliziten Zukunftskontext nicht als aktuelle Pfadzusage. |
| DRIFT-041 | P2 | weiterhin gültig | `docs/reports/auth-status-matrix.md` verwies aktiv nur auf `src/lib.rs`; die reale API-Quelle liegt unter `apps/api/src/lib.rs`. | Aktive Matrix auf den vollständigen Repositorypfad korrigiert. |
| DRIFT-042 | P2 | weiterhin gültig | `docs/reports/auth-pg-002-passkey-db-store.md` nannte den Integration-Proof nur als tests-Unterpfad; die reale Datei liegt unter `apps/api/tests/`. | Pfad auf `apps/api/tests/db_passkey_store_persistence.rs` qualifiziert. |
| DRIFT-043 | P2 | falsch-positiv | `docs/reports/agent-readiness-audit.md` nennt die fehlende Policy-Datei ausdrücklich als Beispiel/Empfehlung, nicht als existierenden Beleg. | Keine Datei erfinden; zukünftiger Beispielkontext wird nicht als Ist-Pfadzusage gewertet. |
| DRIFT-044 | P2 | falsch-positiv | `platform/README.md` verwendet `apps/weltgewebe/base` dokument-relativ zu `platform/`; das reale Ziel ist `platform/apps/weltgewebe/base`. | Dokument-relative Semantik bleibt erhalten. |
| DRIFT-045 | P2 | falsch-positiv | Dasselbe gilt für die Overlays unter `platform/apps/weltgewebe/overlays`. | Keine Mutation. |
| DRIFT-046 | P2 | falsch-positiv | `architecture/semantic-search.md` nennt eine separate semantic-service-Runtime ausdrücklich als **verboten**; Nichtexistenz ist hier die gewünschte Architektur. | Keine verbotene Runtime erzeugen. |
| DRIFT-047 | P2 | weiterhin gültig | `docs/roadmap.md` verwendete `docs/reports/auth-persistence-readiness.md` als aktuellen Statusbeleg, obwohl das Report-Frontmatter deprecated/superseded ist. | Statusbeleg auf ADR-0007 und `docs/reports/optimierungsstatus.md` umgestellt. |
| DRIFT-048 | P2 | weiterhin gültig | Dieselbe aktive Roadmap-Zeile verwendete den ebenfalls deprecated/superseded Report `auth-persistence-next-step.md`. | Dieselbe Statusquellen-Korrektur wie DRIFT-047. |
| DRIFT-049 | P2 | weiterhin gültig | Die Auth-Persistenzphase in `docs/roadmap.md` führte den deprecated Runtime-Proof-Report ohne historische Kennzeichnung als Beleg. | Aktueller Status verweist auf `docs/reports/optimierungsstatus.md`; der alte Zielarchitektur-Abgleich ist ausdrücklich als archiviert gekennzeichnet. |
| DRIFT-050 | P2 | weiterhin gültig | `docs/roadmap.md` verlinkte `planning-registration-findings.md` ohne Hinweis, dass der Bericht deprecated/archived ist. | Link bleibt als Evidenz erhalten, ist nun ausdrücklich „archivierter Ausgangsbefund“. |
| DRIFT-051 | P2 | weiterhin gültig | `docs/runbooks/README.md` führte `domain-mail-cutover.md` trotz deprecated/archived Status in der Liste aktueller wiederkehrender Runbooks. | Aktive Liste verweist auf die DDNS-/Runtime-Verifikation; Domain-/Mail-Cutover steht separat unter „Historische Runbooks“. |
| DRIFT-052 | P2 | weiterhin gültig | `docs/reports/auth-status-matrix.md` präsentierte `passkey-register-verify-prep.md` als Dokumentationsbeleg, obwohl der Report deprecated/archived ist. | Aktueller Cutover-Plan ist Hauptbeleg; der alte Prep-Report ist ausdrücklich als archivierter Vorbereitungsbericht markiert. |

## Zusätzliche Current-Head-Restfunde außerhalb des historischen 52er-Inventars

Der neue Inline-Pfad-/Truth-Check wurde während T036 gegen den gesamten aktiven
Markdown-Bestand ausgeführt. Dabei wurden zusätzliche Gegenwartsdrifts sichtbar,
die im historischen Ox-Inventar nicht enthalten waren. Sie verändern die
52er-Dispositionsmatrix nicht, werden aber vor Closeout ebenfalls bereinigt:

| Restfund | Befund | Current-Head-Disposition |
|---|---|---|
| CURRENT-001 | Aktive Versionierungsgrundlage behauptete weiterhin `VersionDiagnostics.svelte`, obwohl die Diagnose heute als `/build`-Vollansicht implementiert ist. | Auf `apps/web/src/routes/build/+page.svelte` und den weiterhin gültigen Browserbeleg `apps/web/tests/version-diagnostics.spec.ts` korrigiert. |
| CURRENT-002 | `auth-status-matrix.md` verwendete die verkürzten Ist-Pfade `middleware/csrf.rs` und `routes/auth.rs`. | Auf `apps/api/src/middleware/csrf.rs` und `apps/api/src/routes/auth.rs` qualifiziert. |
| CURRENT-003 | Das aktive DB-Recovery-Runbook stellte `postgres/proofs/` wie einen lokalen Repositorypfad dar. | Laufzeit-Default `/var/backups/weltgewebe/postgres/proofs/` und `RESTORE_PROOF_DIR` explizit gemacht. |
| CURRENT-004 | `optimierungsbericht.md` führte `ci/budget.json` noch als aktuelle Budgetquelle. | Altbefund als superseded markiert; Gegenwartsquelle ist `policies/performance.v1.json`, Legacy-Rückkehr ist testseitig verboten. |
| CURRENT-005 | Derselbe Bericht behandelte `../caddy/Caddyfile.prod` pauschal als aufrufverzeichnisabhängigen Produktionsfehler. | Altprämisse als superseded markiert; reale Quelle `infra/caddy/Caddyfile.prod`, erlaubter Compose-Mount durch bestehenden Volume-Guard belegt. |
| CURRENT-006 | Der aktive Fahrplan verwendete `migrations/` ohne Repositoryqualifikation. | Auf `apps/api/migrations/` qualifiziert. |
| CURRENT-007 | Deploy-Dokumentation ließ `receipts/...` wie Repositoryinhalt erscheinen. | Als Pfad unter `$WELTGEWEBE_DEPLOY_STATE_ROOT` mit Default `/var/lib/weltgewebe-main-reconciler` gebunden. |
| CURRENT-008 | Mehrere legitime Nicht-Repo-Bezüge (Runtime-Ausgaben, Policy-Scope, Hostname-Ressourcen, geplante Ziele) erzeugten ohne Semantikgrenze False Positives. | Scanner nutzt vorhandene Gitignore-Wahrheit für unversionierte Ausgaben und eng markierte Kontextklassen; Tippfehler, unbekannte Repo-Pfade und Repository-Flucht bleiben blockierbar. |

Nach dieser Reconciliation läuft `scripts/docmeta/check_links.py` gegen den
aktiven getrackten Markdown-Bestand mit **0 Fehlern und 0 Warnungen**.

## Automatisierte Lifecycle- und Truth-Gates

T036 erweitert vorhandene Mechanismen statt eine zweite Kontrollschicht zu
bauen:

1. `scripts/docmeta/check_doc_review_age.py` prüft neben der bestehenden
   `last_reviewed`-Alterung nun jedes getrackte Markdown-Frontmatter mit
   `review_after` gegen das reale Tagesdatum; `--today` liefert einen
   deterministischen Test-/Audit-Seam.
2. Die bestehende `manifest/review-policy.yaml` bleibt Autorität: `mode: warn`
   erzeugt Sichtbarkeit ohne künstlichen Buildbruch; `strict` und `fail-closed`
   blockieren fällige aktive Reviews.
3. `deprecated`, `archived`, `obsolete`, `retired` und `superseded` werden vom
   Fälligkeitsmechanismus nicht reaktiviert.
4. `scripts/docmeta/check_links.py` behält die vorhandene dokument-relative
   Markdown-Linkprüfung und ergänzt konservative Inline-Repositorypfade für
   maschinenlesbar aktuelle Dokumente. Externe commitgebundene,
   historische/deprecated sowie ausdrücklich zukünftige/verbotene Ziele werden
   nicht in lokale Ist-Pfade umgedeutet.
5. `.github/workflows/docs-guard.yml` löst auf jedem Markdown-PR aus und führt
   über `make ci-validate` die bestehenden Docmeta-Gates aus.

## Reproduzierbare Revisionsgrenze

Der Ausgangsquellstand ist durch das im lokalen Git-Objektbestand vorhandene
Commitobjekt `e34a27a160a37b86e06ba906e320ff24e871db0d` gebunden. Dieser
Repository-Proof enthält dagegen keinen byte-gebundenen Produktions-Receipt und
trifft deshalb keine positive Aussage über den damaligen oder heutigen
Runtime-Readback. Source-Checkout, Deployment und aktive Runtime dürfen nicht
als dieselbe Identität behandelt werden; aktuelle Runtime-Wahrheit erfordert
einen frischen, separat gebundenen Beleg.

## Grenzen

Dieser PR ändert keine Produkt-, API-, Kubernetes-, Domain- oder
Deploymentarchitektur. Historische Evidenz wird nicht auf heutigen Zustand
umgeschrieben. Wenn ein zukünftiger Docmeta-Lauf einen echten Codefehler statt
einer Dokumentationsabweichung findet, gehört dieser als eigener Bureau-
Kandidat in die Code-Lane.

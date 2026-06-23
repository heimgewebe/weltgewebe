---
id: reports.report-lifecycle-restbestand-triage
title: Report Lifecycle Restbestand Triage
doc_type: report
status: deprecated
lifecycle_state: archived
lifecycle: audit
owner_task: DOCMETA-REPORT-LIFECYCLE-001
summary: >
  Archivierte Point-in-Time-Triage der acht noch nicht lifecycle-klassifizierten
  Reports für DOCMETA-REPORT-LIFECYCLE-001. Bereitet evidenzbasierte
  Backfill-Entscheidungen in kleinen Slices vor, ohne die Zielreports zu ändern.
relations:
  - type: relates_to
    target: docs/process/report-lifecycle.md
  - type: relates_to
    target: scripts/docmeta/validate_report_lifecycle.py
  - type: relates_to
    target: docs/tasks/index.json
---

# Report Lifecycle Restbestand Triage

> Diagnostischer Evidenzbericht für `DOCMETA-REPORT-LIFECYCLE-001`. **Keine
> Wahrheitsschicht.** Dies ist eine archivierte Momentaufnahme, die acht
> Backfill-Entscheidungen *vorbereitet* — sie *vollzieht* sie nicht. Die acht
> Zielreports bleiben in diesem PR unverändert. Die laufende Slice-Steuerung
> liegt in `docs/tasks/board.md` und `docs/tasks/index.json`, nicht hier.

## Lifecycle-Einordnung

Dieser Report folgt demselben Muster wie `planning-registration-findings.md`:
`status: deprecated`, `lifecycle_state: archived`, `lifecycle: audit`. Er bleibt
als historische Triage-Evidenz an seinem Pfad erhalten. Ein ablösendes
Report-Artefakt existiert nicht, daher kein `superseded_by`. Für archivierte
Reports verlangt der aktuell implementierte Validator kein `review_after`
(`scripts/docmeta/report_lifecycle_requirements.py`, `LIFECYCLE_STATE_RULES["archived"]`
= `lifecycle` + `owner_task`); es wird daher bewusst weggelassen und **nicht**
erfunden.

Dieser Report erzeugt selbst **keine** Validator-Findings: `status: deprecated`
fällt unter keine `STATUS_RULES`, und `archived` verlangt nur `lifecycle` +
`owner_task`, die beide gesetzt sind.

## Baseline (Pre-Triage)

- Repository: `heimgewebe/weltgewebe`
- Branch: `claude/keen-franklin-ublvj1`
- Baseline-SHA (Merge-Base = `origin/main`): `d0278519ad3c613da80149b78cc3964af3156650`
- Erstellungsdatum: 2026-06-22
- Quelle: `make generate` auf sauberem Baum (kein Drift), danach
  `python3 -m scripts.docmeta.validate_report_lifecycle --mode warn`

Lifecycle-Overview-Zahlen vor dieser Triage (aus dem Generator, nicht hier
gepflegt):

| Metric | Pre | Erwartet nach diesem PR |
| --- | ---: | ---: |
| files_scanned | 27 | 28 |
| reports_checked | 23 | 24 |
| reports_with_lifecycle_state | 15 | 16 |
| reports_missing_lifecycle_state | 8 | 8 |
| findings_total | 24 | 24 |
| archived (lifecycle_state) | 1 | 2 |

Begründung der erwarteten Deltas: dieser archivierte Report erhöht
`files_scanned`/`reports_checked`/`reports_with_lifecycle_state`/`archived` je um 1,
erzeugt aber **null** Findings und ändert **keinen** der acht unklassifizierten
Zielreports. `reports_missing_lifecycle_state` (8) und `findings_total` (24)
bleiben daher unverändert.

Validator-Findings je Zielreport (Warnmodus, Exit 0): `missing_lifecycle`,
`missing_lifecycle_state`, `missing_review_after` (3 × 8 = 24). **Wichtig:** Der
Validator meldet für diese acht **kein** `missing_owner_task`, weil `owner_task`
erst ab gesetztem `lifecycle_state` (active/deferred/superseded/archived)
verlangt wird. Das Inventory listet `owner_task` dagegen unter „Absent Core
Lifecycle Metadata", weil es alle vier Kernfelder prüft. Inventory (Feldpräsenz)
und Validator (zustandsabhängige Pflichtfelder) sind **nicht** identisch — diese
Triage übernimmt die Validator-Semantik und behandelt fehlende `owner_task`
nicht als bestehendes Validator-Finding.

## Self-Reference-Behandlung

Das Inventory zählt Primary References als **exakte vollständige Pfadtreffer**
(`docs/reports/<name>.md`) in handgeschriebenen `docs/**`-Flächen außerhalb von
`docs/_generated/` (`generate_report_lifecycle_inventory.py`,
`_compile_path_reference_pattern`). Damit diese Triage die Nutzungsevidenz der
acht Reports **nicht verfälscht**, gilt durchgehend:

- Die acht Fälle werden nur über Fall-IDs `R1`–`R8` und **Basenamen** (z. B.
  `cost-report.md`) referenziert — **nie** mit dem `docs/reports/…`-Pfadpräfix.
- Die `relations` dieses Reports zeigen auf Lifecycle-Policy, Validator und
  Task-Index — auf **keinen** der acht Zielreports.

Erwartete Primary-Reference-Zahlen der acht bleiben dadurch unverändert
(Baseline): `cost-report.md` 1, `domain-provider-role-finding.md` 1,
`domain-runtime-data-source-reconciliation.md` 1, `inwx-zone-reconciliation-plan.md` 2,
`map-architekturkritik.md` 4, `map-basemap-proof-gap-reconciliation.md` 2,
`optimierungsbericht.md` 2, `passkey-register-verify-prep.md` **0**.

`passkey-register-verify-prep.md` ist der einzige der acht mit **null** Primary
References (einziger Eintrag der acht in „Primary Unreferenced Reports"; in
`orphans.md` taucht er nicht auf, weil er ausgehende Relationen hat). Diese
Baseline-Tatsache wird hier festgehalten und durch die Triage nicht verändert.

Hinweis zu diesem Report selbst: Das Inventory wird **diesen** Report unter
„Absent Core Lifecycle Metadata" mit fehlendem `review_after` führen. Das ist
**kein** Finding und **kein** Widerspruch — archivierte Reports brauchen kein
`review_after` (siehe Lifecycle-Einordnung).

## Evidenzgrade

- **belegt** — durch konkrete Textstelle/Repo-Evidenz/registrierten Task gedeckt.
- **plausibel** — naheliegend, aber nicht zwingend aus Evidenz ableitbar.
- **offen** — Leerstelle; bewusst nicht erfunden.

Querschnittsvorbehalt (gilt für alle acht): Der zulässige Namensraum für
`owner_task` und eine Existenzprüfung sind laut
`DOCMETA-REPORT-LIFECYCLE-001.missing_evidence` **noch nicht festgelegt**; die
Lifecycle-Enums (z. B. `generated`, `planning`) sind **noch nicht** validiert.
Vorgeschlagene `owner_task`-Werte und neue Lifecycle-Werte sind daher
provisorisch, auch wenn der genannte Task registriert ist.

## Einzelfall-Triage R1–R8

### R1 — `cost-report.md`

- Ist-Frontmatter: `status: active`, `owner: docs-mechanik`, kein Lifecycle-Feld.
- Empfehlung: `lifecycle: generated` (belegt), `lifecycle_state: active`
  (plausibel), `owner_task` **offen**, `review_after` = bewusste Entscheidung,
  nicht erfunden.
- Evidenz: `tools/py/cost/report.py` schreibt die **gesamte** Datei
  (hartkodiertes Frontmatter **und** Body) bei jedem Lauf via `write_text`;
  Trigger ist `.github/workflows/cost-report.yml`. Der Body ist eine einzige
  generierte Kennzahl.
- Verworfene Alternative: `audit`/`proof`/`decision-prep` — dies ist keine
  Analyse, sondern ein wiederkehrend erzeugtes Artefakt.
- **Backfill-Blocker (hart):** Ein report-only-Backfill ist wirkungslos — der
  nächste Generatorlauf überschreibt jedes manuell gesetzte Lifecycle-Feld. Der
  `frontmatter`-String in `tools/py/cost/report.py` müsste geändert werden
  (Generator + Output gemeinsam). Zusätzlich offen: Enum-Stützung für
  `generated` und ein Owner. Kein erfundenes Monats-/30-Tage-Datum.

### R2 — `domain-provider-role-finding.md`

- Ist-Frontmatter: `status: active`, kein Lifecycle-Feld.
- Empfehlung: `lifecycle: audit` (belegt), `lifecycle_state: active`
  (plausibel, mit Frischevorbehalt), `owner_task: DEPLOY-DNS-001` (belegt als
  Kandidat), `review_after` = fachlich an den DNS-Cutover/Live-Recheck gebunden.
- Evidenz: Report bezeichnet sich selbst als „operativen Zwischenstand
  (Post-Mailmigration, Pre-DNS-Cutover)"; Mail-Proofs sind als `proved`
  markiert, Web-/Registrar-Rolle „noch offen und vor Registrar-Cutover zu
  verifizieren". `DEPLOY-DNS-001` ist registriert („INWX Registrar/DNS Cutover")
  und führt den Schwester-Plan bereits als Evidenz.
- Verworfene Alternative: `archived` — der Cutover steht noch aus, das Finding
  ist weiter handlungsrelevant.
- **Frischevorbehalt (`requires_live_check`):** Die „aktuellen" Provider-/DNS-/
  Web-Rollen sind extern veränderlich und **nicht** in-repo live verifiziert. Sie
  dürfen nicht als heutige Live-Wahrheit ausgegeben werden; historische
  Mail-Proofs sind vom heutigen Registrar-/DNS-Zustand zu trennen. Keine privaten
  Provider-Rohdaten ins Repo (Report redigiert bereits — bewahren).

### R3 — `domain-runtime-data-source-reconciliation.md`

- Ist-Frontmatter: `status: active`, `owner: docs-mechanik`, kein Lifecycle-Feld.
- Empfehlung: `lifecycle: audit` (belegt), `lifecycle_state: active`
  (plausibel/bedingt), `owner_task: DB-PROOF-001` (belegt), `review_after` =
  fachlich an einen erneuten Runtime-Check gebunden.
- Evidenz: Report nennt explizit „Task: DB-PROOF-001" und dokumentiert dessen
  Blocker. `DB-PROOF-001` ist registriert (status `partial`, „Edge-Orphan- und
  Referenz-Audit vor PostgreSQL-FK-Entscheidung").
- Verworfene Alternative: `archived` — die Empfehlung „DB-PROOF-001 bleibt
  partial" ist weiter handlungsleitend.
- **Zeitbezug (leicht zu übersehen):** Die Runtime-Evidenz ist auf **2026-06-18**
  datiert (4 Tage vor Baseline). Sie ist eine Momentaufnahme, **nicht** die
  heutige Runtime-Wahrheit; ein erneuter Runtime-Check ist Vorbedingung für jede
  Folgeentscheidung. Der Report beweist ausdrücklich **nicht**, dass
  Domain-Postgres defekt oder FK ungeeignet ist — diese Aussagen dürfen nicht
  übernommen werden. Belegte Ownership (DB-PROOF-001) und veränderliche
  Runtime-Wahrheit sind getrennt zu bewerten.

### R4 — `inwx-zone-reconciliation-plan.md`

- Ist-Frontmatter: `status: active`, kein Lifecycle-Feld.
- Empfehlung: `lifecycle: planning` (belegt durch Inhalt), `lifecycle_state:
  active` (plausibel), `owner_task: DEPLOY-DNS-001` (belegt), `review_after` =
  an Aktivierungsfenster/Live-Check gebunden.
- Evidenz: Report sagt „Prepared offline plan only. No live provider changes
  performed" und „not evidence of a completed cutover or a live prepared INWX
  zone". `DEPLOY-DNS-001` ist der registrierte Cutover-Task; dieser Plan ist sein
  Eingabemanifest.
- Verworfene Alternative: `doc_type: report` als Gegenargument gegen `lifecycle:
  planning` — **abgelehnt**; `doc_type` und `lifecycle` sind orthogonal. Der
  Inhalt ist ein Offline-Plan.
- **Vorbedingungen / Stop-Gates:** Offline-Plan, **keine** vorbereitete Live-Zone;
  fehlender IONOS-Export und Provider-Dashboard-Werte sind Voraussetzung; das
  DNSSEC-/Parent-DS-Stop-Gate bleibt erhalten; keine operativen DNS-Schritte;
  kein erfundenes Aktivierungsdatum. `planning`-Enum noch nicht validiert.

### R5 — `map-architekturkritik.md`

- Ist-Frontmatter: `status: active`, kein Lifecycle-Feld.
- Empfehlung: `lifecycle: audit` (plausibel), `lifecycle_state: active` **nur
  plausibel, nicht automatisch belegt**, `owner_task` **offen**, `review_after`
  offen.
- Evidenz/Prüfung des **gesamten** Reports (nicht nur des Basemap-Anteils): Die
  strukturelle Kritik (monolithischer `+page.svelte`-Orchestrator, Hybrid-Basemap
  `remote-style` prod vs. `local-sovereign`, Deprecated-Alias `MapPoint`,
  ungeschlossene Produktionswahrheit) bleibt **gültig**. Eine Gegenwartsaussage
  im Nachtrag ist jedoch **überholt**: „Ein echtes PMTiles-Artefakt ist weder
  gebaut noch hochgeladen im CI" wird durch das neuere `R6` (Stand 2026-06-15,
  P3/P5 grün auf `main`) widerlegt.
- Verworfene Alternative: ungeprüftes `active` — ein Dokument mit bekannt
  überholter Gegenwartsaussage sollte nicht unverändert `active` gestempelt
  werden.
- **Vorbedingung:** Inhaltsreconciliation der überholten CI-Artefakt-Aussage
  (oder expliziter Nachtrag) **vor** Backfill. Kein erfundener Karten-Owner —
  Im Task-Index existiert derzeit kein registrierter MAP-PROOF-* oder
  anderer eindeutig zuständiger Karten-Task. MAP-PROOF-001 und
  MAP-PROOF-002 sind im Repo als Proof- beziehungsweise
  Kontrollpunktbezeichnungen belegt, aber nicht als Task-Einträge
  registriert. Da der zulässige owner_task-Namensraum noch nicht
  abschließend festgelegt ist, bleibt der Owner hier offen.

### R6 — `map-basemap-proof-gap-reconciliation.md`

- Ist-Frontmatter: `status: active`, kein Lifecycle-Feld.
- Empfehlung: `lifecycle: audit` (plausibel), `lifecycle_state: active`
  (plausibel), `owner_task` **offen**, `review_after` = fachlich an `MAP-PROOF-002`
  gebunden.
- Evidenz: Diagnose-/Reconciliation-Report (Stand 2026-06-15) mit über die
  GitHub-Actions-API verifizierten CI-Belegen. Geschlossene Proof-Gaps (P0–P3,
  P5) sind von offenen Restgaps (P4 Struktur, Vector-Tile-Payload, P6
  Pixel-Korrektheit, P7 prod-naher Caddy, Cross-Env-Reproduzierbarkeit) sauber
  getrennt.
- Verworfene Alternative: automatisches `archived`, nur weil Teile grün sind —
  **abgelehnt**; offene Restgaps bestehen, der Report leitet den nächsten PR ab.
- **Owner-Status (kritisch):** `MAP-PROOF-001` (Titel/Label) ist **kein**
  registrierter Task; höchstens ein unregistrierter Kontrollpunkt. `MAP-PROOF-002`
  ist der vorgeschlagene Review-Trigger, ebenfalls **nicht** registriert und
  bisher **nicht** umgesetzt (kein Task, kein Proof-Artefakt darüber hinaus).
  `owner_task` bleibt offen bis zur Namensraum-Entscheidung. Synthetischer
  Range-Proof (P2) ist **nicht** mit visueller/produktionsnaher Korrektheit zu
  verwechseln.

### R7 — `optimierungsbericht.md`

- Ist-Frontmatter: `status: active`, `created: 2026-04-19`, kein Lifecycle-Feld.
- Empfehlung: `lifecycle: audit` (belegt), `lifecycle_state: archived`
  (plausibel), **nicht** `superseded`, `owner_task` **offen**, kein `review_after`.
- Evidenz: Der Report sagt selbst „Diagnosequelle, nicht die operative
  Fortschrittswahrheit"; operative Statusführung liegt in `optimierungsstatus.md`.
  Zahlreiche Diagnose-Claims sind historisch überholt (z. B. N.5 „behoben";
  Passkey-Verify inzwischen umgesetzt, siehe `R8`).
- Verworfene Alternative: `superseded` — **abgelehnt**; `optimierungsstatus.md`
  ist eine Status-Matrix, **kein** vollständiges Ersatzartefakt für den
  Analyseinhalt. Ohne ein den ganzen Bericht ablösendes Artefakt kein
  `superseded`/`superseded_by`.
- **Backfill-Blocker (hart):** Der Bericht ist querschnittlich (API, Frontend,
  Infra, CI/CD, Docs, Contracts). Kein einzelner `OPT-*`-Task (auch nicht das
  registrierte `OPT-ARC-001`, das nur eine Scheibe abdeckt) ist der korrekte
  Owner. Da `archived` ein `owner_task` **verlangt**, ist die Owner-Leerstelle
  ein echter Backfill-Blocker und hier ausdrücklich sichtbar.

### R8 — `passkey-register-verify-prep.md`

- Ist-Frontmatter: `status: active`, kein Lifecycle-Feld. Primary References: **0**.
- Empfehlung: `lifecycle: decision-prep` (belegt), `lifecycle_state: archived`
  (plausibel), `owner_task: AUTH-PG-002` **nur plausibel** (Alternative:
  explizite Owner-Leerstelle), kein `review_after`.
- Evidenz: Der ursprüngliche Zweck (Register-Verify vorbereiten) ist **umgesetzt
  und CI-belegt** (Workflow `auth-passkey-register-proof`, Run `27487642565`,
  `success`, Nachtrag 2026-06-14). Der Report enthält daneben offene
  Persistenzfragen (dauerhafter Credential-Store, `webauthn_user_id`-Writeback,
  DB-Schema) — diese decken sich mit `AUTH-PG-002` („WebAuthn-Credential-Persistenz
  / Passkey-Cutover nach PostgreSQL", registriert, `open`).
- Verworfene Alternative: `superseded` — **abgelehnt**, solange kein Artefakt den
  vollständigen historischen Vorbereitungsbericht ersetzt.
- **Trennung (kritisch):** Abgeschlossene Register-Verify-Arbeit ist von den
  weiterhin offenen Passkey-Themen (Login `auth/options`/`auth/verify`,
  List/Remove, Persistenz, UI) zu **trennen**. `AUTH-PG-002` besitzt die **offene
  Persistenz-Folgearbeit**, ist aber nicht automatisch der historische Owner des
  *fertigen* Register-Verify-Berichts — daher nur plausibel; eine explizite
  Owner-Leerstelle wäre ehrlicher. Die Baseline-Tatsache „0 Primary References"
  bleibt sichtbar.

## Triage-Übersicht

| Fall | Datei | lifecycle | lifecycle_state | owner_task | owner-Grad | Backfill-Reife |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | `cost-report.md` | generated | active | — | offen | Slice F |
| R2 | `domain-provider-role-finding.md` | audit | active | DEPLOY-DNS-001 | belegt | Live-Check + review_after |
| R3 | `domain-runtime-data-source-reconciliation.md` | audit | active | DB-PROOF-001 | belegt | Runtime-Recheck + review_after |
| R4 | `inwx-zone-reconciliation-plan.md` | planning | active | DEPLOY-DNS-001 | belegt | Live/Window + Enum + review_after |
| R5 | `map-architekturkritik.md` | audit | active | — | offen | Inhaltsreconciliation + Owner |
| R6 | `map-basemap-proof-gap-reconciliation.md` | audit | active | — | offen | Owner-Namensraum |
| R7 | `optimierungsbericht.md` | audit | archived | — | offen | Slice E |
| R8 | `passkey-register-verify-prep.md` | decision-prep | archived | AUTH-PG-002 | plausibel | reif (Owner-Vorbehalt) |

## Backfill-Slices (nach Umsetzungsreife, nicht nach Thema)

> Jede künftige Scheibe ist ein eigener kleiner PR. Reihenfolge nach Reife.
> Stop-Kriterium für **alle** Slices: keine Änderung an Validator-/Strict-Logik,
> keine Generated-Datei von Hand, keine Vermischung von Strang A
> (PostgreSQL/Auth) und Strang B (Hygiene) entgegen dem Board.

### Slice A — Auth Decision-Prep (R8) — *weitgehend entscheidungsreif; Owner-Bestätigung bleibt letztes Gate*

- Dateien: `passkey-register-verify-prep.md`.
- Vorgeschlagene Metadaten: `lifecycle: decision-prep`, `lifecycle_state:
  archived`, `owner_task: AUTH-PG-002`, kein `review_after`.
- Offene Vorbedingung: `AUTH-PG-002` ist ein plausibler Owner der offenen
  Persistenz-Folgearbeit; er ist nicht automatisch der historische Owner des
  abgeschlossenen Register-/Verify-Vorbereitungsberichts; ohne
  Owner-Bestätigung kein Backfill.
- Akzeptanz: 0 neue Findings; Register-Verify-Abschluss nicht als offen
  umdeklariert; Primary-Reference-Zahl bleibt 0.
- Risiko/Abhängigkeit: gering; keine Runtime-/Generator-/Live-Abhängigkeit.
- Begründung Reihenfolge: einziger Fall mit `archived` ohne `review_after`-Bedarf,
  Owner als registrierter Task identifizierbar, Kernzweck CI-bewiesen.

### Slice B — DNS-Cutover-Dokumente (R2, R4) — *Owner belegt, Hauptdomain-Live-Check erbracht, Nebendomains offen*

- Dateien: `domain-provider-role-finding.md`, `inwx-zone-reconciliation-plan.md`.
- Gewählte Metadaten: R2 `audit/active`, R4 `planning/archived`, beide
  `owner_task: DEPLOY-DNS-001`.
- Begründung: Der alte INWX-Plan (R4) hat kein einzelnes vollständiges Ersatzartefakt und ist deshalb `archived`, nicht `superseded`. Keine alte IONOS-Anweisung bleibt operativ.
- Status: Hauptdomain-Live-Check erbracht. Nebendomains bleiben offener Restbestand.

### Slice C — DB-Runtime-Audit (R3) — *Owner belegt, Runtime-Recheck offen*

- Dateien: `domain-runtime-data-source-reconciliation.md`.
- Vorgeschlagene Metadaten: `audit/active`, `owner_task: DB-PROOF-001`.
- Offene Vorbedingungen: erneuter Runtime-Check für ein fachliches
  `review_after`; Zeitbezug (2026-06-18) explizit halten.
- Akzeptanz: 0 neue Findings; keine „Postgres defekt"/„FK ungeeignet"-Claims;
  Scope des Reports erhalten.
- Risiko/Abhängigkeit: Strang A (PostgreSQL) — **nicht** mit Slice B mischen.

### Slice D — Map-Governance (R5, R6) — *Owner-Namensraum offen*

- Dateien: `map-architekturkritik.md`, `map-basemap-proof-gap-reconciliation.md`.
- Harte Vorbedingung: Klärung des zulässigen `owner_task`-Namensraums
  (`DOCMETA-REPORT-LIFECYCLE-001.missing_evidence` #4); zusätzlich für R5
  Inhaltsreconciliation der überholten CI-Artefakt-Aussage.
- Akzeptanz: kein erfundener Map-Owner; `MAP-PROOF-001` nicht als registrierter
  Task behandelt.
- Begründung Reihenfolge: **nicht** in einen schnellen Backfill schieben — erst
  Governance/Inhalt klären.

### Slice E — Querschnittliche Optimierungsdiagnose (R7) — *Owner-Entscheidung offen*

- Datei: `optimierungsbericht.md`.
- Vorgeschlagene Metadaten:
  `lifecycle: audit`,
  `lifecycle_state: archived`,
  kein `review_after`.
- Harte Vorbedingung:
  einen evidenzbasierten verantwortlichen Task, Prozess oder Kontrollpunkt
  bestimmen. Kein einzelner OPT-Task darf allein wegen Teilüberdeckung
  eingesetzt werden.
- Alternativpfad:
  Wenn kein belastbarer Owner bestimmt werden kann, bleibt der
  Frontmatter-Backfill bis zur Klärung des `owner_task`-Namensraums
  zurückgestellt.
- Nicht zulässig:
  `superseded` oder
  `superseded_by: docs/reports/optimierungsstatus.md`,
  solange kein Artefakt die vollständige Diagnose ersetzt.
- Akzeptanz:
  Die historische Diagnose bleibt rekonstruierbar; operative
  Fortschrittswahrheit verbleibt in `optimierungsstatus.md`; keine
  künstliche Ownership.
- Risiko:
  technisch niedrig, governance-seitig mittel.

### Slice F — Generierter Cost-Report (R1) — *Generatoränderung nötig*

- Dateien: `tools/py/cost/report.py` (Generator) **plus** Output — getrennt von
  reinen Frontmatter-Slices.
- Harte Vorbedingungen: `generated`-Enum-Stützung; Owner-Entscheidung; Generator
  und Output gemeinsam ändern (report-only-Backfill wäre nicht reproduzierbar).
- Begründung Reihenfolge: zuletzt, weil Code-Änderungsfläche statt nur Frontmatter.

## Scope-Bestätigung dieses PR

- Manuell geändert: dieser Report, `docs/tasks/board.md`, `docs/tasks/index.json`.
- Deterministisch regeneriert: Dateien unter `docs/_generated/` via `make generate`.
- **Unverändert:** alle acht Zielreports; `scripts/`; `.github/`; Contracts;
  `Makefile`/`Justfile`; Validator-/Strict-Logik. Keine Löschungen, keine
  Archivverschiebungen, kein Produktionscode.

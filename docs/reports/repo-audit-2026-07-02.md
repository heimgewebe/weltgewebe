---
id: reports.repo-audit-2026-07-02
title: "Repo-Komplettaudit 2026-07-02"
doc_type: report
status: active
lifecycle_state: active
lifecycle: audit
owner_task: REPO-AUDIT-001
review_after: 2026-10-31
canonicality: evidence
created: 2026-07-02
lang: de
summary: >
  Komplettaudit des Repositories (Code, CI, Meta-Dateien, Dokumentation):
  alle automatisierten Checks grün; dreizehn belegte Hygiene-/Konsistenzbefunde,
  davon zehn behoben (teils in diesem PR, teils durch #1315/#1317/#1318);
  eine Restarbeit unter REPO-AUDIT-001.
relations:
  - type: relates_to
    target: docs/reports/optimierungsstatus.md
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: docs/policies/architecture-critique.md
  - type: relates_to
    target: docs/policies/agent-reading-protocol.md
---

# Repo-Komplettaudit 2026-07-02

**Geltungsbereich:** System (gesamtes Repository) ·
**Kritiktiefe:** Strukturell (Sektionen gemäß `docs/policies/architecture-critique.md`)

## 1. Prüfumfang und Methodik

Ausgeführte automatisierte Prüfungen (alle **grün**, sofern nicht anders vermerkt):

| Prüfung | Ergebnis | Evidenz |
|---|---|---|
| `make validate-tests` (794 docmeta-/Agent-Tests) | grün | lokaler Lauf 2026-07-02 |
| `make validate-core` (Schema, Relations, Links, Freshness, Proof-Matrix) | grün¹ | lokaler Lauf 2026-07-02 |
| `make validate-guards` (System-Map-Drift + 4 Guards) | grün | lokaler Lauf 2026-07-02 |
| `make validate-shell-tests` | grün | lokaler Lauf 2026-07-02 |
| `cargo fmt --check`, `cargo clippy --all-targets --all-features -D warnings` | grün | lokaler Lauf 2026-07-02 |
| `cargo test --all` | grün | lokaler Lauf 2026-07-02 |
| Web: `pnpm run ci` (Budget, Prettier, ESLint, svelte-check: 490 Dateien, 0 Fehler) | grün | lokaler Lauf 2026-07-02 |
| Web: `pnpm test:unit` (122 Tests) | grün | lokaler Lauf 2026-07-02 |
| `yamllint --strict` über alle getrackten YAML-Dateien | grün | lokaler Lauf 2026-07-02 |
| `markdownlint-cli2` (195 Dateien, CI-Globs) | grün | lokaler Lauf 2026-07-02 |
| `scripts/contracts-domain-check.sh` | grün | lokaler Lauf 2026-07-02 |
| `cargo deny check` | **nicht ausgeführt** | Binary in der Audit-Umgebung nicht beziehbar (Netzwerk-Policy); CI deckt über `security.yml` und `just ci` ab |

¹ Erstlauf schlug fehl, weil die Audit-Umgebung ein Shallow-Clone war — siehe Befund R-10.

Zusätzlich: manuelle Konsistenzprüfung über Meta-Dateien (`repo.meta.yaml`,
`AGENTS.md`, `agent-policy.yaml`, `CLAUDE.md`), Justfile/Makefile, alle 33
Workflows, Env-Templates, Lockfiles und Toolchain-Pins.

## 2. Dialektik

**These (wohlwollende Lesart).** Das Repository ist außergewöhnlich
diszipliniert: vollständige Guard-/Validator-Ketten, Claim-Evidence-Spine,
Task-Control-Schicht mit Drift-Checks, grüne Lint-/Test-Strecken und
weitgehend konsistente Toolchain-Pins (Rust 1.89.0, Node 20.19.0,
pnpm 9.11.0). Bestehende Aufgabenmarker in Tests/Reports sind
dokumentierte Folge-/Proof-Bezüge, keine pauschal verschwundenen Altlasten.
Die gefundenen Mängel sind Randdrift,

**Antithese (kritische Lesart).** Genau die Stärke des Systems — viele
redundante Wahrheits- und Kontrollflächen — erzeugt seine typische
Fehlerklasse: dieselbe Information wird an drei bis vier Stellen manuell
gepflegt (Generated-Artifacts-Listen, Required-Checks-Listen,
Kommando-Dokumentation) und driftet still auseinander. Ein Teil der
Kontrollinfrastruktur kontrolliert sich selbst nicht (heavy.yml-e2e nie
exerziert, Shell-Lint nirgends in CI, `.lychee.toml` nie geladen).

**Synthese.** Die Basis ist tragfähig; die Befunde sind Pflege- und
Kopplungsprobleme redundanter Deklarationen, nicht Architekturfehler. Der
strukturelle Hebel ist Deklarations-Deduplikation (siehe §5 Alternativpfad),
der operative Hebel ist die hier umgesetzte Angleichung.

## 3. Diagnose

**Befundklasse: B** (Warnung: potenzielle Schwächen, kontextabhängig).
Begründung der Evidenzlage: Kern-Code, Tests und CI-Hauptpfade sind
nachweislich grün (Klasse-D-Anteile); die Befunde betreffen ausschließlich
Meta-Konsistenz, schlafende CI-Pfade und tote Deklarationen. Kein Befund
stellt die Tragfähigkeit in Frage (kein Klasse-A-Befund).

### Befunde

Evidenzgrade: **belegt** = mit Quellenangabe nachgewiesen; **plausibel** =
strukturelle Ableitung.

| # | Befund | Evidenz | Problemtyp | Status |
|---|---|---|---|---|
| R-01 | `Justfile`-Rezept `seed` doppelt defekt: `cargo run -p api` (Workspace-Paket heißt `weltgewebe-api`; `cargo pkgid -p api` schlägt fehl) und die API besitzt keinen `seed`-Subcommand (`apps/api/src/main.rs` ruft argumentlos `run()` auf) | belegt | Laufzeitproblem (totes Rezept) | **behoben**: Rezept entfernt, Hinweis auf `demo-data`/`bootstrap-first-account` |
| R-02 | Root-`package-lock.json` war gegenüber `package.json` veraltet und in einem pnpm-verwalteten Repo (`packageManager: pnpm@9.11.0`, Root-`pnpm-lock.yaml` vorhanden) mehrdeutig für Dependabot-npm-Ökosystem auf `/` | belegt | Dokumentationsdrift / Tooling-Ambiguität | **behoben**: Lockfile durch #1315 aktualisiert; ursprüngliche Löschstrategie nach Rebase verworfen |
| R-03 | Drei widersprüchliche Generated-Artifacts-Listen: `repo.meta.yaml` (13), `generated-files-guard.sh` (16), real `docs/_generated/` (18); fehlend u. a. `relates-to-audit.md`, `relations-analysis.md` | belegt | Dokumentationsdrift | **behoben**: beide Listen auf 18 angeglichen |
| R-04 | Required-Checks-Drift zwischen kanonischen Quellen gleicher Präzedenzklasse: `repo.meta.yaml` (3), `AGENTS.md` (4), `agent-policy.yaml` (5), `CLAUDE.md` (6); `coverage-guard` läuft real in `validate-guards` | belegt | Truth-Model-Inkonsistenz (Achse A) | **behoben**: Basis-Guard-Liste um `coverage-guard` ergänzt; `agent-policy.yaml`/`CLAUDE.md` behalten zusätzlich `lint`/`test` als Patch-Vorbedingungen; strukturelle Deduplikation bleibt Folgearbeit (§5) |
| R-05 | `ci.yml`-Step „Install cargo-deny" hardcodet `DENY_VERSION="0.18.8"` und überschattet den zuvor aus `toolchain.versions.yml` gelesenen Env-Wert — der Pin in der Versionsdatei war wirkungslos | belegt | Kopplungsproblem (Version-Pinning) | **behoben**: Step nutzt Env-Wert, bricht ohne ihn ab |
| R-06 | `heavy.yml` e2e-Job: `setup-node` mit `cache: 'pnpm'` **vor** pnpm-Verfügbarkeit (Corepack erst danach) — `setup-node` ruft `pnpm store path` auf; zudem `node-version: '22.x'` abweichend von der `.node-version`-Pinning-Strategie aller anderen Workflows | belegt (statisch); Laufzeitversagen plausibel, da Job schlafend | Laufzeitproblem (schlafender CI-Pfad) | **behoben**: `pnpm/action-setup@v6` vor `setup-node`, `node-version-file: '.node-version'` (Muster wie `web.yml`); Restarbeit: Dispatch-Proof (siehe R-13) |
| R-07 | `CLAUDE.md` behauptet „Axum 0.7" (real: `axum = "0.8"` in `apps/api/Cargo.toml`), dokumentiert das defekte `just seed` und das tote `WEB_PORT` | belegt | Dokumentationsdrift | **behoben** |
| R-08 | `.env.example` deklariert `WEB_PORT=5173`; kein Konsument im Repo (weder Compose noch Vite-Config noch Skripte) | belegt | tote Deklaration | **behoben**: durch Kommentar ersetzt |
| R-09 | Verwaistes `src/routes/+page.svelte` im Repo-Root (Debug-Seite „SvelteKit lebt"); keine Referenz im Repo; außerhalb von `apps/web` von keinem Build erfasst | belegt (keine Referenz auffindbar); Obsoleszenz plausibel | möglicherweise obsoletes Artefakt | **behoben**: entfernt; `src/` aus `discovery_roots` genommen (Gegenhypothese in §6 dokumentiert) |
| R-10 | `validate_opt_arc_001_db_proof_matrix` ist nicht Shallow-Clone-robust: CI-Evidence-Commits außerhalb der lokalen Historie erzeugen einen harten Fehler ohne Hinweis auf Shallow-Clone als Ursache (CI nutzt `fetch-depth: 0`, Agent-/lokale Umgebungen nicht zwingend) | belegt (reproduziert in dieser Audit-Umgebung) | Robustheitslücke (Tooling) | **behoben**: fehlende `ci_evidence.commit`-Objekte melden nun explizit Shallow-/Partial-Checkout als mögliche Ursache und nennen `fetch-depth: 0`; Testabdeckung ergänzt |
| R-11 | Shell-Lint-Lücke: `just lint` (bash -n, shfmt, shellcheck) lief in keinem der 33 Workflows; der CI-Job „Docs & Shell Hygiene" (`ci.yml`) enthielt keine Shell-Prüfung (nur markdownlint, lychee, yamllint, JSON) | belegt | CI-Abdeckungslücke + Namensproblem | **behoben**: `Docs & Shell Hygiene` läuft nun bei Hygiene-Änderungen und führt blockierend bash/shfmt/shellcheck für getrackte Shell-Dateien aus; die Dateiliste wird über `scripts/tools/list-shell-files.py` erzeugt und umfasst `.sh`, `.bash` sowie Shell-Shebang-Dateien ohne Endung (#1318) |
| R-12 | `.lychee.toml` wird von keinem lychee-Aufruf geladen (lychee-Default ist `lychee.toml` ohne Punkt; beide Workflows übergeben alle Optionen via `args`); Datei wirkt nur als Cache-Key-Bestandteil in `ci.yml` | belegt (keine `--config`-Referenz im Repo) | tote Konfiguration | **behoben**: `ci.yml` und `links.yml` laden `.lychee.toml` nun explizit via `--config .lychee.toml`; die Config wurde für Lychee v0.23 auf `max_retries` korrigiert (#1320) |
| R-13 | `heavy.yml` e2e-Job wurde in den letzten 30 Läufen nie ausgeführt (alle Läufe Gate-only, e2e `skipped`; belegt via GitHub-Actions-API 2026-07-02, z. B. Run 28534919650) — der Fix aus R-06 braucht einen `workflow_dispatch`-Proof | belegt | schlafender CI-Pfad | **offen** → REPO-AUDIT-001 |

### Positivbefunde (Klasse D, earned)

- Rust-/Web-Codebasis mit grünem fmt/clippy/test-Stand; Aufgabenmarker in Tests/Reports existieren weiterhin und sind als dokumentierte Folge-/Proof-Bezüge einzuordnen.
- Toolchain-Pins Rust 1.89.0 konsistent über `toolchain.versions.yml`, `apps/api/Dockerfile`, `infra/compose/compose.core.yml`.
- Docmeta-/Guard-/Task-Control-Ketten laufen vollständig und grün durch; `docs/_generated/*`-Diagnosen melden keine Orphans, keine Staleness, keine Drift.

## 4. Architekturkritik (Achsenzuordnung)

- **Achse A (Truth Model):** R-03/R-04 sind Klassiker impliziter Wahrheit —
  vier kanonische Quellen gleicher Präzedenzklasse trugen divergierende
  Required-Checks-Listen; das Truth Model selbst bot keine Auflösung, weil
  die Divergenz *innerhalb* einer Klasse lag. Behoben durch Angleichung;
  strukturell adressierbar nur durch Deduplikation (§5).
- **Achse B (Contracts):** keine Befunde; Domain-Contracts validieren, der
  AGENT-SAFE-008-Kontrollvertrag (`.wgx/generated-artifacts.yml`) ist die
  richtige Keimzelle gegen R-03-artige Drift.
- **Achse C (Semantik):** R-11 war ein Namens-/Verhaltensbruch („Docs & Shell Hygiene" ohne Shell-Lint); die CI-Abdeckung wurde in #1318 nachgezogen.
- **Achse D (Runtime vs. Dokumentation):** R-01, R-07, R-08 — tote
  Kommandos/Variablen in operativer Doku.
- **Achse G (Komplexität):** Die Kontroll-Redundanz (Board + Index + Matrix +
  Claims + Guards) ist durch Systemgrenzen begründet (Agenten-Betrieb),
  erzeugt aber genau die hier gefundene Drift-Klasse. Kein Overengineering-
  Urteil; Wartungskosten sind sichtbar zu halten.
- **Achsen E/F (Karte, Identität):** nicht anwendbar (keine Karten-/
  Identitätsbefunde in diesem Audit; bestehende Proof-Ketten unberührt).

## 5. Alternativpfad (zu Befundklasse B)

Statt redundante Listen weiter manuell zu synchronisieren: **eine
deklarative Quelle, aus der Guard und Meta abgeleitet werden.**
`.wgx/generated-artifacts.yml` (AGENT-SAFE-008) auf alle 18 Generated-
Artefakte ausbauen; `generated-files-guard.sh` liest die REQUIRED_FILES aus
dem Manifest statt aus einer eigenen Liste; `repo.meta.yaml.generated_artifacts`
wird per Check gegen das Manifest validiert. Analog könnten die
Required-Checks-Listen aus `repo.meta.yaml` von AGENTS.md/CLAUDE.md nur noch
referenziert statt kopiert werden. Das ist strukturelles Neu-Denken der
Pflegequelle, kein Variantenwechsel — und bereits als „Vollausbau bleibt
Folgearbeit" in AGENT-SAFE-008 angelegt.

## 6. Gegenhypothesen und Selbstkritik

- **R-09 (Root-`src/`):** Gegenhypothese: bewusst platzierter
  Codespaces-Smoke-Artefakt. Nicht belegbar — keine Referenz, kein Build-
  Einstieg, letzte Änderung in altem Merge. Entfernung ist per Git
  reversibel; falls doch gewollt, gehört das Artefakt nach `apps/web` und
  dokumentiert.
- **R-06 (Node 22.x):** Gegenhypothese: absichtlicher Forward-Compat-Test
  gegen Node 22. Nirgends dokumentiert (Leerstelle). Die Angleichung auf
  `.node-version` folgt der dokumentierten Pinning-Strategie; ein bewusster
  Node-22-Kanal wäre als eigener, dokumentierter Job wieder einzuführen.
- **Wahrscheinlichste Überdehnung der Diagnose:** R-06 als „defekt" zu
  werten, obwohl der Pfad nie lief — das Laufzeitversagen ist abgeleitet
  (aus dem dokumentierten Verhalten von `setup-node` mit `cache: 'pnpm'`),
  nicht beobachtet. Deshalb bleibt R-13 (Dispatch-Proof) offen.
- **Unsicherste Aussage:** R-12 — lychees Config-Discovery wurde nicht
  im Lauf verifiziert, sondern aus Default-Konfigurationspfad (`lychee.toml`)
  und fehlender `--config`-Übergabe abgeleitet.
- **Größter Interpretationsanteil:** die Wahl, R-04 durch Vereinheitlichung
  auf die Obermenge (inkl. `coverage-guard`) zu lösen statt durch Reduktion.
  Begründung: `coverage-guard.sh` läuft real und blockierend in
  `make validate-guards`.

## 7. Essenz + Folgepfad

**Hebel — Entscheidung — nächste Aktion:**

1. **Größter Hebel (umgesetzt):** Angleichung der divergierenden
   Meta-Listen und Entfernung toter Artefakte (R-01…R-09) — geringer
   Aufwand, beseitigt alle akuten Widersprüche zwischen kanonischen Quellen.
2. **Struktureller Hebel (offen):** Deklarations-Deduplikation über den
   Generated-Artifact-Kontrollvertrag (§5); anschlussfähig an
   AGENT-SAFE-008-Folgearbeit.
3. **Später Ausbaupfad:** R-13 abschließen, ohne neue redundante Guard-Listen einzuführen.
4. **Wahrscheinlichste Überkorrektur:** weitere Guards/Listen *hinzufügen*,
   statt bestehende zu deduplizieren — das würde die Drift-Klasse
   vergrößern, nicht verkleinern.

**Folgepfad (Befundklasse B):** Steuerung der Restarbeiten (R-13) über
Board-Task `REPO-AUDIT-001` (`docs/tasks/board.md`, `docs/tasks/index.json`).
Bewusst kein neuer OPT-Eintrag in `docs/reports/optimierungsstatus.md`:
Repo-Hygiene-Restarbeiten laufen — wie die Task-Control-Phasen — über
`docs/tasks/` (Präzedenz: Eintrag „Dokumentationsstruktur & Task-Steuerung"
in `docs/roadmap.md`). `docs/roadmap.md` bleibt unberührt (kein Phasen- oder
Reihenfolge-Wechsel in einer Sub-Roadmap).

**Unsicherheits- und Evidenzlage:**

- Unsicherheitsgrad: **0.15** — Ursachen: R-06/R-12 statisch statt im Lauf
  belegt; `cargo deny` lokal nicht ausführbar (Netzwerk-Policy der
  Audit-Umgebung).
- Evidenzstatus: teilweise belegt (R-06 Laufzeitversagen, R-12
  Config-Discovery: strukturelle Ableitungen; alles Übrige belegt).
- Offene Lücken: „Dispatch-Lauf von heavy.yml fehlt, nötig für
  Laufzeit-Beweis von R-06-Fix" · „lychee-Lauf mit/ohne `.lychee.toml`
  fehlt, nötig für R-12-Entscheidung".

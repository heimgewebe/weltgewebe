### 📄 docs/process/README.md

**Größe:** 350 B | **md5:** `a64145073affb3b77a3cdf93997e0251`

```markdown
# Prozess

Übersicht über Abläufe und Konventionen.

## Index

- [Fahrplan](fahrplan.md) – zeitlicher Ablauf und Meilensteine (**kanonisch**)
- [Sprache](sprache.md) – Leitfaden zur Projektsprache
- [Bash Tooling Guidelines](bash-tooling-guidelines.md) – Best Practices für zukünftige Shell-Skripte

[Zurück zum Doku-Index](../README.md)
```

### 📄 docs/process/bash-tooling-guidelines.md

**Größe:** 3 KB | **md5:** `ef60df9aa99bb48d8f5b68ea6e049bab`

```markdown
# Bash-Tooling-Richtlinien

Diese Richtlinien beschreiben, wie wir Shell-Skripte im Weltgewebe-Projekt entwickeln, prüfen und ausführen.  
Sie kombinieren generelle Best Practices (Formatierung, Checks) mit projektspezifischen Vorgaben
wie Devcontainer-Setup, CLI-Bootstrap und SemVer.

## Ziele

- Einheitliche Formatierung der Skripte.
- Automatisierte Qualitätssicherung mit statischer Analyse.
- Gute Developer Experience für wiederkehrende Aufgaben.
- Projektkontext: sauberes Devcontainer-Setup, klare CLI-Kommandos, reproduzierbare SemVer-Logik.

## Kernwerkzeuge

### shfmt

- Formatierung gemäß POSIX-kompatiblen Standards.
- Nutze `shfmt -w` für automatische Formatierung.
- Setze `shfmt -d` in CI-Checks ein, um Abweichungen aufzuzeigen.

### ShellCheck

- Analysiert Skripte auf Fehler, Portabilität und Stilfragen.
- Lokaler Aufruf: `shellcheck <skript>`.
- In CI-Pipelines verpflichtend.

### Bash Language Server (optional)

- Bietet Editor-Unterstützung (Autocompletion, Inlay-Hints).
- Installierbar via `npm install -g bash-language-server`.
- Im Editor als LSP aktivieren.

## Arbeitsweise

1. Skripte beginnen mit `#!/usr/bin/env bash` und enthalten `set -euo pipefail`.
2. Vor Commit: `shfmt` und `shellcheck` lokal ausführen.
3. Ergebnisse der Checks im Pull Request sichtbar machen.
4. Neue Tools → Dokumentation hier ergänzen.
5. CI-Checks sind verbindlich; Ausnahmen werden dokumentiert.

## Projektspezifische Ergänzungen

### Devcontainer-Setup

- **Bash-Version dokumentieren** (z. B. Hinweis auf `nameref` → Bash ≥4.3).
- **Paketsammlungen per Referenz (`local -n`)** statt Subshell-Kopien.
- **`check`-Ziel ignorieren**, falls versehentlich mitinstalliert.

### CLI-Bootstrap (`wgx`)

- Debug-Ausgabe optional via `WGX_DEBUG=1`.
- Dispatcher validiert Subcommands:  
  - Ohne Argument → Usage + `exit 1`.  
  - Unbekannte Befehle → Fehlermeldung auf Englisch (für CI-Logs).  
  - Usage-Hilfe auf `stderr`.

### SemVer-Caret-Ranges

- `^0.0.x` → nur Patch-Updates erlaubt.
- Major-Sprünge blockiert (`^1.2.3` darf nicht auf `2.0.0` gehen).  
- Automatisierte Bats-Tests dokumentieren dieses Verhalten.

## Troubleshooting

- Legacy-Skripte mit `# shellcheck disable=...` markieren und begründen.  
- Plattformunterschiede (Linux/macOS) im Skript kommentieren.  
- `shfmt`-Fehler → prüfen, ob Tabs statt Spaces verwendet wurden (wir nutzen nur Spaces).

---

Diese Leitlinien werden zum **Gate-C-Übergang** erneut evaluiert und ggf. in produktive Skripte überführt.  
Weitere Infos werden im Fahrplan dokumentiert.
```

### 📄 docs/process/fahrplan.md

**Größe:** 9 KB | **md5:** `f91c67532806d908e78f8f595aa60876`

```markdown
# Fahrplan

**Stand:** 2025-10-20

**Bezug:**

- ADR-0001 (Clean Slate & Monorepo)
- ADR-0002 (Re-Entry-Kriterien)
- ADR-0003 (Privacy: Unschärferadius & RoN)

## Prinzipien: mobile-first, audit-ready, klein schneiden, Metriken vor Features

## Inhalt

- [Kurzfahrplan (Gates A–D)](#kurzfahrplan-gates-ad)
- [Gate-Checkliste (A–D)](#gate-checkliste-ad)
  - [Gate A — Web (SvelteKit) *Minimal sichtbares Skelett*](#gate-a--web-sveltekit-minimal-sichtbares-skelett)
  - [Gate B — API (Axum) *Health & Kernverträge*](#gate-b--api-axum-health--kernverträge--phaseziele)
  - [Gate C — Infra-light (Compose, Caddy, PG)](#gate-c--infra-light-compose-caddy-pg--phaseziele)
  - [Gate D — Security-Basis](#gate-d--security-basis-grundlagen)
- [0) Vorbereitungen (sofort)](#0-vorbereitungen-sofort)
- [Gate A — Web (SvelteKit) *Minimal sichtbares Skelett* —
  Phaseziele](#gate-a--web-sveltekit-minimal-sichtbares-skelett--phaseziele)

---

## Kurzfahrplan (Gates A–D)

- **Gate A:** UX Click-Dummy (keine Backends)
- **Gate B:** API-Mock (lokal)
- **Gate C:** Infra-light (Compose, minimale Pfade)
- **Gate D:** Produktive Pfade (härten, Observability)

## Gate-Checkliste (A–D)

### Gate A — Web (SvelteKit) *Minimal sichtbares Skelett*

#### Checkliste „bereit für Gate B“

- [ ] Interaktiver UX-Click-Dummy ist verlinkt (README) und deckt Karte → Knoten → Zeit-UI ab.
- [ ] Contracts-Schemas (`contracts/`) für `node`, `role`, `thread` abgestimmt und dokumentiert.
- [ ] README-Landing beschreibt Click-Dummy, Contracts und verweist auf diesen Fahrplan.
- [ ] Vale-Regeln laufen gegen README/Fahrplan ohne Verstöße.
- [ ] PWA installierbar, Offline-Shell lädt Grundlayout.
- [ ] Dummy-Karte (MapLibre) sichtbar, Layout-Slots vorhanden; Budgets ≤ 60 KB / TTI ≤ 2 s
  dokumentiert.
- [ ] Minimal-Smoke-Test (Playwright) grün, Lighthouse Mobile ≥ 85.

### Gate B — API (Axum) *Health & Kernverträge*

#### Checkliste „bereit für Gate C“

- [ ] Axum-Service liefert `/health/live`, `/health/ready`, `/version`.
- [ ] OpenAPI-Stub (utoipa) generiert und CI veröffentlicht Artefakt.
- [ ] Kernverträge (`POST /nodes`, `GET /nodes/{id}`, `POST /roles`, `POST /threads`) als Stubs
  implementiert.
- [ ] `migrations/` vorbereitet (Basis-Tabellen) und CI führt `cargo fmt`, `clippy -D warnings`,
  `cargo test` aus.
- [ ] `docker compose` (nur API) startet fehlerfrei.
- [ ] Contract-Test gegen `POST /nodes` grün, OpenAPI JSON abrufbar.

### Gate C — Infra-light (Compose, Caddy, PG)

#### Checkliste „bereit für Gate D“

- [ ] `infra/compose/compose.core.yml` umfasst web, api, postgres, pgBouncer, caddy.
- [ ] `infra/caddy/Caddyfile` mit HTTP/3, strikter CSP, gzip/zstd vorhanden.
- [ ] `.env.example` komplettiert, Healthchecks für Dienste konfiguriert.
- [ ] `docker compose -f infra/compose/compose.core.yml up -d` läuft lokal ohne Fehler.
- [ ] Caddy terminiert TLS (self-signed) und proxyt Web+API korrekt.
- [ ] Web-Skelett lädt mit CSP ohne Console-Fehler.

### Gate D — Security-Basis

#### Checkliste „bereit für Re-Entry“

- [ ] Lizenz final (AGPL-3.0-or-later) bestätigt und dokumentiert.
- [ ] Secrets-Plan (sops/age) dokumentiert, keine Klartext-Secrets im Repo.
- [ ] SBOM/Scan (Trivy oder Syft) in CI aktiv, bricht bei kritischen CVEs ab.
- [ ] Runbook „Incident 0“ (Logs sammeln, Restart, Contact) verfügbar.
- [ ] CI schützt Budgets, Policies verlinkt; Observability-Basis beschrieben.

> Details, Akzeptanzkriterien, Budgets und Risiken folgen im Langteil unten.

---

## 0) Vorbereitungen (sofort)

- **Sprache & Vale:** Vale aktiv, Regeln aus `styles/Weltgewebe/*` verbindlich.
- **Lizenz gewählt:** `LICENSE` verwendet **AGPL-3.0-or-later**.
- **Issue-Backlog:** Mini-Issues je Punkt unten (30–90 Min pro Issue).

**Done-Kriterien:** Vale grün in PRs; Lizenz festgelegt; 10–20 Start-Issues.

---

## Gate A — Web (SvelteKit) *Minimal sichtbares Skelett* — Phaseziele

**Ziel:** „Karte hallo sagen“ – startfähiges Web, PWA-Shell, Basislayout, MapLibre-Stub.

### Gate A: Umfang

- PWA: `manifest.webmanifest`, Offline-Shell, App-Icon.
- Layout: Header-Slot, Drawer-Platzhalter (links: Webrat/Nähstübchen, rechts: Filter/Zeitleiste).
- Route `/`: Überschrift + Dummy-Karte (MapLibre einbinden, Tiles später).
- Budgets: **≤60 KB Initial-JS**, **TTI ≤2 s** (Mess-Skript + Budgetdatei).
- Telemetrie (Client): PerformanceObserver für Long-Tasks (nur Log/console bis Gate C).

### Gate A: Aufgabenblöcke

- **UX-Click-Dummy:** Interaktiver Ablauf für Karte → Knoten → Zeit-UI. Figma/Tool-Link im README
  vermerken.
- **Contracts-Schemas:** JSON-Schemas/OpenAPI für `node`, `role`, `thread`
  abstimmen (Basis für Gate B). Ablage unter `contracts/` und im README
  verlinken.
- **README-Landing:** Landing-Abschnitt aktualisieren (Screenshot/Diagramm +
  Hinweise zum Click-Dummy, Contracts, Fahrplan).
- **Vale-Regeln:** Vale-Regeln aus `styles/Weltgewebe/*` gegen README,
  Fahrplan und Gate-A-Dokumente prüfen, Verstöße beheben.

### Gate A: Done

- Lighthouse lokal ≥ 85 (Mobile), Budgets eingehalten.
- PWA installierbar, Offline-Shell lädt Grundlayout.
- Minimal-Smoke-Test (Playwright) läuft.

---

## Gate B — API (Axum) *Health & Kernverträge* — Phaseziele

**Ziel:** API lebt, dokumentiert und testet minimal **Kernobjekte**: Knoten, Rolle, Faden.

### Gate B: Umfang

- Axum-Service mit `/health/live`, `/health/ready`, `/version`.
- OpenAPI-Stub (utoipa) generiert.
- **Kernverträge:** `POST /nodes`, `GET /nodes/{id}`, `POST /roles`, `POST /threads`
  (Stub-Implementierung).
- `migrations/` vorbereitet (ohne Fachtabellen).
- CI: `cargo fmt`, `clippy -D warnings`, `cargo test`.

### Gate B: Done

- `docker compose` (nur API) startet grün.
- OpenAPI JSON auslieferbar, minimaler Contract-Test grün (inkl. `POST /nodes`).

---

## Gate C — Infra-light (Compose, Caddy, PG) — Phaseziele

**Ziel:** Dev-Stack per `compose.core.yml` startbar (web+api+pg+caddy).

### Gate C: Umfang

- `infra/compose/compose.core.yml`: web, api, postgres, pgBouncer, caddy.
- `infra/caddy/Caddyfile`: HTTP/3, strikte CSP (später lockern), gzip/zstd.
- `.env.example` vervollständigt; Healthchecks verdrahtet.

### Gate C: Done

- `docker compose -f infra/compose/compose.core.yml up -d` läuft lokal.
- Caddy terminiert TLS lokal (self-signed), Proxies funktionieren.
- Basic CSP ohne Console-Fehler im Web-Skelett.

---

## Gate D — Security-Basis (Grundlagen)

**Ziel:** Minimaler Schutz und Compliance-Leitplanken.

### Gate D: Umfang

- **Lizenz final** (AGPL-3.0-or-later empfohlen).
- Secrets-Plan (sops/age, kein Klartext im Repo).
- SBOM/Scan: Trivy oder Syft in CI (Fail bei kritischen CVEs).
- Doku-Pfad: Kurz-Runbook „Incident 0“ (Logs sammeln, Restart, Contact).

### Gate D: Done

- Lizenz im Repo, CI bricht bei kritischen CVEs.
- Runbook-Skelett vorhanden.

---

## Phase A (Woche 1–2): **Karten-Demo, Zeit-UI, Knoten-Placement**

- Karte sichtbar (MapLibre), Dummy-Layer, UI-Skeleton für Filter & Zeitleiste.
- Zeit-Slider (UI) ohne Datenwirkung, nur State/URL-Sync.
- **Knoten anlegen (UI)**: kleines Formular (Name), flüchtige Speicherung (Client/Mem), Marker
  erscheint.
- Mobile-Nav-Gesten (Drawer wischen).

**Akzeptanz:** Mobile Lighthouse ≥ 90; TTI ≤ 2 s; UI-Flows klickbar; Knoten-Form erzeugt Marker.

---

## Phase B (Woche 3–4): **Kernmodell — Knoten, Rolle, Faden**

- Domain-Events: `node.created`, `role.created`, `thread.created`.
- Tabellen (PG): `nodes`, `roles`, `threads` (nur ID/Meta), Outbox (leer, aber vorhanden).
- API: `POST /nodes`, `GET /nodes/{id}` echt (PG); `POST /roles`, `POST /threads` stub.
- Web: „Rolle drehen 7 Sekunden“ (UI-Effekt), Faden-Stub Linie Rolle→Knoten (Fake-Data).

**Akzeptanz:** Knoten persistiert in PG; Faden-Stub sichtbar; E2E-Flow „Knoten knüpfen“ klickbar.

---

## Phase C (Woche 5–6): **Privacy-UI (ADR-0003) & 7-Tage-Verblassen**

- UI: **Unschärferadius-Slider** + **RoN-Toggle** (Profil-State; Fake-Persist).
- Zeitleiste wirkt auf Sichtbarkeit (Fäden/Knoten blenden weich aus; Client-seitig).
- `public_pos` im View-Modell (Fake-Backend oder Local-Derivation).

**Akzeptanz:** Vorschau der öffentlichen Position reagiert; Zeitleiste verhält sich wie
spezifiziert.

---

## Phase D (Woche 7–8): **Persistenz komplett & Outbox-Hook**

- API: echte Writes für Rolle/Faden in PG; Outbox-Write (noch ohne NATS-Relay).
- Worker-Stub: CLI liest Outbox und füllt Read-Model `public_role_view`.
- Web: liest Read-Model, zeigt `public_pos`, respektiert RoN-Flag.

**Akzeptanz:** Neustart-fest; nach Write→Read-Model erscheint korrekte `public_pos`.

---

## Messpunkte & Budgets

- Web: Initial-JS ≤ 60 KB; p75 Long-Tasks ≤ 200 ms/Route.
- API: p95 Latenz ≤ 300 ms (lokal); Fehlerquote < 1 %.
- Compose-Start ≤ 30 s bis „grün“.

---

## Risiken (kurz)

- Überplanung bremst Tempo → **kleine Issues** erzwingen.
- Privacy-Erwartung vs. Transparenz-Standard → UI-Texte klar formulieren.
- Mobile-Leistung → Budgets als CI-Gate früh aktivieren.

---

## Nächste konkrete Schritte

1. Gate A-Issues anlegen, PWA/Map-Stub bauen.
2. Compose core vorbereiten (web+api+pg+caddy), Caddy mit CSP.
3. API Gate B: `POST /nodes` als erster echter Vertrag, einfache PG-Migration `nodes`.
4. Privacy-UI (Slider/Toggle) per Feature-Flag einhängen.
```

### 📄 docs/process/sprache.md

**Größe:** 826 B | **md5:** `4557cff8f801c413a82df07f72ad138c`

```markdown
# Sprache & Ton im Weltgewebe

## 1. Grundsatz

- Primärsprache Deutsch (Duden-nah), Du-Form, präzise, knapp.
- Keine Gender-Sonderzeichen (Stern, Doppelpunkt, Binnen-I, Mediopunkt, Slash).
- Anglizismen nur bei echten Fachbegriffen ohne gutes deutsches Pendant.

## 2. Formatkonventionen

- UI: 24-h-Zeit, TT.MM.JJJJ, Dezimalkomma.
- Code/Protokolle: ISO-8601, Dezimalpunkt, SI-Einheiten.

## 3. Artefakte

- Commits: Conventional Commits; Kurzbeschreibung deutsch.
- Code-Kommentare: Englisch (knapp); ADRs/Domäne: Deutsch.
- PRs: deutsch, mit Evidenz-Verweisen.

## 4. Verbote & Alternativen

- Verboten: Schüler:innen, Schüler*innen, SchülerInnen, Schüler/innen, Schüler·innen.
- Nutze Alternativen: Lernende, Team, Ansprechperson, Beteiligte.

## 5. Prüfung

- Vale als Prose-Linter; PR blockt bei Verstößen.
```


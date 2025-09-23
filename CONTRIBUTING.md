Hier ist das finale CONTRIBUTING.md – optimiert, konsistent mit docs/architekturstruktur.md, und so geschrieben, dass Menschen und KIs sofort wissen, was wohin gehört, warum, und wie gearbeitet wird.

⸻

CONTRIBUTING.md

Weltgewebe – Beiträge, Qualität, Wegeführung

Dieses Dokument erklärt, wie im Weltgewebe-Repository gearbeitet wird: Ordner-Orientierung, Workflows, Qualitätsmaßstäbe und Entscheidungswege. Es baut auf folgenden Dateien auf:
	•	docs/architekturstruktur.md – verbindliche Repo-Struktur (Ordner, Inhalte, Zweck)
	•	docs/techstack.md – Stack-Referenz (SvelteKit, Rust/Axum, Postgres+Outbox, JetStream, Caddy, Observability)
	•	ci/budget.json – Performance-Budgets (Frontend)
	•	docs/runbook.md – Woche-1/2, DR/DSGVO-Drills
	•	docs/datenmodell.md – Tabellen, Projektionen, Events

Kurzprinzip: „Richtig routen, klein schneiden, sauber messen.“
Beiträge landen im richtigen Ordner, klein und testbar, mit Metriken und Budgets im Blick.

⸻

1) Repo-Topographie in 30 Sekunden
	•	apps/ – Business-Code (Web-Frontend, API, Worker, optionale Search-Adapter)
	•	packages/ – gemeinsame Libraries/SDKs (optional)
	•	infra/ – Compose-Profile, Proxy (Caddy), DB-Init, Monitoring, optional Nomad/K8s
	•	docs/ – ADRs, Architektur-Poster, Datenmodell, Runbook, CONTRIBUTING
	•	ci/ – GitHub-Workflows, Skripte, Performance-Budgets
	•	Root – .env.example, Editor/Git-Konfig, Lizenz, README

Details: siehe docs/architekturstruktur.md.

⸻

2) Routing-Matrix „Wohin gehört was?“

Beitragstyp	Zielordner/Datei	Typisches Pattern	Grund (warum dort)
Neue Seite/Route im UI	apps/web/src/routes/...	+page.svelte, +page.ts, +server.ts	SvelteKit-Routing, SSR/Islands, nahe an UI
UI-Komponente/Store/Util	apps/web/src/lib/...	*.svelte, stores.ts, utils.ts	Wiederverwendung, klare Trennung vom Routing
Statische Assets	apps/web/static/	manifest.webmanifest, Icons, Fonts	Build-unabhängige Auslieferung
Neuer API-Endpoint	apps/api/src/routes/...	mod.rs, Handler, Router	HTTP/SSE-Schnittstelle gehört in routes
Geschäftslogik/Service	apps/api/src/domain/...	Use-Case-Funktionen	Fachlogik von I/O trennen
DB-Zugriff (nur PG)	apps/api/src/repo/...	sqlx-Queries, Mappings	Konsistente Datenzugriffe
Outbox-Publizierer/Eventtypen	apps/api/src/events/...	publish_*, Event-Schema	Transaktionale Events am SoT
DB-Migrationen	apps/api/migrations/	YYYYMMDDHHMM__beschreibung.sql	Änderungsverfolgung am Schema
Timeline-Projektor	apps/worker/src/projector_timeline.rs	Outbox → Timeline	Read-Model separat, idempotent
Search-Projektor	apps/worker/src/projector_search.rs	Outbox → Typesense/Meili	Indexing asynchron
DSGVO/DR-Rebuilder	apps/worker/src/replayer.rs	Replay/Shadow-Rebuild	Audit-/Forget-Pfad
Search-Adapter/SDK	apps/search/adapters/...	typesense.ts, meili.ts	Client-Adapter gekapselt
Compose-Profile	infra/compose/*.yml	compose.core.yml usw.	Start-/Betriebsprofile
Proxy/Headers/CSP	infra/caddy/Caddyfile	HTTP/3, TLS, CSP	Auslieferung & Sicherheit
DB-Init/Partitionierung	infra/db/{init,partman}/	Extensions, Partman	Basis-Setup für PG
Monitoring	infra/monitoring/...	prometheus.yml, Dashboards, Alerts	Metriken, SLO-Wächter
Architektur-Entscheidung	docs/adr/ADR-xxx.md	Datum- oder Nummernschema	Nachvollziehbarkeit
Runbook	docs/runbook.md	Woche-1/2, DR/DSGVO	Betrieb in der Praxis
Datenmodell	docs/datenmodell.md	Tabellen/Projektionen	Referenz für API/Worker


⸻

3) Arbeitsweise / Workflow

Branch-Strategie: kurzes Feature-Branching gegen main. Kleine, thematisch fokussierte PRs.
Commit-Präfixe:
	•	feat(web): … | feat(api): … | feat(worker): … | feat(infra): …
	•	fix(...) | chore(...) | refactor(...) | docs(adr|runbook|...)

PR-Prozess:
	1.	Lokal: Lints/Tests/Budgets laufen lassen.
	2.	PR klein halten, Zweck und „Wie getestet“ kurz erläutern.
	3.	Bei Architektur- oder Sicherheitsauswirkungen: ADR oder Runbook-Update beilegen/verlinken.

CI-Gates (brechen Builds):
	•	Frontend-Budget aus ci/budget.json (Initial-JS ≤ 60 KB, TTI ≤ 2000 ms).
	•	Lints/Formatter (Web: ESLint/Prettier; API/Worker: cargo fmt, cargo clippy -D).
	•	Tests (npm test, cargo test).
	•	Sicherheitschecks (cargo audit/deny), Konfiglint (Prometheus, Caddy).

⸻

4) Qualitätsmaßstäbe je Schicht

Frontend (SvelteKit):
	•	SSR/PWA-freundlich; Caching per Header (Caddy).
	•	Insel-Denken: nur nötiges JS auf die Route.
	•	Budget: ≤60 KB Initial-JS, TTI ≤2000 ms (3G).
	•	Routen unter src/routes, Bausteine unter src/lib.
	•	RUM/Long-Tasks optional via hooks.client.ts.

API (Rust/Axum):
	•	Layer: routes (I/O) → domain (Fachlogik) → repo (sqlx, PG).
	•	Postgres-only, Migrations in migrations/.
	•	Outbox-Write transaktional, Events minimal (IDs, wenige Felder).
	•	Telemetrie: strukturiertes Logging, /metrics für Prometheus.

Worker:
	•	Idempotente Projektoren (Event-Wiederholung vertragen).
	•	Lag/Throughput messen, Backoff/Retry setzen.
	•	Projektionen und Indizes schlank halten (nur benötigte Felder).
	•	Replayer für DSGVO/DR pflegen und regelmäßig testen (Runbook).

Search (Typesense/Meili):
	•	Delta-Indexierung ereignisbasiert, Dokumente minimal.
	•	Feldevolution über Versionierung (abwärtskompatibel halten).

GIS (falls genutzt):
	•	Geometrien in PostGIS (GiST), H3-Spalten für Nachbarschaften.
	•	BRIN/Partitionen für Event-/Timeline-Tabellen.

⸻

5) Daten & Events – Konsistenzpfad

Source of Truth: PostgreSQL + Outbox.
Event-Namen: <aggregate>.<verb> (z. B. post.created, comment.deleted).
Payload-Prinzip: IDs + minimal nötige Felder. Schema-Version bei Änderungen.

Minimal-Beispiel (Event-Payload):

{
  "schema": "post.created@1",
  "aggregate_id": "5cfe6f3e-…",
  "occurred_at": "2025-09-11T12:34:56Z",
  "by": "account:…",
  "data": {
    "thread_id": "…",
    "author_id": "…",
    "h3_9": 613566756…
  }
}

Projektionsfluss: Outbox → JetStream → Projector → Read-Model / Timeline / Search.
DSGVO/Forget: Redaktions-/Lösch-Events erzeugen; Rebuild (Shadow) und Nachweis im Runbook.

⸻

6) Performance & Observability
	•	Frontend: Budgets gemäß ci/budget.json. Regelmäßige Lighthouse-Checks.
	•	Server: Ziel-Latenzen p95 route-spezifisch definieren (API, SSE).
	•	JetStream: Topic/Consumer-Lag überwachen; Consumer-Namen stabil halten; Ack-Strategie dokumentieren.
	•	Edge/Cache: s-maxage für SSR-HTML, immutable Assets über Caddy, Tiles/Prebakes getrennt cachen.

⸻

7) Sicherheit & Compliance (Kurz)
	•	Secrets: niemals ins Repo; .env.example als Vorlage.
	•	PII: isolieren gemäß Datenmodell; keine PII in Logs/Events.
	•	CSP/CORS: per Caddyfile verwalten; restriktiv beginnen, bei Bedarf öffnen.
	•	Auditierbarkeit: sicherheitsrelevante Änderungen mit ADR begründen.

⸻

8) Lokaler Quickstart

# 1) .env anlegen
cp .env.example .env

# 2) Core-Profile hochfahren (API, Web, PG, PgBouncer, Caddy)
docker compose -f infra/compose/compose.core.yml up -d

# 3) DB-Migrationen
docker exec -it welt_api sqlx migrate run   # oder eigenes Migrations-Binary

# 4) Web-Dev
cd apps/web && npm install && npm run dev   # http://localhost:3000

# 5) Tests
cd apps/api && cargo test
cd ../web && npm test

# 6) Budgets lokal prüfen (falls Skript vorhanden)
node ci/scripts/lhci.mjs

Weitere Profile: compose.stream.yml (JetStream), compose.search.yml (Typesense/Meili), compose.observ.yml (Prom/Grafana).

⸻

9) Doku & Entscheidungen

ADR-Pflicht bei:
	•	neuem Framework/Tool,
	•	Datenmodell-/Event-Änderungen mit Folgen,
	•	Sicherheits-/Compliance-Themen,
	•	SLO/Monitoring-Regeländerungen.

Schreibe docs/adr/ADR-<laufende_nummer>__<kurztitel>.md mit: Kontext → Entscheidung → Alternativen → Konsequenzen.
Aktualisiere Runbook (Betrieb/Drills) und Datenmodell (Tabellen/Projektionen) bei Bedarf.

⸻

10) Versionierung & Releases (Kurz)
	•	SemVer: MAJOR.MINOR.PATCH
	•	Breaking Changes → MAJOR erhöhen, ADR ergänzen.
	•	Tagging und Changelog optional; CI kann Release-Artefakte bauen.

⸻

11) Entscheidungsbaum „Wohin mit meinem Beitrag?“

Start
 ├─ Ist es UI (Seite/Komponente/Store)?
 │    └─ apps/web/src/(routes|lib)
 ├─ Ist es ein API-Endpunkt / Server-Use-Case?
 │    ├─ Handler → apps/api/src/routes
 │    ├─ Logik  → apps/api/src/domain
 │    └─ DB     → apps/api/src/repo (+ migrations/)
 ├─ Ist es ein Event-Projektor / Replayer?
 │    └─ apps/worker/src/(projector_*|replayer.rs)
 ├─ Geht es um Suche?
 │    ├─ Projektor → apps/worker/src/projector_search.rs
 │    └─ Adapter  → apps/search/adapters
 ├─ Infrastruktur / Deploy / Monitoring?
 │    └─ infra/(compose|caddy|db|monitoring|nomad|k8s)
 └─ Dokumentation / Entscheidung / Runbook?
      └─ docs/(adr|runbook|datenmodell|techstack)

PR-Checkliste (kurz):
	•	Lints/Formatter/Tests lokal grün
	•	Frontend-Budgets eingehalten (falls UI)
	•	Migrationen geprüft (falls DB) – mit Rollback-Gedanken
	•	Event-Schema minimal & versioniert (falls Events)
	•	Doku/ADR/Runbook aktualisiert (falls nötig)
	•	Zweck & „Wie getestet“ in der PR-Beschreibung

⸻

12) Anhänge (kleine Referenzen)

Namensregeln:
	•	Rust: snake_case; TypeScript: kebab-case; ENV: UPPER_SNAKE.
	•	Standard-Ordner: routes/, domain/, repo/, events/, migrations/, telemetry/.

Beispiel-Commit-Nachrichten:

feat(web): neue karte mit layer-toggle (pwa friendly)
fix(api): race-condition im timeline-endpunkt behoben
docs(adr): ADR-012 jetstream-lag-alarme ergänzt
infra(compose): search-profile (typesense+keydb) aktiviert

Beispiel-Migration (Kopfkommentar):

-- 2025-09-11 add_post_stats
-- Kontext: Zählerprojektion für Reaktions-/Kommentarzahl
-- Rollback: DROP TABLE post_stats;

CREATE TABLE post_stats (
  post_id uuid PRIMARY KEY REFERENCES post(id) ON DELETE CASCADE,
  reactions int NOT NULL DEFAULT 0,
  comments  int NOT NULL DEFAULT 0,
  last_activity_at timestamptz
);


⸻

Schlusswort

Dieses Dokument ist die Arbeitslandkarte.
Bei Unklarheiten: zuerst docs/architekturstruktur.md (Ordner), dann docs/ (Entscheidungen/Runbooks), danach kleiner PR, sauber getestet.
So bleibt Weltgewebe mobil-first, messbar schnell und audit-fest.
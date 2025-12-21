# Architektur & Struktur

Dieses Dokument beschreibt die Zielstruktur des Weltgewebe-Repositories. Es dient als Referenzrahmen,
damit sich Contributors schnell orientieren können und klar ist, wo welche Verantwortlichkeiten liegen.
Wo die Realität aktuell noch abweicht (z.B. fehlender `apps/worker`), ist dies explizit markiert.

⸻

ASCII-Baum

Damit das Weltgewebe langfristig wartbar bleibt, folgt das Repo einer bewusst
einfachen, aber erweiterbaren Struktur:

```txt
weltgewebe/weltgewebe-repo/
├─ apps/                         # Ausführbare Anwendungen (Web, API, Worker)
│  ├─ web/                       # SvelteKit-Frontend (PWA, MapLibre)
│  │  ├─ src/
│  │  │  ├─ routes/             # Seiten, Endpunkte (+page.svelte/+server.ts)
│  │  │  ├─ lib/                # UI-Komponenten, Stores, Utilities
│  │  │  ├─ hooks.client.ts     # RUM-Initialisierung (LongTasks)
│  │  │  └─ app.d.ts            # App-Typdefinitionen
│  │  ├─ static/                # Fonts, Icons, manifest.webmanifest
│  │  ├─ tests/                 # Frontend-Tests (Vitest, Playwright)
│  │  ├─ svelte.config.js
│  │  ├─ vite.config.ts
│  │  └─ README.md
│  │
│  ├─ api/                      # Rust (Axum) – REST + SSE
│  │  ├─ src/
│  │  │  ├─ main.rs             # Einstiegspunkt, Router
│  │  │  ├─ routes/             # HTTP- und SSE-Endpunkte
│  │  │  ├─ domain/             # (geplant) Geschäftslogik, Services
│  │  │  ├─ repo/               # (geplant) SQLx-Abfragen, Postgres-Anbindung
│  │  │  ├─ events/             # (geplant) Outbox-Publisher, Eventtypen
│  │  │  └─ telemetry/          # Prometheus/OTel-Integration
│  │  ├─ migrations/            # Datenbankschemata, pg_partman
│  │  ├─ tests/                 # API-Tests (Rust)
│  │  ├─ Cargo.toml
│  │  └─ README.md
│  │
│  ├─ worker/                   # (geplant) Projector/Indexer/Jobs
│  │                             # Aktuell noch nicht im Repo angelegt.
│  └─ search/                   # (optional, geplant) Such-Adapter/SDKs
│                                # Wird bei Bedarf als eigener Ordner ergänzt.
│
├─ contracts/                   # Datenverträge & Schemata (JSON Schema)
│  ├─ domain/                   # Schemata für Kernentitäten (Node, Edge, ...)
│  └─ README.md
│
├─ packages/                    # (optional) Geteilte Libraries/SDKs
│  └─ README.md
│
├─ infra/                       # Betrieb/Deployment/Observability
│  ├─ compose/                  # Docker Compose Profile
│  │  ├─ compose.core.yml       # Basis-Stack: web, api, db, caddy
│  │  ├─ compose.observ.yml     # Monitoring: Prometheus, Grafana, Loki/Tempo
│  │  ├─ compose.stream.yml     # (optional) Event-Streaming: NATS/JetStream
│  │  └─ compose.search.yml     # (optional) Suche: Typesense/Meili, KeyDB
│  ├─ caddy/
│  │  └─ Caddyfile              # Proxy, HTTP/3, CSP, TLS
│  ├─ compose/
│  │  ├─ sql/
│  │  │  └─ init/               # SQL-Init-Skripte, Extensions (z.B. uuid-ossp, pgcrypto)
│  │  └─ monitoring/
│  │     └─ prometheus.yml      # Prometheus-Konfiguration
│  │
│  │  # Hinweis:
│  │  # Die frühere Unterscheidung `infra/db` und `infra/monitoring`
│  │  # wurde in der Realität durch `infra/compose/sql` und
│  │  # `infra/compose/monitoring` ersetzt.
│  ├─ nomad/                    # (optional, geplant) Orchestrierungsspezifikationen
│  └─ k8s/                      # (optional, geplant) Kubernetes-Manifeste
│
├─ docs/                        # Dokumentation & Entscheidungen
│  ├─ adr/                      # Architecture Decision Records
│  │  └─ ADR-0005-auth.md       # Minimales Auth-Konzept
│  ├─ techstack.md              # Techstack v3.2 (Referenz)
│  ├─ datenmodell.md            # Datenbank- und Projektionstabellen
│  └─ runbook.md                # Woche-1/2 Setup, DR/DSGVO-Drills
│
├─ .github/
│  └─ workflows/                # GitHub Actions für Build, Tests, Infra
│                               # (z.B. ci.yml, web-e2e.yml, infra.yml, metrics.yml, links.yml)
├─ policies/                    # Governance & Qualitäts-Geländer
│  ├─ limits.yaml               # Budget-Grenzen (z.B. max. Payload-Größe)
│  ├─ perf.json                 # Performance-Budgets (Frontend)
│  ├─ retention.yml             # Aufbewahrungsfristen
│  ├─ security.yml              # Minimal-Sicherheitsanforderungen
│  └─ slo.yaml                  # SLO-/SLI-Definitionen
├─ scripts/                     # Hilfsskripte (Setup, Metriken, Domain-Checks, Dev-Helper)
│  ├─ dev/
│  │  └─ gewebe-demo-server.mjs
│  ├─ tools/
│  │  ├─ json_escape
│  │  ├─ uv-pin.sh
│  │  └─ yq-pin.sh
│  ├─ contracts-domain-check.sh # Domain-Verträge (JSON Schema) prüfen
│  ├─ setup.sh                  # Lokales Setup (Rust-Tooling, etc.)
│  └─ wgx-metrics-snapshot.sh   # Metrik-Snapshot für WGX
│
├─ .env.example                 # Beispiel-Umgebungsvariablen
├─ .editorconfig                # Editor-Standards
├─ .gitignore                   # Ignorier-Regeln
├─ LICENSE                      # Lizenztext
└─ README.md                    # Projektüberblick, Quickstart

⸻

Erläuterungen zu den Hauptordnern

- **apps/**
  Enthält ausführbare Anwendungen: Web-Frontend (SvelteKit) und API (Rust/Axum). Worker (Eventprojektionen, Rebuilds)
  und optionale Search-Adapter sind im Architekturplan vorgesehen, aber aktuell noch nicht angelegt.
  Jeder Unterordner ist eine eigenständige App mit eigenem README und Build-Konfig.
- **packages/**
  Platz für geteilte Libraries oder SDKs, die von mehreren Apps genutzt werden. Wird erst angelegt, wenn Bedarf an
  gemeinsamem Code entsteht.
- **infra/**
  Infrastruktur- und Deployment-Ebene. Compose-Profile für verschiedene Betriebsmodi (`infra/compose/*.yml`),
  Caddy-Konfiguration (`infra/caddy`), DB-Init (`infra/compose/sql/init`), Monitoring-Setup (`infra/compose/monitoring`).
  Optional Nomad- oder Kubernetes-Definitionen für spätere Skalierung können als `infra/nomad` bzw. `infra/k8s` ergänzt werden.
- **docs/**
  Dokumentation und Architekturentscheidungen. Enthält ADRs, Techstack-Beschreibung, Diagramme,
  Datenmodellübersicht und Runbooks.
- **.github/workflows/**
  Alle GitHub-Actions-Workflows rund um Continuous Integration/Deployment (Builds, Tests, Link-Checks, Metrics).
- **scripts/**
  Hilfsskripte für Setup, Domain-Checks, Dev-Demos und Metriken.
- **policies/**
  Zentrale Budgets und Leitplanken (Performance, Limits, Retention, Security, SLOs).
- **Root**
  Repository-Metadaten: .env.example (Vorlage), Editor- und Git-Configs, Lizenz und README mit Projektüberblick.

⸻

Zusammenfassung

Diese Struktur spiegelt den aktuellen Techstack (v3.2) wider:

- Mobil-first via PWA (SvelteKit).
- Rust/Axum API mit Outbox/JetStream-Eventing.
- Compose-first Infrastruktur mit klar getrennten Profilen.
- Observability und Compliance fest verankert.
- Erweiterbar durch optionale packages/, nomad/, k8s/.

Dies dient als Referenzrahmen für alle weiteren Arbeiten am Weltgewebe-Repository.

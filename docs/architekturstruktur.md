Weltgewebe – Repository-Struktur

Dieses Dokument beschreibt den Aufbau des Repositories.
Ziel: Übersicht für Entwickler und KI, damit alle Beiträge am richtigen Ort landen.

⸻

ASCII-Baum

weltgewebe/weltgewebe-repo/
├─ apps/                       # Anwendungen (Business-Code)
│  ├─ web/                      # SvelteKit-Frontend (PWA, MapLibre)
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
│  │  │  ├─ domain/             # Geschäftslogik, Services
│  │  │  ├─ repo/               # SQLx-Abfragen, Postgres-Anbindung
│  │  │  ├─ events/             # Outbox-Publisher, Eventtypen
│  │  │  └─ telemetry/          # Prometheus/OTel-Integration
│  │  ├─ migrations/            # Datenbankschemata, pg_partman
│  │  ├─ tests/                 # API-Tests (Rust)
│  │  ├─ Cargo.toml
│  │  └─ README.md
│  │
├─ infra/                       # Betrieb/Deployment/Observability
│  ├─ compose/                  # Docker Compose Profile
│  │  ├─ compose.core.yml       # Basis-Stack: web, api, db, caddy
│  │  ├─ compose.observ.yml     # Monitoring: Prometheus, Grafana, Loki/Tempo
│  │  ├─ compose.stream.yml     # Event-Streaming: NATS/JetStream
│  │  └─ compose.search.yml     # Suche: Typesense/Meili, KeyDB
│  ├─ caddy/
│  │  ├─ Caddyfile              # Proxy, HTTP/3, CSP, TLS
│  │  └─ README.md
│  ├─ db/
│  │  ├─ init/                  # SQL-Init-Skripte, Extensions (postgis, h3)
│  │  ├─ partman/               # Partitionierung (pg_partman)
│  │  └─ README.md
│  ├─ monitoring/
│  │  ├─ prometheus.yml         # Prometheus-Konfiguration
│  │  ├─ grafana/
│  │  │  ├─ dashboards/         # Web-Vitals, JetStream, Edge-Kosten
│  │  │  └─ alerts/             # Alarme: Opex, Lag, LongTasks
│  │  └─ README.md
│  ├─ nomad/                    # (optional) Orchestrierungsspezifikationen
│  └─ k8s/                      # (optional) Kubernetes-Manifeste
│
├─ docs/                        # Dokumentation & Entscheidungen
│  ├─ adr/                      # Architecture Decision Records
│  │  ├─ ADR-0005-auth.md      # Minimales Auth-Konzept
│  ├─ techstack.md              # Techstack v3.2 (Referenz)
│  ├─ architektur.ascii         # Architektur-Poster/ASCII-Diagramme
│  ├─ datenmodell.md            # Datenbank- und Projektionstabellen
│  └─ runbook.md                # Woche-1/2 Setup, DR/DSGVO-Drills
│
├─ ci/                          # CI/CD & Qualitätsprüfungen
│  ├─ github/
│  │  └─ workflows/             # GitHub Actions für Build, Tests, Infra
│  │     ├─ web.yml
│  │     ├─ api.yml
│  │     └─ infra.yml
│  ├─ scripts/                  # Hilfsskripte (migrate, seed, db-wait)
│  └─ budget.json               # Performance-Budgets (≤60KB JS, ≤2s TTI)
│
├─ .env.example                 # Beispiel-Umgebungsvariablen
├─ .editorconfig                # Editor-Standards
├─ .gitignore                   # Ignorier-Regeln
├─ LICENSE                      # Lizenztext
└─ README.md                    # Projektüberblick, Quickstart

⸻

Erläuterungen zu den Hauptordnern

- **apps/**
  Enthält alle Anwendungen: Web-Frontend (SvelteKit) und API (Rust/Axum). Jeder Unterordner ist eine eigenständige App mit eigenem README und Build-Konfig.
- **infra/**
  Infrastruktur- und Deployment-Ebene. Compose-Profile für verschiedene Betriebsmodi, Caddy-Konfiguration,
  DB-Init, Monitoring-Setup. Optional Nomad- oder Kubernetes-Definitionen für spätere Skalierung.
- **docs/**
  Dokumentation und Architekturentscheidungen. Enthält ADRs, Techstack-Beschreibung, Diagramme,
  Datenmodellübersicht und Runbooks.
- **ci/**
  Alles rund um Continuous Integration/Deployment: Workflows für GitHub Actions, Skripte für Tests/DB-Handling,
  sowie zentrale Performance-Budgets (Lighthouse).
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

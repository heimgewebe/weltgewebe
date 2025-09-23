<!-- Repo ist aktuell Docs-only. Befehle für spätere Gates sind unten als Vorschau markiert. -->
<!-- Docs-only (ADR-0001 Clean-Slate) • Re-Entry via Gates A–D -->
# Weltgewebe

Mobil-first Webprojekt auf SvelteKit (Web), Rust/Axum (API), Postgres+Outbox, JetStream, Caddy.  
Struktur und Beiträge: siehe `architekturstruktur.md` und `CONTRIBUTING.md`.

## Quickstart
```bash
cp .env.example .env
docker compose -f infra/compose/compose.core.yml up -d
# API migrieren (siehe apps/api/README.md), Web starten (apps/web/README.md)

> **Hinweis:** Aktuell **Docs-only/Clean-Slate** gemäß ADR-0001. Code-Re-Entry erfolgt über die Gates A–D (siehe `docs/process/fahrplan.md`).


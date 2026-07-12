---
id: docs.techstack
title: Techstack
doc_type: architecture
status: active
summary: Tatsächlich vorhandener Technologie-Stack, getrennt nach Betrieb, Implementierung und Planung.
relations:
  - type: relates_to
    target: architecture/overview.md
  - type: relates_to
    target: docs/architekturstruktur.md
  - type: relates_to
    target: docs/datenmodell.md
---

# Techstack

Dieses Dokument trennt vier Zustände. „Im Repository vorhanden“ bedeutet nicht
automatisch „produktiv betrieben“.

## Heute implementiert und kanonisch

### Web

- SvelteKit 2 und Svelte 5
- TypeScript und Vite
- statischer Adapter
- MapLibre GL und PMTiles
- Playwright und Vitest
- pnpm 9 mit versioniertem Lockfile

### API

- Rust 2021
- Axum 0.8 und Tokio
- sqlx für PostgreSQL
- WebAuthn über `webauthn-rs`
- SMTP über `lettre`
- Prometheus-Metriken

`rust-version = 1.85.0` beschreibt die minimale Cargo-Kompatibilität des
API-Pakets. Die repositoryweit gepinnte Entwicklungs-/CI-Toolchain kann neuer
sein. Beide Angaben sind verschiedene Verträge und dürfen nicht gleichgesetzt
werden.

### Datenhaltung

- PostgreSQL als Produktionswahrheit für Accounts/Garnrollen, Knoten, Fäden,
  Sitzungen, Passkey-Credentials und Migrationen
- JSONL als lokaler, Legacy-, Import-/Export- und expliziter Rollbackpfad
- fail-closed Lese- und Schreibschalter, damit keine versteckte Doppelwahrheit
  entsteht
- kein allgemeiner Transactional-Outbox-Pfad
- kein vollständig belegtes PostGIS-Modell; Koordinaten liegen derzeit als
  `DOUBLE PRECISION` vor

### Delivery

- Docker und Docker Compose
- Caddy als Frontdoor und Reverse Proxy
- VPS-Ziel `wg-prod-1`
- statische interne Caddy-Auslieferung von `apps/web/build`
- Cloudflare- und Vercel-Status als zusätzliche Build-/Vorschaubelege

### Qualität und Sicherheit

- GitHub Actions mit Rust-, Web-, Datenbank-, Auth-, Proxy-, Basemap- und
  CodeQL-Prüfungen
- externe GitHub Actions und reusable Workflows sind auf 40-stellige Commit-SHAs
  gepinnt; lokale Actions und `docker://` folgen der im Guard dokumentierten
  Ausnahmepolicy
- `cargo deny`
- Domain-Contract-Validierung
- Security-Header-Policy in `policies/security.yml`, statisch geprüft gegen
  produktionsrelevante Caddyfiles
- Caddy-Adaptions- und Compose-Vorprüfungen
- logische PostgreSQL-Backups und Restore-Proofs über `scripts/ops/`
- risikogewichtetes, head- und diffgebundenes Selbstreview vor Merge

## Im Repository vorhanden, aber nicht allgemein produktiv belegt

- NATS im Produktions-Compose und API-Verbindungsfläche
- PgBouncer im Core-Profil
- Prometheus-Konfiguration und optionale Observability-Profile
- PWA-/Offline-nahe Webbestandteile
- Gesprächs-, Nachrichten- und Rollencontracts

Für diese Punkte ist jeweils ein eigener Runtime- oder Ende-zu-Ende-Beleg nötig.

## Geplant oder noch unvollständig

- Entfernung der nullable Legacy-`mode`-Rollbackspalte nach eigenem Post-Cutover-Beleg
- Gespräche und Nachrichten
- föderale Governance und Gewebekonten
- normalisierte Geoabfragen beziehungsweise PostGIS
- verlässliche Eventprojektionen und Outbox
- konsolidierte Observability mit definierten SLOs
- WAL-/PITR- oder Object-Lock-Backupstrategie, falls sie betrieblich benötigt
  wird

## Nicht aktueller Standard

Folgende Technologien sind keine heutige Betriebswahrheit und dürfen nur nach
einer neuen Architekturentscheidung als Standard bezeichnet werden:

- Nomad oder Kubernetes als Primärorchestrierung
- Multi-AZ- oder Multi-Region-Betrieb
- KeyDB
- Typesense oder MeiliSearch
- Debezium
- Loki/Tempo als vollständig betriebene Plattform
- automatische Cosign-/SLSA-Attestierung aller Artefakte
- automatisierte Rotation sämtlicher Schlüssel

## Entscheidungsregel

Eine neue Technologie wird erst Teil des kanonischen Stacks, wenn

1. ein konkretes Produkt- oder Betriebsproblem belegt ist,
2. der einfachere vorhandene Stack nicht genügt,
3. Betriebs- und Wiederherstellungspfad definiert sind,
4. Tests und Ownership existieren,
5. die Änderung in Code oder Runtime nachgewiesen ist.

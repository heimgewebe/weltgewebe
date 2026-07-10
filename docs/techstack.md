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

- JSONL als Standardquelle für Domänendaten
- PostgreSQL-Tabellen für Sitzungen, Accounts, Knoten, Fäden und
  Passkey-Credentials
- getrennte opt-in Lese- und Schreibschalter für den PostgreSQL-Cutover
- kein allgemeiner Transactional-Outbox-Pfad
- kein vollständig belegtes PostGIS-Modell; Koordinaten liegen derzeit als
  `DOUBLE PRECISION` vor

### Delivery

- Docker und Docker Compose
- Caddy als Frontdoor und Reverse Proxy
- VPS-Ziel `wg-prod-1`
- statischer Web-Upstream über eine extern konfigurierte Hostingplattform
- Cloudflare- und Vercel-Status als zusätzliche Build-/Vorschaubelege

### Qualität und Sicherheit

- GitHub Actions mit Rust-, Web-, Datenbank-, Auth-, Proxy-, Basemap- und
  CodeQL-Prüfungen
- `cargo deny`
- Domain-Contract-Validierung
- Caddy-Adaptions- und Compose-Vorprüfungen
- risikogewichtetes, head- und diffgebundenes Selbstreview vor Merge

## Im Repository vorhanden, aber nicht allgemein produktiv belegt

- NATS im Produktions-Compose und API-Verbindungsfläche
- PgBouncer im Core-Profil
- Prometheus-Konfiguration und optionale Observability-Profile
- PostgreSQL-Domainlese- und einzelne Schreibpfade
- PostgreSQL-Passkeypersistenz
- PWA-/Offline-nahe Webbestandteile
- Gesprächs-, Nachrichten- und Rollencontracts

Für diese Punkte ist jeweils ein eigener Runtime- oder Ende-zu-Ende-Beleg nötig.

## Geplant oder noch unvollständig

- vollständiger JSONL-zu-PostgreSQL-Cutover
- einheitliches Garnrollenmodell ohne RoN-Kontotyp
- durchgängiger Garnrolle–Knoten–Faden-Produktfluss
- Gespräche und Nachrichten
- föderale Governance und Gewebekonten
- normalisierte Geoabfragen beziehungsweise PostGIS
- verlässliche Eventprojektionen und Outbox
- konsolidierte Observability mit definierten SLOs
- automatisierte Restore- und Disaster-Recovery-Beweise

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

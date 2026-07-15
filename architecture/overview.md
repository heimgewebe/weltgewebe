---
id: overview
title: Architecture Overview
summary: Aktuelle Komponenten, Datenflüsse, Wahrheitsorte und Ausbaugrenzen des Weltgewebe-Systems.
role: norm
organ: governance
status: canonical
canonicality: normative
lifecycle_state: active
owner: governance
review_after: 2026-10-11
last_reviewed: 2026-07-11
depends_on: []
relations:
  - type: relates_to
    target: architecture/security.md
  - type: relates_to
    target: runtime/README.md
  - type: relates_to
    target: docs/techstack.md
  - type: relates_to
    target: architecture/weltgewebe-os.md
verifies_with: []
---

# Architecture Overview

## Systemgrenze

Weltgewebe ist ein Karten- und Koordinationssystem. Die heute implementierte
Kernfläche besteht aus:

1. einer statisch baubaren SvelteKit-Webanwendung,
2. einer Rust-/Axum-API,
3. Caddy als öffentlichem beziehungsweise lokalem Frontdoor,
4. JSONL- und opt-in PostgreSQL-Persistenzpfaden,
5. PostgreSQL für Sitzungen und ausgewählte Auth-/Domänenpfade,
6. NATS als im Produktions-Compose vorhandener, optional genutzter Eventkanal.

Gespräche, Nachrichten, föderale Governance und Gewebekonten sind teilweise als
Contracts oder Konzepte vorhanden, aber nicht als vollständige produktive
Ende-zu-Ende-Systeme.

## Kanonische Zielrichtung

Die langfristige Zielarchitektur steht in [`architecture/weltgewebe-os.md`](weltgewebe-os.md). Weltgewebe wird als föderiertes System autonomer Gewebe-Zellen mit globalen Identitäten, Beziehungen und gemeinsamen Räumen entwickelt. Kubernetes ist die kanonische Zielplattform; Compose bleibt die heutige reale Runtime und ein begrenzter Entwicklungs-/Recoverypfad.

Diese Zielrichtung ändert keine unbelegte Gegenwartswahrheit: Der Single-Instance-Guard bleibt aktiv, bis gemeinsame Zustände, Transactional Outbox, idempotente Konsumenten und Zwei-API-Kohärenz belegt sind.

## Komponenten

| Komponente | Pfad | heutige Verantwortung |
|---|---|---|
| Web | `apps/web` | Karte, Login, Einstellungen, Account- und Knotenansichten, statischer Build |
| API | `apps/api` | Authentifizierung, Sitzungen, Accounts, Knoten, Fäden, Health und Metriken |
| Domain-Contracts | `contracts/domain` | JSON-Schema-Verträge für Account, Knoten, Faden sowie noch nicht vollständig implementierte Gesprächsobjekte |
| Caddy | `infra/caddy` | TLS-/Host-Routing, Proxygrenze, Sicherheitsheader und Web-Upstream |
| Compose | `infra/compose` | lokale, produktive und zielbezogene Servicezusammenstellung |
| PostgreSQL | `apps/api/migrations` | Sitzungen, Domain-Tabellen und Passkey-Credentials; Nutzung hängt von expliziten Quellschaltern ab |
| JSONL | `.gewebe/in` beziehungsweise konfigurierte Datenpfade | Standardquelle für Domänendaten und Standard-Schreibpfad |
| NATS | Produktions-Compose und `NATS_URL` | Verbindungs- und Readinessfläche; kein vollständig belegter Outbox-/Projektionskern |

## Hauptdatenflüsse

### Lesen von Domänendaten

```text
Web -> Caddy -> Axum API -> konfigurierte Domain-Lesequelle
                              |- JSONL (Standard)
                              `- PostgreSQL (explizites Opt-in)
```

### Schreiben von Domänendaten

Accounts, Knoten und Fäden besitzen getrennte Quellschalter. PostgreSQL-Schreiben
ist nur zulässig, wenn auch aus PostgreSQL gelesen wird. Es gibt keinen
stillschweigenden Fallback und keinen allgemeinen Dual-Write.

### Anmeldung

```text
Browser -> Magic Link oder Passkey -> API -> Session Store
Browser <- HttpOnly/SameSite/Secure-Sitzungscookie
```

Der Browser speichert keinen Bearer-Token in `localStorage` oder
`sessionStorage`. Normale Tabs und Fenster desselben Browserprofils teilen die
Cookie-Sitzung; andere Profile und private Kontexte bleiben getrennt.

### Karte

Die Webanwendung lädt eine MapLibre-Karte und PMTiles-basierte Basiskarten. Die
Komponente besitzt einen expliziten asynchronen Abbauvertrag, damit eine laufende
Initialisierung nach dem Verlassen der Seite keine Kartenressourcen zurücklässt.

## Wahrheitsmodell

Bei Konflikten gilt die Reihenfolge aus `repo.meta.yaml`:

1. Domain-Contracts,
2. kanonische Policies,
3. Runtime-Konfiguration und Code,
4. normative Spezifikationen,
5. Berichte und Navigationsartefakte.

Migrationen und ausführbare Konfiguration präzisieren den realen physischen
Zustand. Eine Roadmap darf einen geplanten Zustand nicht als bereits betrieben
darstellen.

## Bewusste Ausbaugrenzen

- JSONL ist noch nicht vollständig durch PostgreSQL abgelöst.
- Neue Accounts und öffentliche Projektionen verwenden nur noch Garnrolle plus
  `map_state`. Legacy-RoN wird lesend auf `not_on_map` normalisiert; die nullable
  DB-Spalte `mode` bleibt bis zum belegten Produktionscutover als Rollbackbrücke.
- Gesprächs- und Nachrichtencontracts bedeuten noch keine produktive
  Persistenzfläche.
- NATS im Stack bedeutet noch keinen belegten Transactional-Outbox-Betrieb.
- Kubernetes als Zielplattform bedeutet noch keinen laufenden Cluster oder HA-Beleg.
- Föderationsverträge bedeuten noch keine öffentliche Zellföderation.
- Externe Vorschauplattformen sind keine Quelle für die Produktionsrouting-
  oder Runtimewahrheit.

## Nächster fachlicher Integrationsbeweis

Der wichtigste vertikale Schnitt ist:

1. Account anmelden,
2. Garnrolle bearbeiten und verorten,
3. Knoten dauerhaft anlegen,
4. Knoten nach Neuladen auf Karte und Profil wiederfinden,
5. Faden anlegen und erneut lesen.

Dieser Schnitt soll ohne Demo-Fallback und mit eindeutigem Persistenzpfad
belegt werden.

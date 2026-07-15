---
id: docs.reports.weltgewebe-os-foundation-status
title: Weltgewebe OS Foundation — Status und Beweisgrenzen
doc_type: status
status: active
summary: >
  Trennt den belegten heutigen Laufzeitstand vom kanonischen Weltgewebe-OS-Ziel und benennt die nächsten Beweisgates.
owner_task: WELTGEWEBE-OS-001
review_after: 2026-08-15
relations:
  - type: depends_on
    target: architecture/weltgewebe-os.md
  - type: relates_to
    target: docs/blueprints/weltgewebe-os-masterplan.md
  - type: relates_to
    target: docs/reports/domain-postgres-instance-coherence-decision.md
  - type: relates_to
    target: docs/tasks/board.md
---

# Weltgewebe OS Foundation — Status und Beweisgrenzen

## Zweck

Dieser Bericht verhindert, dass langfristige Architektur als bereits betriebene Realität gelesen wird. Er bündelt den Ausgangspunkt für die Initiative `WELTGEWEBE-OS-001`.

## Belegt

- Weltgewebe besitzt eine SvelteKit-Webanwendung und eine Rust/Axum-API.
- Caddy und Docker Compose bilden den heutigen realen Frontdoor- und Orchestrierungspfad.
- PostgreSQL ist für wesentliche Domain- und Auth-Persistenzpfade eingeführt.
- NATS ist im Produktionsstack vorhanden.
- Karten-, Garnrollen-, Knoten- und Fadenflächen besitzen reale Implementierungen und Tests.
- Task-Control, Agent-Safety und beweisgebundene Dokumentationsmechanismen sind vorhanden.
- Der bestehende Single-Instance-Guard verhindert derzeit zu Recht eine unbelegte horizontale API-Skalierung.
- `architecture/weltgewebe-os.md` und ADR-0010 bis ADR-0012 definieren nach Annahme dieses Änderungsschnitts die langfristige Zielrichtung.

## Noch nicht belegt

- vollständige Multi-Instanz-Kohärenz,
- ausschließlich gemeinsam persistierte autoritative Auth-Zwischenzustände,
- Transactional Outbox,
- ein produktives versioniertes Domain-Ereignisrückgrat,
- idempotente Projektionen über alle relevanten Ereignisklassen,
- Kubernetes als laufende Produktionsplattform,
- eine hochverfügbare Referenzzelle,
- gemessene SLOs, RTO und RPO für ein HA-Profil,
- öffentliche Zellidentitäten und signierte Föderation,
- gemeinsame Räume über unabhängige Zellen,
- Zwei-Zellen-Nachbarschaft,
- globale rekonstruierbare Such- und Kartenprojektionen,
- GewebeZelle-Operator oder deklarative Zell-API.

## Aktuelle zentrale Blockade

Der Bericht `docs/reports/domain-postgres-instance-coherence-decision.md` belegt, dass `accounts`, `nodes` und `edges` in prozesslokalen Caches gehalten werden und mehrere Auth-Zwischenzustände nicht vollständig gemeinsam persistiert sind. Zwei API-Replikate können deshalb divergieren.

Die korrekte aktuelle Entscheidung bleibt:

> höchstens eine produktive API-Instanz, bis die Kohärenzbeweise abgeschlossen sind.

Die Weltgewebe-OS-Zielentscheidung supersediert diese Sicherheitsgrenze nicht. Sie macht deren kontrollierte Ablösung zu einer priorisierten Initiative.

## Status der Grundlagenwelle

| Bestandteil | Status | Beleggrenze |
|---|---|---|
| Weltgewebe-OS-Verfassung | in Änderung | kanonischer Architekturtext vorhanden; Merge und Post-Merge-Beleg offen |
| Kubernetes-ADR | in Änderung | Zielplattform entschieden; keine laufende Clusterrealität behauptet |
| Zellföderations-ADR | in Änderung | Fach- und Eigentumsmodell entschieden; kein Protokoll implementiert |
| Ereignis-ADR | in Änderung | Outbox- und Idempotenzmodell entschieden; keine Runtime implementiert |
| Masterplan | in Änderung | Wellen und Systemrollen geordnet; Task- und Bureau-Verankerung offen bis Commit/PR |
| Multi-Instance-State-Audit | offen | vollständiges State-Inventar und Testmatrix fehlen |
| Kubernetes-Referenzpfad | offen | keine kanonischen Manifeste oder lokaler Clusterbeweis |
| HA-Referenzzelle | offen | keine Failover-, PITR- oder Restore-Messung |
| Föderationskern | offen | keine Zellschlüssel, Inbox/Outbox oder Konformitätstests |

## Erste Beweisgates

### Gate A — Verfassungs- und Registrierungsbeweis

- kanonische Architektur und ADRs sind auf `main`,
- Master-Roadmap und Navigationsflächen verweisen darauf,
- Bureau-Gesamtinitiative und Folgetasks sind schema-konform registriert,
- kein Dokument behauptet eine bereits erfolgte Kubernetes- oder HA-Migration.

### Gate B — Multi-Instanz-State-Audit

- alle prozesslokalen Zustände sind inventarisiert,
- jeder Zustand ist als autoritativ, Cache, temporär oder rein diagnostisch klassifiziert,
- Eigentümer, Persistenz, Lebensdauer und Fehlerwirkung sind dokumentiert,
- konkrete Umsetzungsslices sind registriert.

### Gate C — Outbox- und Kohärenzbeweis

- Mutation und Outbox sind atomar,
- Relay kann nach Absturz fortsetzen,
- Konsumenten deduplizieren,
- zwei API-Instanzen sehen nach Mutationen denselben Zustand,
- Neustarts und verzögerte Ereignisse bleiben korrekt.

### Gate D — Kubernetes-Reproduzierbarkeit

- lokaler Cluster aus versionierten Artefakten,
- gleiche Anwendungsbasis in CI und Staging,
- Probes, Shutdown, Secrets, Policies und Telemetrie sind belegt,
- Compose bleibt begrenzter und geprüfter Nebenpfad.

### Gate E — HA und Recovery

- mehrere Fehlerdomänen,
- Datenbank- und Messagingfailover,
- PITR und Blank-Cluster-Restore,
- gemessene RTO/RPO,
- Upgrade und Rollback.

### Gate F — Zwei-Zellen-Föderation

- unabhängige Zellidentitäten,
- signierte Ereignisse,
- Reichweiten und Quarantäne,
- zellübergreifende Knoten, Fäden und gemeinsamer Raum,
- Trennung und kontrollierte Wiederverbindung.

## Aktuell ausgeschlossene Aussagen

Dieser Bericht etabliert nicht:

- Produktionsfreigabe für Kubernetes,
- Berechtigung zur Entfernung des Single-Instance-Guards,
- vorhandene Hochverfügbarkeit,
- globale Datenschutzkonformität,
- ActivityPub- oder Matrix-Kompatibilität,
- Auswahl eines endgültigen Kubernetes-Distributors oder Cloudanbieters,
- Berechtigung, laufende Compose- oder Deploymentpfade zu verändern.

## Nächster ausführbarer Schnitt

Der nächste technische Schnitt ist ein read-only Multi-Instance-State-Audit mit anschließender registrierter Zerlegung in:

1. Shared Auth State,
2. Domain-Cache-Autoritätsabbau,
3. Outbox-Schema und Relay,
4. erster idempotenter Konsument,
5. Zwei-API-Kohärenztest,
6. Graceful Shutdown und Migrationsvertrag.

Erst nach diesen Belegen wird der Single-Instance-Guard neu bewertet.

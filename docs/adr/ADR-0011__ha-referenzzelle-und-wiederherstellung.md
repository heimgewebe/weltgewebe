---
id: adr.ADR-0011__ha-referenzzelle-und-wiederherstellung
title: ADR-0011 — Hochverfügbare Referenzzelle und Wiederherstellungsbeweis
doc_type: reference
status: active
summary: >
  Definiert den nichtproduktiven Referenzvertrag für drei Fehlerdomänen, PostgreSQL- und JetStream-Quorum, kontrollierten Zonenausfall und Point-in-Time-Restore in einen leeren Cluster.
relations:
  - type: relates_to
    target: adr/ADR-0010__kubernetes-kanonische-plattform.md
  - type: relates_to
    target: runbooks/kubernetes-ha-recovery-proof.md
---

# ADR-0011 — Hochverfügbare Referenzzelle und Wiederherstellungsbeweis

Datum: 2026-07-17
Status: Accepted

## Kontext

Die T003-Plattform beweist deklaratives Kubernetes, zwei API-Replikate, GitOps, Gateway API, Cilium und ephemere Datenkomponenten. Sie beweist ausdrücklich weder Datenquorum noch Point-in-Time-Recovery, Fehlerdomänen oder gemessene Wiederherstellungszeiten.

## Entscheidung

Die T004-Referenzzelle verwendet drei explizite Zonen und folgende Verträge:

- drei API-Replikate mit verpflichtender Zonenverteilung,
- CloudNativePG mit drei PostgreSQL-Instanzen und verpflichtender Zonen-Anti-Affinität,
- NATS JetStream mit drei RAFT-Mitgliedern und `minAvailable: 2`,
- einen ausschließlich für den Beweis verwendeten externen S3-kompatiblen SeaweedFS-Dienst,
- dynamisch erzeugte kurzlebige Secrets statt eingecheckter Zugangsdaten,
- einen kontrollierten Ausfall des Worker-Knotens, der den PostgreSQL-Primary trägt,
- Backup und Point-in-Time-Restore, während diese Fehlerdomäne weiterhin ausgefallen ist,
- einen für diesen degradierten Beweis gezielt auf den neuen Primary gebundenen Backupauftrag,
- einen neuen zweiten kind-Cluster für den Point-in-Time-Restore.

Alle Drittimages und das CloudNativePG-Releaseartefakt sind per SHA-256 beziehungsweise OCI-Digest gebunden.

## Messvertrag

Der Beweis erfasst getrennt:

- Zeit bis zu einem neuen PostgreSQL-Primary,
- Zeit bis zum erfolgreichen API-Readback einer bestätigten Fachmutation,
- Zeit bis zu einer neuen bestätigten JetStream-Publikation,
- Zeit bis zum vollständigen PostgreSQL-Restore im leeren Cluster,
- Datenvergleich vor und nach dem gewählten PITR-Zeitpunkt.

Eine Messung gilt nur, wenn die vor dem Ausfall bestätigte Domänenmutation und die JetStream-Nachricht erhalten bleiben.

## Sicherheitsgrenzen

- Bestehende Cluster oder Container werden niemals adoptiert.
- Jeder erzeugte Cluster, Container und Datenträger besitzt eine Commit- und Repositorybindung.
- Cleanup löscht nur exakt diese gebundenen Beweisressourcen.
- Produktion, Compose und produktive Daten werden nicht verändert.
- Im Repository liegen keine Secrets.

## Nicht belegt

Der Referenzbeweis belegt nicht:

- Multi-Region-Betrieb,
- einen verwalteten, redundant replizierten Produktions-Objektstore,
- SLOs unter Produktionslast,
- den gleichzeitigen Verlust von zwei Fehlerdomänen,
- einen Produktionscutover,
- die automatische Wiedereingliederung einer zurückkehrenden ausgefallenen Zone.

Diese Grenzen bleiben im maschinenlesbaren Receipt erhalten.

---
id: adr.ADR-0011__ha-referenzzelle-und-wiederherstellung
title: ADR-0011 — Hochverfügbare Referenzzelle und Wiederherstellungsbeweis
doc_type: reference
status: active
summary: >
  Definiert den nichtproduktiven Referenzvertrag für drei Fehlerdomänen, PostgreSQL- und JetStream-Quorum, Upgrade/Rollback, kontrollierten Zonenausfall und Point-in-Time-Restore in einen leeren Cluster.
relations:
  - type: relates_to
    target: docs/adr/ADR-0010__kubernetes-kanonische-plattform.md
  - type: relates_to
    target: docs/runbooks/kubernetes-ha-recovery-proof.md
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
- drei CloudNativePG-Operatorreplikate mit verpflichtender Verteilung über unterschiedliche Knoten,
- cert-manager und das Barman-Cloud-Plugin einschließlich des injizierten Instanz-Sidecars als getrennte, digestgebundene Sicherungskomponenten,
- einen pluginbasierten `ObjectStore` für WAL-Archivierung, Basisbackup und PITR statt der auslaufenden nativen Barman-Integration,
- NATS JetStream mit drei RAFT-Mitgliedern und `minAvailable: 2`,
- einen ausschließlich für den Beweis verwendeten externen S3-kompatiblen SeaweedFS-Dienst,
- dynamisch erzeugte kurzlebige Secrets statt eingecheckter Zugangsdaten,
- einen kontrollierten Kubernetes-Rollout auf ein getrenntes unveränderliches API-Artefakt und ein echtes `rollout undo` auf die vorherige Revision,
- eine während Upgrade und Rollback sekündlich owner-lokal gegen alle beworbenen Gateway-Listener gemessene Gateway-Service-Verfügbarkeit der Referenzzelle mit Null-Ausfall-Vertrag, separat ausgewiesener Listener-Degradation und Referenz-Fehlerbudget,
- einen kontrollierten Ausfall des Worker-Knotens, der den PostgreSQL-Primary trägt,
- einen neuen zweiten kind-Cluster für den Point-in-Time-Restore, der nach dem Restore selbst wieder WAL archiviert.

Alle Drittimages sowie die Releaseartefakte von CloudNativePG, cert-manager und Barman Cloud sind per SHA-256 beziehungsweise OCI-Digest gebunden. Dies umfasst auch das vom Barman-Plugin dynamisch in jede PostgreSQL-Instanz injizierte Sidecar-Image. Die PostgreSQL-Operanden bleiben minimale Standardimages; Sicherungswerkzeuge werden nicht in das Datenbankimage eingebaut.

## Messvertrag

Der Beweis erfasst getrennt:

- Zeit bis zu einem neuen PostgreSQL-Primary,
- Zeit bis zum erfolgreichen API-Readback einer bestätigten Fachmutation,
- Zeit bis zu einer neuen bestätigten JetStream-Publikation,
- Dauer eines vollständigen API-Upgrades und Rollbacks einschließlich vollständig ersetzter Pod-UIDs,
- beobachtete Gateway-Ausfallzeit, Verfügbarkeitsstichproben und Verbrauch eines 99,9-Prozent-Referenz-Fehlerbudgets,
- Zeit bis zum `Ready`-Zustand des wiederhergestellten PostgreSQL-Clusters; Sidecar- und WAL-Kontinuitätsprüfungen werden davon getrennt gemessen,
- erzwungene WAL-Archivlatenz im Primär- und Restorecluster als Referenzobergrenze für den archivierungsgebundenen RPO,
- Datenvergleich vor und nach dem gewählten PITR-Zeitpunkt.

Eine Messung gilt nur, wenn Upgrade und Rollback über die owner-lokal geprüften beworbenen Gateway-Listener keinen globalen Gateway-Ausfall der Referenzzelle erzeugen, alle drei API-Pods ersetzt werden und die vor dem Ausfall bestätigte Domänenmutation sowie die JetStream-Nachricht erhalten bleiben. Globaler Gateway-Ausfall bedeutet, dass in einer Stichprobe keiner der beworbenen Listener aus dem Netzraum seines zugehörigen Kind-Node-Owners die bestätigte API-Mutation liefert. Ausfälle einzelner Listener werden als Pfaddegradation separat erfasst. Cross-Node-Kind-/Cilium-Pfade gehören nicht zum Ausfallvertrag und werden als eigener Infrastrukturbefund behandelt. Da die Cilium-Gateway-Adressen der Kind-Referenzzelle außerhalb der Kind-Node-Netzräume nicht routbar sind, belegt diese Messung ausdrücklich keine externe Host- oder Produktions-Load-Balancer-Erreichbarkeit. Das Upgrade-Artefakt verwendet dieselben Runtime-Bits mit abweichender unveränderlicher Metadatenebene; damit wird der Kubernetes-Änderungspfad, nicht die semantische Kompatibilität einer neuen Anwendungsversion bewiesen.

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
- die semantische Kompatibilität einer eigenständigen neuen Anwendungsversion,
- ein Produktions-Fehlerbudget unter repräsentativer Last.

Diese Grenzen bleiben im maschinenlesbaren Receipt erhalten.

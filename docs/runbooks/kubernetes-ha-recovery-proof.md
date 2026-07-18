---
id: runbook.kubernetes-ha-recovery-proof
title: Kubernetes-HA- und Recovery-Beweis
doc_type: runbook
status: active
summary: >
  Führt den eigentumsgebundenen T004-Beweis für Zonenverteilung, PostgreSQL- und JetStream-Failover sowie PITR in einen leeren kind-Cluster aus.
relations:
  - type: relates_to
    target: docs/adr/ADR-0011__ha-referenzzelle-und-wiederherstellung.md
---

# Kubernetes-HA- und Recovery-Beweis

## Voraussetzungen

- sauberer, commitgebundener Worktree,
- Docker mit Zugriff auf den lokalen Daemon,
- ausreichend Speicher für zwei kurzzeitig parallele Vier-Knoten-kind-Cluster,
- keine vorhandenen Cluster, Container oder Volumes mit demselben Beweisnamen.

## Ausführung

```bash
python scripts/platform/ha_reference.py proof --cluster weltgewebe-ha-reference
```

Der Runner installiert Werkzeuge ausschließlich aus `platform/toolchain.lock.json`, baut die Weltgewebe-Images aus dem aktuellen Commit und erzeugt alle kurzlebigen Secrets erst zur Laufzeit.

## Beweisphasen

1. Primärcluster mit drei Datenzonen erzeugen.
2. Cilium, Gateway API, Flux, cert-manager, drei auf unterschiedliche Knoten verteilte CloudNativePG-Operatorreplikate und das Barman-Cloud-Plugin installieren.
3. Das Plugin- und Instanz-Sidecar-Image digestgebunden zurücklesen, den pluginbasierten `ObjectStore` anwenden und PostgreSQL, NATS JetStream sowie drei API-Replikate über die Zonen verteilen.
4. Eine gültige `domain_nodes`-Mutation schreiben und über die API zurücklesen.
5. Den Worker des PostgreSQL-Primary stoppen.
6. PostgreSQL-Failover, API-Readback und JetStream-Quorum messen.
7. Worker wieder aufnehmen und vollständige Bereitschaft abwarten.
8. Basisbackup erstellen, PITR-Zeitpunkt festhalten und eine spätere Mutation schreiben.
9. Das danach erzwungene WAL-Segment exakt bestimmen und seine Archivierung abwarten.
10. Einen zweiten leeren kind-Cluster erzeugen.
11. Datenbank auf den Zielzeitpunkt wiederherstellen und die Zeilengrenze vergleichen.

## Ergebnisse

Bei Erfolg entsteht unter `.cache/weltgewebe-platform/receipts/` ein JSON-Receipt mit:

- Commit und Tool-Lock-Hash,
- Image-IDs einschließlich der in Haupt- und Restorecluster injizierten Barman-Sidecars,
- Pod-, Knoten- und Zonenbelegung einschließlich der verteilten CloudNativePG-Operatorreplikate,
- gemessenen RTO-Werten,
- Backup- und PITR-Zeitpunkt,
- erforderliches und über PostgreSQLs `pg_stat_archiver` tatsächlich bestätigtes WAL-Segment,
- Datenvergleich des Restoreclusters,
- expliziten Nichtaussagen.

## Fehlerdiagnose

Bei einem Fehler werden Clusterzustand, Pods, Events, Flux, Gateway, CloudNativePG-Status, Barman-Plugin- und Pod-Logs, Zertifikats- sowie Storagezustand unter `.cache/weltgewebe-platform/failures/<cluster>/` gesichert. Einzelne Diagnosekommandos sind zeitlich begrenzt; Timeouts und Startfehler werden als Diagnoseevidenz vermerkt. Der Runner startet einen gestoppten Knoten wieder und entfernt standardmäßig nur seine eigenen markierten Ressourcen.

## Manuelles eigentumsgebundenes Cleanup

Nur für einen abgebrochenen Lauf mit bekanntem Commit:

```bash
python scripts/platform/ha_reference.py down \
  --cluster weltgewebe-ha-reference \
  --commit <exakter-commit>
```

Ohne passende Eigentumsmarker verweigert der Befehl das Löschen.

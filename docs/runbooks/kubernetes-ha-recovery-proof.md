---
id: runbook.kubernetes-ha-recovery-proof
title: Kubernetes-HA- und Recovery-Beweis
doc_type: runbook
status: active
summary: >
  Führt den eigentumsgebundenen T004-Beweis für Zonenverteilung, PostgreSQL- und JetStream-Failover sowie PITR in einen leeren kind-Cluster aus.
relations:
  - type: relates_to
    target: adr/ADR-0011__ha-referenzzelle-und-wiederherstellung.md
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
2. Cilium, Gateway API, Flux und CloudNativePG installieren.
3. PostgreSQL, NATS JetStream und drei API-Replikate über die Zonen verteilen.
4. Eine gültige `domain_nodes`-Mutation schreiben und über die API zurücklesen.
5. Den Worker des PostgreSQL-Primary stoppen.
6. PostgreSQL-Failover, API-Readback und JetStream-Quorum messen.
7. Die ausgefallene Zone bewusst weiter gestoppt lassen.
8. Im degradierten Zwei-Zonen-Betrieb ein Basisbackup erstellen, den PITR-Zeitpunkt festhalten und eine spätere Mutation schreiben.
9. Einen zweiten leeren kind-Cluster erzeugen.
10. Während die Ursprungszone weiterhin fehlt, die Datenbank auf den Zielzeitpunkt wiederherstellen und die Zeilengrenze vergleichen.

## Ergebnisse

Bei Erfolg entsteht unter `.cache/weltgewebe-platform/receipts/` ein JSON-Receipt mit:

- Commit und Tool-Lock-Hash,
- Image-IDs,
- Pod-, Knoten- und Zonenbelegung,
- gemessenen RTO-Werten,
- Backup- und PITR-Zeitpunkt,
- Datenvergleich des Restoreclusters,
- dem Beleg, dass die Ausfallzone bis nach Backup und Restore gestoppt blieb,
- expliziten Nichtaussagen einschließlich der nicht geprüften automatischen Wiedereingliederung der ausgefallenen Zone.

## Fehlerdiagnose

Bei einem Fehler werden Clusterzustand, Pods, Events, Flux und Gateway unter `.cache/weltgewebe-platform/failures/<cluster>/` gesichert. Der Runner startet einen gestoppten Knoten wieder und entfernt standardmäßig nur seine eigenen markierten Ressourcen.

## Manuelles eigentumsgebundenes Cleanup

Nur für einen abgebrochenen Lauf mit bekanntem Commit:

```bash
python scripts/platform/ha_reference.py down \
  --cluster weltgewebe-ha-reference \
  --commit <exakter-commit>
```

Ohne passende Eigentumsmarker verweigert der Befehl das Löschen.

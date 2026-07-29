---
id: docs.reports.kubernetes-platform-foundation-status
title: Kubernetes- und GitOps-Grundlage — Status und Beweisgrenzen
summary: Dokumentiert die Referenzplattform, ihre GitOps- und Single-Host-HA-Referenzbeweise sowie die offenen Multi-Host- und Produktionsaktivierungsgates.
doc_type: status
status: active
owner_task: WELTGEWEBE-OS-006
review_after: 2026-08-16
relations:
  - type: depends_on
    target: docs/adr/ADR-0010__kubernetes-kanonische-plattform.md
  - type: relates_to
    target: platform/README.md
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: docs/reports/domain-postgres-instance-coherence-decision.md
  - type: verifies
    target: scripts/platform/validate_platform.py
  - type: verifies
    target: scripts/platform/kind_reference.py
  - type: verifies
    target: scripts/platform/ha_reference.py
---

# Kubernetes- und GitOps-Grundlage — Status und Beweisgrenzen

## Aktueller Belegstand

Stand: 29. Juli 2026. Der vollständige Workflow `kubernetes-platform-proof` hat auf Main-Commit `9bc263761207763cb78f57e385b64311f13a509b` in Lauf `30423949500` den statischen Vertrag, den commitgebundenen Flux-/GitOps-Beweis, den gerenderten Trivy-Scan sowie den Single-Host-kind-Failover- und Blank-Cluster-Recovery-Beweis erfolgreich abgeschlossen. Die Proofs veränderten die laufende Produktion nicht.

## Belegter Vertragsumfang

- gemeinsame Kustomize-Basis für API und Web mit kleinen Overlays für Local, CI, HA, Staging und Production;
- durch Promotion gesperrte First-Party-Images und digestgebundene Drittimages;
- SHA-verifizierter Werkzeug- und Artefaktlock;
- kontrollierter privater OCI-Mirror mit Digest-, Herkunfts-, Paketbudget- und Retentionsvertrag;
- Offline-Beweise nach dem Laden der kontrollierten OCI-Eingaben und anschließender Blockade öffentlicher Registries;
- restricted Pod Security, Default-Deny und explizite Datenpfade;
- externer Secretvertrag ohne versionierte Secretwerte;
- Gateway API, Cilium und Hubble als Netzwerk-, Eingangs- und Beobachtbarkeitsbasis der Referenzzelle;
- Flux-Abhängigkeitskette `data → migration → app → gateway` mit Wait, Prune, Health Checks und Driftkorrektur;
- isolierter kind-Lifecycle mit Commit-, Owner- und Clustermarker sowie eigentumsgebundener Bereinigung;
- deklarativer, completion-gesteuerter Migration-only-Job vor dem Start mehrerer API-Replikate;
- direkter und GitOps-basierter Blank-Cluster-Aufbau aus versionierten Artefakten;
- API-/Web-Restart, vollständiger Pod-Austausch, Gateway-Listener-Readback und Flux-Driftkorrektur;
- logisch zonierte Single-Host-kind-Referenzzelle mit drei API-, PostgreSQL- und JetStream-Instanzen;
- kontrollierter Ausfall einer logisch simulierten Zone mit PostgreSQL-, API-, Barman- und JetStream-Erholung ohne Verlust bestätigter Fachmutationen;
- Barman-Backup, WAL-Archivierung, Point-in-Time-Recovery und Wiederherstellung in einen zweiten leeren kind-Cluster;
- gemessene Referenzwerte für Failover-RTO, Restore-RTO, archivierungsgebundene RPO-Obergrenze, Upgrade, Rollback und Fehlerbudget.

## Weiterhin nicht behauptet

- Kubernetes ist noch nicht die laufende Weltgewebe-Produktion.
- Staging und Production sind ohne echte Imagepromotion, externen Secretpfad und umgebungsspezifischen Clustervertrag nicht freigegeben.
- Die kind-Beweise belegen keine Verteilung über mehrere physische Hosts oder vergleichbar unabhängige Fehlerdomänen.
- Die kind-Beweise belegen keine RTO-/RPO- oder Fehlerbudgetwerte unter repräsentativer Produktionslast.
- Der Proof-Object-Store belegt keine verwaltete Multi-Region-Dauerhaftigkeit.
- Zwei gleichzeitig verlorene Fehlerdomänen, Multi-Cluster und Multi-Region-Betrieb sind nicht belegt.
- Die Gateway-Beweise belegen keine Erreichbarkeit über einen realen externen Load Balancer außerhalb der kind-Bridge.
- Das Upgrade-Artefakt belegt den Kubernetes-Änderungs- und Rollbackpfad, nicht die semantische Kompatibilität eines abweichenden Produktreleases.
- Der Compose-Produktionspfad bleibt die aktuelle Laufzeit, bis der getrennte Produktionscutover abgeschlossen ist.

## Offene Aktivierungsgates

1. Einen realen Staging-Cluster mit umgebungseigenem Flux-Bootstrap, Storage-, TLS-, DNS- und Load-Balancer-Vertrag betreiben.
2. First-Party-Images commit- und provenienzgebunden promoten und Secrets über einen auditierten externen Pfad bereitstellen.
3. Produktionsnahe Last-, Kapazitäts-, SLO-, Alarm- und Burn-Rate-Beweise abschließen.
4. Datenübergang, gestuften Trafficwechsel, automatische Stopbedingungen und vollständigen Rückfall auf Compose messen.
5. Erst danach `WELTGEWEBE-OS-V1-T044` als eigenen revisionsgebundenen Produktionscutover ausführen.

Kein Aktivierungsschritt darf aus der bloßen Existenz der Manifeste oder aus einem erfolgreichen kind-Beweis abgeleitet werden.

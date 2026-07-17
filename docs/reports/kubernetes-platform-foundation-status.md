---
id: docs.reports.kubernetes-platform-foundation-status
title: Kubernetes- und GitOps-Grundlage — Status und Beweisgrenzen
summary: Dokumentiert die kanonische Plattformbasis, ihre reproduzierbaren lokalen Beweise und die weiterhin offenen Produktions- und HA-Gates.
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
---

# Kubernetes- und GitOps-Grundlage — Status und Beweisgrenzen

## Belegter Vertragsumfang

- gemeinsame Kustomize-Basis für API und Web;
- kleine Overlays für Local, CI, Staging und Production;
- durch Promotion gesperrte First-Party-Images und digestgebundene Drittimages;
- SHA-verifizierter Werkzeug- und Artefaktlock;
- restricted Pod Security, Default-Deny und explizite Datenpfade;
- externer Secretvertrag ohne versionierte Secretwerte;
- Gateway API als Eingangsschicht;
- Cilium/Hubble als lokaler Netzwerk- und Beobachtbarkeitsbeweis;
- Flux-Abhängigkeitskette `data → migration → app → gateway` mit Wait, Prune, Health Checks und Driftkorrektur;
- isolierter kind-Lifecycle mit Besitzmarker und eigener Bereinigung;
- deklarativer, completion-gesteuerter Migration-only-Job vor dem Start mehrerer API-Replikate;
- Zwei-API- und vollständiger Pod-Austausch beim Restart; Gateway-Listener-Readback einschließlich des öffentlichen `/api/nodes`-Rewrite-Pfads innerhalb der kind-Zelle; GitOps-Driftbeweis.

## Nicht behauptet

- Kubernetes ist noch nicht die laufende Weltgewebe-Produktion.
- Staging und Production sind ohne Imagepromotion und externen Secretpfad nicht freigegeben.
- PostgreSQL und JetStream im lokalen Overlay sind nicht hochverfügbar und nicht persistent.
- Backup, Restore, PITR, RTO, RPO, Multi-Cluster und Föderation sind nicht belegt.
- Der Compose-Produktionspfad bleibt unverändert.
- Der lokale Gateway-Beweis behauptet keine Erreichbarkeit vom Docker-Host oder aus externen Netzen.

## Freigabefolge

1. Plattformvertrag und lokaler Referenzbeweis.
2. Separater Staging-Secret- und Imagepromotionsvertrag.
3. Restore- und Ausfallbeweise der Referenzzelle.
4. Eigene Produktionsfreigabe mit Rollback und Beobachtbarkeit.

Kein Schritt darf aus der bloßen Existenz von Kubernetes-Manifests abgeleitet werden.

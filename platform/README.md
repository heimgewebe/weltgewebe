---
id: platform.readme
title: Weltgewebe Kubernetes- und GitOps-Plattform
summary: Kanonischer Plattformvertrag für Kustomize, Flux, Gateway API, Cilium und den isolierten kind-Referenzbeweis.
role: norm
organ: ops
status: canonical
canonicality: normative
lifecycle_state: active
owner: ops
review_after: 2026-08-16
last_reviewed: 2026-07-16
depends_on: []
relations:
  - type: relates_to
    target: architecture/weltgewebe-os.md
  - type: relates_to
    target: docs/reports/kubernetes-platform-foundation-status.md
  - type: relates_to
    target: docs/runbooks/gewebezelle-manual-pilot.md
  - type: verifies
    target: scripts/platform/validate_platform.py
  - type: verifies
    target: scripts/platform/kind_reference.py
verifies_with:
  - scripts/platform/validate_platform.py
  - scripts/platform/kind_reference.py
---

# Weltgewebe Kubernetes- und GitOps-Plattform

`platform/` ist die kanonische deklarative Zielplattform für Weltgewebe. Docker Compose bleibt die gegenwärtige Produktions- und Recovery-Laufzeit, bis ein eigener Produktionsfreigabevertrag abgeschlossen ist.

## Wahrheitsschichten

- `apps/weltgewebe/base/` enthält den gemeinsamen Anwendungsvertrag.
- `apps/weltgewebe/overlays/` enthält ausschließlich kleine Umgebungsdeltas.
- `infrastructure/local-data/` stellt PostgreSQL und JetStream nur für lokale und CI-Beweise bereit.
- `infrastructure/gateway/` definiert Gateway API und HTTPRoute.
- `clusters/local/` definiert die Flux-Abhängigkeitskette `data → migration → app → gateway`.
- `toolchain.lock.json` bindet Werkzeuge, Clusterimage und Drittartefakte an SHA-256.
- `cell-profile.contract.json` definiert das erste manuelle, nicht selbstbedienbare GewebeZelle-Pilotprofil.
- `apps/weltgewebe/cell-pilot/federation-delivery-egress.yaml` ist ein nicht eingebundenes, fail-closed Cilium-FQDN-Template für exakt benannte ausgehende Peerziele.

## Sicherheitsgrenzen

- Keine Secret-Objekte oder Secretwerte werden versioniert.
- Local und CI verwenden für Datenzelle und lokale App eine deterministische, ausdrücklich öffentliche Test-Fixture als ConfigMap; sie ist kein Produktionsgeheimnis.
- Der Referenzrunner verwendet für Local/CI einen deklarativen Migration-only-Job mit öffentlicher ConfigMap-Fixture. Staging und Produktion bleiben durch den externen Secret- und Image-Promotionsvertrag blockiert.
- Staging und Production benötigen einen externen, auditierten Secretpfad.
- Eigene Container laufen ohne Root, ohne Service-Account-Token, ohne Privilege Escalation und mit Default-Deny-Netzpolitik.
- Der Referenzrunner übernimmt oder löscht niemals einen bereits vorhandenen Cluster.
- Proof-Cluster werden lokal unter einem pro Cluster serialisierten Ownership-Lock reserviert; Cleanup verlangt den exakten Commit und dieselbe Owner-ID. Verwaiste Marker werden fail-closed nicht automatisch entfernt.
- Werkzeugarchive werden vor jeder Schreibwirkung vollständig geprüft; nur reguläre Dateien und Verzeichnisse sind zulässig. Symlinks, Hardlinks, Devices, FIFOs, Traversal und widersprüchliche Member werden fail-closed abgewiesen; die ausführbare Datei wird anschließend atomisch installiert.
- Produktionsdeployments, DNS, Compose und reale Replikazahlen werden durch diesen Vertrag nicht verändert.

## Beweise

```bash
make platform-check
make platform-render
make platform-kind-proof
```

Der unprivilegierte Workflow `kubernetes-platform` prüft Pull Requests gegen den exakt ausgecheckten Merge-Zustand, ohne Zugriff auf private OCI-Pakete. Der getrennte Workflow `kubernetes-platform-proof` läuft nach passenden Pushes auf `main` oder bei einem ausdrücklich an den vollständigen aktuellen Main-Commit gebundenen Handstart. Er prüft den privaten OCI-Mirror sowie die vollständige Flux-/GitOps- und HA-Wiederherstellungskette gegen eindeutig benannte, kurzlebige kind-Cluster. Wiederverwendete Beweise sind an Commit, Eingabemanifest, Werkzeug-Lock, OCI-Lock, Image- und Knotenbindungen sowie Registry-Sperren gebunden.

## Manuelles GewebeZelle-Pilotprofil

Eine eigenständige Pilotzelle kann die gemeinsame Anwendungsbasis mit einem zelleigenen Overlay, externer Secretbereitstellung, eigener Zellidentität und ausdrücklich konfigurierten Peerbeziehungen verwenden. Die automatische Auslieferung ist standardmäßig deaktiviert und wird nur mit PostgreSQL, vollständiger Identität, mindestens einem gültigen HTTPS-Ziel und einer auf dessen exakten DNS-Host und TCP-Port begrenzten Cilium-Egress-Regel gestartet. Die Basis erhält keine allgemeine Internetfreigabe.

Der Betreibervertrag steht in `docs/runbooks/gewebezelle-manual-pilot.md`. Er etabliert weder Self-Service noch einen GewebeZelle-Operator und ersetzt nicht die getrennte Kubernetes-Produktionsfreigabe.

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

## Sicherheitsgrenzen

- Keine Secret-Objekte oder Secretwerte werden versioniert.
- Local und CI verwenden für Datenzelle und lokale App eine deterministische, ausdrücklich öffentliche Test-Fixture als ConfigMap; sie ist kein Produktionsgeheimnis.
- Der Referenzrunner verwendet für Local/CI einen deklarativen Migration-only-Job mit öffentlicher ConfigMap-Fixture. Staging und Produktion bleiben durch den externen Secret- und Image-Promotionsvertrag blockiert.
- Staging und Production benötigen einen externen, auditierten Secretpfad.
- Eigene Container laufen ohne Root, ohne Service-Account-Token, ohne Privilege Escalation und mit Default-Deny-Netzpolitik.
- Der Referenzrunner übernimmt oder löscht niemals einen bereits vorhandenen Cluster.
- Produktionsdeployments, DNS, Compose und reale Replikazahlen werden durch diesen Vertrag nicht verändert.

## Beweise

```bash
make platform-check
make platform-render
make platform-kind-proof
```

Der Workflow `kubernetes-platform` prüft Pull Requests im Direct-Modus gegen den exakt ausgecheckten Merge-Zustand. Nach einem Push auf `main` und bei manuellen Läufen prüft er zusätzlich die vollständige Flux-/GitOps-Kette gegen einen eindeutig benannten, kurzlebigen kind-Cluster.

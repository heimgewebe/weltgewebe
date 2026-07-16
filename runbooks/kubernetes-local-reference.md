---
id: runbooks.kubernetes-local-reference
title: Kubernetes- und GitOps-Referenzzelle lokal prüfen
summary: Fail-closed Ablauf für den isolierten kind-, Cilium-, Gateway- und Flux-Beweis ohne Produktionswirkung.
role: runbooks
organ: ops
status: canonical
canonicality: operational
lifecycle_state: active
owner: ops
review_after: 2026-08-16
last_reviewed: 2026-07-16
depends_on:
  - platform.readme
relations:
  - type: relates_to
    target: docs/reports/kubernetes-platform-foundation-status.md
  - type: verifies
    target: scripts/platform/kind_reference.py
verifies_with:
  - scripts/platform/kind_reference.py
---

# Kubernetes- und GitOps-Referenzzelle lokal prüfen

## Vorbedingungen

- sauberer, isolierter Weltgewebe-Worktree;
- funktionierender Docker-Daemon;
- Linux amd64;
- kein bestehender Cluster mit dem gewählten Namen;
- keine laufende Produktionsänderung in diesem Pfad.

Die Werkzeuge werden nicht global installiert. `bootstrap_tools.py` lädt sie in den ignorierten Repositorycache und verifiziert jeden SHA-256.

## Statischer Vertrag

```bash
make platform-check
make platform-render
```

## Direkter lokaler Beweis

```bash
python3 scripts/platform/kind_reference.py proof   --cluster weltgewebe-reference   --mode direct
```

Der Runner baut API und Web, lädt sie in kind, installiert Gateway API, Cilium/Hubble und Flux, erzeugt ephemere Secrets, führt die Migration kontrolliert vor dem Replica-Start aus, startet zwei API-Pods, prüft Restart und Gateway und entfernt ausschließlich den selbst markierten Cluster.

## GitOps-Beweis

Ein Git-Branch muss bereits veröffentlicht sein:

```bash
python3 scripts/platform/kind_reference.py proof   --cluster weltgewebe-reference-gitops   --mode gitops   --source-ref <branch>
```

Zusätzlich wird ein absichtlicher Replica-Drift gesetzt und durch Flux korrigiert.

## Abbruch und Diagnose

Bei Fehlern liegen redigierte Kubernetesdiagnosen unter `.cache/weltgewebe-platform/failures/<cluster>/`. Secretwerte werden nicht in Receipts geschrieben. Ein Cluster ohne gültigen Marker wird niemals durch `down` gelöscht.

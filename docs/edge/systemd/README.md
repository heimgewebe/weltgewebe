---
id: edge.systemd.README
title: Edge Systemd
doc_type: reference
status: active
summary: Systemd-Konfiguration für den Edge-Gateway-Dienst.
relations:
  - type: relates_to
    target: docs/deploy/README.md
---
# Edge systemd units (optional)

This is **not** the primary orchestration path. The current runtime path remains Docker Compose; Kubernetes is the canonical target platform defined by ADR-0010. Nomad is not the current target.
Use these units only for tiny single-node or future edge-cell installs where Compose or Kubernetes is not appropriate, and do not infer high availability from a systemd deployment.

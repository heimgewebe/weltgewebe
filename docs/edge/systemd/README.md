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

This is **not** the primary orchestration path. Default remains **Docker Compose → Nomad**.
Use these units only for tiny single-node edge installs where Compose isn't available.

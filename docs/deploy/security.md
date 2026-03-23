---
id: deploy.security
title: Deploy Security
doc_type: architecture
status: active
summary: Security configuration and CSP rules for deployment.
relates_to:
  - docs/deployment.md
  - docs/deploy/README.md
---

## Deploy Security

## CSP Contract Guard

The frontend build may contain an inline bootstrap script.
If CSP blocks inline scripts, the application will render a blank page.

The deploy guard ensures that:

inline bootstrap → CSP allows inline execution

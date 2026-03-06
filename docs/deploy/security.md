---
id: deploy.security
role: reality
organ: deploy
status: canonical
last_reviewed: 2026-03-06
depends_on: []
verifies_with: []
audit_gaps: []
---

# Deploy Security

## CSP Contract Guard

The frontend build may contain an inline bootstrap script.
If CSP blocks inline scripts, the application will render a blank page.

The deploy guard ensures that:

inline bootstrap → CSP allows inline execution

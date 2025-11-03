### 📄 policies/limits.yaml

**Größe:** 1 KB | **md5:** `1dee2dc0df293c029b353894c90a3135`

```yaml
---
# Weltgewebe – Soft Limits (v1)
# Zweck: Leitplanken sichtbar machen. Zunächst nur dokumentarisch; keine harten Gates.
version: v1
updated: 2025-02-14
owner: platform

web:
  bundle:
    # Gesamtbudget für alle produktiven JS/CSS-Assets (komprimiert)
    total_kb: 350
    note: "Muss zum 'ci/budget.json' passen; später automatische Prüfung."
  build:
    max_minutes: 10
    note: "CI-Build der Web-App soll schnell bleiben; Ziel für Developer-Feedback."

api:
  latency:
    p95_ms: 300
    note: "Lokales/dev-nahes Ziel; Produktions-SLOs stehen in policies/slo.yaml."
  test:
    max_minutes: 10
    note: "Schnelle Rust-Tests, damit PR-Feedback nicht stockt."

ci:
  max_runtime_minutes:
    default: 20
    heavy: 45
    note: "Deckel pro Job; deckt sich mit aktuellen Timeouts in Workflows (Stand Februar 2025)."

observability:
  required:
    - "compose.core.yml"
    - "compose.observ.yml"
  note: "Sobald Observability-Compose landet, wird hier 'compose.observ.yml' Pflicht."

docs:
  runbooks_required:
    - "docs/runbooks/README.md"
    - "docs/runbooks/codespaces-recovery.md"
    - "docs/runbooks/observability.md"
  note: "observability.md folgt; zunächst nur als Reminder gelistet."

semantics:
  max_nodes_jsonl_mb: 50
  max_edges_jsonl_mb: 50
  note: "Nur Informationsaufnahme; Import-Job folgt separat."
```

### 📄 policies/perf.json

**Größe:** 421 B | **md5:** `ec77e50ece7ad6399752423748414e0f`

```json
{
  "frontend": {
    "js_budget_kb": 60,
    "tti_ms_p95": 2500,
    "lcp_ms_p75": 2500,
    "long_tasks_per_view_max": 10
  },
  "api": {
    "latency_ms_p95": 300,
    "db_query_ms_p95": 150,
    "latency_target_note": "API latency target and SLO policy latency target are both set to 300ms intentionally for consistency."
  },
  "edge": {
    "monthly_egress_gb_max": 200,
    "edge_cost_delta_30d_pct_max": 10
  }
}
```

### 📄 policies/retention.yml

**Größe:** 416 B | **md5:** `67096157882cd66d87f83024d4e5313e`

```yaml
data_lifecycle:
  fade_days: 7
  ron_days: 84
  delegation_expire_days: 28
  anonymize_opt_in_default: true
forget_pipeline:
  - name: primary_accounts
    actions:
      - type: anonymize
        deadline_days: 7
      - type: delete
        deadline_days: 84
  - name: delegation_tokens
    actions:
      - type: revoke
        deadline_days: 28
compliance:
  privacy_by_design: true
  ron_anonymization: enabled
```

### 📄 policies/security.yml

**Größe:** 371 B | **md5:** `6609aa917e7b36ec6d837afd9e342cb8`

```yaml
content_security_policy:
  default-src: "'self'"
  img-src: "'self' data:"
  script-src: "'self' 'unsafe-inline'"
  connect-src:
    - "'self'"
    - https://api.weltgewebe.internal
allowed_origins:
  - https://app.weltgewebe.example
  - https://console.weltgewebe.example
strict_transport_security:
  max_age_seconds: 63072000
  include_subdomains: true
  preload: true
```

### 📄 policies/slo.yaml

**Größe:** 437 B | **md5:** `406302df1aad0e217bf229bfeb9c5298`

```yaml
version: 1
services:
  web:
    # availability_target is a percentage (e.g., 99.9% uptime)
    availability_target: 99.9
    latency:
      p95_ms: 3000
      alert_threshold_pct_over_budget: 5
  api:
    # availability_target is a percentage (e.g., 99.95% uptime)
    availability_target: 99.95
    latency:
      p95_ms: 300
      alert_threshold_pct_over_budget: 5
error_budgets:
  window_days: 30
  warn_at_pct: 25
  page_at_pct: 50
```


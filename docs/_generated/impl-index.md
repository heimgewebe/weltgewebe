---
id: docs.generated.impl-index
title: Implementation Index
doc_type: generated
status: active
summary: Automatisch generierter Index kritischer Implementierungen.
---

## Weltgewebe Implementation Index

Generated automatically. Do not edit.

| implementation | path | impl_type | criticality | documented_by | verification | evidence_level |
| --- | --- | --- | --- | --- | --- | --- |
| impl.service.api | apps/api/ | service | high | apps/api/README.md, docs/specs/auth-api.md, docs/blueprints/domain-data-postgres-cutover.md | .github/workflows/api.yml, apps/api/tests/api_nodes.rs, apps/api/tests/api_edges.rs, apps/api/tests/db_domain_read_path.rs, apps/api/tests/db_domain_account_write_path.rs | ci |
| impl.workflow.ci | .github/workflows/ | workflow | high | ci/README.md, docs/process/README.md | .github/workflows/ci.yml, .github/workflows/docs-guard.yml, .github/workflows/task-index.yml | ci |
| impl.service.web | apps/web/ | service | high | apps/web/README.md, docs/blueprints/ui-blaupause.md, docs/blueprints/ui-roadmap.md | .github/workflows/web.yml, apps/web/tests/smoke.home.spec.ts, apps/web/src/lib/stores/uiInvariants.test.ts | ci |
| impl.infra.compose | infra/compose/ | config | high | docs/deploy/README.md, docs/deploy/heimserver.deployment.md, docs/runbooks/ops.runbook.weltgewebe-selfhost-deploy.md | .github/workflows/compose-smoke.yml, scripts/tests/test_compose_volumes_guard.sh, scripts/guard-compose-no-relative-volumes.sh | ci |
| impl.contracts | contracts/domain/ | schema | high | contracts/README.md, docs/specs/contract.md, docs/datenmodell.md | .github/workflows/contracts-domain.yml, scripts/contracts-domain-check.sh | ci |
| impl.agent.safety-preflight | scripts/agent/ | guard | high | docs/blueprints/blueprint-agent-safety-control-layer.md, docs/security/agent-write-scope-baseline.md, AGENTS.md | .github/workflows/agent-safety-preflight.yml, scripts/agent/tests/test_check_agent_preflight.py, scripts/agent/tests/test_check_non_ideal_task.py | ci |
| impl.pipeline.basemap | scripts/basemap/ | workflow | medium | docs/blueprints/map-blaupause.md, docs/blueprints/map-roadmap.md | scripts/guard/caddy-basemap-route-guard.sh | guard |
| impl.assets.map-style | map-style/ | config | low | docs/blueprints/map-blaupause.md, map-style/ASSETS.md | none | none |
| impl.infra.caddy | infra/caddy/ | config | medium | docs/blueprints/map-blaupause.md | scripts/guard/caddy-basemap-route-guard.sh | guard |
| impl.guard.basemap-runtime-proof | scripts/guard/basemap-runtime-proof.sh | guard | medium | docs/blueprints/kartenklarheit-roadmap.md, docs/blueprints/kartenklarheit-phase6.md, docs/reports/map-status-matrix.md, docs/reports/map-architekturkritik.md | .github/workflows/basemap-runtime-proof.yml | ci |
| impl.auth.db-session-store | apps/api/src/auth/session_db.rs | service | high | docs/blueprints/auth-roadmap.md | apps/api/tests/db_session_store_persistence.rs | test |

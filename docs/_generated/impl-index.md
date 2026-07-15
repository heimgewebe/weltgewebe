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
| impl.service.web | apps/web/ | service | high | apps/web/README.md, docs/specs/ui-interaction.md, docs/specs/ui-state-machine.md, docs/deploy/secondary-domain-web-surfaces.md | .github/workflows/web.yml, apps/web/tests/smoke.home.spec.ts, apps/web/tests/weltweberei-information.spec.ts, apps/web/src/lib/stores/uiInvariants.test.ts | ci |
| impl.infra.compose | infra/compose/ | config | high | docs/deploy/README.md, docs/deploy/heimserver.deployment.md, docs/runbooks/ops.runbook.weltgewebe-selfhost-deploy.md | .github/workflows/compose-smoke.yml, scripts/tests/test_compose_volumes_guard.sh, scripts/guard-compose-no-relative-volumes.sh, scripts/guard/domain-single-instance-guard.sh, scripts/tests/test_domain_single_instance_guard.sh | ci |
| impl.contracts | contracts/domain/ | schema | high | contracts/README.md, docs/specs/contract.md, docs/datenmodell.md | .github/workflows/contracts-domain.yml, scripts/contracts-domain-check.sh | ci |
| impl.agent.safety-preflight | scripts/agent/ | guard | high | docs/blueprints/blueprint-agent-safety-control-layer.md, docs/security/agent-write-scope-baseline.md, AGENTS.md | .github/workflows/agent-safety-preflight.yml, scripts/agent/tests/test_check_agent_preflight.py, scripts/agent/tests/test_check_non_ideal_task.py | ci |
| impl.pipeline.basemap | scripts/basemap/ | workflow | medium | docs/blueprints/map-blaupause.md, docs/specs/map-experience.md | scripts/guard/caddy-basemap-route-guard.sh | guard |
| impl.assets.map-style | map-style/ | config | low | docs/blueprints/map-blaupause.md, map-style/ASSETS.md | none | none |
| impl.infra.caddy | infra/caddy/ | config | medium | docs/blueprints/map-blaupause.md, docs/deployment.md | scripts/guard/caddy-basemap-route-guard.sh, scripts/guard/domain-single-instance-guard.sh, scripts/tests/test_domain_single_instance_guard.sh, scripts/ci/tests/test_regional_basemap_style.py, scripts/ci/tests/test_public_live_readiness.py | guard |
| impl.guard.basemap-runtime-proof | scripts/guard/basemap-runtime-proof.sh | guard | medium | docs/specs/map-experience.md, docs/reports/map-status.md, docs/deployment.md | .github/workflows/basemap-runtime-proof.yml, scripts/ci/tests/test_regional_basemap_style.py, scripts/ci/tests/test_public_live_readiness.py | ci |
| impl.guard.pmtiles-deep-validator | apps/web/scripts/validate-pmtiles.mjs | guard | medium | docs/deployment.md, docs/reports/map-basemap-proof-gap-reconciliation.md | apps/web/scripts/validate-pmtiles.test.mjs, .github/workflows/basemap-runtime-proof.yml | ci |
| impl.auth.db-session-store | apps/api/src/auth/session_db.rs | service | high | docs/blueprints/auth-roadmap.md | apps/api/tests/db_session_store_persistence.rs | test |
| impl.guard.domain-single-instance | scripts/guard/domain-single-instance-guard.sh | guard | high | docs/reports/domain-postgres-instance-coherence-decision.md, docs/blueprints/domain-data-postgres-cutover.md | scripts/tests/test_domain_single_instance_guard.sh, .github/workflows/ci.yml | ci |
| impl.guard.prod-public-base-url | scripts/guard/prod-public-base-url-guard.sh | guard | high | docs/deploy/public-app-base-url.md | scripts/tests/test_prod_public_base_url_guard.sh, .github/workflows/ci.yml | ci |
| impl.ops.postgres-backup-restore-proof | scripts/ops/postgres-backup.sh | workflow | high | docs/runbooks/db-recovery.md, runtime/README.md | scripts/tests/test_postgres_backup_restore_contract.sh, .github/workflows/ci.yml | ci |
| impl.ops.web-artifact-install | scripts/ops/install-web-artifact.sh | workflow | high | docs/runbook.md, runtime/README.md | scripts/tests/test_web_artifact_install_contract.sh, .github/workflows/ci.yml | ci |
| impl.guard.security-and-supply-chain | scripts/guard/security-headers-guard.sh | guard | high | policies/security.yml, docs/techstack.md | scripts/guard/run.sh, scripts/tests/test_security_headers_guard.sh, scripts/tests/test_repo_contract_guards.sh, scripts/ci/tests/test_check_github_action_pinning.py, .github/workflows/ci.yml | ci |

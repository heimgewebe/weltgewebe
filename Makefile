.PHONY: up down logs ps smoke docs-guard validate ci-validate validate-tests validate-core validate-guards validate-shell-tests platform-check platform-render platform-kind-proof generate diagnose prepare-commit generate-system-map check-system-map-drift

# Fixture repositories are short-lived. Detached Git maintenance can outlive a
# command and race with TemporaryDirectory cleanup or a following local clone.
CI_TEST_GIT_ENV = \
	GIT_CONFIG_COUNT=2 \
	GIT_CONFIG_KEY_0=maintenance.auto \
	GIT_CONFIG_VALUE_0=false \
	GIT_CONFIG_KEY_1=gc.auto \
	GIT_CONFIG_VALUE_1=0

validate-tests:
	python3 -m unittest discover scripts/docmeta/tests/
	python3 -m unittest discover scripts/agent/tests/
	$(CI_TEST_GIT_ENV) python3 -m unittest discover scripts/ci/tests/
	python3 -m pytest -q scripts/ci/tests/test_semantic_search_production_activation.py
	python3 scripts/docmeta/validate_claim_registry.py
	python3 scripts/docmeta/validate_doc_freshness_registry.py
	python3 -m scripts.docmeta.generate_claim_evidence_map --check

platform-check:
	python3 scripts/platform/validate_platform.py
	python3 -m unittest scripts.ci.tests.test_kubernetes_platform_contract

platform-render:
	python3 scripts/platform/validate_platform.py --render

platform-kind-proof:
	python3 scripts/platform/kind_reference.py proof --mode direct

validate-core:
	python3 -m scripts.docmeta.validate_schema
	python3 -m scripts.docmeta.validate_relations
	python3 -m scripts.docmeta.check_repo_index_consistency
	python3 -m scripts.docmeta.check_doc_review_age
	python3 -m scripts.docmeta.review_impact
	python3 -m scripts.docmeta.validate_opt_arc_001_db_proof_matrix
	python3 -m scripts.docmeta.export_docs_index
	python3 -m scripts.docmeta.generate_audit_gaps
	python3 -m scripts.docmeta.check_links
	python3 -m scripts.search.validate_relevance_goldset

generate-system-map:
	python3 -m scripts.docmeta.generate_system_map

check-system-map-drift: generate-system-map
	git diff --exit-code HEAD -- docs/_generated/system-map.md

validate-guards: check-system-map-drift
	bash scripts/docmeta/repo-structure-guard.sh
	bash scripts/docmeta/docs-relations-guard.sh
	bash scripts/docmeta/generated-files-guard.sh
	bash scripts/docmeta/coverage-guard.sh

validate-shell-tests:
	bash scripts/tests/test_weltgewebe_up_git_branch.sh
	bash scripts/tests/test_weltgewebe_up_frontend_required.sh
	bash scripts/tests/test_weltgewebe_up_deploy_scope.sh
	bash scripts/tests/test_version_guard.sh
	bash scripts/tests/test_basemap_mode_guard.sh
	bash scripts/tests/test_basemap_runtime_proof_contract.sh
	bash scripts/tests/test_security_headers_guard.sh
	bash scripts/tests/test_repo_contract_guards.sh
	bash scripts/tests/test_postgres_backup_restore_contract.sh
	bash scripts/tests/test_offhost_backup_pull_contract.sh
	bash scripts/tests/test_web_artifact_install_contract.sh
	bash scripts/tests/test_api_release_identity_contract.sh

validate: platform-check validate-tests validate-core validate-guards validate-shell-tests

ci-validate: validate

docs-guard: validate

generate:
	bash scripts/docmeta/generate-doc-index.sh
	python3 -m scripts.docmeta.generate_backlinks
	bash scripts/docmeta/generate-impl-index.sh
	python3 -m scripts.docmeta.generate_orphans
	python3 -m scripts.docmeta.generate_supersession_map
	python3 -m scripts.docmeta.generate_system_map
	python3 -m scripts.docmeta.generate_architecture_drift
	python3 -m scripts.docmeta.generate_doc_coverage
	python3 -m scripts.docmeta.generate_knowledge_gaps
	python3 -m scripts.docmeta.generate_implicit_dependencies
	python3 -m scripts.docmeta.generate_change_resonance
	python3 -m scripts.docmeta.generate_staleness_report
	python3 -m scripts.docmeta.generate_agent_readiness
	python3 -m scripts.docmeta.generate_claim_evidence_map
	python3 -m scripts.docmeta.generate_relations_analysis
	python3 -m scripts.docmeta.generate_relates_to_audit
	python3 -m scripts.docmeta.generate_report_lifecycle
	python3 -m scripts.docmeta.generate_report_lifecycle_inventory

diagnose: generate

# prepare-commit intentionally runs only blocking validation checks.
prepare-commit: validate

up:
	GIT_COMMIT_SHA="$$(git rev-parse HEAD)" docker compose -f infra/compose/compose.core.yml --profile dev up -d --build

down:
	docker compose -f infra/compose/compose.core.yml --profile dev down -v

logs:
	docker compose -f infra/compose/compose.core.yml --profile dev logs -f --tail=200

ps:
	docker compose -f infra/compose/compose.core.yml --profile dev ps

smoke:
	gh workflow run compose-smoke --ref main || true

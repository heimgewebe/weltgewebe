.PHONY: up down logs ps smoke docs-guard

docs-guard:
	python3 -m unittest discover scripts/docmeta/tests/
	python3 -m scripts.docmeta.validate_schema
	python3 -m scripts.docmeta.validate_relations
	python3 -m scripts.docmeta.check_repo_index_consistency
	python3 -m scripts.docmeta.check_doc_review_age
	python3 -m scripts.docmeta.review_impact
	python3 -m scripts.docmeta.export_docs_index
	python3 -m scripts.docmeta.generate_audit_gaps
	python3 -m scripts.docmeta.check_links
	bash scripts/docmeta/generate-doc-index.sh
	bash scripts/docmeta/generate-backlinks.sh
	bash scripts/docmeta/generate-impl-index.sh
	bash scripts/docmeta/orphan-guard.sh
	bash scripts/docmeta/generate-supersession-map.sh
	python3 -m scripts.docmeta.generate_system_map
	python3 -m scripts.docmeta.generate_architecture_drift
	python3 -m scripts.docmeta.generate_doc_coverage
	python3 -m scripts.docmeta.generate_knowledge_gaps
	python3 -m scripts.docmeta.generate_implicit_dependencies
	python3 -m scripts.docmeta.generate_change_resonance
	python3 -m scripts.docmeta.generate_staleness_report
	python3 -m scripts.docmeta.generate_agent_readiness
	python3 -m scripts.docmeta.generate_relations_analysis
	git diff --exit-code docs/_generated/

up:
	docker compose -f infra/compose/compose.core.yml --profile dev up -d --build

down:
	docker compose -f infra/compose/compose.core.yml --profile dev down -v

logs:
	docker compose -f infra/compose/compose.core.yml --profile dev logs -f --tail=200

ps:
	docker compose -f infra/compose/compose.core.yml --profile dev ps

smoke:
	gh workflow run compose-smoke --ref main || true

.PHONY: up down logs ps smoke docs-guard

docs-guard:
	python3 -m unittest discover scripts/docmeta/tests/
	python3 -m scripts.docmeta.validate_schema
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
	python3 scripts/docmeta/generate-architecture-drift.py
	python3 scripts/docmeta/generate-doc-coverage.py
	python3 scripts/docmeta/generate-knowledge-gaps.py
	python3 scripts/docmeta/generate-implicit-dependencies.py
	python3 scripts/docmeta/generate-change-resonance.py
	python3 scripts/docmeta/generate-staleness-report.py
	python3 scripts/docmeta/generate-agent-readiness.py
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

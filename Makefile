.PHONY: up down logs ps smoke docs-guard

docs-guard:
	python3 -m unittest discover scripts/docmeta/tests/
	python3 -m scripts.docmeta.validate_schema
	python3 -m scripts.docmeta.check_repo_index_consistency
	python3 -m scripts.docmeta.check_doc_review_age
	python3 -m scripts.docmeta.review_impact
	python3 -m scripts.docmeta.check_links
	python3 -m scripts.docmeta.generate_system_map
	python3 -m scripts.docmeta.export_docs_index
	git diff --exit-code SYSTEM_MAP.md

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

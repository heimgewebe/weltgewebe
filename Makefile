.PHONY: up down logs ps smoke

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

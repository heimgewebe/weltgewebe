set shell := ["bash", "-euo", "pipefail", "-c"]

# Default recipe: run lint when `just` is called without arguments.
# Must be the FIRST recipe — just picks the first recipe as default,
# not the one named "default".
default: lint

# Reset & Restart Web Dev Environment (Codespaces-tauglich)
reset-web:
	@echo "🧹 Cleaning up and restarting web environment..."
	# Kill lingering vite/svelte-kit processes
	pkill -f vite || true
	pkill -f svelte-kit || true
	# Clean and restart in apps/web
	cd apps/web && \
	rm -f package-lock.json && \
	pnpm install && \
	pnpm svelte-kit sync && \
	echo "🚀 Starting Vite Dev Server on 0.0.0.0:5173 ..." && \
	pnpm run dev -- --host 0.0.0.0 --port 5173
	@echo "✅ If you see 'localhost:5173' in Ports → set to Public to preview."

alias c := ci

ci:
	# Web: unit tests, build, lint and typecheck. Run Vitest directly so the
	# package pretest generator hook is not repeated after the explicit sync.
	# Hosted workflows delegate unit tests here; browser jobs keep E2E separate.
	@echo "==> Web: install, sync, unit tests, build, typecheck"
	if [ -d apps/web ]; then \
		pushd apps/web >/dev/null; \
		pnpm install --frozen-lockfile; \
		pnpm sync; \
		pnpm exec vitest run; \
		pnpm build; \
		pnpm run ci; \
		popd >/dev/null; \
	fi
	@echo "==> API: fmt, clippy, build, test (falls vorhanden)"
	if [ -d apps/api ]; then \
		pushd apps/api >/dev/null; \
		cargo fmt -- --check; \
		cargo clippy -- -D warnings; \
		cargo build --locked; \
		cargo test --locked; \
		popd >/dev/null; \
	fi
	@echo "==> Root: local CI contract"
	python3 -m unittest scripts.ci.tests.test_justfile_contract -v
	@echo "==> Root: dependency check"
	cargo deny check

# ---------- Rust ----------
fmt:       # format all
	cargo fmt --all

clippy:    # lint all (deny warnings)
	cargo clippy --all-targets --all-features -- -D warnings

test:      # run tests (PostgreSQL-backed tests are skipped; see note below)
	cargo test --all --quiet
	@echo "note: DB-backed tests (#[ignore]) were skipped — they need a live PostgreSQL."
	@echo "      CI runs them with --include-ignored (.github/workflows/api.yml)."

# Write-free hygiene check. Formatting that mutates sources is `just fmt`.
# This recipe must not invoke formatters or generators in write mode.
check:     # quick hygiene check (no writes)
	cargo fmt --all -- --check
	just clippy
	just test
	just check-demo-data
	just contracts-domain-check
	just contracts-search-check
	just agent-contract-check
	cargo deny check

# Validate the canonical repository agent contract (strict JSON + projection parity).
agent-contract-check:
	uv run --project tools/py --locked python -m scripts.agent.validate_agent_tooling_lock
	uv run --project tools/py --locked python -m scripts.agent.validate_repo_agent_contract

# ---------- Compose ----------
up:        # dev stack up (dev profile)
	make up

down:      # stop dev stack
	make down

observ:    # monitoring profile (optional)
	docker compose -f infra/compose/compose.observ.yml up -d

stream:    # event streaming profile (optional)
	docker compose -f infra/compose/compose.stream.yml up -d

# ---------- Drills ----------
drill:     # run disaster recovery drill smoke sequence
	just up
	./tools/drill-smoke.sh

# ---------- DB ----------
db-wait:    # wait for database to be ready
	./ci/scripts/db-wait.sh

db-migrate:    # run database migrations (requires sqlx-cli 0.8.1: cargo install sqlx-cli --version 0.8.1 --locked --no-default-features --features native-tls,postgres)
	sqlx migrate run --source apps/api/migrations

proof-auth-session-sqlx-direct:    # run ignored SQLx direct-Postgres session CRUD proof test
	if [ -z "${PG_DIRECT_URL:-}" ]; then \
		echo "Set PG_DIRECT_URL to direct PostgreSQL (not PgBouncer)." >&2; \
		exit 1; \
	fi
	DATABASE_URL="${PG_DIRECT_URL}" PG_DIRECT_URL="${PG_DIRECT_URL}" cargo test --locked -p weltgewebe-api --test sqlx_postgres_direct_session_crud -- --include-ignored

# Hinweis: Ein API-seitiger `seed`-Subcommand existiert nicht.
# Für Demo-Daten: `just demo-data`; für den ersten echten Account:
# `just bootstrap-first-account` (siehe Abschnitt "Real seed" unten).
# Lokaler Helper: Schnelltests & Linter – sicher mit Null-Trennung und Quoting
lint:
	@set -euo pipefail; \
	shell_files="$$(mktemp)"; \
	trap 'rm -f "$$shell_files"' EXIT; \
	python3 scripts/tools/list-shell-files.py > "$$shell_files"; \
	if [ -s "$$shell_files" ]; then \
		xargs -0 -a "$$shell_files" -n 1 bash -n --; \
		xargs -0 -a "$$shell_files" shfmt -d -i 2 -ci -sr --; \
		xargs -0 -a "$$shell_files" shellcheck -S style --; \
	else \
		echo "Keine Shell-Dateien gefunden."; \
	fi

# Port überschreibbar: `just serve-demo PORT=9090`
PORT := "8080"

# Erzeugt Demo-Daten falls nicht vorhanden.
demo-data:
	./scripts/dev/generate-demo-data.sh

# Startet den Demo-API-Server auf :${PORT}
serve-demo: demo-data
	PORT={{PORT}} node scripts/dev/gewebe-demo-server.mjs

# Schneller Smoke-Test der Endpunkte
check-demo:
	curl -fsS "http://127.0.0.1:{{PORT}}/api/nodes" | jq length
	curl -fsS "http://127.0.0.1:{{PORT}}/api/edges" | jq length

# ---------- Real seed (erster echter Account + reale Anfangsdaten) ----------
# Smoke-Origin überschreibbar: `just smoke-seed BASE_URL=http://127.0.0.1:8081`
BASE_URL := "http://127.0.0.1:8081"

# Bootstrapped den ersten echten Account (idempotent) nach .gewebe/in.
# Benötigt Umgebungsvariablen: ACCOUNT_TITLE, PUBLIC_LAT, PUBLIC_LON (alle Pflicht).
# Optional: ACCOUNT_ID, ACCOUNT_SUMMARY, ACCOUNT_ROLE, ACCOUNT_TAGS, ACCOUNT_EMAIL.
# Beispiel:
#   ACCOUNT_TITLE="Alice" PUBLIC_LAT="53.55" PUBLIC_LON="9.99" just bootstrap-first-account
bootstrap-first-account:
	./scripts/dev/bootstrap-first-account.sh

# Smoke-Check des Bootstrapped-Accounts gegen einen laufenden Stack (Caddy-Origin).
# Liest Account-ID aus .gewebe/in/bootstrap-first-account.env.
smoke-seed:
	BASE_URL={{BASE_URL}} ./scripts/dev/smoke-seed.sh

# Smoke-Check für Account Creation v0: Admin legt Account per POST /api/accounts an.
# Benötigt laufenden Stack + AUTH_DEV_LOGIN=1 + Admin-Account (bootstrap mit ACCOUNT_ROLE=admin).
smoke-account-create:
	BASE_URL={{BASE_URL}} ./scripts/dev/smoke-account-create.sh

# ---------- Contracts ----------
contracts-domain-check:
	./scripts/contracts-domain-check.sh --check

contracts-search-check:
	python3 -m scripts.search.validate_relevance_goldset

check-demo-data:
	pnpm exec tsx scripts/verify-demo-data.ts --dry-run

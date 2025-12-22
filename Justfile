set shell := ["bash", "-euo", "pipefail", "-c"]

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
	@echo "==> Web: install, sync, build, typecheck"
	if [ -d apps/web ]; then \
		pushd apps/web >/dev/null; \
		pnpm install --frozen-lockfile; \
		pnpm sync; \
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
	@echo "==> Root: dependency check"
	cargo deny check

# ---------- Rust ----------
fmt:       # format all
	cargo fmt --all

clippy:    # lint all (deny warnings)
	cargo clippy --all-targets --all-features -- -D warnings

test:      # run tests
	cargo test --all --quiet

check:     # quick hygiene check
	just fmt
	just clippy
	just test
	just check-demo-data
	cargo deny check

# ---------- Compose ----------
up:        # dev stack up (dev profile)
	docker compose -f infra/compose/compose.core.yml --profile dev up -d --build

down:      # stop dev stack
	docker compose -f infra/compose/compose.core.yml --profile dev down -v

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

db-migrate:    # run database migrations
	cargo run -p api -- migrate

seed:          # seed database with initial data
	cargo run -p api -- seed
default: lint

# Lokaler Helper: Schnelltests & Linter – sicher mit Null-Trennung und Quoting
lint:
	@set -euo pipefail; \
	if [ -n "$(git ls-files -- '*.sh' '*.bash')" ]; then \
		git ls-files -z -- '*.sh' '*.bash' | xargs -0 -n 1 bash -n --; \
		git ls-files -z -- '*.sh' '*.bash' | xargs -0 shfmt -d -i 2 -ci -sr --; \
		git ls-files -z -- '*.sh' '*.bash' | xargs -0 shellcheck -S style --; \
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
	curl -fsS "http://127.0.0.1:{{PORT}}/api/edges" | jq 'length'

# ---------- Contracts ----------
contracts-domain-check:
	./scripts/contracts-domain-check.sh

check-demo-data:
	pnpm exec tsx scripts/verify-demo-data.ts

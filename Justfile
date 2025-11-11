set shell := ["bash", "-euo", "pipefail", "-c"]

# Reset & Restart Web Dev Environment (Codespaces-tauglich)
reset-web:
    echo "🧹 Cleaning up and restarting web environment..."
    cd apps/web

    # Kill lingering vite/svelte-kit processes
    pkill -f vite || true
    pkill -f svelte-kit || true

    # Remove stale node_modules & lockfiles
    rm -rf node_modules package-lock.json

    # Verify npm cache (avoid corrupt deps)
    npm cache verify --force

    # Reinstall (include optional deps like rollup)
    npm install --include=optional

    # Re-sync routes and SvelteKit structure
    npx svelte-kit sync

    echo "🚀 Starting Vite Dev Server on 0.0.0.0:5173 ..."
    npx vite dev --host 0.0.0.0 --port 5173

    echo "✅ If you see 'localhost:5173' in Ports → set to Public to preview."

alias c := ci

ci:
	@echo "==> Web: install, sync, build, typecheck"
	if [ -d apps/web ]; then
		pushd apps/web >/dev/null
		npm ci
		npm run sync
		npm run build
		npm run ci
		popd >/dev/null
	fi
	@echo "==> API: fmt, clippy, build, test (falls vorhanden)"
	if [ -d apps/api ]; then
		pushd apps/api >/dev/null
		cargo fmt -- --check
		cargo clippy -- -D warnings
		cargo build --locked
		cargo test --locked
		popd >/dev/null
	fi

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
    mapfile -d '' files < <(git ls-files -z -- '*.sh' '*.bash' || true); \
    if [ "${#files[@]}" -eq 0 ]; then echo "keine Shell-Dateien"; exit 0; fi; \
    printf '%s\0' "${files[@]}" | xargs -0 bash -n; \
    shfmt -d -i 2 -ci -sr -- "${files[@]}"; \
    shellcheck -S style -- "${files[@]}"

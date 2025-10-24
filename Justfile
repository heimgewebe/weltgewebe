set shell := ["bash", "-euo", "pipefail", "-c"]

alias c := ci

ci:
	@echo "==> Web: install, sync, build, typecheck"
	if [ -d apps/web ]; then
		pushd apps/web >/dev/null
		npm ci
		npm run sync
		npm run build
		npm run check:ci
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

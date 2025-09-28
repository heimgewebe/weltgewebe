set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

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
up:        # dev stack up (core profile)
	docker compose -f infra/compose/compose.core.yml up -d --build

down:      # stop dev stack
	docker compose -f infra/compose/compose.core.yml down -v

observ:    # monitoring profile (optional)
	docker compose -f infra/compose/compose.observ.yml up -d

stream:    # event streaming profile (optional)
	docker compose -f infra/compose/compose.stream.yml up -d

# ---------- DB ----------
db-wait:
	./ci/scripts/db-wait.sh

db-migrate:
	cargo run -p api -- migrate

seed:
	cargo run -p api -- seed

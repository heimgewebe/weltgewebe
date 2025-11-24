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

    # Reinstall dependencies with pnpm
    pnpm install

    # Re-sync routes and SvelteKit structure
    pnpm svelte-kit sync

    echo "🚀 Starting Vite Dev Server on 0.0.0.0:5173 ..."
    pnpm vite dev --host 0.0.0.0 --port 5173

    echo "✅ If you see 'localhost:5173' in Ports → set to Public to preview."

alias c := ci

ci:
	@echo "==> Web: install, sync, build, typecheck"
	if [ -d apps/web ]; then \
		pushd apps/web >/dev/null; \
		pnpm install --frozen-lockfile; \
		pnpm sync; \
		pnpm build; \
		pnpm ci; \
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

# Port überschreibbar: `just serve-demo PORT=9090`
PORT := "8080"

# Erzeugt Demo-Daten falls nicht vorhanden.
demo-data:
	mkdir -p .gewebe/in
	test -s .gewebe/in/demo.nodes.jsonl || { echo "→ seeds: nodes"; cat > .gewebe/in/demo.nodes.jsonl <<'JSONL'
	{"type":"Feature","id":"n1","geometry":{"type":"Point","coordinates":[9.9937,53.5511]},"properties":{"title":"Marktplatz Hamburg","type":"Ort","updated_at":"2025-11-01T09:00:00Z"}}
	{"type":"Feature","id":"n2","geometry":{"type":"Point","coordinates":[10.0002,53.5523]},"properties":{"title":"Nachbarschaftshaus","type":"Initiative","updated_at":"2025-11-02T12:15:00Z"}}
	{"type":"Feature","id":"n3","geometry":{"type":"Point","coordinates":[9.9813,53.5456]},"properties":{"title":"Tauschbox Altona","type":"Projekt","updated_at":"2025-10-30T18:45:00Z"}}
	{"type":"Feature","id":"n4","geometry":{"type":"Point","coordinates":[10.0184,53.5631]},"properties":{"title":"Gemeinschaftsgarten","type":"Ort","updated_at":"2025-11-05T10:00:00Z"}}
	{"type":"Feature","id":"n5","geometry":{"type":"Point","coordinates":[9.9708,53.5615]},"properties":{"title":"Reparaturcafé","type":"Initiative","updated_at":"2025-11-03T16:20:00Z"}}
	JSONL
	}
	test -s .gewebe/in/demo.edges.jsonl || { echo "→ seeds: edges"; cat > .gewebe/in/demo.edges.jsonl <<'JSONL'
	{"id":"e1","src":"n1","dst":"n2","kind":"connection","title":"Kooperation Marktplatz ↔ Nachbarschaftshaus"}
	{"id":"e2","src":"n2","dst":"n4","kind":"support","title":"Gemeinschaftsaktion Gartenpflege"}
	{"id":"e3","src":"n1","dst":"n3","kind":"exchange","title":"Tauschbox liefert Material"}
	{"id":"e4","src":"n5","dst":"n1","kind":"support","title":"Reparaturcafé hilft Marktplatz"}
	JSONL
	}

# Startet den Demo-API-Server auf :${PORT}
serve-demo: demo-data
	node scripts/dev/gewebe-demo-server.mjs

# Schneller Smoke-Test der Endpunkte
check-demo:
	curl -fsS "http://127.0.0.1:{{PORT}}/api/nodes" | jq length
	curl -fsS "http://127.0.0.1:{{PORT}}/api/edges" | jq 'length'

# ---------- Contracts ----------
contracts-domain-check:
    ./scripts/contracts-domain-check.sh

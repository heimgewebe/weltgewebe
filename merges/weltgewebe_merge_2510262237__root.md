### 📄 .dockerignore

**Größe:** 136 B | **md5:** `e1f0168eace98a0b6158666ab4df57ff`

```plaintext
/node_modules
**/node_modules
**/.svelte-kit
**/.vite
**/.next
**/dist
**/build
**/target
/.cargo
.git
.gitignore
.DS_Store
.env
.env.*
```

### 📄 .editorconfig

**Größe:** 195 B | **md5:** `c5c030dca5adf99ed51d20fb9dd88b35`

```plaintext
root = true

[*]
end_of_line = lf
insert_final_newline = true
charset = utf-8
trim_trailing_whitespace = true
indent_style = space
indent_size = 2

[*.rs]
indent_size = 4

[*.sh]
indent_size = 4
```

### 📄 .gitattributes

**Größe:** 17 B | **md5:** `71450edb9a4f8cf9d474fb0a1432a3d5`

```plaintext
*.sh text eol=lf
```

### 📄 .gitignore

**Größe:** 279 B | **md5:** `feff7a80ee0ac93560795b8818869afa`

```plaintext
# Weltgewebe repository ignores
# Prevent accidental check-in of local Git directories
/.git/

# Environment files
.env
.env.local
.env.*
!.env.example

# Node/NPM artifacts
node_modules/
npm-debug.log*

# Build outputs
build/
dist/
.tmp/
target/

# OS files
.DS_Store
Thumbs.db
```

### 📄 .lychee.toml

**Größe:** 287 B | **md5:** `ae4d79202645000d4956d73acb13c7d3`

```toml
# Retries & Timeouts
max_redirects = 5
timeout = 10
retry_wait_time = 2
retry_count = 2

# Private/temporäre Hosts ignorieren (Beispiele)
exclude = [
  "localhost",
  "127.0.0.1",
  "0.0.0.0"
]

# Pfade: node_modules & Git-Ordner ausnehmen
exclude_path = [
  "node_modules",
  ".git"
]
```

### 📄 .markdownlint.jsonc

**Größe:** 109 B | **md5:** `aa1753b57ccc3fb5b53d7370b9ae2f73`

```plaintext
{
  "default": true,
  "MD013": { "line_length": 120, "tables": false },
  "MD033": false,
  "MD041": false
}
```

### 📄 .markdownlint.yaml

**Größe:** 86 B | **md5:** `3800019826b32c0cd883553dfa5a4fab`

```yaml
---
default: true
MD013:
  line_length: 120
  tables: false
MD033: false
MD041: false
```

### 📄 .nvmrc

**Größe:** 4 B | **md5:** `54cd1eb655dd4f5ee6410c4fd4a9c53a`

```plaintext
v20
```

### 📄 .vale.ini

**Größe:** 94 B | **md5:** `4f2775559c47a6279a64d9ed0f1675b7`

```plaintext
StylesPath = .vale/styles
MinAlertLevel = suggestion

[*.md]
BasedOnStyles = Vale, Weltgewebe
```

### 📄 .yamllint.yml

**Größe:** 161 B | **md5:** `d826f0422646e4e79b47ac7b319fd52e`

```yaml
extends: default

rules:
  line-length:
    max: 120
    allow-non-breakable-words: true
  truthy:
    level: warning
  comments:
    min-spaces-from-content: 1
```

### 📄 CONTRIBUTING.md

**Größe:** 5 KB | **md5:** `bdff7cad9dc64f137f0e75a6df11f304`

```markdown
Hier ist das finale CONTRIBUTING.md – optimiert, konsistent mit docs/architekturstruktur.md, und so
geschrieben, dass Menschen
und KIs sofort wissen, was wohin gehört, warum, und wie gearbeitet wird.

⸻

# CONTRIBUTING.md

## Weltgewebe – Beiträge, Qualität, Wegeführung

Dieses Dokument erklärt, wie im Weltgewebe-Repository gearbeitet wird: Ordner-Orientierung,
Workflows, Qualitätsmaßstäbe und
Entscheidungswege.

Es baut auf folgenden Dateien auf:

- docs/architekturstruktur.md – verbindliche Repo-Struktur (Ordner, Inhalte, Zweck).
- docs/techstack.md – Stack-Referenz (SvelteKit, Rust/Axum, Postgres+Outbox, JetStream, Caddy,
  Observability).
- ci/budget.json – Performance-Budgets (Frontend).
- docs/runbook.md – Woche-1/2, DR/DSGVO-Drills.
- docs/datenmodell.md – Tabellen, Projektionen, Events.

Kurzprinzip: „Richtig routen, klein schneiden, sauber messen.“ Beiträge landen im richtigen Ordner,
klein und testbar, mit
Metriken und Budgets im Blick.

⸻

## 1. Repo-Topographie in 30 Sekunden

- apps/ – Business-Code (Web-Frontend, API, Worker, optionale Search-Adapter).
- packages/ – gemeinsame Libraries/SDKs (optional).
- infra/ – Compose-Profile, Proxy (Caddy), DB-Init, Monitoring, optional Nomad/K8s.
- docs/ – ADRs, Architektur-Poster, Datenmodell, Runbook.
- ci/ – GitHub-Workflows, Skripte, Performance-Budgets.
- Root – .env.example, Editor/Git-Konfig, Lizenz, README.

Details: siehe docs/architekturstruktur.md.

⸻

## 2. Routing-Matrix „Wohin gehört was?“

- Neue Seite oder Route im UI
  - Zielordner/Datei: apps/web/src/routes/...
  - Typisches Pattern: +page.svelte, +page.ts, +server.ts.
  - Grund: SvelteKit-Routing, SSR/Islands, nahe an UI.
- UI-Komponente, Store oder Util
  - Zielordner/Datei: apps/web/src/lib/...
  - Typisches Pattern: *.svelte, stores.ts, utils.ts.
  - Grund: Wiederverwendung, klare Trennung vom Routing.
- Statische Assets
  - Zielordner/Datei: apps/web/static/.
  - Typisches Pattern: manifest.webmanifest, Icons, Fonts.
  - Grund: Build-unabhängige Auslieferung.
- Neuer API-Endpoint
  - Zielordner/Datei: apps/api/src/routes/...
  - Typisches Pattern: mod.rs, Handler, Router.
  - Grund: HTTP/SSE-Schnittstelle gehört in routes.
- Geschäftslogik oder Service
  - Zielordner/Datei: apps/api/src/domain/...
  - Typisches Pattern: Use-Case-Funktionen.
  - Grund: Fachlogik von I/O trennen.
- DB-Zugriff (nur PostgreSQL)
  - Zielordner/Datei: apps/api/src/repo/...
  - Typisches Pattern: sqlx-Queries, Mappings.
  - Grund: Konsistente Datenzugriffe.
- Outbox-Publizierer oder Eventtypen
  - Zielordner/Datei: apps/api/src/events/...
  - Typisches Pattern: publish_*, Event-Schema.
  - Grund: Transaktionale Events am System of Truth.
- DB-Migrationen
  - Zielordner/Datei: apps/api/migrations/.
  - Typisches Pattern: YYYYMMDDHHMM__beschreibung.sql.
  - Grund: Änderungsverfolgung am Schema.
- Timeline-Projektor
  - Zielordner/Datei: apps/worker/src/projector_timeline.rs.
  - Typisches Pattern: Outbox → Timeline.
  - Grund: Read-Model separat, idempotent.
- Search-Projektor
  - Zielordner/Datei: apps/worker/src/projector_search.rs.
  - Typisches Pattern: Outbox → Typesense/Meili.
  - Grund: Indexing asynchron.
- DSGVO- oder DR-Rebuilder
  - Zielordner/Datei: apps/worker/src/replayer.rs.
  - Typisches Pattern: Replay/Shadow-Rebuild.
  - Grund: Audit- und Forget-Pfad.
- Search-Adapter oder SDK
  - Zielordner/Datei: apps/search/adapters/...
  - Typisches Pattern: typesense.ts, meili.ts.
  - Grund: Client-Adapter gekapselt.
- Compose-Profile
  - Zielordner/Datei: infra/compose/*.yml.
  - Typisches Pattern: compose.core.yml usw.
  - Grund: Start- und Betriebsprofile.
- Proxy, Headers, CSP
  - Zielordner/Datei: infra/caddy/Caddyfile.
  - Typisches Pattern: HTTP/3, TLS, CSP.
  - Grund: Auslieferung & Sicherheit.
- DB-Init und Partitionierung
  - Zielordner/Datei: infra/db/{init,partman}/.
  - Typisches Pattern: Extensions, Partman.
  - Grund: Basis-Setup für PostgreSQL.
- Monitoring
  - Zielordner/Datei: infra/monitoring/...
  - Typisches Pattern: prometheus.yml, Dashboards, Alerts.
  - Grund: Metriken, SLO-Wächter.
- Architektur-Entscheidung
  - Zielordner/Datei: docs/adr/ADR-xxx.md.
  - Typisches Pattern: Datum- oder Nummernschema.
  - Grund: Nachvollziehbarkeit.
- Runbook
  - Zielordner/Datei: docs/runbook.md.
  - Typisches Pattern: Woche-1/2, DR/DSGVO.
  - Grund: Betrieb in der Praxis.
- Datenmodell
  - Zielordner/Datei: docs/datenmodell.md.
  - Typisches Pattern: Tabellen/Projektionen.
  - Grund: Referenz für API/Worker.

⸻

## 3. Arbeitsweise / Workflow

Branch-Strategie: kurzes Feature-Branching gegen main.
Kleine, thematisch fokussierte Pull Requests.

Commit-Präfixe:

- feat(web): … | feat(api): … | feat(worker): … | feat(infra): …
- fix(...) | chore(...) | refactor(...) | docs(adr|runbook|...)

PR-Prozess:

1. Lokal: Lints, Tests und Budgets laufen lassen.
2. PR klein halten, Zweck und „Wie getestet“ kurz erläutern.
3. Bei Architektur- oder Sicherheitsauswirkungen: ADR oder Runbook-Update beilegen oder verlinken.

CI-Gates (brechen Builds):

- Frontend-Budget aus ci/budget.json (Initial-JS ≤ 60 KB, TTI ≤ 2000 ms).
- Lints/Formatter (Web: ESLint/Prettier; API/Worker: cargo fmt, cargo clippy -D).
- Tests (npm test, cargo test).
- Sicherheitschecks (cargo audit/deny), Konfiglint (Prometheus, Caddy).
```

### 📄 Cargo.lock

**Größe:** 63 KB | **md5:** `534509eff6be9f906bb07d41eda3bfe7`

```plaintext
# This file is automatically @generated by Cargo.
# It is not intended for manual editing.
version = 4

[[package]]
name = "aho-corasick"
version = "1.1.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "8e60d3430d3a69478ad0993f19238d2df97c507009a52b3c10addcd7f6bcb916"
dependencies = [
 "memchr",
]

[[package]]
name = "allocator-api2"
version = "0.2.21"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "683d7910e743518b0e34f1186f92494becacb047c7b6bf616c96772180fef923"

[[package]]
name = "anyhow"
version = "1.0.100"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "a23eb6b1614318a8071c9b2521f36b424b2c83db5eb3a0fead4a6c0809af6e61"

[[package]]
name = "async-nats"
version = "0.35.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "ab8df97cb8fc4a884af29ab383e9292ea0939cfcdd7d2a17179086dc6c427e7f"
dependencies = [
 "base64",
 "bytes",
 "futures",
 "memchr",
 "nkeys",
 "nuid",
 "once_cell",
 "portable-atomic",
 "rand",
 "regex",
 "ring",
 "rustls-native-certs",
 "rustls-pemfile",
 "rustls-webpki 0.102.8",
 "serde",
 "serde_json",
 "serde_nanos",
 "serde_repr",
 "thiserror 1.0.69",
 "time",
 "tokio",
 "tokio-rustls",
 "tracing",
 "tryhard",
 "url",
]

[[package]]
name = "async-trait"
version = "0.1.89"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9035ad2d096bed7955a320ee7e2230574d28fd3c3a0f186cbea1ff3c7eed5dbb"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "atoi"
version = "2.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "f28d99ec8bfea296261ca1af174f24225171fea9664ba9003cbebee704810528"
dependencies = [
 "num-traits",
]

[[package]]
name = "atomic-waker"
version = "1.1.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1505bd5d3d116872e7271a6d4e16d81d0c8570876c8de68093a09ac269d8aac0"

[[package]]
name = "autocfg"
version = "1.5.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "c08606f8c3cbf4ce6ec8e28fb0014a2c086708fe954eaa885384a6165172e7e8"

[[package]]
name = "axum"
version = "0.7.9"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "edca88bc138befd0323b20752846e6587272d3b03b0343c8ea28a6f819e6e71f"
dependencies = [
 "async-trait",
 "axum-core",
 "axum-macros",
 "bytes",
 "futures-util",
 "http",
 "http-body",
 "http-body-util",
 "hyper",
 "hyper-util",
 "itoa",
 "matchit",
 "memchr",
 "mime",
 "percent-encoding",
 "pin-project-lite",
 "rustversion",
 "serde",
 "serde_json",
 "serde_path_to_error",
 "serde_urlencoded",
 "sync_wrapper",
 "tokio",
 "tower",
 "tower-layer",
 "tower-service",
 "tracing",
]

[[package]]
name = "axum-core"
version = "0.4.5"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "09f2bd6146b97ae3359fa0cc6d6b376d9539582c7b4220f041a33ec24c226199"
dependencies = [
 "async-trait",
 "bytes",
 "futures-util",
 "http",
 "http-body",
 "http-body-util",
 "mime",
 "pin-project-lite",
 "rustversion",
 "sync_wrapper",
 "tower-layer",
 "tower-service",
 "tracing",
]

[[package]]
name = "axum-macros"
version = "0.4.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "57d123550fa8d071b7255cb0cc04dc302baa6c8c4a79f55701552684d8399bce"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "base64"
version = "0.22.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "72b3254f16251a8381aa12e40e3c4d2f0199f8c6508fbecb9d91f575e0fbb8c6"

[[package]]
name = "base64ct"
version = "1.8.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "55248b47b0caf0546f7988906588779981c43bb1bc9d0c44087278f80cdb44ba"

[[package]]
name = "bitflags"
version = "2.9.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "2261d10cca569e4643e526d8dc2e62e433cc8aba21ab764233731f8d369bf394"

[[package]]
name = "block-buffer"
version = "0.10.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "3078c7629b62d3f0439517fa394996acacc5cbc91c5a20d8c658e77abd503a71"
dependencies = [
 "generic-array",
]

[[package]]
name = "byteorder"
version = "1.5.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1fd0f2584146f6f2ef48085050886acf353beff7305ebd1ae69500e27c67f64b"

[[package]]
name = "bytes"
version = "1.10.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "d71b6127be86fdcfddb610f7182ac57211d4b18a3e9c82eb2d17662f2227ad6a"
dependencies = [
 "serde",
]

[[package]]
name = "cc"
version = "1.2.41"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "ac9fe6cdbb24b6ade63616c0a0688e45bb56732262c158df3c0c4bea4ca47cb7"
dependencies = [
 "find-msvc-tools",
 "shlex",
]

[[package]]
name = "cfg-if"
version = "1.0.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9330f8b2ff13f34540b44e946ef35111825727b38d33286ef986142615121801"

[[package]]
name = "concurrent-queue"
version = "2.5.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "4ca0197aee26d1ae37445ee532fefce43251d24cc7c166799f4d46817f1d3973"
dependencies = [
 "crossbeam-utils",
]

[[package]]
name = "const-oid"
version = "0.9.6"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "c2459377285ad874054d797f3ccebf984978aa39129f6eafde5cdc8315b612f8"

[[package]]
name = "core-foundation"
version = "0.9.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "91e195e091a93c46f7102ec7818a2aa394e1e1771c3ab4825963fa03e45afb8f"
dependencies = [
 "core-foundation-sys",
 "libc",
]

[[package]]
name = "core-foundation-sys"
version = "0.8.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "773648b94d0e5d620f64f280777445740e61fe701025087ec8b57f45c791888b"

[[package]]
name = "cpufeatures"
version = "0.2.17"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "59ed5838eebb26a2bb2e58f6d5b5316989ae9d08bab10e0e6d103e656d1b0280"
dependencies = [
 "libc",
]

[[package]]
name = "crc"
version = "3.3.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9710d3b3739c2e349eb44fe848ad0b7c8cb1e42bd87ee49371df2f7acaf3e675"
dependencies = [
 "crc-catalog",
]

[[package]]
name = "crc-catalog"
version = "2.4.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "19d374276b40fb8bbdee95aef7c7fa6b5316ec764510eb64b8dd0e2ed0d7e7f5"

[[package]]
name = "crossbeam-queue"
version = "0.3.12"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "0f58bbc28f91df819d0aa2a2c00cd19754769c2fad90579b3592b1c9ba7a3115"
dependencies = [
 "crossbeam-utils",
]

[[package]]
name = "crossbeam-utils"
version = "0.8.21"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "d0a5c400df2834b80a4c3327b3aad3a4c4cd4de0629063962b03235697506a28"

[[package]]
name = "crypto-common"
version = "0.1.6"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1bfb12502f3fc46cca1bb51ac28df9d618d813cdc3d2f25b9fe775a34af26bb3"
dependencies = [
 "generic-array",
 "typenum",
]

[[package]]
name = "curve25519-dalek"
version = "4.1.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "97fb8b7c4503de7d6ae7b42ab72a5a59857b4c937ec27a3d4539dba95b5ab2be"
dependencies = [
 "cfg-if",
 "cpufeatures",
 "curve25519-dalek-derive",
 "digest",
 "fiat-crypto",
 "rustc_version",
 "subtle",
]

[[package]]
name = "curve25519-dalek-derive"
version = "0.1.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "f46882e17999c6cc590af592290432be3bce0428cb0d5f8b6715e4dc7b383eb3"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "data-encoding"
version = "2.9.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "2a2330da5de22e8a3cb63252ce2abb30116bf5265e89c0e01bc17015ce30a476"

[[package]]
name = "der"
version = "0.7.10"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "e7c1832837b905bbfb5101e07cc24c8deddf52f93225eee6ead5f4d63d53ddcb"
dependencies = [
 "const-oid",
 "pem-rfc7468",
 "zeroize",
]

[[package]]
name = "deranged"
version = "0.5.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "a41953f86f8a05768a6cda24def994fd2f424b04ec5c719cf89989779f199071"
dependencies = [
 "powerfmt",
 "serde_core",
]

[[package]]
name = "digest"
version = "0.10.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9ed9a281f7bc9b7576e61468ba615a66a5c8cfdff42420a70aa82701a3b1e292"
dependencies = [
 "block-buffer",
 "crypto-common",
 "subtle",
]

[[package]]
name = "displaydoc"
version = "0.2.5"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "97369cbbc041bc366949bc74d34658d6cda5621039731c6310521892a3a20ae0"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "dotenvy"
version = "0.15.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1aaf95b3e5c8f23aa320147307562d361db0ae0d51242340f558153b4eb2439b"

[[package]]
name = "ed25519"
version = "2.2.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "115531babc129696a58c64a4fef0a8bf9e9698629fb97e9e40767d235cfbcd53"
dependencies = [
 "signature",
]

[[package]]
name = "ed25519-dalek"
version = "2.2.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "70e796c081cee67dc755e1a36a0a172b897fab85fc3f6bc48307991f64e4eca9"
dependencies = [
 "curve25519-dalek",
 "ed25519",
 "sha2",
 "signature",
 "subtle",
]

[[package]]
name = "either"
version = "1.15.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "48c757948c5ede0e46177b7add2e67155f70e33c07fea8284df6576da70b3719"
dependencies = [
 "serde",
]

[[package]]
name = "equivalent"
version = "1.0.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "877a4ace8713b0bcf2a4e7eec82529c029f1d0619886d18145fea96c3ffe5c0f"

[[package]]
name = "errno"
version = "0.3.14"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "39cab71617ae0d63f51a36d69f866391735b51691dbda63cf6f96d042b63efeb"
dependencies = [
 "libc",
 "windows-sys 0.61.2",
]

[[package]]
name = "etcetera"
version = "0.8.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "136d1b5283a1ab77bd9257427ffd09d8667ced0570b6f938942bc7568ed5b943"
dependencies = [
 "cfg-if",
 "home",
 "windows-sys 0.48.0",
]

[[package]]
name = "event-listener"
version = "5.4.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "e13b66accf52311f30a0db42147dadea9850cb48cd070028831ae5f5d4b856ab"
dependencies = [
 "concurrent-queue",
 "parking",
 "pin-project-lite",
]

[[package]]
name = "fastrand"
version = "2.3.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "37909eebbb50d72f9059c3b6d82c0463f2ff062c9e95845c43a6c9c0355411be"

[[package]]
name = "fiat-crypto"
version = "0.2.9"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "28dea519a9695b9977216879a3ebfddf92f1c08c05d984f8996aecd6ecdc811d"

[[package]]
name = "find-msvc-tools"
version = "0.1.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "52051878f80a721bb68ebfbc930e07b65ba72f2da88968ea5c06fd6ca3d3a127"

[[package]]
name = "fnv"
version = "1.0.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "3f9eec918d3f24069decb9af1554cad7c880e2da24a9afd88aca000531ab82c1"

[[package]]
name = "foldhash"
version = "0.1.5"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "d9c4f5dac5e15c24eb999c26181a6ca40b39fe946cbe4c263c7209467bc83af2"

[[package]]
name = "form_urlencoded"
version = "1.2.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "cb4cb245038516f5f85277875cdaa4f7d2c9a0fa0468de06ed190163b1581fcf"
dependencies = [
 "percent-encoding",
]

[[package]]
name = "futures"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "65bc07b1a8bc7c85c5f2e110c476c7389b4554ba72af57d8445ea63a576b0876"
dependencies = [
 "futures-channel",
 "futures-core",
 "futures-executor",
 "futures-io",
 "futures-sink",
 "futures-task",
 "futures-util",
]

[[package]]
name = "futures-channel"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "2dff15bf788c671c1934e366d07e30c1814a8ef514e1af724a602e8a2fbe1b10"
dependencies = [
 "futures-core",
 "futures-sink",
]

[[package]]
name = "futures-core"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "05f29059c0c2090612e8d742178b0580d2dc940c837851ad723096f87af6663e"

[[package]]
name = "futures-executor"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1e28d1d997f585e54aebc3f97d39e72338912123a67330d723fdbb564d646c9f"
dependencies = [
 "futures-core",
 "futures-task",
 "futures-util",
]

[[package]]
name = "futures-intrusive"
version = "0.5.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1d930c203dd0b6ff06e0201a4a2fe9149b43c684fd4420555b26d21b1a02956f"
dependencies = [
 "futures-core",
 "lock_api",
 "parking_lot",
]

[[package]]
name = "futures-io"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9e5c1b78ca4aae1ac06c48a526a655760685149f0d465d21f37abfe57ce075c6"

[[package]]
name = "futures-sink"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "e575fab7d1e0dcb8d0c7bcf9a63ee213816ab51902e6d244a95819acacf1d4f7"

[[package]]
name = "futures-task"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "f90f7dce0722e95104fcb095585910c0977252f286e354b5e3bd38902cd99988"

[[package]]
name = "futures-util"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9fa08315bb612088cc391249efdc3bc77536f16c91f6cf495e6fbe85b20a4a81"
dependencies = [
 "futures-channel",
 "futures-core",
 "futures-io",
 "futures-sink",
 "futures-task",
 "memchr",
 "pin-project-lite",
 "pin-utils",
 "slab",
]

[[package]]
name = "generic-array"
version = "0.14.9"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "4bb6743198531e02858aeaea5398fcc883e71851fcbcb5a2f773e2fb6cb1edf2"
dependencies = [
 "typenum",
 "version_check",
]

[[package]]
name = "getrandom"
version = "0.2.16"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "335ff9f135e4384c8150d6f27c6daed433577f86b4750418338c01a1a2528592"
dependencies = [
 "cfg-if",
 "libc",
 "wasi",
]

[[package]]
name = "getrandom"
version = "0.3.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "899def5c37c4fd7b2664648c28120ecec138e4d395b459e5ca34f9cce2dd77fd"
dependencies = [
 "cfg-if",
 "libc",
 "r-efi",
 "wasip2",
]

[[package]]
name = "hashbrown"
version = "0.15.5"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9229cfe53dfd69f0609a49f65461bd93001ea1ef889cd5529dd176593f5338a1"
dependencies = [
 "allocator-api2",
 "equivalent",
 "foldhash",
]

[[package]]
name = "hashbrown"
version = "0.16.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "5419bdc4f6a9207fbeba6d11b604d481addf78ecd10c11ad51e76c2f6482748d"

[[package]]
name = "hashlink"
version = "0.10.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "7382cf6263419f2d8df38c55d7da83da5c18aef87fc7a7fc1fb1e344edfe14c1"
dependencies = [
 "hashbrown 0.15.5",
]

[[package]]
name = "heck"
version = "0.5.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "2304e00983f87ffb38b55b444b5e3b60a884b5d30c0fca7d82fe33449bbe55ea"

[[package]]
name = "hex"
version = "0.4.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "7f24254aa9a54b5c858eaee2f5bccdb46aaf0e486a595ed5fd8f86ba55232a70"

[[package]]
name = "hkdf"
version = "0.12.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "7b5f8eb2ad728638ea2c7d47a21db23b7b58a72ed6a38256b8a1849f15fbbdf7"
dependencies = [
 "hmac",
]

[[package]]
name = "hmac"
version = "0.12.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "6c49c37c09c17a53d937dfbb742eb3a961d65a994e6bcdcf37e7399d0cc8ab5e"
dependencies = [
 "digest",
]

[[package]]
name = "home"
version = "0.5.11"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "589533453244b0995c858700322199b2becb13b627df2851f64a2775d024abcf"
dependencies = [
 "windows-sys 0.59.0",
]

[[package]]
name = "http"
version = "1.3.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "f4a85d31aea989eead29a3aaf9e1115a180df8282431156e533de47660892565"
dependencies = [
 "bytes",
 "fnv",
 "itoa",
]

[[package]]
name = "http-body"
version = "1.0.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1efedce1fb8e6913f23e0c92de8e62cd5b772a67e7b3946df930a62566c93184"
dependencies = [
 "bytes",
 "http",
]

[[package]]
name = "http-body-util"
version = "0.1.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "b021d93e26becf5dc7e1b75b1bed1fd93124b374ceb73f43d4d4eafec896a64a"
dependencies = [
 "bytes",
 "futures-core",
 "http",
 "http-body",
 "pin-project-lite",
]

[[package]]
name = "httparse"
version = "1.10.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "6dbf3de79e51f3d586ab4cb9d5c3e2c14aa28ed23d180cf89b4df0454a69cc87"

[[package]]
name = "httpdate"
version = "1.0.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "df3b46402a9d5adb4c86a0cf463f42e19994e3ee891101b1841f30a545cb49a9"

[[package]]
name = "hyper"
version = "1.7.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "eb3aa54a13a0dfe7fbe3a59e0c76093041720fdc77b110cc0fc260fafb4dc51e"
dependencies = [
 "atomic-waker",
 "bytes",
 "futures-channel",
 "futures-core",
 "http",
 "http-body",
 "httparse",
 "httpdate",
 "itoa",
 "pin-project-lite",
 "pin-utils",
 "smallvec",
 "tokio",
]

[[package]]
name = "hyper-util"
version = "0.1.17"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "3c6995591a8f1380fcb4ba966a252a4b29188d51d2b89e3a252f5305be65aea8"
dependencies = [
 "bytes",
 "futures-core",
 "http",
 "http-body",
 "hyper",
 "pin-project-lite",
 "tokio",
 "tower-service",
]

[[package]]
name = "icu_collections"
version = "2.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "200072f5d0e3614556f94a9930d5dc3e0662a652823904c3a75dc3b0af7fee47"
dependencies = [
 "displaydoc",
 "potential_utf",
 "yoke",
 "zerofrom",
 "zerovec",
]

[[package]]
name = "icu_locale_core"
version = "2.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "0cde2700ccaed3872079a65fb1a78f6c0a36c91570f28755dda67bc8f7d9f00a"
dependencies = [
 "displaydoc",
 "litemap",
 "tinystr",
 "writeable",
 "zerovec",
]

[[package]]
name = "icu_normalizer"
version = "2.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "436880e8e18df4d7bbc06d58432329d6458cc84531f7ac5f024e93deadb37979"
dependencies = [
 "displaydoc",
 "icu_collections",
 "icu_normalizer_data",
 "icu_properties",
 "icu_provider",
 "smallvec",
 "zerovec",
]

[[package]]
name = "icu_normalizer_data"
version = "2.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "00210d6893afc98edb752b664b8890f0ef174c8adbb8d0be9710fa66fbbf72d3"


<<TRUNCATED: max_file_lines=800>>
```

### 📄 Cargo.toml

**Größe:** 57 B | **md5:** `f55d8c30bed478d4a3847fedbba48634`

```toml
[workspace]
members = [
    "apps/api",
]
resolver = "2"
```

### 📄 Justfile

**Größe:** 2 KB | **md5:** `62d85b8ec7c714be601e0876f5f720ee`

```plaintext
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
```

### 📄 LICENSE

**Größe:** 34 KB | **md5:** `f1ca515ad092d9773815721600c05759`

```plaintext
                    GNU AFFERO GENERAL PUBLIC LICENSE
                       Version 3, 19 November 2007

 Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.

                            Preamble

  The GNU Affero General Public License is a free, copyleft license for
software and other kinds of works, specifically designed to ensure
cooperation with the community in the case of network server software.

  The licenses for most software and other practical works are designed
to take away your freedom to share and change the works.  By contrast,
our General Public Licenses are intended to guarantee your freedom to
share and change all versions of a program--to make sure it remains free
software for all its users.

  When we speak of free software, we are referring to freedom, not
price.  Our General Public Licenses are designed to make sure that you
have the freedom to distribute copies of free software (and charge for
them if you wish), that you receive source code or can get it if you
want it, that you can change the software or use pieces of it in new
free programs, and that you know you can do these things.

  Developers that use our General Public Licenses protect your rights
with two steps: (1) assert copyright on the software, and (2) offer you
this License which gives you legal permission to copy, distribute and/or
modify the software.

  A secondary benefit of defending all users' freedom is that
improvements made in alternate versions of the program, if they receive
widespread use, become available for other developers to incorporate.
Many developers of free software are heartened and encouraged by the
resulting cooperation.  However, in the case of software used on network
servers, this result may fail to come about.  The GNU General Public
License permits making a modified version and letting the public access
it on a server without ever releasing its source code to the public.

  The GNU Affero General Public License is designed specifically to
ensure that, in such cases, the modified source code becomes available to
the community.  It requires the operator of a network server to provide
the source code of the modified version running there to the users of
that server.  Therefore, public use of a modified version, on a publicly
accessible server, gives the public access to the source code of the
modified version.

  An older license, called the Affero General Public License and
published by Affero, was designed to accomplish similar goals.  This is a
different license, not a version of the Affero GPL, but Affero has
released a new version of the Affero GPL which permits relicensing under
this license.

  The precise terms and conditions for copying, distribution and
modification follow.

                       TERMS AND CONDITIONS

  0. Definitions.

  "This License" refers to version 3 of the GNU Affero General Public
License.

  "Copyright" also means copyright-like laws that apply to other kinds of
works, such as semiconductor masks.

  "The Program" refers to any copyrightable work licensed under this
License.  Each licensee is addressed as "you".  "Licensees" and
"recipients" may be individuals or organizations.

  To "modify" a work means to copy from or adapt all or part of the work
in a fashion requiring copyright permission, other than the making of an
exact copy.  The resulting work is called a "modified version" of the
earlier work or a work "based on" the earlier work.

  A "covered work" means either the unmodified Program or a work based
on the Program.

  To "propagate" a work means to do anything with it that, without
permission, would make you directly or secondarily liable for
infringement under applicable copyright law, except executing it on a
computer or modifying a private copy.  Propagation includes copying,
distribution (with or without modification), making available to the
public, and in some countries other activities as well.

  To "convey" a work means any kind of propagation that enables other
parties to make or receive copies.  Mere interaction with a user through
a computer network, with no transfer of a copy, is not conveying.

  An interactive user interface displays "Appropriate Legal Notices"
to the extent that it includes a convenient and prominently visible
feature that (1) displays an appropriate copyright notice, and (2)
tells the user that there is no warranty for the work (except to the
extent that warranties are provided), that licensees may convey the
work under this License, and how to view a copy of this License.  If
the interface presents a list of user commands or options, such as a
menu, a prominent item in the list meets this criterion.

  1. Source Code.

  The "source code" for a work means the preferred form of the work
for making modifications to it.  "Object code" means any non-source
form of a work.

  A "Standard Interface" means an interface that either is an official
standard defined by a recognized standards body, or, in the case of
interfaces specified for a particular programming language, one that is
widely used among developers working in that language.

  The "System Libraries" of an executable work include anything, other
than the work as a whole, that (a) is included in the normal form of
packaging a Major Component, but which is not part of that Major
Component, and (b) serves only to enable use of the work with that
Major Component, or to implement a Standard Interface for which an
implementation is available to the public in source code form.  A
"Major Component", in this context, means a major essential component
(kernel, window system, and so on) of the specific operating system
(if any) on which the executable work runs, or a compiler used to
produce the work, or an object code interpreter used to run it.

  The "Corresponding Source" for a work in object code form means all
the source code needed to generate, install, and (for an executable
work) run the object code and to modify the work, including scripts to
control those activities.  However, it does not include the work's
System Libraries, or general-purpose tools or generally available free
programs which are used unmodified in performing those activities but
which are not part of the work.  For example, Corresponding Source
includes interface definition files associated with source files for
the work, and the source code for shared libraries and dynamically
linked subprograms that the work is specifically designed to require,
such as by intimate data communication or control flow between those
subprograms and other parts of the work.

  The Corresponding Source need not include anything that users can
regenerate automatically from other parts of the Corresponding Source.

  The Corresponding Source for a work in source code form is that same
work.

  2. Basic Permissions.

  All rights granted under this License are granted for the term of
copyright on the Program, and are irrevocable provided the stated
conditions are met.  This License explicitly affirms your unlimited
permission to run the unmodified Program.  The output from running a
covered work is covered by this License only if the output, given its
content, constitutes a covered work.  This License acknowledges your
rights of fair use or other equivalent, as provided by copyright law.

  You may make, run and propagate covered works that you do not convey,
without conditions so long as your license otherwise remains in force.
You may convey covered works to others for the sole purpose of having
them make modifications exclusively for you, or provide you with
facilities for running those works, provided that you comply with the
terms of this License in conveying all material for which you do not
control copyright.  Those thus making or running the covered works for
you must do so exclusively on your behalf, under your direction and
control, on terms that prohibit them from making any copies of your
copyrighted material outside their relationship with you.

  Conveying under any other circumstances is permitted solely under the
conditions stated below.  Sublicensing is not allowed; section 10 makes
it unnecessary.

  3. Protecting Users' Legal Rights From Anti-Circumvention Law.

  No covered work shall be deemed part of an effective technological
measure under any applicable law fulfilling obligations under article
11 of the WIPO copyright treaty adopted on 20 December 1996, or
similar laws prohibiting or restricting circumvention of such
measures.

  When you convey a covered work, you waive any legal power to forbid
circumvention of technological measures to the extent such circumvention
is effected by exercising rights under this License with respect to the
covered work, and you disclaim any intention to limit operation or
modification of the work as a means of enforcing, against the work's
users, your or third parties' legal rights to forbid circumvention of
technological measures.

  4. Conveying Verbatim Copies.

  You may convey verbatim copies of the Program's source code as you
receive it, in any medium, provided that you conspicuously and
appropriately publish on each copy an appropriate copyright notice;
keep intact all notices stating that this License and any
non-permissive terms added in accord with section 7 apply to the code;
keep intact all notices of the absence of any warranty; and give all
recipients a copy of this License along with the Program.

  You may charge any price or no price for each copy that you convey,
and you may offer support or warranty protection for a fee.

  5. Conveying Modified Source Versions.

  You may convey a work based on the Program, or the modifications to
produce it from the Program, in the form of source code under the terms
of section 4, provided that you also meet all of these conditions:

    a) The work must carry prominent notices stating that you modified
    it, and giving a relevant date.

    b) The work must carry prominent notices stating that it is
    released under this License and any conditions added under section
    7.  This requirement modifies the requirement in section 4 to
    "keep intact all notices".

    c) You must license the entire work, as a whole, under this
    License to anyone who comes into possession of a copy.  This
    License will therefore apply, along with any applicable section 7
    additional terms, to the whole of the work, and all its parts,
    regardless of how they are packaged.  This License gives no
    permission to license the work in any other way, but it does not
    invalidate such permission if you have separately received it.

    d) If the work has interactive user interfaces, each must display
    Appropriate Legal Notices; however, if the Program has interactive
    interfaces that do not display Appropriate Legal Notices, your
    work need not make them do so.

  A compilation of a covered work with other separate and independent
works, which are not by their nature extensions of the covered work,
and which are not combined with it such as to form a larger program,
in or on a volume of a storage or distribution medium, is called an
"aggregate" if the compilation and its resulting copyright are not
used to limit the access or legal rights of the compilation's users
beyond what the individual works permit.  Inclusion of a covered work
in an aggregate does not cause this License to apply to the other
parts of the aggregate.

  6. Conveying Non-Source Forms.

  You may convey a covered work in object code form under the terms of
sections 4 and 5, provided that you also convey the machine-readable
Corresponding Source under the terms of this License, in one of these
ways:

    a) Convey the object code in, or embodied in, a physical product
    (including a physical distribution medium), accompanied by the
    Corresponding Source fixed on a durable physical medium
    customarily used for software interchange.

    b) Convey the object code in, or embodied in, a physical product
    (including a physical distribution medium), accompanied by a
    written offer, valid for at least three years and valid for as
    long as you offer spare parts or customer support for that product
    model, to give anyone who possesses the object code either (1) a
    copy of the Corresponding Source for all the software in the
    product that is covered by this License, on a durable physical
    medium customarily used for software interchange, for a price no
    more than your reasonable cost of physically performing this
    conveying of source, or (2) access to copy the
    Corresponding Source from a network server at no charge.

    c) Convey individual copies of the object code with a copy of the
    written offer to provide the Corresponding Source.  This
    alternative is allowed only occasionally and noncommercially, and
    only if you received the object code with such an offer, in accord
    with subsection 6b.

    d) Convey the object code by offering access from a designated
    place (gratis or for a charge), and offer equivalent access to the
    Corresponding Source in the same way through the same place at no
    further charge.  You need not require recipients to copy the
    Corresponding Source along with the object code.  If the place to
    copy the object code is a network server, the Corresponding Source
    may be on a different server (operated by you or a third party)
    that supports equivalent copying facilities, provided you maintain
    clear directions next to the object code saying where to find the
    Corresponding Source.  Regardless of what server hosts the
    Corresponding Source, you remain obligated to ensure that it is
    available for as long as needed to satisfy these requirements.

    e) Convey the object code using peer-to-peer transmission, provided
    you inform other peers where the object code and Corresponding
    Source of the work are being offered to the general public at no
    charge under subsection 6d.

  A separable portion of the object code, whose source code is excluded
from the Corresponding Source as a System Library, need not be
included in conveying the object code work.

  A "User Product" is either (1) a "consumer product", which means any
tangible personal property which is normally used for personal, family,
or household purposes, or (2) anything designed or sold for incorporation
into a dwelling.  In determining whether a product is a consumer product,
doubtful cases shall be resolved in favor of coverage.  For a particular
product received by a particular user, "normally used" refers to a
typical or common use of that class of product, regardless of the status
of the particular user or of the way in which the particular user
actually uses, or expects or is expected to use, the product.  A product
is a consumer product regardless of whether the product has substantial
commercial, industrial or non-consumer uses, unless such uses represent
the only significant mode of use of the product.

  "Installation Information" for a User Product means any methods,
procedures, authorization keys, or other information required to install
and execute modified versions of a covered work in that User Product from
a modified version of its Corresponding Source.  The information must
suffice to ensure that the continued functioning of the modified object
code is in no case prevented or interfered with solely because
modification has been made.

  If you convey an object code work under this section in, or with, or
specifically for use in, a User Product, and the conveying occurs as
part of a transaction in which the right of possession and use of the
User Product is transferred to the recipient in perpetuity or for a
fixed term (regardless of how the transaction is characterized), the
Corresponding Source conveyed under this section must be accompanied
by the Installation Information.  But this requirement does not apply
if neither you nor any third party retains the ability to install
modified object code on the User Product (for example, the work has
been installed in ROM).

  The requirement to provide Installation Information does not include a
requirement to continue to provide support service, warranty, or updates
for a work that has been modified or installed by the recipient, or for
the User Product in which it has been modified or installed.  Access to a
network may be denied when the modification itself materially and
adversely affects the operation of the network or violates the rules and
protocols for communication across the network.

  Corresponding Source conveyed, and Installation Information provided,
in accord with this section must be in a format that is publicly
documented (and with an implementation available to the public in
source code form), and must require no special password or key for
unpacking, reading or copying.

  7. Additional Terms.

  "Additional permissions" are terms that supplement the terms of this
License by making exceptions from one or more of its conditions.
Additional permissions that are applicable to the entire Program shall
be treated as though they were included in this License, to the extent
that they are valid under applicable law.  If additional permissions
apply only to part of the Program, that part may be used separately
under those permissions, but the entire Program remains governed by this
License without regard to the additional permissions.

  When you convey a copy of a covered work, you may at your option
remove any additional permissions from that copy, or from any part of
it.  (Additional permissions may be written to require their own
removal in certain cases when you modify the work.)  You may place
additional permissions on material, added by you to a covered work,
for which you have or can give appropriate copyright permission.

  Notwithstanding any other provision of this License, for material you
add to a covered work, you may (if authorized by the copyright holders of
that material) supplement the terms of this License with terms:

    a) Disclaiming warranty or limiting liability differently from the
    terms of sections 15 and 16 of this License; or

    b) Requiring preservation of specified reasonable legal notices or
    author attributions in that material or in the Appropriate Legal
    Notices displayed by works containing it; or

    c) Prohibiting misrepresentation of the origin of that material, or
    requiring that modified versions of such material be marked in
    reasonable ways as different from the original version; or

    d) Limiting the use for publicity purposes of names of licensors or
    authors of the material; or

    e) Declining to grant rights under trademark law for use of some
    trade names, trademarks, or service marks; or

    f) Requiring indemnification of licensors and authors of that
    material by anyone who conveys the material (or modified versions of
    it) with contractual assumptions of liability to the recipient, for
    any liability that these contractual assumptions directly impose on
    those licensors and authors.

  All other non-permissive additional terms are considered "further
restrictions" within the meaning of section 10.  If the Program as you
received it, or any part of it, contains a notice stating that it is
governed by this License along with a term that is a further restriction,
you may remove that term.  If a license document contains a further
restriction but permits relicensing or conveying under this License, you
may add to a covered work material governed by the terms of that license
document, provided that the further restriction does not survive such
relicensing or conveying.

  If you add terms to a covered work in accord with this section, you
must place, in the relevant source files, a statement of the additional
terms that apply to those files, or a notice indicating where to find the
applicable terms.

  Additional terms, permissive or non-permissive, may be stated in the
form of a separately written license, or stated as exceptions; the above
requirements apply either way.

  8. Termination.

  You may not propagate or modify a covered work except as expressly
provided under this License.  Any attempt otherwise to propagate or
modify it is void, and will automatically terminate your rights under
this License (including any patent licenses granted under the third
paragraph of section 11).

  However, if you cease all violation of this License, then your license
from a particular copyright holder is reinstated (a) provisionally,
unless and until the copyright holder explicitly and finally terminates
your license, and (b) permanently, if the copyright holder fails to
notify you of the violation by some reasonable means prior to 60 days
after the cessation.

  Moreover, your license from a particular copyright holder is
reinstated permanently if the copyright holder notifies you of the
violation by some reasonable means, this is the first time you have
received notice of violation of this License (for any work) from that
copyright holder, and you cure the violation prior to 30 days after
your receipt of the notice.

  Termination of your rights under this section does not terminate the
licenses of parties who have received copies or rights from you under
this License.  If your rights have been terminated and not permanently
reinstated, you do not qualify to receive new licenses for the same
material under section 10.

  9. Acceptance Not Required for Having Copies.

  You are not required to accept this License in order to receive or run
a copy of the Program.  Ancillary propagation of a covered work
occurring solely as a consequence of using peer-to-peer transmission to
receive a copy likewise does not require acceptance.  However, nothing
other than this License grants you permission to propagate or modify any
covered work.  These actions infringe copyright if you do not accept this
License.  Therefore, by modifying or propagating a covered work, you
indicate your acceptance of this License to do so.

  10. Automatic Licensing of Downstream Recipients.

  Each time you convey a covered work, the recipient automatically
receives a license from the original licensors, to run, modify and
propagate that work, subject to this License.  You are not responsible
for enforcing compliance by third parties with this License.

  An "entity transaction" is a transaction transferring control of an
organization, or substantially all assets of one, or subdividing an
organization, or merging organizations.  If propagation of a covered
work results from an entity transaction, each party to that transaction
who receives a copy of the work also receives whatever licenses to the
work the party's predecessor in interest had or could give under the
previous paragraph, plus a right to possession of the Corresponding
Source of the work from the predecessor in interest, if the predecessor
has it or can get it with reasonable efforts.

  You may not impose any further restrictions on the exercise of the
rights granted or affirmed under this License.  For example, you may not
impose a license fee, royalty, or other charge for exercise of rights
granted under this License, and you may not initiate litigation
(including a cross-claim or counterclaim in a lawsuit) alleging that
any patent claim is infringed by making, using, selling, offering for
sale, or importing the Program or any portion of it.

  11. Patents.

  A "contributor" is a copyright holder who authorizes use under this
License of the Program or a work on which the Program is based.  The
work thus licensed is called the contributor's "contributor version".

  A contributor's "essential patent claims" are all patent claims
owned or controlled by the contributor, whether already acquired or
hereafter acquired, that would be infringed by some manner, permitted by
this License, of making, using, or selling its contributor version, but
do not include claims that would be infringed only as a consequence of
further modification of the contributor version.  For purposes of this
definition, "control" includes the right to grant patent sublicenses in a
manner consistent with the requirements of this License.

  Each contributor grants you a non-exclusive, worldwide, royalty-free
patent license under the contributor's essential patent claims, to make,
use, sell, offer for sale, import and otherwise run, modify and propagate
the contents of its contributor version.

  In the following three paragraphs, a "patent license" is any express
agreement or commitment, however denominated, not to enforce a patent
(such as an express permission to practice a patent or covenant not to
sue for patent infringement).  To "grant" such a patent license to a
party means to make such an agreement or commitment not to enforce a
patent against the party.

  If you convey a covered work, knowingly relying on a patent license,
and the Corresponding Source of the work is not available for anyone to
copy, free of charge and under the terms of this License, through a
publicly available network server or other readily accessible means,
then you must either (1) cause the Corresponding Source to be so
available, or (2) arrange to deprive yourself of the benefit of the
patent license for this particular work, or (3) arrange, in a manner
consistent with the requirements of this License, to extend the patent
license to downstream recipients.  "Knowingly relying" means you have
actual knowledge that, but for the patent license, your conveying the
covered work in a country, or your recipient's use of the covered work in
a country, would infringe one or more identifiable patents in that
country that you have reason to believe are valid.

  If, pursuant to or in connection with a single transaction or
arrangement, you convey, or propagate by procuring conveyance of, a
covered work, and grant a patent license to some of the parties receiving
the covered work authorizing them to use, propagate, modify or convey a
specific copy of the covered work, then the patent license you grant is
automatically extended to all recipients of the covered work and works
based on it.

  A patent license is "discriminatory" if it does not include within the
scope of its coverage, prohibits the exercise of, or is conditioned on
the non-exercise of one or more of the rights that are specifically
granted under this License.  You may not convey a covered work if you are
a party to an arrangement with a third party that is in the business of
distributing software, under which you make payment to the third party
based on the extent of your activity of conveying the work, and under
which the third party grants, to any of the parties who would receive the
covered work from you, a discriminatory patent license (a) in connection
with copies of the covered work conveyed by you (or copies made from
those copies), or (b) primarily for and in connection with specific
products or compilations that contain the covered work, unless you entered
into that arrangement, or that patent license was granted, prior to
28 March 2007.

  Nothing in this License shall be construed as excluding or limiting any
implied license or other defenses to infringement that may otherwise be
available to you under applicable patent law.

  12. No Surrender of Others' Freedom.

  If conditions are imposed on you (whether by court order, agreement or
otherwise) that contradict the conditions of this License, they do not
excuse you from the conditions of this License.  If you cannot convey a
covered work so as to satisfy simultaneously your obligations under this
License and any other pertinent obligations, then as a consequence you may
not convey it at all.  For example, if you agree to terms that obligate you
to collect a royalty for further conveying from those to whom you convey
the Program, the only way you could satisfy both those terms and this
License would be to refrain entirely from conveying the Program.

  13. Remote Network Interaction; Use with the GNU General Public License.

  Notwithstanding any other provision of this License, if you modify the
Program, your modified version must prominently offer all users
interacting with it remotely through a computer network (if your version
supports such interaction) an opportunity to receive the Corresponding
Source of your version by providing access to the Corresponding Source
from a network server at no charge, through some standard or customary
means of facilitating copying of software.  This Corresponding Source
shall include the Corresponding Source for any work covered by version 3
of the GNU General Public License that is incorporated pursuant to the
following paragraph.

  Notwithstanding any other provision of this License, you have
permission to link or combine any covered work with a work licensed under
version 3 of the GNU General Public License into a single combined work,
and to convey the resulting work.  The terms of this License will
continue to apply to the part which is the covered work, but the work
with which it is combined will remain governed by version 3 of the GNU
General Public License.

  14. Revised Versions of this License.

  The Free Software Foundation may publish revised and/or new versions of
the GNU Affero General Public License from time to time.  Such new
versions will be similar in spirit to the present version, but may differ
in detail to address new problems or concerns.

  Each version is given a distinguishing version number.  If the Program
specifies that a certain numbered version of the GNU Affero General
Public License "or any later version" applies to it, you have the option of
following the terms and conditions either of that numbered version or of
any later version published by the Free Software Foundation.  If the
Program does not specify a version number of the GNU Affero General
Public License, you may choose any version ever published by the Free
Software Foundation.

  If the Program specifies that a proxy can decide which future versions
of the GNU Affero General Public License can be used, that proxy's public
statement of acceptance of a version permanently authorizes you to choose
that version for the Program.

  Later license versions may give you additional or different
permissions.  However, no additional obligations are imposed on any
author or copyright holder as a result of your choosing to follow a later
version.

  15. Disclaimer of Warranty.

  THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY
APPLICABLE LAW.  EXCEPT WHEN OTHERWISE STATED IN WRITING THE COPYRIGHT
HOLDERS AND/OR OTHER PARTIES PROVIDE THE PROGRAM "AS IS" WITHOUT WARRANTY
OF ANY KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
PURPOSE.  THE ENTIRE RISK AS TO THE QUALITY AND PERFORMANCE OF THE PROGRAM
IS WITH YOU.  SHOULD THE PROGRAM PROVE DEFECTIVE, YOU ASSUME THE COST OF
ALL NECESSARY SERVICING, REPAIR OR CORRECTION.

  16. Limitation of Liability.

  IN NO EVENT UNLESS REQUIRED BY APPLICABLE LAW OR AGREED TO IN WRITING
WILL ANY COPYRIGHT HOLDER, OR ANY OTHER PARTY WHO MODIFIES AND/OR CONVEYS
THE PROGRAM AS PERMITTED ABOVE, BE LIABLE TO YOU FOR DAMAGES, INCLUDING ANY
GENERAL, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES ARISING OUT OF THE
USE OR INABILITY TO USE THE PROGRAM (INCLUDING BUT NOT LIMITED TO LOSS OF
DATA OR DATA BEING RENDERED INACCURATE OR LOSSES SUSTAINED BY YOU OR THIRD
PARTIES OR A FAILURE OF THE PROGRAM TO OPERATE WITH ANY OTHER PROGRAMS),
EVEN IF SUCH HOLDER OR OTHER PARTY HAS BEEN ADVISED OF THE POSSIBILITY OF
SUCH DAMAGES.

  17. Interpretation of Sections 15 and 16.

  If the disclaimer of warranty and limitation of liability provided
above cannot be given local legal effect according to their terms,
reviewing courts shall apply local law that most closely approximates an
absolute waiver of all civil liability in connection with the Program,
unless a warranty or assumption of liability accompanies a copy of the
Program in return for a fee.

                     END OF TERMS AND CONDITIONS

            How to Apply These Terms to Your New Programs

  If you develop a new program, and you want it to be of the greatest
possible use to the public, the best way to achieve this is to make it
free software which everyone can redistribute and change under these terms.

  To do so, attach the following notices to the program.  It is safest to
attach them to the start of each source file to most effectively state the
exclusion of warranty; and each file should have at least the "copyright"
line and a pointer to where the full notice is found.

    <one line to give the program's name and a brief idea of what it does.>
    Copyright (C) <year>  <name of author>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

Also add information on how to contact you by electronic and paper mail.

  If your software can interact with users remotely through a computer
network, you should also make sure that it provides a way for users to get
its source.  For example, if your program is a web application, its
interface could display a "Source" link that leads users to an archive of
the code.  There are many ways you could offer source, and different
solutions will be better for different programs; see section 13 for the
specific requirements.

  You should also get your employer (if you work as a programmer) or
school, if any, to sign a "copyright disclaimer" for the program, if
necessary.  For more information on this, and how to apply and follow the
GNU AGPL, see <https://www.gnu.org/licenses/>.
```

### 📄 Makefile

**Größe:** 412 B | **md5:** `16861eaf28c9f702ef23840e66aaa750`

```plaintext
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
```

### 📄 README.md

**Größe:** 5 KB | **md5:** `a4009b758746f93c8b715dc34b09f3c9`

```markdown
<!-- Repo ist aktuell Docs-only. Befehle für spätere Gates sind unten als Vorschau markiert. -->
<!-- Docs-only (ADR-0001 Clean-Slate) • Re-Entry via Gates A–D -->
# Weltgewebe

Mobile-first Webprojekt auf SvelteKit (Web), Rust/Axum (API), Postgres+Outbox, JetStream, Caddy.
Struktur und Beiträge: siehe `architekturstruktur.md` und `CONTRIBUTING.md`.

## Landing

Für einen schnellen Einstieg in Ethik, UX und Projektkontext:

- [Einführung: Ethik- & UX-First-Startpunkt](docs/overview/inhalt.md)
- [Systematik & Strukturüberblick](docs/overview/zusammenstellung.md)

> **Hinweis / Scope**
>
> - **Kein** Teilnahme-/Freigabeprozess für Fleet-Rollouts oder operativen Leitstandbetrieb.
> - Optionales Dashboard-Widget liest **ausschließlich** über das Leitstand-REST/Gateway;
>   **kein Direktzugriff** auf JSONL-Dateien.
> - Entspricht ADR-0001 (Docs-only) und bleibt kompatibel mit den Gates A–D.

## Getting started

> ⚙️ **Preview:** Die folgenden Schritte werden mit Gate C (Infra-light) aktiviert.
> Solange das Repo Docs-only ist, dienen sie lediglich als Ausblick.

### Development quickstart

(Preview; wird mit Gate C aktiviert – siehe `docs/process/fahrplan.md`.)

- Install Rust (stable), Docker, Docker Compose, and `just`.
- Bring up the core stack:

  ```bash
  just up
  ```

  Alternativ steht ein äquivalentes Makefile zur Verfügung:

  ```bash
  make up
  ```

- Siehe auch `docs/quickstart-gate-c.md` für die Compose-Befehle.

- Run hygiene checks locally:

  ```bash
  just check
  ```

- Öffnest du das Repo im VS Code Devcontainer, richtet `.devcontainer/post-create.sh`
  die benötigten Tools (u. a. `just`, `uv`, `vale`) automatisch ein. Danach stehen
  Python-Helfer über `uv` sofort zur Verfügung (`uv --version`).
  Falls du Python-Tools in Unterordnern verwaltest (z. B. `tools/py/`), achte darauf,
  das entstehende `uv.lock` mit einzuchecken – standardmäßig landet es im jeweiligen
  Projektstamm (Root oder Unterordner).

- CI enforces: `cargo fmt --check`, `clippy -D warnings`, `cargo deny check`.
- Performance budgets & SLOs live in `policies/` and are referenced in docs & dashboards.

> **Hinweis:** Aktuell **Docs-only/Clean-Slate** gemäß ADR-0001. Code-Re-Entry erfolgt über die Gates A–D
> (siehe [docs/process/fahrplan.md](docs/process/fahrplan.md)). Dort sind die Gate-Checklisten (A–D) als
> To-dos dokumentiert.

### Build-Zeit-Metadaten (Version/Commit/Zeitstempel)

Die API stellt unter `/version` Build-Infos bereit:

```json
{ "version": "0.1.0", "commit": "<git sha>", "build_timestamp": "<UTC ISO8601>" }
```

Diese Werte werden **zur Compile-Zeit** gesetzt. In CI exportieren die Workflows
`GIT_COMMIT_SHA` und `BUILD_TIMESTAMP` als Umgebungsvariablen. Lokal sind sie optional
und fallen auf `"unknown"` zurück. Es ist **nicht nötig**, diese Variablen in `.env` zu pflegen.

### Build-Zeit-Variablen

`GIT_COMMIT_SHA`, `CARGO_PKG_VERSION` und `BUILD_TIMESTAMP` stammen direkt aus dem
CI bzw. Compiler. Sie werden **nicht** in `.env` oder `.env.example` gepflegt.
Beim lokalen Build ohne CI-Kontext setzen wir sie automatisch auf `"unknown"`,
während die Pipelines im CI die echten Werte einspeisen. Es besteht daher kein
Bedarf, `.env.example` um diese Variablen zu erweitern.

### Policies-Pfad (Override)

Standardmäßig sucht die API die Datei `policies/limits.yaml`. Für abweichende Layouts
kannst du den Pfad via `POLICY_LIMITS_PATH=/pfad/zur/limits.yaml` setzen.

### Konfigurations-Overrides (HA_*)

Die API liest Standardwerte aus `configs/app.defaults.yml`. Für Deployments können
wir diese Defaults über folgende Umgebungsvariablen anpassen:

- `HA_FADE_DAYS`
- `HA_RON_DAYS`
- `HA_ANONYMIZE_OPT_IN`
- `HA_DELEGATION_EXPIRE_DAYS`

Optional kann `APP_CONFIG_PATH` auf eine alternative YAML-Datei zeigen.

### Soft-Limits & Policies

- Zweck: **Frühwarnung, kein Hard-Fail.**
- Hinweis: **Werden nach und nach automatisiert in CI erzwungen.**

Unter `policies/limits.yaml` dokumentieren wir Leitplanken (z. B. Web-Bundle-Budget,
CI-Laufzeiten). Sie sind zunächst informativ und werden derzeit über Kommentare in der
CI gespiegelt. Abweichungen dienen als Diskussionsgrundlage im Review.

## Semantik (Externe Quelle: semantAH)

- Verträge: `contracts/semantics/*.schema.json`
- Manuelle Aufnahme: siehe `docs/runbooks/semantics-intake.md`
- Aktuell: nur Infos, kein Event-Import.

## Continuous Integration

Docs-Only-CI aktiv mit den Checks Markdown-Lint, Link-Check, YAML/JSON-Lint und Budget-Stub (ci/budget.json).

## Gate-Fahrplan & Gate A – UX Click-Dummy

- **Gate-Checklisten:** [docs/process/fahrplan.md](docs/process/fahrplan.md) (Gates A–D mit konkreten Prüfpunkten)
- **Gate A (Preview/Docs):** [apps/web/README.md](apps/web/README.md) (Frontend-Prototyp für Karte · Drawer ·
  Zeitleiste · Ethik-UI)

## Beiträge & Docs

Stilprüfung via Vale läuft automatisch bei Doku-PRs; lokal `vale docs/` für Hinweise.
```

### 📄 deny.toml

**Größe:** 1022 B | **md5:** `b36cf17f76cc5d55f960ce9df73b6271`

```toml
[advisories]
version = 2
yanked = "warn"

# NOTE: Diese Einträge verwenden das neue Schema mit dem Schlüssel `crate`.
# Sie ersetzen die zuvor entfernten [[advisories.ignore]]-Blöcke, damit
# cargo-deny bekannte, noch nicht gefahrlos upgradebare Abhängigkeiten
# nicht als Fehler markiert.

[[advisories.ignore]]
crate  = "paste"
reason = "Ignore until a non-breaking 1.x release is available/upstream issue resolved."

[[advisories.ignore]]
crate  = "protobuf"
reason = "Pinned while waiting for a safe upgrade path compatible with current codegen."

[[advisories.ignore]]
crate  = "sqlx"
reason = "Ignore until the project can adopt a patched release without breaking changes."


[bans]
multiple-versions = "warn"
wildcards = "deny"

[licenses]
version = 2
allow = [
  "Apache-2.0",
  "BSD-2-Clause",
  "BSD-3-Clause",
  "ISC",
  "MIT",
  "Zlib",
  "Unicode-3.0"
]
confidence-threshold = 0.8

[sources]
unknown-registry = "deny"
unknown-git = "deny"
allow-registry = ["https://github.com/rust-lang/crates.io-index"]
```

### 📄 package-lock.json

**Größe:** 89 B | **md5:** `6d5f61acc9205f1f31fd0f56aaf29100`

```json
{
  "name": "weltgewebe",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {}
}
```

### 📄 toolchain.versions.yml

**Größe:** 71 B | **md5:** `12a623ad59785fb247bc36f6ec0ed63b`

```yaml
rust: "stable"       # oder z. B. "1.81.0"
python: "3.12"
uv: "0.4.20"
```


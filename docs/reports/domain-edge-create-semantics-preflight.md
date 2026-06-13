---
id: reports.domain-edge-create-semantics-preflight
title: "Domain Edge Create Semantics Preflight — OPT-ARC-001 Phase E-C"
doc_type: report
status: active
created: 2026-06-11
lang: de
summary: >
  Diagnose- und Vorbereitungsbericht für OPT-ARC-001 Phase E-C (Edge Create /
  Edge Write Path). Belegt den Ist-Zustand (kein POST /edges), nagelt die
  Create-Semantik fest (expires_at, created_at, source_type/target_type,
  JSONL-Default-Write, PostgreSQL-Payload-Mapping, Config-Matrix), listet den
  Proof-/Task-Control-Ripple des späteren E-C-PR und empfiehlt einen Schnitt.
  Keine Implementierung — ausschließlich belegter Befund und Entscheidungsgrundlage.
relations:
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
  - type: relates_to
    target: docs/reports/domain-account-write-path-proof.md
  - type: relates_to
    target: docs/reports/domain-node-write-path-proof.md
  - type: relates_to
    target: docs/reports/opt-arc-001-db-proof-matrix.json
  - type: relates_to
    target: contracts/domain/edge.schema.json
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: docs/tasks/index.json
---

# Domain Edge Create Semantics Preflight

Task: OPT-ARC-001 Phase E-C Preflight
Status: diagnostic

## Kurzurteil

**Ja, aber nur nach Mini-Spec-Änderung — und nicht als ein einzelner PR.**

- `POST /edges` existiert **nicht** (weder Route, noch JSONL-Writer, noch
  PostgreSQL-Insert, noch `edges_persist`-Mutex, noch Tests). Phase E-C ist also
  ein echter, neuer Schreibpfad und kein Re-Wording vorhandenen Codes.
- Der Schreibpfad ist aus den Account-/Node-Konventionen **eindeutig ableitbar**:
  JSONL-Append als Default-Write, PostgreSQL-Insert hinter Gate, vier-Felder-
  Config-Matrix, `id`-Kollision → 409. Die Semantik ist also belastbar
  festnagelbar.
- Blockierend bis zur Entscheidung ist **eine 3-fach-Divergenz** der Pflichtfelder
  (Contract vs. Rust-Modell vs. tatsächliche JSONL-Fixtures), insbesondere
  `expires_at` (Contract-Feld, das auf **jeder** Ebene stillschweigend
  verworfen wird) und `created_at`/`source_type`/`target_type` (Contract
  `required`, Rust `Option`, Fixtures leer). Diese müssen vor dem Runtime-Patch
  entschieden sein — genau das ist der Zweck dieses Preflights.
- **Empfohlener Schnitt: drei sequenzielle PRs** (Semantik-Lock → JSONL-Create →
  PostgreSQL-Write + Proof-Ripple). Ein einzelner PR wäre zu breit: er vermischt
  Contract-Klärung, Runtime-Logik, ein neues Config-Feld mit ~17 betroffenen
  `AppConfig`-Literalen und einen großen Proof-/Task-Control-Ripple.

## Belege

Alle Pfade/Zeilen beziehen sich auf den lokalen Stand nach `git pull --ff-only origin main`
(HEAD `8c3edec`).

| Befund | Beleg |
|---|---|
| Keine `POST /edges`-Route | `apps/api/src/routes/mod.rs:39-40` (`get(list_edges)`, `get(get_edge)`; **kein** `.post`) |
| Kein Edge-Create/Write-Symbol | repo-weit kein `create_edge`/`insert_edge`/`EdgeCreate`/`EdgeWrite`/`NewDomainEdge`/`append_edge`/`DomainEdgeWriteSource`; alle „edge writes"-Treffer sind Out-of-Scope-Marker |
| Edge-Modell ohne `expires_at`/`payload` | `apps/api/src/routes/edges.rs:19-30` |
| Contract verlangt `expires_at`-Nachbar-Felder | `contracts/domain/edge.schema.json:32-46` |
| Migration: Spalten + `payload` | `apps/api/migrations/20260531000002_create_domain_edges.up.sql:26-33` |
| PostgreSQL-Read verwirft `expires_at` | `apps/api/src/domain_db.rs:162-171` (liest nur `source_type`/`target_type`/`note` aus payload) |
| Backfill verwirft `expires_at` | `apps/api/tests/db_domain_backfill.rs:249` (`payload_str(&["source_type","target_type","note"], …)`) |
| Kein `edges_persist`-Mutex | `apps/api/src/state.rs:76,79` (nur `nodes_persist`, `accounts_persist`) |
| Account-Create als Vorlage | `apps/api/src/routes/accounts.rs:434-642` |
| Write-Guard-Muster (4 Kombinationen) | `apps/api/src/routes/domain_write_guard.rs:59-108` |
| Config-Enums + Hard-Fail | `apps/api/src/config.rs:55-156, 435-455` |
| Edge-JSONL-Pfad | `apps/api/src/utils.rs:14-15` (`.gewebe/in/demo.edges.jsonl`) |
| Proof-Matrix mit `edge_writes` als non_goal | `docs/reports/opt-arc-001-db-proof-matrix.json:10-17` |
| Validator erzwingt `edge_writes` ∈ non_goals | `scripts/docmeta/validate_opt_arc_001_db_proof_matrix.py:82-83` (`REQUIRED_NON_GOALS`) |

## Aktueller Ist-Zustand

### Edge-Route

`apps/api/src/routes/edges.rs` exportiert ausschließlich Leseendpunkte:
`load_edges` (JSONL→Cache), `list_edges` (GET, Filter/Pagination/Cursor) und
`get_edge` (GET mit Source/Target-Detail-Anreicherung). Router
(`apps/api/src/routes/mod.rs:39-40`) verdrahtet nur `GET /edges` und
`GET /edges/:id`. Zum Vergleich: `/accounts` trägt `.post(create_account)` hinter
`require_admin` (`mod.rs:42-46`). Ein Edge-Create existiert auf keiner Ebene.

### Edge-Contract

`contracts/domain/edge.schema.json` (draft-07, `additionalProperties: false`):

- Properties: `id`, `source_type` (enum `role|node|account`), `source_id`,
  `target_type` (enum), `target_id`, `edge_kind`
  (enum `delegation|membership|ownership|reference`), `created_at`,
  `expires_at`, `note` (1–1000).
- `required`: `id, source_type, source_id, target_type, target_id, edge_kind, created_at`.
- `expires_at` und `note` sind **optional**; `metadata`/`payload` existieren nicht
  (durch `additionalProperties: false` sogar **verboten**).

### Rust Edge-Modell

`apps/api/src/routes/edges.rs:19-30`:

```rust
pub struct Edge {
    pub id: String,
    pub source_id: String,
    pub source_type: Option<String>,
    pub target_id: String,
    pub target_type: Option<String>,
    #[serde(alias = "kind", alias = "edgeKind")]
    pub edge_kind: String,
    pub note: Option<String>,
    pub created_at: Option<String>,
}
```

Kein `#[serde(deny_unknown_fields)]` ⇒ unbekannte JSONL-Schlüssel (inkl.
`expires_at`) werden beim Deserialisieren **still ignoriert**. `source_type`,
`target_type`, `created_at` sind `Option` — also faktisch optional, obwohl der
Contract sie als `required` führt.

### PostgreSQL `domain_edges`

`apps/api/migrations/20260531000002_create_domain_edges.up.sql:26-33`:
Spalten `id TEXT PK`, `source_id TEXT NOT NULL`, `target_id TEXT NOT NULL`,
`edge_kind TEXT NOT NULL DEFAULT ''`, `created_at TIMESTAMPTZ` (nullable),
`payload JSONB NOT NULL DEFAULT '{}'`. Die Migrationskommentare halten fest:
`payload` bewahrt `source_type, target_type, note`; `updated_at` ist bewusst
ausgelassen; **FKs sind aufgeschoben** (Orphan-Audit erforderlich). `expires_at`
wird im Migrationskommentar **nicht** erwähnt — es ist weder Spalte noch in der
payload-Liste.

### JSONL Edge-Semantik

Edges werden heute **read-only** aus `.gewebe/in/demo.edges.jsonl`
(`apps/api/src/utils.rs:14-15`) via `load_edges` geladen. Duplikate werden beim
Laden gezählt, aber nicht abgewiesen (`OrderedCache::insert` = last-write-wins,
`edges.rs:108-110`). Tatsächliche Fixtures tragen **nur** `id, source_id,
target_id, edge_kind` (`apps/api/tests/api_edges.rs:109-111`,
`db_domain_backfill.rs:514-515`) — `source_type`/`target_type`/`created_at`/
`expires_at` fehlen in der Praxis durchgängig.

### Existing Account/Node Write Patterns

- **Account-Create** (`accounts.rs:434-642`): `reject_account_create_unless_writable`
  → Validierung → kanonischer JSONL-Record → `accounts_persist`-Mutex →
  In-Cache-Dup-Check (`id`, `email`) → Write je `DomainAccountWriteSource`
  (JSONL `append_account_line` mit `fsync`, oder `insert_account_from_jsonl_record`)
  → **erst nach durabler Schreibung** Cache-Mutation → 201. „No dual-write",
  „failed write must never leave a phantom in memory".
- **Node-Patch** (`domain_db.rs:301-462`): `SELECT … FOR UPDATE` + bedingtes
  `UPDATE`, Projektion vor `commit`, Cache-Update beim Aufrufer.
- **PostgreSQL-Account-Insert** (`domain_db.rs:676-721`): reiner `INSERT`
  (kein `ON CONFLICT`); Unique-Violation → `DuplicateId` → 409. Mapping spiegelt
  exakt den Phase-C-Backfill (`from_jsonl_record`), damit eine hier geschriebene
  Zeile **ununterscheidbar** von „JSONL-Create + Backfill" ist.

### Proof-Matrix / Validator / Workflow

`docs/reports/opt-arc-001-db-proof-matrix.json`: `overall_status: partial`,
`cutover_status: not_cutover`, `non_goals` enthält **`edge_writes`**; fünf Proofs
(B, C, D, E-A, E-B), alle `ci_proven` (PR #1165, Run 27041187630).
Der Validator `scripts/docmeta/validate_opt_arc_001_db_proof_matrix.py` erzwingt:
`REQUIRED_NON_GOALS` enthält `edge_writes` (Z. 82-83); `EXPECTED_PROOFS` ist die
fixe 5er-Menge (Z. 117-148); `state ∈ {prepared, ci_proven}` (Z. 728-741);
`prepared` ⇒ `ci_evidence: null`; Freshness-Pfade je Proof =
`(WORKFLOW_PATH, test)` (Z. 554-557). Guard-Workflow
`.github/workflows/opt-arc-001-db-proof-matrix.yml` triggert pfadbasiert
(`fetch-depth: 0`) auf Matrix-JSON, Validator(+Test), Status-Artefakte, api.yml
und die fünf Proof-Tests.

## Semantikentscheidungen

### Field Matrix

| Feld | Contract | Rust Edge | DB | Create-Entscheidung | Mapping | Risiko |
|---|---|---|---|---|---|---|
| `id` | required, uuid | `String` | `id TEXT PK` | Request optional; Server generiert UUID, falls fehlt (wie Account) | promoted column | niedrig |
| `source_id` | required, uuid | `String` | `source_id TEXT NOT NULL` | Request-Pflichtfeld | promoted column | niedrig |
| `target_id` | required, uuid | `String` | `target_id TEXT NOT NULL` | Request-Pflichtfeld | promoted column | niedrig |
| `edge_kind` | required, enum(4) | `String` (alias `kind`/`edgeKind`) | `edge_kind TEXT` | Request-Pflichtfeld; Enum-Validierung empfohlen | promoted column | mittel (Enum heute nicht erzwungen) |
| `source_type` | **required**, enum(3) | `Option<String>` | payload | Request **optional** (modell-/fixture-treu) | payload-Feld | mittel (Contract↔Runtime-Divergenz) |
| `target_type` | **required**, enum(3) | `Option<String>` | payload | Request **optional** | payload-Feld | mittel |
| `created_at` | **required**, date-time | `Option<String>` | `created_at TIMESTAMPTZ` (nullable) | Server generiert `now()` beim Create | promoted column | mittel (Abweichung zu Account-Create, das NULL lässt) |
| `expires_at` | optional, date-time | **fehlt** | **fehlt** | **Nicht Teil des Create-Slice** (Variante 2) | — (verworfen) | **hoch — Gefahr des stillen Verwerfens** |
| `note` | optional, 1–1000 | `Option<String>` | payload | Request optional | payload-Feld | niedrig |
| `payload`/`metadata` | nicht im Contract (verboten) | fehlt | `payload` ist der DB-Container | kein Request-Feld | — | niedrig |

### JSONL Write Decision

**Ja — JSONL-Edge-Create als Default-Write ist repo-konform und empfohlen.**

Begründung: `default_domain_write_truth: jsonl` (Matrix). Accounts schreiben per
JSONL-Append (`append_account_line` + `accounts_persist` + `fsync`), Nodes per
JSONL-Rewrite — beide sind die **Default**-Write-Wahrheit. Edges sind heute nur
deshalb read-only, weil noch kein Create existiert, **nicht** weil JSONL-Write
für Edges verboten wäre. Der Edge-Create im Default-Modus ist daher:

1. Neuer `edges_persist: Arc<Mutex<()>>` in `ApiState` (analog `accounts_persist`).
2. `append_edge_line(record)` mit `create_dir_all` + `append` + `flush` +
   `sync_all` (1:1 wie `append_account_line`).
3. Unter `edges_persist`: In-Cache-Dup-Check `edges.read().get(&id)` → 409
   `edge id already exists`.
4. Erst nach durablem Append: `edges.write().insert(id, edge)` (Cache-Kohärenz).
5. Persistenzfehler → 500 `failed to persist edge` (kein Cache-Insert).

Datei: `.gewebe/in/demo.edges.jsonl`. Keine dritte stille Semantik.

### PostgreSQL Payload Mapping

Symmetrieprinzip wie Account-Write: eine per `POST /edges` (Postgres-Modus)
geschriebene Zeile muss **ununterscheidbar** von „JSONL-Create + Phase-C-Backfill"
sein. Daraus folgt exakt:

- **Promoted columns:** `id`, `source_id`, `target_id`, `edge_kind`, `created_at`.
- **`payload` JSONB:** `source_type`, `target_type`, `note` — identisch zu
  `db_domain_backfill.rs:249` und `domain_db.rs:165-169`. Aufbau über einen
  `payload_from_keys(&["source_type","target_type","note"], record)`-Helfer
  (stabile, kompakte JSON-Serialisierung in fixer Schlüsselreihenfolge,
  null/absent übersprungen — wie `domain_db.rs:487-497`).
- **`expires_at`:** weder Spalte noch payload (Variante 2). Würde es je
  unterstützt, gehörte es in `payload` (kein Schema-Migrationsbedarf) — separater
  Folge-Task.
- **`created_at`:** Server-`now()` → `created_at`-Spalte (Empfehlung). Abweichung
  zu Account-Create (NULL) ist bewusst, da der Edge-Contract `created_at`
  `required` führt.
- **Read-after-Write-Symmetrie:** `load_edges_from_postgres` (`domain_db.rs:138-187`)
  rekonstruiert exakt diese Felder — keine Anpassung der Read-Logik nötig.
- **DB-Fehler-Mapping:** Serialisierter Pfad via `LOCK TABLE domain_edges IN
  EXCLUSIVE MODE`, Duplicate-Precheck (`SELECT EXISTS`) → 409, Limit-Check
  (`COUNT(*) >= MAX_EDGES_CACHE`) → 409, finaler `INSERT`. Unique-Violation
  ist nur ein defensiver Fallback; sonstige `sqlx::Error` → 500. **Keine FKs,
  kein Orphan-Audit.**

### Config Matrix

Neues `DomainEdgeWriteSource`-Enum (analog `DomainAccountWriteSource`/
`DomainNodeWriteSource`): `Jsonl` (default) / `Postgres`, Aliase
`file|files|pg|db`, `parse_env_value`, Env `WELTGEWEBE_DOMAIN_EDGE_WRITE_SOURCE`.
Neues `AppConfig`-Feld `domain_edge_write_source`. Config-Load-Hard-Fail:
`domain_edge_write_source=postgres requires domain_read_source=postgres`. Neuer
Guard `reject_edge_create_unless_writable` (Muster `domain_write_guard.rs:59-108`).

| `DOMAIN_READ_SOURCE` | `EDGE_WRITE_SOURCE` | Verhalten |
|---|---|---|
| jsonl | jsonl | **erlaubt** — JSONL-Append |
| postgres | postgres | **erlaubt** — PostgreSQL-Insert |
| postgres | jsonl | **409** `DOMAIN_READ_SOURCE_READ_ONLY` |
| jsonl | postgres | **Config-Load-Hard-Fail**; manuell konstruierter `ApiState` → **500** `INVALID_DOMAIN_WRITE_CONFIG` |

Statuscodes/Fehlerkörper bleiben wortgleich mit Account-/Node-Write (gemeinsame
Konstanten in `domain_write_guard.rs:8-14`).

### Cache-Kohärenz

Cache wird **nur nach** erfolgreicher durabler Schreibung aktualisiert (JSONL:
nach `fsync`; Postgres: nach `INSERT` ohne Fehler). Bei Persistenzfehler **kein**
Cache-Insert (kein Phantom-Edge). Der `edges_persist`-Mutex serialisiert
Dup-Check und Schreibung, damit nebenläufige Creates die `id`-Prüfung nicht
unterlaufen. Im Postgres-Modus ist die `id`-Eindeutigkeit primär durch den
`SELECT EXISTS`-Precheck innerhalb der Transaktion sichergestellt, die
PK-Unique-Violation (409) ist nur ein defensiver Fallback.

### Duplicate-/Fehler-Mapping

| Fall | Code |
|---|---|
| `id` existiert bereits (Cache, JSONL-Modus) | 409 `edge id already exists` |
| `id` existiert bereits (Duplicate-Precheck, Postgres-Modus) | 409 `edge id already exists` |
| ungültige Eingabe (fehlendes `source_id`/`target_id`, ungültiges `edge_kind`) | 400 |
| JSONL-`fsync`-/Append-Fehler | 500 `failed to persist edge` |
| sonstiger DB-Fehler | 500 |
| `postgres` read + `jsonl` edge write | 409 `DOMAIN_READ_SOURCE_READ_ONLY` |
| `jsonl` read + `postgres` edge write (manueller State) | 500 `INVALID_DOMAIN_WRITE_CONFIG` |

## Proof- und Task-Control-Ripple für späteren E-C-PR

Der spätere E-C-Implementierungs-PR (bzw. dessen PostgreSQL-Teil) **muss** ändern:

1. `docs/reports/opt-arc-001-db-proof-matrix.json` — `edge_writes` aus `non_goals`
   entfernen; Proof `db-domain-edge-write-path-proof` (Phase `E-C`,
   `state: "prepared"`, `ci_evidence: null`, `test:
   apps/api/tests/db_domain_edge_write_path.rs`, `report:
   docs/reports/domain-edge-write-path-proof.md`) **am Listenende** ergänzen
   (Reihenfolge wird gegen `EXPECTED_PROOFS` geprüft).
2. `scripts/docmeta/validate_opt_arc_001_db_proof_matrix.py` — `edge_writes` aus
   `REQUIRED_NON_GOALS` entfernen; E-C-Eintrag in `EXPECTED_PROOFS`
   (`phase: "E-C"`, `command_test_name: "db_domain_edge_write_path"`).
3. `scripts/docmeta/tests/test_validate_opt_arc_001_db_proof_matrix.py` —
   Fixtures/Erwartungen nachziehen.
4. `.github/workflows/api.yml` — neuer DB-Job `db-domain-edge-write-path-proof`
   (Vorlage: `db-domain-node-write-path-proof`, Postgres-16-Service,
   `-- --include-ignored --test-threads=1`).
5. `.github/workflows/opt-arc-001-db-proof-matrix.yml` — neuen Test + Report in
   die `paths:`-Trigger aufnehmen; `fetch-depth: 0` bleibt erforderlich.
6. `docs/reports/domain-edge-write-path-proof.md` — neuer Proof-Bericht.
7. `apps/api/tests/db_domain_edge_write_path.rs` — neuer DB-Test (zugleich
   Freshness-Pfad `(api.yml, test)`).
8. Status-Artefakte `docs/tasks/board.md`, `docs/tasks/index.json`,
   `docs/reports/optimierungsstatus.md`, `docs/reports/optimierungsstatus.json` —
   Evidenzlisten erweitern (Test/Report/`CI-Job:`-Mention werden via
   `ALL_REQUIRED_EVIDENCE` aus `EXPECTED_PROOFS` abgeleitet). **Status bleibt
   `partial`**; Edge-Writes als „Proof vorbereitet; PR-CI ausstehend" führen —
   **nicht** als erledigt, **kein** verbotenes `ci-proven`-Wording auf der
   OPT-ARC-001-Zeile, bis echte PR-CI-Evidenz vorliegt.
9. **Nach PR-CI-Harvest:** E-C-Proof auf `state: "ci_proven"` mit
   `ci_evidence`-Objekt; `commit` muss voller **40-Zeichen-lowercase-SHA** und
   **Vorfahr von HEAD** sein; Freshness verlangt, dass `api.yml` und der E-C-Test
   seit dem Evidenz-Commit unverändert sind.

## Nichtziele für E-C

- kein Cutover
- kein Dual-Write
- keine Foreign Keys
- kein Orphan-/Referenzaudit
- kein `updated_at`
- kein PATCH/DELETE auf Edges
- keine UI
- keine Step-up-E-Mail-Persistenz
- kein WebAuthn-Writeback

## Stopper

**Kein harter Stopper für E-C als nächsten Schritt** — aber vor dem Runtime-Patch
sind folgende Entscheidungen verbindlich zu treffen (alle lösbar):

Blockierend, bis entschieden (lösbar):

- **`expires_at`-Politik (hoch).** Contract-Feld, das heute auf jeder Ebene still
  verworfen wird. Ohne Entscheidung würde der Implementierungsagent es während
  des Runtime-Patches still wegdefinieren — genau das soll verhindert werden.
- **Pflichtfeld-Divergenz (mittel).** `created_at`, `source_type`, `target_type`
  sind Contract-`required`, im Rust-Modell `Option` und in Fixtures leer. Das
  Create muss einen klaren Vertrag wählen, sonst entscheidet ihn der Patch beiläufig.

Lösbar/mechanisch (kein Blocker):

- Config-Feld-Ripple (~17 `AppConfig`-Literale) und Proof-/Task-Control-Ripple —
  groß, aber geradlinig nach Account-/Node-Vorlage.

**Entscheidungen, die Alex treffen muss:**

1. **`expires_at`:** Variante 2 (im Create-Slice **nicht** unterstützt, als
   Risiko/Nichtziel dokumentiert) — *empfohlen* — vs. Variante 1 (ins
   Runtime-Modell aufnehmen, inkl. payload + Read + Tests).
2. **Stiller-Verwurf-Schutz:** unbekannte/`expires_at`-Felder im Request
   **explizit abweisen** (400/422) — *empfohlen, weil es das stille Verwerfen
   sichtbar macht* — vs. ignorieren + dokumentieren (Parität zu `create_account`,
   das Extras still ignoriert).
3. **`created_at`:** Server-`now()` in die `created_at`-Spalte — *empfohlen,
   contract-treu* — vs. NULL (Parität zu Account-Create).
4. **`source_type`/`target_type`:** im Create **optional** akzeptieren und in
   payload ablegen — *empfohlen, modell-/backfill-treu* — vs. Contract-`required`
   erzwingen (würde reale Fixtures brechen).
5. **PR-Schnitt:** 3 PRs — *empfohlen* — vs. 1 PR.

## Empfohlener Folge-Agentenauftrag

**Schnitt in drei sequenzielle PRs** (Begründung: Risiko-Isolation des
Config-Feld-Ripples, getrennte Testbarkeit JSONL vs. DB, beherrschbare
Reviewgröße):

- **PR-1 — Semantik-Lock / Contract↔Modell-Abgleich.** Setzt die Entscheidungen
  1–4 um: `expires_at`/`created_at`/`source_type`/`target_type` festnageln,
  minimaler Modell-/Contract-Abgleich, Unit-Tests, die das Verhalten (z. B.
  Drop bzw. Reject von `expires_at`) festschreiben. Keine DB, kein neuer Endpunkt.
- **PR-2 — JSONL Edge-Create.** `POST /edges` (hinter passendem Gate/Middleware),
  `edges_persist`-Mutex, `append_edge_line` (+`fsync`), In-Cache-Dup-Check → 409,
  Cache-after-persist, Eingabevalidierung, Create-Tests in `api_edges.rs`.
  Default-Modus (JSONL), keine DB.
- **PR-3 — PostgreSQL Edge-Write + Proof-Ripple.** `DomainEdgeWriteSource` +
  `AppConfig`-Feld (~17 Literale), Config-Load-Hard-Fail, Write-Guard-Kombinationen,
  `NewDomainEdgeRow`/`insert_edge_from_jsonl_record` (Backfill-Symmetrie),
  `db_domain_edge_write_path.rs`, api.yml-DB-Job, **vollständiger Proof-Matrix-/
  Validator-/Workflow-/Status-Ripple** (siehe oben), neuer Proof-Bericht.

Reihenfolge ist bindend: PR-2 und PR-3 setzen den in PR-1 fixierten Feldvertrag
voraus.

## Anhang: Diese-Task-Validierung

Dieser Bericht ist diagnostisch und kein registriertes `canonical_doc`; er ändert
**keine** Proof-Matrix-, Status- oder `non_goals`-Aussage und markiert **keine**
OPT-ARC-001-Evidenz als erledigt. `edge_writes` bleibt unverändert in `non_goals`.

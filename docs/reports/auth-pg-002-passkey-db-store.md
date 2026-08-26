---
id: reports.auth-pg-002-passkey-db-store
title: "AUTH-PG-002 Passkey Credential DB-Store (Slice A) Proof"
doc_type: report
status: active
lifecycle_state: active
lifecycle: proof
owner_task: AUTH-PG-002
review_after: 2026-09-30
canonicality: evidence
created: 2026-06-30
lang: de
summary: >
  Proof-Bericht für AUTH-PG-002, Store-Slice: PostgreSQL-Migration und
  isolierter DbPasskeyStore für registrierte WebAuthn-Credentials, plus
  ignored Restart-Proof. Kein Routen-Cutover, kein Default-Wechsel: der
  In-Memory-PasskeyStore bleibt Default. Belegt ist die Persistenz-Primitive
  (Insert/List/Find/Update/Remove + Restart-Stabilität auf Store-Ebene), nicht
  der vollständige Passkey-Cutover.
relations:
  - type: relates_to
    target: docs/reports/auth-status-matrix.md
  - type: relates_to
    target: docs/reports/passkey-register-verify-prep.md
  - type: relates_to
    target: docs/adr/ADR-0007__auth-persistence-production-db-path.md
---

# AUTH-PG-002 Passkey Credential DB-Store (Slice A) Proof

## 1. Scope und Nicht-Scope

**Belegt (dieser Slice):**

- PostgreSQL-Migration `passkey_credentials` (up/down, reversibel).
- Isolierter `DbPasskeyStore` (`apps/api/src/auth/passkeys_db.rs`) mit
  `insert` / `list_for_account` / `credential_ids_for_account` /
  `find_by_credential_id` / `remove_for_account` / `update_credential`.
- Reine (DB-freie) Unit-Tests für die Persistenz-Invarianten:
  `Passkey`-JSON-Roundtrip, Stabilität/Reversibilität des
  Credential-ID-Schlüssels und Fehlerfälle beim Hex-Decode.
- Ignored Integration-Proof `apps/api/tests/db_passkey_store_persistence.rs` analog zu
  `db_session_store_persistence.rs`, plus CI-Job
  `db-passkey-persistence-proof` in `.github/workflows/api.yml`.

**Ausdrücklich NICHT belegt / Nicht-Scope dieses Slice:**

- Zum Zeitpunkt dieses Store-Slice war kein Routen-Cutover belegt:
  `register/verify`, `auth/options`, `auth/verify` und `register/options`
  nutzten weiterhin den In-Memory-`PasskeyStore`. Seit Slice B ist der
  Runtime-Cutover separat dokumentiert in
  `docs/reports/auth-pg-002-passkey-runtime-facade.md`.
- Kein Default-Wechsel: In-Memory bleibt Default (JSONL-/Single-Instance-
  kompatibel).
- Kein Production-Cutover, keine JSONL-Demontage, kein
  `webauthn_user_id`-Backfill (AUTH-PG-003 bleibt blocked).

## 2. Datenmodell

`passkey_credentials`:

| Spalte | Typ | Anmerkung |
|---|---|---|
| `credential_id` | `TEXT PRIMARY KEY` | lowercase-Hex der rohen Credential-ID-Bytes; global unique; PK ist letzte Wahrheit für Duplicate-Detection |
| `account_id` | `TEXT NOT NULL` | kein FK (siehe unten); Index `passkey_credentials_account_id` |
| `webauthn_user_id` | `UUID NOT NULL` | WebAuthn-User-Handle zur Identitätskonsistenz |
| `credential` | `JSONB NOT NULL` | `serde_json`-Form des `webauthn_rs::prelude::Passkey` |
| `created_at` / `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` | |
| `last_used_at` | `TIMESTAMPTZ` | gesetzt bei `update_credential` |

**FK-Entscheidung (bewusst, dokumentiert):** Kein `FOREIGN KEY` auf
`domain_accounts(id)`. Dies spiegelt die bestehende `sessions`-Tabelle, deren
`account_id` ebenfalls `TEXT NOT NULL` ohne FK ist, weil Accounts im
Default-Modus (`domain_read_source=jsonl`) weiterhin in JSONL liegen können. Ein
FK jetzt würde dieses Schema an eine Vorbedingung koppeln, die die Store-Ebene
allein nicht garantieren kann. Die Integritätsbedingung gehört in den späteren
opt-in PostgreSQL-Passkey-Modus (Slice B), der zusätzlich
`domain_read_source=postgres` und einen Live-Pool verlangen muss, damit die
referenzierte Account-Zeile garantiert existiert. Das ist eine **explizit
aufgeschobene Vorbedingung, keine stille Orphan-Toleranz.**

**Index-Entscheidung:** Kein Index auf `webauthn_user_id` in diesem Slice. Es
gibt noch keinen Query-Pfad, der danach selektiert; ein Index gehört in Slice B,
sobald Runtime-Facade, Identity-Abgleich, Löschung oder Backfill diesen Zugriff
wirklich benötigen.

**Serialisierung:** `Passkey` und `AuthenticationResult` sind über `serde_json`
stabil serialisierbar (durch bestehende Fixtures in `passkeys.rs` und durch die
neuen Unit-Tests belegt). Es werden keine privaten Schlüssel gespeichert;
`Passkey` ist ein serverseitiger öffentlicher Credential-Record plus
Counter/Backup-Flags. Trotzdem als private Auth-Daten behandelt (kein Rohlog,
keine öffentliche Projektion).

## 3. Sicherheitsrelevante Entscheidungen

- **Duplicate:** `INSERT ... ON CONFLICT (credential_id) DO NOTHING` +
  `rows_affected == 0` → `DuplicateCredentialId`. Die DB-Unique ist die letzte
  Wahrheit auch bei nebenläufigen Inserts.
- **Observability:** Backend- und Serialisierungsfehler werden nicht geglättet;
  `DbPasskeyStoreError` bewahrt den ursprünglichen `sqlx::Error` bzw.
  `serde_json::Error` als `#[source]`. Runtime-Logger können damit Ursache,
  SQL-State und Backendfehler sehen, ohne Credential-Rohdaten zu loggen.
- **Credential-ID-Liste:** `credential_ids_for_account` liest nur
  `credential_id` aus PostgreSQL und decodiert Hex. Die große `credential`-
  JSONB-Spalte wird dafür nicht deserialisiert.
- **Cross-Account:** `find_by_credential_id` ist global (löst nur den Owner
  auf, autorisiert nichts). `update_credential` und `remove_for_account` sind
  owner-gebunden (`account_id`-Prädikat).
- **Counter-Monotonie:** `update_credential` läuft in einer Transaktion mit
  `SELECT ... FOR UPDATE`, damit der Signatur-Counter unter Nebenläufigkeit
  nicht zurückfällt; der fortgeschriebene Counter ist restart-stabil belegt.
- **Kein stilles Glätten:** ein `None` aus `Passkey::update_credential`
  (Credential-ID-Mismatch) wird als harter Fehler (`NotFound`) gemeldet, nicht
  als „keine Änderung".

## 4. Tests — Kommandos und Ergebnis

Offline (ohne DB), Teil des Standard-`cargo test`:

```text
auth::passkeys_db::tests::passkey_survives_json_roundtrip ... ok
auth::passkeys_db::tests::credential_id_key_is_stable_and_reversible ... ok
auth::passkeys_db::tests::credential_id_key_matches_passkey_cred_id ... ok
auth::passkeys_db::tests::credential_id_from_key_round_trips_lowercase_and_uppercase_hex ... ok
auth::passkeys_db::tests::credential_id_from_key_rejects_malformed_hex ... ok
cargo test --locked -p weltgewebe-api --all-features  ->  252+ passed; 0 failed
cargo fmt --all -- --check  ->  ok
cargo clippy --locked -p weltgewebe-api --all-targets --all-features -- -D warnings  ->  ok
```

Ignored DB-Proof, lokal gegen eine Wegwerf-PostgreSQL-16 ausgeführt
(`postgres:16-alpine`, direkter Port):

```text
db_passkey_store_persists_across_reinit ... ok
db_passkey_store_rejects_duplicate_credential_id ... ok
db_passkey_store_find_and_remove_are_account_scoped ... ok
db_passkey_store_update_credential_persists_counter ... ok
db_passkey_store_credential_id_key_is_primary_key ... ok
test result: ok. 5 passed; 0 failed
```

Migration up→down→up wurde gegen dieselbe Instanz manuell als reversibel
verifiziert. Der PR-CI-Job `db passkey persistence proof (direct postgres)` ist
der maßgebliche Merge-Beleg und muss auf der aktuellen PR-Revision grün sein.

## 5. Offene Leerstellen

- **Produktions-Cutover fehlt.** `passkey_credential_source` existiert in
  Slice B, bleibt aber default `in_memory`; bewusster Runtime-Cutover ist
  weiterhin erforderlich.
- **FK-/Integritäts-Cutover fehlt.** Ein Foreign Key
  `passkey_credentials.account_id -> domain_accounts(id)` bleibt bewusst
  aufgeschoben, bis der Produktionsmodus garantiert, dass Accounts aus
  PostgreSQL gelesen werden und die referenzierte Account-Zeile existiert.
- **Menschliches Review für `credentials/`** bleibt Akzeptanzkriterium vor
  Merge (AUTH-PG-002).

## 6. Status

AUTH-PG-002 bleibt **open**. Dieser Slice liefert die Persistenz-Primitive und
einen Restart-Proof auf Store-Ebene, aber keinen Cutover. `OPT-ARC-001` bleibt
`partial`; `webauthn_credential_writeback` war dort ein Non-Goal und wird hier
nur auf Store-Ebene vorbereitet, nicht als Produktions-Cutover deklariert.

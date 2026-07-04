---
id: reports.auth-pg-002-schema-preflight-ci
title: "AUTH-PG-002-C2 Passkey-Schema-Preflight (CI, heimserverfrei)"
doc_type: report
status: active
lifecycle_state: active
lifecycle: proof
owner_task: AUTH-PG-002
review_after: 2026-09-30
canonicality: evidence
created: 2026-07-04
lang: de
summary: >
  CI-faehiger, heimserverfreier Schema-Preflight fuer die AUTH-PG-002
  Passkey-Migration: belegt Einbettung in den Produktions-Migrator,
  Registrierung in _sqlx_migrations, Tabellenform, Constraints/Indizes und
  bewusste FK-Abwesenheit gegen ein frisches PostgreSQL. Kein Runtime-Schritt,
  kein Cutover.
relations:
  - type: depends_on
    target: docs/reports/auth-pg-002-runtime-schema-readiness-heimserver-2026-07-01.md
  - type: relates_to
    target: docs/reports/auth-pg-002-controlled-preflight.md
  - type: relates_to
    target: docs/reports/auth-pg-002-cutover-plan.md
  - type: relates_to
    target: docs/reports/auth-status-matrix.md
---

# AUTH-PG-002-C2 Passkey-Schema-Preflight (CI, heimserverfrei)

## 1. Zweck

Der Heimserver-Runtime-Audit vom 2026-07-01 fand eine Runtime, in der
`_sqlx_migrations` die Migration `20260630000001_create_passkey_credentials`
nicht enthaelt und `passkey_credentials` fehlt. Der Controlled-Preflight-Report
verlangt vor jeder Runtime-Wirkung eine Review-Grenze.

Dieser Slice liefert den heimserverfreien Teil davon: Er pinnt in CI gegen ein
frisches PostgreSQL 16 exakt die Invarianten, die ein spaeterer kontrollierter
Runtime-Migrationsschritt reproduzieren muss. Er fuehrt keinen Runtime-Schritt
aus und ersetzt keinen.

## 2. Beweisgegenstand

Testdatei: `apps/api/tests/db_passkey_schema_preflight.rs`
CI-Job: `db-passkey-persistence-proof` in `.github/workflows/api.yml`
(Preflight laeuft dort vor den Verhaltens-Proofs).

| # | Invariante | Test |
|---|---|---|
| 1 | Die Passkey-Migration ist Teil des compile-time eingebetteten Produktions-Migrators (`sqlx::migrate!("./migrations")`, identisch zu `lib.rs`), als reversibles up/down-Paar — nicht nur eine Datei auf der Platte | `passkey_migration_is_embedded_in_production_migrator` (laeuft auch offline, nicht ignored) |
| 2 | Der eingebettete Migrator registriert `20260630000001` in `_sqlx_migrations` mit `success = true` — derselbe Check, den der Heimserver-Audit read-only ausfuehrt | `passkey_schema_preflight_migration_is_registered` |
| 3 | `passkey_credentials` hat exakt die vertraglichen Spalten, Typen und Nullability; `created_at`/`updated_at` behalten einen Current-Time-Default (`now()`/`CURRENT_TIMESTAMP`) | `passkey_schema_preflight_table_shape_matches_contract` |
| 4 | PRIMARY KEY ist exakt `credential_id`; `passkey_credentials_account_id` existiert als nicht-unique Sekundaerindex und ein nicht-unique Index deckt semantisch exakt `(account_id)` ab; es existiert KEIN Foreign Key (bewusste, dokumentierte Verschiebung auf den gated Cutover-Slice — ein still ergaenzter FK laesst den Preflight fehlschlagen) | `passkey_schema_preflight_constraints_and_indexes` |
| 5 | Die Datenbank selbst erzwingt NOT NULL auf `account_id`/`webauthn_user_id`/`credential` (SQLSTATE 23502) und Unique auf `credential_id` (SQLSTATE 23505), unabhaengig vom Store-Layer-Mapping | `passkey_schema_preflight_rejects_null_and_duplicate_rows` |

## 3. Grenzen (nicht bewiesen)

- Der Heimserver-Runtime-Schemastand bleibt unveraendert; die Migration ist
  dort weiterhin nicht angewendet.
- Kein kontrollierter Runtime-Migrationsschritt, kein erneuter Runtime-Audit.
- Kein Produktions-Cutover; `passkey_credential_source` bleibt Default
  `in_memory`.
- Keine FK-Migration; die FK-Entscheidung bleibt beim gated Cutover-Slice
  (siehe Cutover-Plan und Migrations-Header).
- Kein `webauthn_user_id`-Backfill/NOT-NULL (AUTH-PG-003).

## 4. Lokale Verifikation 2026-07-04

Gegen ein frisch initialisiertes lokales PostgreSQL 16
(`initdb` + `CREATE DATABASE weltgewebe`), direkt (kein PgBouncer):

```text
cargo test --locked -p weltgewebe-api --test db_passkey_schema_preflight -- --include-ignored --test-threads=1
  -> 5 passed; 0 failed
cargo test --locked -p weltgewebe-api --test db_passkey_store_persistence -- --include-ignored --test-threads=1
  -> 9 passed; 0 failed
cargo test --locked -p weltgewebe-api --test db_passkey_fk_readiness -- --include-ignored --test-threads=1
  -> 1 passed; 0 failed
```

Massgeblicher Merge-Beleg bleibt der PR-CI-Job `db-passkey-persistence-proof`
(frischer Postgres-16-Service-Container pro Lauf).

## 5. Naechster Schritt

Unveraendert AUTH-PG-002-R2 aus dem Runtime-Schema-Readiness-Report:
kontrollierte Anwendung der Migration in der Zielumgebung nach menschlicher
Freigabe (Freigabeform im Controlled-Preflight-Report), danach erneuter
read-only Runtime-Audit, erst danach FK-Readiness neu bewerten. Dieser
CI-Preflight definiert dafuer die Soll-Invarianten.

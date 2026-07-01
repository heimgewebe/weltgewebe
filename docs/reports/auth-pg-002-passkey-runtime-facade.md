---
id: reports.auth-pg-002-passkey-runtime-facade
title: "AUTH-PG-002 Passkey Runtime Facade (Slice B) Proof"
doc_type: report
status: active
lifecycle_state: active
lifecycle: proof
owner_task: AUTH-PG-002
review_after: 2026-09-30
canonicality: evidence
created: 2026-07-01
lang: de
summary: >
  Proof-Bericht für AUTH-PG-002, Slice B: explizites Config-Gate
  passkey_credential_source, Runtime-Facade zwischen In-Memory- und
  PostgreSQL-Credential-Store, Routen-Cutover für register/options,
  register/verify, auth/options und auth/verify. Kein Production-Cutover und
  kein webauthn_user_id-Backfill.
relations:
  - type: relates_to
    target: docs/reports/auth-pg-002-passkey-db-store.md
  - type: relates_to
    target: docs/reports/auth-status-matrix.md
  - type: relates_to
    target: docs/adr/ADR-0007__auth-persistence-production-db-path.md
---

# AUTH-PG-002 Passkey Runtime Facade (Slice B) Proof

## 1. Scope

Dieser Slice schaltet **nicht** global die Produktion um. Er führt eine explizite
Runtime-Auswahl für registrierte WebAuthn-/Passkey-Credentials ein:

- `passkey_credential_source: in_memory | postgres`
- Env: `WELTGEWEBE_PASSKEY_CREDENTIAL_SOURCE`
- Default: `in_memory`
- `postgres` verlangt `domain_read_source=postgres` auf Config-Ebene
- `postgres` verlangt beim Start einen verfügbaren PostgreSQL-Pool
- kein stiller Fallback zu In-Memory, wenn `postgres` explizit gewählt ist
- YAML und Environment verwenden konsistent `in_memory` / `postgres`

Kurzlebige Ceremony-Stores bleiben bewusst in-memory:

- `PasskeyRegistrationStore`
- `PasskeyAuthenticationStore`
- `PasskeyRegistrationGrantStore`

## 2. Runtime-Facade

`apps/api/src/auth/passkeys_runtime.rs` kapselt die Auswahl zwischen:

- `PasskeyStore` im Default-Modus `in_memory`
- `DbPasskeyStore` im expliziten Modus `postgres`

Die Facade bietet async-Funktionen für die langlebigen Credential-Operationen:

- `insert`
- `list_for_account`
- `credential_ids_for_account`
- `find_by_credential_id`
- `update_credential`

Datenbankfehler werden nicht in Memory-Operationen zurückgebogen. Im
PostgreSQL-Modus führt ein fehlender Pool zu `BackendUnavailable`; SQL-/Serde-
Fehler aus `DbPasskeyStore` bleiben über die `#[source]`-Kette erhalten.

## 3. Routen-Cutover

Diese Routen nutzen nun die Runtime-Facade statt direkt `state.passkeys`:

- `POST /auth/passkeys/register/options`
  - `exclude_credentials` kommt aus dem gewählten Credential-Store
- `POST /auth/passkeys/register/verify`
  - das verifizierte Credential wird vor `ok: true` im gewählten Store
    persistiert
  - Duplicate bleibt `409 CREDENTIAL_ALREADY_REGISTERED`
  - vor der Persistenz wird der Account frisch revalidiert; gelöschte,
    deaktivierte oder zwischenzeitlich geänderte Account-Bindings speichern kein
    Credential
  - Backendfehler liefern fail-closed `503 PASSKEY_CREDENTIAL_BACKEND_UNAVAILABLE`
- `POST /auth/passkeys/auth/options`
  - Credentials werden aus dem gewählten Store gelesen
  - Backendfehler erzeugen keine Ceremony und keinen Cookie
- `POST /auth/passkeys/auth/verify`
  - Credential-Auflösung und Counter-/Backup-Flag-Update laufen über den
    gewählten Store
  - Session wird erst nach erfolgreichem Credential-State-Update erstellt
  - Backendfehler führen fail-closed zu `503`, kein Cookie

## 4. Tests und Belege

Offline/Standardpfad:

```text
cargo test --locked -p weltgewebe-api config::tests::passkey_credential --all-features
-> 6 passed

cargo clippy --locked -p weltgewebe-api --all-targets --all-features -- -D warnings
-> ok

cargo test --locked -p weltgewebe-api --all-features
-> 258 passed
```

Neuer ignored DB-Proof in `apps/api/tests/db_passkey_store_persistence.rs`:

- `passkey_runtime_facade_postgres_persists_across_state_reinit`
- `passkey_auth_options_route_reads_postgres_runtime_facade`

Der Test baut zwei `ApiState`-Instanzen mit
`passkey_credential_source=postgres` über getrennten Pool-Instanzen. Ein über
die Runtime-Facade persistiertes Credential wird nach State-/Pool-Reinitialisierung
über dieselbe Facade wieder per `credential_ids_for_account` und
`find_by_credential_id` gefunden. Zusätzlich belegt der Route-Level-Test, dass
`auth/options` im Postgres-Modus ein Credential findet, obwohl der
In-Memory-`PasskeyStore` leer ist, und die Credential-ID in `allowCredentials`
zurückgibt. Damit ist belegt, dass die Runtime-Facade im Postgres-Modus nicht
heimlich den In-Memory-Store nutzt.

Lokale Ausführung des ignored DB-Tests wurde versucht, scheiterte aber an
lokaler PostgreSQL-Erreichbarkeit (`PoolTimedOut` auf `localhost:5432`). Das ist
kein Assert-Fehler des Tests. Der bestehende CI-Job `db passkey persistence proof
(direct postgres)` führt das gesamte Testfile mit `--include-ignored` gegen einen
PostgreSQL-Service aus und ist der maßgebliche Merge-Beleg.

## 5. Weiterhin offen

AUTH-PG-002 bleibt **partial**:

- kein Produktions-Cutover
- kein Foreign Key `passkey_credentials.account_id -> domain_accounts(id)`;
  dieser bleibt bis zum Integritäts-/Produktions-Cutover aufgeschoben
- kein `webauthn_user_id`-Backfill und kein späteres `NOT NULL`
- kein vollständiger Browser-/Authenticator-E2E für Register → Reload → Login
- kein Passkey-Management-UI/List/Remove-Cutover

## 6. Status

Dieser Slice beendet die Leerstelle "Runtime-Facade/Config-Gate fehlt". Er
beendet nicht die gesamte AUTH-PG-002-Aufgabe.

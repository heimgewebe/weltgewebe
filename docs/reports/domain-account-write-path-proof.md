---
id: reports.domain-account-write-path-proof
title: "Domain Account Write Path Proof"
doc_type: report
status: deprecated
lifecycle_state: archived
lifecycle: proof
owner_task: OPT-ARC-001
canonicality: evidence
created: 2026-06-04
lang: de
summary: >
  Proof-Bericht für OPT-ARC-001 Phase E-A: optionaler PostgreSQL-Schreibpfad für
  Account-Erzeugung (`POST /accounts`), das private Eigenprofil der Garnrolle
  (`GET/PATCH /accounts/me/profile`) und die Step-up-E-Mail-Aktualisierung
  (AUTH-PG-001, `UpdateEmail`-Intent). JSONL
  bleibt Default; kein Dual-Write; Knoten-, Kanten- und WebAuthn-Credential-
  Persistenz bleiben unverändert.
relations:
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
  - type: relates_to
    target: docs/reports/domain-read-path-proof.md
  - type: relates_to
    target: docs/reports/optimierungsstatus.md
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: apps/api/tests/db_domain_account_write_path.rs
  - type: relates_to
    target: .github/workflows/api.yml
---

# Domain Account Write Path Proof

> **Lifecycle-Hinweis (2026-08-24):** Archivierter Point-in-Time-Beleg.
> Die historischen Aussagen bleiben unverändert; aktuelle Statuswahrheit ist aus
> den kanonischen Status-, Architektur- und Runtimequellen abzuleiten.


> **Sicherheitsnachtrag 2026-07-18:** Die in diesem historischen Phase-E-A-Beleg
> beschriebene ID-deterministische Radiusprojektion ist durch Issue #1464 und
> Migration `20260718000001_radius_projection_privacy` abgelöst. Radiuspunkte
> stammen nun aus einer privat persistierten kryptografischen Zufallsbindung;
> Altbestände ohne gültige Bindung werden fail-closed ausgeblendet. Die übrigen
> Aussagen dieses Berichts bleiben historische Evidenz ihres damaligen Stands.

## Scope

Dieser Proof dokumentiert OPT-ARC-001 **Phase E-A** als bewusst engen,
opt-in PostgreSQL-Schreibpfad für die Account-Erzeugung (`POST /accounts`),
das private Eigenprofil (`GET/PATCH /accounts/me/profile`) sowie den unter
**AUTH-PG-001** ergänzten, über dasselbe Write-Gate laufenden
Step-up-E-Mail-Aktualisierungspfad (`UpdateEmail`-Intent beim Step-up-Consume).

Geltende Grenzen:

- JSONL bleibt Default-Schreibpfad und Default-Lesequelle.
- PostgreSQL-Account-Writes werden nur über
  `WELTGEWEBE_DOMAIN_ACCOUNT_WRITE_SOURCE=postgres` bzw.
  `domain_account_write_source: postgres` aktiviert.
- Der Account-Write-Gate ist getrennt vom Read-Gate
  (`WELTGEWEBE_DOMAIN_READ_SOURCE`). Es ist **kein** breiter
  `WELTGEWEBE_DOMAIN_WRITE_SOURCE`; alle Account-Mutationen bleiben an den
  spezifischen Account-Schreibschalter gebunden.
- PostgreSQL-Account-Write **erfordert** den PostgreSQL-Read-Source und einen
  konfigurierten Pool. Andernfalls bricht Config-Load bzw. Startup hart ab
  (kein stiller JSONL-Fallback).
- Kein Dual-Write: Im JSONL-Modus wird nie PostgreSQL beschrieben, im
  PostgreSQL-Modus wird nie JSONL angehängt.

## Nicht implementiert (bewusst außerhalb dieser Phase)

- Kein `PATCH /nodes` PostgreSQL-Write (im Postgres-Read-Modus weiterhin
  blockiert).
- Kein Edge-Write-Path.
- Kein WebAuthn-Credential-Writeback nach PostgreSQL.
- Kein Backfill und kein `NOT NULL` für bestehende Accounts mit
  `webauthn_user_id IS NULL`.
- Keine Entfernung von JSONL.
- Kein Startup-Backfill.
- Kein Produktions-Cutover. OPT-ARC-001 bleibt `partial`.

## Lifecycle

- Zweck: Belegt den OPT-ARC-001 PostgreSQL-Teilpfad für den Account-Schreibpfad `POST /accounts` im dokumentierten Scope.
- Bereitet vor: Fortlaufende OPT-ARC-001 Cutover- und Proof-Matrix-Entscheidungen.
- Gültig bis: Review am 2026-07-16 oder bis ein neuerer Proof diesen Bericht ersetzt.
- Wird abgelöst durch: Noch offen; mögliche spätere Runtime-/Cutover-Proofs oder aktualisierte Proof-Matrix-Artefakte.

## Konfiguration

| Aspekt | Wert |
|---|---|
| Config-Key | `domain_account_write_source` |
| Env-Var | `WELTGEWEBE_DOMAIN_ACCOUNT_WRITE_SOURCE` |
| Akzeptierte Werte | `jsonl`/`file`/`files`, `postgres`/`pg`/`db` |
| Default | `jsonl` |
| Leerer Env-Wert | behält Default |
| Ungültiger Wert | harter Config-Fehler (kein Fallback) |
| Harte Kopplung | `postgres` erfordert `domain_read_source=postgres` (Config-Load) **und** einen Pool (Startup) |

## Route-Verhalten

### `POST /accounts`

| Read-Source | Account-Write-Source | Verhalten |
|---|---|---|
| JSONL | JSONL | Append nach `demo.accounts.jsonl` (unverändert), dann Cache-Update |
| Postgres | JSONL | `409 CONFLICT` + `DOMAIN_READ_SOURCE_READ_ONLY` (kein Write, kein Cache-Update) |
| Postgres | Postgres | Insert nach `domain_accounts`, dann Cache-Update; **kein** JSONL-Append |
| JSONL | Postgres | Config-Load bricht hart ab; manuell konstruierte `ApiState`-Zustände werden defensiv mit `500` / `INVALID_DOMAIN_WRITE_CONFIG` blockiert |

`PATCH /nodes` bleibt im Postgres-Read-Modus unverändert blockiert
(`reject_if_postgres_read_source`).

### `GET/PATCH /accounts/me/profile`

- `GET` verlangt eine gültige Sitzung und liefert nur das private Profil des
  aktiven Accounts: Titel, Beschreibung, Kategorien, Adresse, interne
  Koordinate, `map_state` und Radius. E-Mail, Rolle und WebAuthn-Identität
  werden nie serialisiert.
- `PATCH` akzeptiert keine Account-ID und verwendet ausschließlich die
  `account_id` der Sitzung. Unbekannte Felder wie `id` oder `role` werden
  abgewiesen.
- `PATCH` ist für authentifizierte Gäste, Weber und Admin erlaubt und bleibt
  strikt auf die eigene Garnrolle begrenzt.
- Die private Adresse oder Ortsnotiz ist optional. `exact` und `radius`
  verlangen ausschließlich eine gültige vorhandene oder neu übermittelte
  Koordinate. `not_on_map` setzt Radius 0 und entfernt jede öffentliche
  Position, bewahrt die private Koordinate aber standardmäßig.
- Nicht übermittelte `address`- und `location`-Felder bleiben unverändert.
  `clear_address=true` löscht die private Adressnotiz; `clear_location=true`
  löscht die private Koordinate und ist nur zusammen mit `map_state=not_on_map`
  zulässig. Ein Löschsignal darf nicht mit einem neuen Wert desselben Feldes
  kombiniert werden.
- PostgreSQL-Modus: Transaktion und Zeilensperre, DB-Update vor Cache-Update,
  kein JSONL-Write. JSONL-Modus: Append eines vollständigen neuen Snapshots,
  danach Cache-Update. Kein Dual-Write.


## Implementierte Belege

- `apps/api/src/config.rs`: `DomainAccountWriteSource` (Default `Jsonl`),
  Env-Parsing, harte Validierung der Read/Write-Kopplung; Unit-Tests für
  Default, Aliase, ungültigen Wert, leeren Wert, Postgres+JSONL-Read-Reject und
  Postgres+Postgres-Read-Accept.
- `apps/api/src/lib.rs`: Startup-Gate — `Postgres` verlangt einen Pool, sonst
  harter Startfehler; klares Logging „account-create write source“.
- `apps/api/src/domain_db.rs`: `NewDomainAccountRow::from_jsonl_record`,
  `load_account_profile_from_postgres` und
  `update_account_profile_in_postgres` (Transaktion, Zeilensperre,
  DB-vor-Cache-Vertrag, Erhalt der operativen Identität);
  (gleiches semantisches Mapping wie der Phase-C-Backfill) und
  `insert_account_from_jsonl_record` (eine Zeile, plain `INSERT` ohne
  `ON CONFLICT`; UUID/JSONB via `::uuid`/`::jsonb`-Casts, weil der sqlx-Build
  kein `uuid`-Feature hat); `AccountWriteError::{DuplicateId, Mapping, Database}`;
  Unit-Tests für Create-Mapping, private Visibility, approximate-Radius und
  ron_flag.
- `apps/api/src/routes/domain_write_guard.rs`:
  `reject_account_create_unless_writable` (Account-Create-Gate) neben dem
  unveränderten `reject_if_postgres_read_source` (Node-Writes).
- `apps/api/src/routes/accounts.rs`: `create_account` sowie strikt auf den
  aktiven Session-Account gebundene Eigenprofil-Handler; gemeinsame
  Validierung/Record-Bau/Public-Projektion/Duplikatprüfung; Verzweigung nur am
  Persistenzschritt; Cache-Update erst nach erfolgreichem Write; DB-Insert-Fehler
  mappt `DuplicateId` → `409 CONFLICT`, sonst `500`.
- `apps/api/tests/db_domain_account_write_path.rs`: DB-gestützte
  Integrationsproofs (ignored by default).
- `.github/workflows/api.yml`: PR-CI-Job `db-domain-account-write-path-proof`
  (PostgreSQL-16-Service, direkter Port 5432, `--include-ignored --test-threads=1`).

## Spalten, die der Account-Create schreibt

`id`, `kind` (aus `type`, hier `garnrolle`), `title`, `mode` (`verortet`),
`radius_m`, `disabled` (`false`), `location_lat`/`location_lon` (private
Residenz), `role`, `email` (optional), `webauthn_user_id` (beim Account-Create
neu erzeugte UUID), `created_at`/`updated_at` (NULL — wie JSONL-Create +
Backfill),
`public_payload` (`summary`, `tags`), `private_payload` (spiegelt den
Backfill: explizites `mode`; bei Legacy-Eingaben zusätzlich `visibility`,
`suppress_public_pos`, `ron_flag`).

Neue PostgreSQL-Account-Create-Zeilen persistieren damit eine stabile
`webauthn_user_id`, die der lokale Cache unverändert übernimmt und die
`load_accounts_from_postgres` nach einem Reload wiederherstellt. Bestehende
NULL-Werte bleiben über den Legacy-Fallback unterstützt.

`public_pos` ist **keine** eigene Tabellenspalte. Bei `radius_m = 0` kann sie
exakt den eingereichten Koordinaten entsprechen. Seit dem Sicherheitsnachtrag
2026-07-18 wird sie bei Radiusdarstellung aus einer privaten, persistierten
Zufallsbindung gelesen. Weder die exakte Position noch diese Bindung werden
öffentlich serialisiert.

## Validierung

### Offline (ohne PostgreSQL)

```bash
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --locked -p weltgewebe-api --no-run
cargo test --locked -p weltgewebe-api
cargo test --locked -p weltgewebe-api --test db_domain_account_write_path --no-run
```

### Integrationsproof (direkter PostgreSQL)

```bash
DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
  cargo test --locked -p weltgewebe-api --test db_domain_account_write_path \
  -- --include-ignored --test-threads=1
```

Testfälle:

- `own_garnrolle_profile_persists_privately_and_reloads_from_postgres`:
  PATCH des eigenen Profils, private Adresse/Koordinate, Erhalt von E-Mail,
  Rolle und WebAuthn-Identität, kein JSONL-Write, Reload aus PostgreSQL sowie
  Wechsel zu `not_on_map` ohne öffentliche Projektion.
- `account_create_persists_stable_webauthn_user_id_across_reload`:
  Erfolg (201), korrekte Spalten/Payloads, Cache enthält den Account sofort,
  kein JSONL-Append; DB, Cache und `load_accounts_from_postgres` verwenden
  dieselbe parsebare `webauthn_user_id`.
- `postgres_account_create_radius_persists_private_projection`:
  Bei `radius_m>0` speichert die DB die reale Residenz, den Radius und die
  private Zufallsbindung. Die Antwort enthält nur den Punkt innerhalb des
  geodätischen Radius; Loader und mehrere Instanzen lesen dieselbe Bindung.
- `postgres_account_create_duplicate_id_conflicts_without_side_effects`:
  Primärschlüsselkollision → `409`, keine Überschreibung, kein Cache-Update,
  kein JSONL.

### Lokaler PostgreSQL-Status

DB-Suiten für lokalen PostgreSQL-Proof sind vorbereitet (`db_domain_schema_migrations`,
`db_domain_backfill`, `db_domain_read_path`, `db_domain_account_write_path`).
Der neue Eigenprofil-Test wurde lokal gegen PostgreSQL 16 ausgeführt und ist
zusätzlich durch GitHub Actions Run `29149078893`, Job
`db-domain-account-write-path-proof` (`86535506561`), auf Commit
`83eeced1f1235687f3ccc99cf4300a133b8686ef` erfolgreich gebunden.

`suppress_public_pos` wird von `POST /accounts` nicht akzeptiert; Phase E-A
erhält Datenschutz über `visibility=private` und bestehende Loader-Semantik
(siehe `NewDomainAccountRow::from_jsonl_record` in `apps/api/src/domain_db.rs`).

## AUTH-PG-001: Step-up-E-Mail-Aktualisierung

Der Step-up-`UpdateEmail`-Intent teilt sich das enge Account-Write-Gate mit
`POST /accounts` (`reject_account_email_update_unless_writable` delegiert an
`reject_account_create_unless_writable`). Es entsteht **kein** neues Config-Feld
und **kein** breiter Write-Switch — PostgreSQL-Account-Mutationen bleiben nur
erlaubt, wenn `domain_read_source` **und** `domain_account_write_source` beide
`postgres` sind.

### Ablauf (DB-vor-Cache)

Im PostgreSQL-Account-Write-Modus schreibt der `UpdateEmail`-Consume die neue
E-Mail zuerst nach `domain_accounts`; der `AccountStore`-Cache wird **erst nach**
erfolgreichem DB-Write mutiert. Dabei wird der Account nach dem asynchronen
DB-Write frisch unter dem `write()`-Lock aus dem Cache geladen, damit parallele
Cache-Mutationen nicht durch einen vor dem Await gelesenen Snapshot überschrieben
werden. DB-Fehler hinterlassen keinen abweichenden Cache-Zustand. Im JSONL-Modus
bleibt das bisherige cache-lokale Verhalten erhalten: Konfliktprüfung und
Mutation laufen unter demselben Write-Lock.

Der Cache-Konfliktcheck (`get_by_email`) bleibt als schneller Vorabpfad
erhalten; die eigentliche Race-Sicherheit liefert im Postgres-Modus die
DB-Constraint.

### Helper `update_account_email_in_postgres`

`apps/api/src/domain_db.rs` ergänzt `update_account_email_in_postgres` mit
normalisierendem `UPDATE domain_accounts SET email=$2, updated_at=now() WHERE
id=$1 RETURNING updated_at` ohne In-Memory-Mutation und ohne JSONL-Write. Der
Helper trimmt und lowercased selbst und gibt den von PostgreSQL gesetzten
`updated_at`-Zeitpunkt zurück. Fehlerklassifikation über
`AccountEmailUpdateError`:

| Bedingung | Variante | Route-Antwort |
|---|---|---|
| `rows_affected == 0` | `NotFound` | `400` `ACCOUNT_INVALID` |
| Constraint `domain_accounts_email_normalized_unique` | `DuplicateEmail` | `409` `CONFLICT` |
| Constraint `domain_accounts_email_not_empty_after_trim` bzw. Länge/Leer vorab | `InvalidEmail` | `400` `BAD_REQUEST` |
| sonstiger DB-Fehler | `Database` | `500` `INTERNAL_SERVER_ERROR` |

Fehlt im Postgres-Modus der Pool, antwortet der Consume kontrolliert mit `500`
statt still cache-only zu schreiben.

### DB-gestützte Belege (ignored by default)

- `update_account_email_helper_persists_and_classifies_duplicate`: Helper
  normalisiert und persistiert die neue E-Mail, setzt und returned `updated_at`,
  wird vom Phase-D-Loader wiederhergestellt und klassifiziert einen
  normalisierten Duplikatkonflikt als `DuplicateEmail`, ohne die bestehende
  E-Mail zu überschreiben.
- `step_up_update_email_persists_to_postgres_and_reloads`: Route-Level-Proof —
  Step-up-Consume schreibt vor der Cache-Mutation nach PostgreSQL (`204`),
  Cache und `load_accounts_from_postgres` beobachten die neue E-Mail, kein
  JSONL-Append.

## Verbleibende OPT-ARC-001-Phasen

| Phase | Inhalt | Status |
|---|---|---|
| A | Blueprint und Planung | done |
| B | PostgreSQL-Schema-Migrationen | done |
| C | Backfill-/Import-Proof | implementiert; CI-Beleg ausstehend |
| D | Read-Path-Switch (read-only, opt-in) | implementiert; CI-Beleg ausstehend |
| E-A | Account-Create-Write-Path (diese Slice) | implementiert; CI-Beleg ausstehend |
| E-B | Node-Patch-Write-Path (`PATCH /nodes`) | implementiert; CI-Beleg ausstehend |
| E-A+ | Step-up-E-Mail-Aktualisierung (AUTH-PG-001, gleiches Gate) | implementiert; CI-Beleg ausstehend |
| E (Rest) | WebAuthn-Credential-Writeback, Passkey-Cutover sowie Backfill/Audit und späteres `NOT NULL` für Legacy-NULL-Werte | offen |
| F | Runtime-Smoke und CI-Beweis | offen |
| G | JSONL-Demontage | offen |

OPT-ARC-001 bleibt `partial`. Kein Produktions-Cutover, kein `done` ohne
grünen PR-CI-Beleg.

---
id: reports.auth-pg-003-runtime-audit-heimserver-2026-07-01
title: "AUTH-PG-003 Heimserver Runtime Audit 2026-07-01"
doc_type: report
status: active
lifecycle_state: active
lifecycle: proof
owner_task: AUTH-PG-003
review_after: 2026-09-30
canonicality: evidence
created: 2026-07-01
lang: de
summary: >
  Read-only AUTH-PG-003 Runtime-Audit gegen heimserver / weltgewebe-db-1:
  domain_accounts existiert, passkey_credentials fehlt. Damit ist ein
  Backfill-Count-Audit noch nicht auswertbar; kein Backfill, kein NOT NULL.
relations:
  - type: relates_to
    target: docs/reports/auth-pg-003-backfill-readiness.md
  - type: relates_to
    target: docs/reports/auth-pg-003-runtime-audit-wg-pg-proof-2026-07-01.md
  - type: relates_to
    target: docs/reports/auth-pg-002-runtime-schema-readiness-heimserver-2026-07-01.md
  - type: relates_to
    target: docs/reports/auth-pg-002-passkey-runtime-audit-heimserver-2026-07-01.md
---

# AUTH-PG-003 Heimserver Runtime Audit 2026-07-01

## 1. Entscheidung

**These:** Nach dem Runtime-Audit-Werkzeug ist die nächste sichere Handlung ein
read-only Lauf gegen die Zielumgebung.

**Antithese:** Ein fehlendes `passkey_credentials`-Schema erlaubt keine
Backfill-Counts. Es wäre methodisch falsch, daraus „keine Credentials“ oder
`NOT NULL`-Readiness abzuleiten.

**Synthese:** Der Heimserver-Lauf ist ein negativer, aber nützlicher Beleg:
AUTH-PG-003 bleibt blocked, weil zuerst der Runtime-Schema-Stand geklärt werden
muss. Kein Backfill, kein `NOT NULL`, kein Cutover.

## 2. Ausführung

Ziel:

```text
heimserver / laufender Docker-PostgreSQL-Container weltgewebe-db-1
```

Ausführungsgrenzen:

- Query über Container-`psql`,
- `BEGIN TRANSACTION READ ONLY`,
- `ROLLBACK`,
- keine Migration,
- keine Datenmutation,
- keine Secret-Ausgabe,
- keine Roh-Account-IDs,
- keine Credential-IDs,
- keine WebAuthn-User-IDs,
- keine Credential-Payloads.

Ein erster Versuch über Container-Env-Fallback fiel auf die Datenbankrolle `root`
zurück und wurde verworfen. Der belegte Lauf nutzte den dokumentierten Container-
Datenbanknamen und gab keine Secrets aus.

## 3. Redigierte Ausgabe

```json
{
  "audit": "webauthn_user_id_backfill_runtime",
  "findings": {
    "has_backfill_scope": null,
    "has_cutover_blockers": true,
    "next_step": "fix_runtime_schema_before_backfill_audit",
    "not_null_count_ready": false,
    "schema_ready_for_audit": false
  },
  "mutation_performed": false,
  "read_only": true,
  "redaction": {
    "account_ids": "pseudonymous-sha256-prefix-12",
    "credential_ids": "not_emitted",
    "credentials": "not_emitted",
    "webauthn_user_ids": "not_emitted"
  },
  "sample_limit": 10,
  "samples": [],
  "schema": {
    "domain_accounts_exists": true,
    "passkey_credentials_exists": false
  },
  "schema_version": 1,
  "source_label": "heimserver-runtime-postgres",
  "totals": null
}
```

## 4. Interpretation

Belegt ist:

- `domain_accounts` existiert in der Heimserver-Runtime-Datenbank.
- `passkey_credentials` existiert dort nicht.
- Das AUTH-PG-003 Backfill-Audit kann deshalb keine Credential-/Mismatch-/Orphan-
  Counts liefern.
- `has_backfill_scope` bleibt `null`, nicht `false`.
- `has_cutover_blockers=true` ist hier ein Schema-/Audit-Blocker, kein Datenbefund
  über echte Credential-Orphans.

## 5. Nicht-Beweise

Dieser Lauf beweist nicht:

- dass keine Passkey-Credentials existieren,
- dass ein Backfill sicher ist,
- dass `NOT NULL` geprüft oder gesetzt werden darf,
- dass die Zielumgebung auf dem erwarteten AUTH-PG-002-Schema steht,
- dass Produktions-Cutover möglich ist.

## 6. Nächste Aktion

Vor Backfill-Regeln oder `NOT NULL` muss der Runtime-Schema-Stand korrigiert oder
zumindest entschieden werden:

1. Wie und wann wird die vorhandene Migration
   `20260630000001_create_passkey_credentials` kontrolliert angewendet?
2. Wird danach ein erneuter read-only AUTH-PG-002 Passkey-FK-Audit ausgeführt?
3. Erst danach kann AUTH-PG-003 erneut Backfill-Counts gegen die Zielumgebung
   liefern.

Kurz: Wir wollten die Patientenakte lesen. Der Aktenschrank steht da, aber das
Passkey-Fach fehlt. Diagnose: erst Schrankbau, dann Therapie.

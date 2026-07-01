---
id: reports.auth-pg-002-runtime-schema-readiness-heimserver-2026-07-01
title: "AUTH-PG-002 Heimserver Runtime Schema Readiness 2026-07-01"
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
  Read-only Runtime-Schema-Audit gegen die Heimserver-PostgreSQL-Instanz:
  _sqlx_migrations und domain_accounts existieren, aber die AUTH-PG-002
  Migration 20260630000001_create_passkey_credentials ist nicht angewendet und
  die Tabelle passkey_credentials fehlt.
relations:
  - type: relates_to
    target: docs/reports/auth-pg-002-passkey-runtime-audit-heimserver-2026-07-01.md
  - type: relates_to
    target: docs/reports/auth-pg-002-passkey-runtime-audit-plan.md
  - type: relates_to
    target: docs/reports/auth-pg-002-cutover-plan.md
  - type: relates_to
    target: docs/reports/auth-status-matrix.md
---

# AUTH-PG-002 Heimserver Runtime Schema Readiness 2026-07-01

## 1. Kontext

Der vorherige Runtime-Audit gegen die Heimserver-PostgreSQL-Instanz konnte keine
Passkey-FK-Readiness-Counts erzeugen, weil die Relation `passkey_credentials`
fehlt. Dieser R1-Slice prüft deshalb read-only den Runtime-Migrationsstand.

Ziel ist nicht, Migrationen auszuführen. Ziel ist nur, die Blockade zu lokalisieren.

## 2. Ausführung

Ziel:

```text
heimserver / laufender Docker-PostgreSQL-Container weltgewebe-db-1
```

Ausführungsgrenzen:

- read-only Query,
- `BEGIN TRANSACTION READ ONLY`,
- `ROLLBACK`,
- keine Secret-Ausgabe,
- keine Roh-Account-IDs,
- keine Credential-Daten,
- keine Migration,
- kein FK,
- kein Runtime-Cutover.

## 3. Redigierter Audit-Output

```json
{
  "schema_version": 1,
  "audit": "runtime_schema_migration_readiness_v2",
  "source_label": "heimserver-runtime-postgres",
  "read_only": true,
  "mutation_performed": false,
  "table_state": {
    "sqlx_migrations_exists": true,
    "domain_accounts_exists": true,
    "passkey_credentials_exists": false
  },
  "repo_expected_migrations": [
    "20260428000000_create_sessions",
    "20260531000001_create_domain_nodes",
    "20260531000002_create_domain_edges",
    "20260531000003_create_domain_accounts",
    "20260613000001_domain_accounts_email_normalized_unique",
    "20260630000001_create_passkey_credentials"
  ],
  "applied_migrations": [
    {
      "version": "20260428000000",
      "description": "create sessions",
      "success": true
    },
    {
      "version": "20260531000001",
      "description": "create domain nodes",
      "success": true
    },
    {
      "version": "20260531000002",
      "description": "create domain edges",
      "success": true
    },
    {
      "version": "20260531000003",
      "description": "create domain accounts",
      "success": true
    },
    {
      "version": "20260613000001",
      "description": "domain accounts email normalized unique",
      "success": true
    }
  ],
  "findings": {
    "passkey_schema_present": false,
    "passkey_migration_applied": false,
    "schema_ready_for_passkey_fk_audit": false
  }
}
```

## 4. Interpretation

Der Heimserver ist nicht auf dem AUTH-PG-002-Passkey-Schema-Stand.

Belegt ist:

- SQLx-Migrationstracking existiert.
- Die bisherigen Domain-/Session-Migrationen sind registriert.
- `domain_accounts` existiert.
- `passkey_credentials` fehlt.
- Migration `20260630000001_create_passkey_credentials` ist nicht registriert.

Damit ist der vorherige Fehler `relation "passkey_credentials" does not exist`
erklärt: Nicht die FK-Readiness ist blockiert, sondern der Runtime-Schema-Stand.

## 5. Entscheidung

Aktuell nicht tun:

- keine FK-Migration,
- kein `passkey_credential_source=postgres`,
- kein Produktions-Cutover,
- kein Passkey-Orphan-Claim gegen Runtime-Daten.

Zuerst muss entschieden werden, wie die bereits im Repo vorhandene Migration
`20260630000001_create_passkey_credentials` kontrolliert in der Runtime angewendet
und danach erneut auditiert wird.

## 6. Nächster kleinster Slice

Empfohlen:

### AUTH-PG-002-R2: Controlled runtime migration preflight

Scope:

- prüfen, wie Migrationen im Deployment normalerweise angewendet werden,
- vorhandene Runbooks/Compose/API-Startpfade auswerten,
- einen Review-before-effect Plan für genau diese Migration erstellen,
- weiterhin kein `sqlx migrate run` ohne explizite Freigabe,
- danach erneuter read-only Runtime-Audit.

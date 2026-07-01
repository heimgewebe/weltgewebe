---
id: reports.auth-pg-002-passkey-fk-readiness-audit
title: "AUTH-PG-002 Passkey Account FK Readiness Audit"
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
  Audit-Proof für die spätere FK-Entscheidung
  passkey_credentials.account_id -> domain_accounts.id: ergänzt einen
  deterministischen Orphan-Detector gegen direkten PostgreSQL und hält fest,
  dass noch keine FK-Migration und kein Produktions-Cutover erfolgen.
relations:
  - type: relates_to
    target: docs/reports/auth-pg-002-passkey-db-store.md
  - type: relates_to
    target: docs/reports/auth-pg-002-passkey-runtime-facade.md
  - type: relates_to
    target: docs/reports/auth-pg-002-cutover-plan.md
  - type: relates_to
    target: docs/reports/auth-status-matrix.md
---

# AUTH-PG-002 Passkey Account FK Readiness Audit

## 1. Scope

Dieser Slice ergänzt einen **Audit**, keine Migration.

Belegt wird: Die spätere Integritätsfrage
`passkey_credentials.account_id -> domain_accounts.id` ist mit einem
reproduzierbaren PostgreSQL-Test sichtbar prüfbar.

Nicht umgesetzt wird:

- kein Foreign Key,
- kein Daten-Backfill,
- kein Produktions-Cutover,
- keine Änderung am Runtime-Verhalten.

## 2. Hintergrund

Die Tabelle `passkey_credentials` speichert registrierte WebAuthn-Credentials
restart-stabil. Ihr Feld `account_id` ist derzeit `TEXT NOT NULL`, aber bewusst
noch ohne FK auf `domain_accounts(id)`. Der Grund ist weiterhin gültig: Ein FK
ist erst zulässig, wenn der Produktionsmodus garantiert, dass die referenzierte
Account-Zeile in PostgreSQL existiert.

Seit Store-Slice, Runtime-Facade und Browser-Route-Proof ist die technische
Credential-Persistenz belegt. Der nächste sichere Schritt ist deshalb nicht der
FK selbst, sondern ein Orphan-Audit.

## 3. Audit-Harness

Neu:

- `apps/api/tests/db_passkey_fk_readiness.rs`

Der Test `passkey_account_fk_readiness_audit_detects_orphans` läuft gegen
direktes PostgreSQL und erzeugt zwei kontrollierte Fixtures:

1. ein Credential mit passender `domain_accounts`-Zeile,
2. ein Credential mit fehlender `domain_accounts`-Zeile.

Die Audit-Query nutzt einen `LEFT JOIN` von `passkey_credentials` nach
`domain_accounts` und meldet genau die Credentials, deren `account_id` keine
Account-Zeile besitzt.

Damit ist belegt:

- gültige Account-Referenzen werden nicht fälschlich als Orphan gemeldet,
- echte Orphans werden gezählt,
- Fixture-Cleanup hinterlässt keine Audit-Reste.

## 4. CI-Einbindung

Der bestehende Job `db passkey persistence proof (direct postgres)` führt nun
zusätzlich aus:

```text
cargo test --locked -p weltgewebe-api \
  --test db_passkey_fk_readiness \
  -- --include-ignored --test-threads=1
```

Der Job bleibt bewusst im direkten PostgreSQL-Pfad. PgBouncer ist für diesen
Proof weiterhin ausgeschlossen.

## 5. Interpretation

Ein grüner Audit-Proof bedeutet nicht, dass Produktionsdaten FK-ready sind.
Er bedeutet nur:

- die Audit-Frage ist technisch ausdrückbar,
- der CI-Harness erkennt Orphans deterministisch,
- ein späterer Produktions-/Runtime-Audit kann dieselbe Semantik nutzen.

## 6. Weiterhin offen

AUTH-PG-002 bleibt **partial**.

Offen bleiben:

- repräsentativer Runtime-/Produktionsaudit gegen echte Daten,
- Entscheidung zur Behandlung bestehender Orphans,
- spätere FK-Migration,
- Produktions-Cutover auf `passkey_credential_source=postgres`,
- AUTH-PG-003 (`webauthn_user_id`-Backfill / `NOT NULL`),
- Passkey-Management-UI/List/Remove.

## 7. Nächster Schritt

Der nächste technische Schritt nach grünem CI-Audit ist ein read-only
Runtime-/Deployment-Audit, der dieselbe Orphan-Semantik gegen die tatsächlich
verwendete PostgreSQL-Instanz ausführt und nur Counts/IDs in redigierter Form
berichtet. Erst danach ist eine FK-Migration diskutierbar.

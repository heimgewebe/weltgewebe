---
id: reports.auth-pg-003-runtime-audit-wg-pg-proof-2026-07-01
title: "AUTH-PG-003 Runtime Audit Smoke: wg-pg-proof 2026-07-01"
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
  Read-only Smoke des AUTH-PG-003 Runtime-Audit-Werkzeugs gegen den lokalen
  PostgreSQL-Proof-Container wg-pg-proof. Kein Produktionsaudit, kein Backfill,
  kein NOT NULL.
relations:
  - type: relates_to
    target: docs/reports/auth-pg-003-backfill-readiness.md
  - type: relates_to
    target: docs/reports/auth-pg-002-runtime-schema-readiness-heimserver-2026-07-01.md
---

# AUTH-PG-003 Runtime Audit Smoke: wg-pg-proof 2026-07-01

## 1. Entscheidung

**These:** Das neue Runtime-Audit-Werkzeug soll fehlende Tabellen als Blocker
klassifizieren, nicht als leeres Ergebnis.

**Antithese:** Dieser Lauf ist kein Produktionsaudit. `wg-pg-proof` ist ein
lokaler Proof-Container und ersetzt weder Heimserver-Runtime noch Cutover-Daten.

**Synthese:** Der Smoke ist als Werkzeugbeleg nützlich: Das Audit läuft read-only
und gibt bei fehlender Schemaoberfläche `fix_runtime_schema_before_backfill_audit`
aus. AUTH-PG-003 bleibt blocked.

## 2. Laufgrenze

- Quelle: lokaler Container `wg-pg-proof`.
- Ausführung: Container-`psql`; der Host-`psql`-Wrapper hatte keinen installierten
  Client und wurde deshalb nicht als Belegkanal genutzt.
- Mutation: keine.
- Redaktion: keine Account-IDs, Credential-IDs, WebAuthn-User-IDs oder Credential-
  Payloads ausgegeben.

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
    "account_ids": "sha256-prefix-12",
    "credential_ids": "not_emitted",
    "credentials": "not_emitted",
    "webauthn_user_ids": "not_emitted"
  },
  "sample_limit": 5,
  "samples": [],
  "schema": {
    "domain_accounts_exists": false,
    "passkey_credentials_exists": false
  },
  "schema_version": 1,
  "source_label": "wg-pg-proof",
  "totals": null
}
```

## 4. Nicht-Beweise

Dieser Smoke beweist nicht:

- dass Produktionsdaten auditierbar vorliegen,
- dass Heimserver dieselbe Schemaoberfläche hat,
- dass ein Backfill sicher ausführbar ist,
- dass `NOT NULL` geprüft oder gesetzt werden darf,
- dass der spätere Backfill idempotent ist.

## 5. Nächste Aktion

Runtime-Audit gegen die tatsächliche Zielumgebung ausführen, sobald der sichere
Datenbankzugriff geklärt ist. Erst danach Backfill-Proof ableiten.

Kurz: Das Messgerät piept korrekt. Es hat aber noch nicht den Patienten gesehen.

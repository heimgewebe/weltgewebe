---
id: reports.auth-pg-003-backfill-readiness
title: "AUTH-PG-003 Legacy webauthn_user_id Backfill Readiness"
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
  Vorbereitender Readiness-Bericht für AUTH-PG-003: beschreibt Audit-Fragen,
  Backfill-Strategie, Nicht-Beweise und Gates für einen späteren
  webauthn_user_id-Backfill und ein mögliches NOT NULL. Kein Runtime-Cutover,
  keine Migration und kein Live-Datenbeweis.
relations:
  - type: relates_to
    target: docs/reports/auth-status-matrix.md
  - type: relates_to
    target: docs/reports/auth-pg-002-passkey-runtime-facade.md
  - type: relates_to
    target: docs/reports/auth-pg-002-cutover-plan.md
  - type: relates_to
    target: docs/reports/opt-arc-001-db-proof-matrix.json
---

# AUTH-PG-003 Legacy webauthn_user_id Backfill Readiness

## 1. Entscheidung

AUTH-PG-003 bleibt **blocked**, aber die nächste sichere Vorarbeit ist klar:
Vor einem `NOT NULL` auf `domain_accounts.webauthn_user_id` braucht es zuerst
Audit, deterministische Backfill-Regeln und einen wiederholbaren Proof.

**These:** Nach AUTH-PG-002 Store/Runtime-Facade liegt genug Architektur vor, um
AUTH-PG-003 vorzubereiten.

**Antithese:** Ein tatsächlicher Backfill vor Produktions-Cutover oder ohne
repräsentative Datenquelle wäre methodisch falsch: fehlende UUIDs könnten
still neu erzeugt werden und bestehende Passkey-Identitäten entkoppeln.

**Synthese:** Dieses Dokument verankert nur Readiness-Gates. Es erlaubt keinen
`NOT NULL`, keinen FK-Cutover und keinen Produktions-Backfill.

## 2. Belegter Ausgangspunkt

- AUTH-PG-002 Store/Runtime-Facade ist vorhanden und dokumentiert.
- `webauthn_user_id` ist als Account-Feld vorhanden.
- Der Cutover-Plan fordert Register→Reload→Login-Proof und trennt Store-/Runtime-
  Belege von Produktions-Cutover.
- OPT-ARC-001 führt `legacy_webauthn_user_id_backfill` und
  `webauthn_user_id_not_null` ausdrücklich als Non-Goals.

## 3. Was fehlt

- Live- oder Fixture-Audit: Wie viele Accounts haben `webauthn_user_id IS NULL`?
- Nachweis, ob solche Accounts bereits Passkey-Credentials besitzen.
- Backfill-Test gegen eine repräsentative PostgreSQL-Datenbasis.
- Regel, wann ein Account ohne Passkey überhaupt eine UUID erhalten darf.
- Rollback-Grenze: ab wann darf eine einmal gesetzte WebAuthn-User-ID nicht mehr
  automatisch verändert werden?

Kurz: **NULL-Audit fehlt, nötig für Backfill-Scope.**
**Backfill-Test fehlt, nötig für NOT-NULL-Entscheidung.**
**Register→Reload→Login-E2E fehlt, nötig für Produktions-Cutover.**

## 4. Backfill-Regelvorschlag

Ein späterer Backfill darf nur eine dieser Quellen nutzen:

1. Bereits persistierte `domain_accounts.webauthn_user_id`.
2. Eindeutig account-gebundene Passkey-Credentials mit konsistenter
   `webauthn_user_id`.
3. Für Accounts ohne Credentials: explizite, getestete Neuzuweisung nur, wenn
   dokumentiert ist, dass keine bestehende WebAuthn-Identität verloren gehen kann.

Nicht zulässig:

- stille UUID-Neuerzeugung bei jedem Reload,
- unterschiedliche UUIDs je Prozessstart,
- `NOT NULL` vor Audit und Backfill-Proof,
- FK-/Credential-Cutover ohne Account-Referenzprüfung.

## 5. Minimaler Proof-Schnitt

Ein späterer Implementierungs-PR sollte zunächst nur diese Belege liefern:

- Audit-Helfer für `domain_accounts.webauthn_user_id IS NULL`.
- Fixture mit drei Klassen:
  - Account mit UUID,
  - Account ohne UUID und ohne Credential,
  - Account ohne UUID, aber mit eindeutig account-gebundenem Credential.
- Backfill-Test, der UUIDs deterministisch und idempotent setzt.
- Negativtest: widersprüchliche Credential-UUIDs blockieren fail-closed.
- Report-Update mit Zählergebnis und Nicht-Beweisen.

## 6. Umgesetzter Audit-Proof

AUTH-PG-003-AUDIT-001 ergaenzt einen read-only Audit-Helfer und einen ignored DB-Proof. Der Proof zaehlt Account-, Credential-, Orphan-, Multi-UUID- und Mismatch-Faelle, mutiert aber keine Daten und bleibt kein Backfill.

## 7. Nicht-Beweise

Dieser Bericht beweist nicht:

- dass Produktionsdaten auditierbar vorliegen,
- dass ein Backfill bereits sicher ausführbar ist,
- dass `NOT NULL` gesetzt werden darf,
- dass Passkey-Login nach Prozess-Restart im Browser vollständig funktioniert,
- dass `passkey_credentials.account_id -> domain_accounts(id)` schon als FK
  aktiviert werden kann.

## 8. Nächste Aktion

`AUTH-PG-003-AUDIT-001` ist als read-only Audit- und Fixture-Proof vorbereitet.
Nächster PR-Schnitt: Backfill-Regeln aus Audit-Zählern ableiten; danach erst Backfill-Migration und `NOT NULL` prüfen.

Humorlos gesagt: Erst zählen, dann füllen, dann verriegeln. Wer zuerst verriegelt,
baut ein Museum für ausgesperrte Nutzer.

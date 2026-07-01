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

AUTH-PG-003-AUDIT-001 ergänzt einen read-only Audit-Helfer und einen ignored DB-Proof. Der Audit-Helfer zählt Account-, Credential-, Orphan-, Multi-UUID- und Mismatch-Fälle, mutiert aber keine Daten und bleibt kein Backfill.

Der ignored DB-Proof selbst ist fixture-mutierend: Er führt Migrationen aus und legt Testzeilen mit dem Prefix `auth-pg-003-audit-proof` in `domain_accounts` und `passkey_credentials` an, bevor er sie wieder löscht. Er darf nur gegen eine disposable direkte PostgreSQL-Testdatenbank laufen und verlangt zusätzlich `AUTH_PG_003_FIXTURE_MUTATION=1`.

Die Zähler sind nicht zwingend disjunkt; Multi-UUID-Fälle können zusätzlich als Account-/Credential-UUID-Mismatch erscheinen. Der Audit beweist auch keine Race-Freiheit während eines späteren Backfills.

## 7. Runtime-Audit-Werkzeug

AUTH-PG-003-AUDIT-002 ergänzt ein read-only Runtime-Audit-Werkzeug:

```bash
python3 -m scripts.docmeta.audit_webauthn_user_id_backfill_runtime \
  --database-url-env DATABASE_URL \
  --source-label runtime-postgres \
  --pretty
```

Das Werkzeug benötigt lokal verfügbare PostgreSQL-Client-Tools (`psql`); ohne
einen echten Client bricht es fail-closed ab, statt ein Pseudo-Audit auszugeben.
Ohne expliziten `connect_timeout` setzt es `PGCONNECT_TIMEOUT=5`; `--sample-limit`
ist auf 0 bis 100 begrenzt.

Das Werkzeug läuft in `BEGIN TRANSACTION READ ONLY`, gibt keine Account-IDs,
Credential-IDs, WebAuthn-User-IDs oder Credential-Payloads aus und hasht
Account-Samples als `account:sha256:<12>`. Diese Samples sind pseudonymisiert,
nicht anonymisiert; externe Reports sollten bei unklarem Empfängerkreis mit
`--sample-limit 0` erzeugt werden. Vor der eigentlichen Zählung prüft es
`domain_accounts` und `passkey_credentials` per `to_regclass`; fehlende Tabellen
werden als Audit-Blocker ausgegeben, nicht als leerer Audit.

Die Runtime-Ausgabe klassifiziert vier nächste Schritte:

- `fix_runtime_schema_before_backfill_audit`: benötigte Tabellen fehlen.
- `review_identity_blockers_before_backfill`: Orphan-, Multi-UUID-,
  NULL-Credential- oder Mismatch-Fälle blockieren einen mechanischen Backfill.
- `prepare_idempotent_backfill_proof`: keine Blocker, aber NULL-Scope vorhanden.
- `counts_ready_for_not_null_review`: keine NULLs und keine Count-Blocker; das
  ist nur Count-Readiness, kein automatisches `NOT NULL`.

AUTH-PG-003-AUDIT-002 mutiert keine Daten und enthält weiterhin keinen Backfill.

## 8. Nicht-Beweise

Dieser Bericht beweist nicht:

- dass Produktionsdaten auditierbar vorliegen,
- dass ein Backfill bereits sicher ausführbar ist,
- dass `NOT NULL` gesetzt werden darf,
- dass Passkey-Login nach Prozess-Restart im Browser vollständig funktioniert,
- dass `passkey_credentials.account_id -> domain_accounts(id)` schon als FK
  aktiviert werden kann.

## 9. Nächste Aktion

`AUTH-PG-003-AUDIT-001` ist als read-only Audit-Helfer und explizit fixture-mutierender Scratch-DB-Proof vorbereitet.
`AUTH-PG-003-AUDIT-002` ist als read-only Runtime-Audit-Werkzeug vorbereitet.
Nächster PR-Schnitt: Runtime-Audit gegen die Zielumgebung ausführen und daraus erst den idempotenten Backfill-Proof ableiten; danach erst Backfill-Migration und `NOT NULL` prüfen.

Humorlos gesagt: Erst zählen, dann füllen, dann verriegeln. Wer zuerst verriegelt,
baut ein Museum für ausgesperrte Nutzer.

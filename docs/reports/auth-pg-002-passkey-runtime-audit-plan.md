---
id: reports.auth-pg-002-passkey-runtime-audit-plan
title: "AUTH-PG-002 Passkey Runtime FK Audit Plan"
doc_type: report
status: active
lifecycle_state: active
lifecycle: planning
owner_task: AUTH-PG-002
review_after: 2026-09-30
canonicality: evidence
created: 2026-07-01
lang: de
summary: >
  Plan und Werkzeugnachweis für einen read-only Runtime-/Deployment-Audit der
  Passkey-FK-Readiness gegen eine konkrete PostgreSQL-Instanz. Der Audit gibt
  nur Counts und gehashte Account-ID-Samples aus und verändert keine Daten.
relations:
  - type: relates_to
    target: docs/reports/auth-pg-002-passkey-fk-readiness-audit.md
  - type: relates_to
    target: docs/reports/auth-pg-002-cutover-plan.md
  - type: relates_to
    target: docs/reports/auth-status-matrix.md
---

# AUTH-PG-002 Passkey Runtime FK Audit Plan

## 1. Zweck

Der CI-FK-Readiness-Audit aus `apps/api/tests/db_passkey_fk_readiness.rs`
beweist die Orphan-Semantik an kontrollierten Fixtures. Dieser Slice ergänzt den
nächsten Schritt: ein read-only Werkzeug für echte Runtime-/Deployment-Daten.

Es beantwortet:

> Wie viele `passkey_credentials` zeigen auf keine vorhandene
> `domain_accounts`-Zeile?

## 2. Werkzeug

Neu:

```text
scripts/docmeta/audit_passkey_fk_runtime.py
```

Beispiel:

```bash
DATABASE_URL='postgres://…direct-5432…' \
  python3 -m scripts.docmeta.audit_passkey_fk_runtime \
    --source-label production-candidate \
    --sample-limit 10 \
    --pretty
```

Das Werkzeug nutzt `psql`, startet eine `BEGIN TRANSACTION READ ONLY`-Transaktion
und beendet sie mit `ROLLBACK`.

## 3. Redaktion

Der Audit gibt keine Credential-Daten und keine rohen Account-IDs aus.

Ausgabeoberfläche:

- globale Counts,
- `orphan_credentials_total`,
- `orphan_account_ids_total`,
- maximal `sample_limit` gehashte Account-ID-Samples,
- `fk_ready_by_count` als rein numerische Vorprüfung.

Hashformat:

```text
account:sha256:<12 hex chars>
```

Das reicht zum Wiedererkennen innerhalb eines Audits, ohne Account-IDs offen zu
legen.

## 4. Grenzen

Ein grünes Ergebnis bedeutet nicht automatisch Produktionsfreigabe. Es bedeutet
nur:

- In der geprüften Datenbank wurden keine Orphans nach dieser Query gefunden,
  oder Orphans wurden redigiert sichtbar gemacht.
- Die Query ist read-only.
- Keine FK-Migration wurde ausgeführt.
- Kein Runtime-Config-Cutover wurde ausgeführt.

## 5. Tests

Neu:

```text
scripts/docmeta/tests/test_audit_passkey_fk_runtime.py
```

Die Tests prüfen ohne Datenbank:

- stabile Account-ID-Hashredaktion,
- keine Roh-IDs in JSON-Ausgabe,
- `fk_ready_by_count`-Semantik,
- SQL ist read-only und enthält keine Mutationsstatements,
- `DATABASE_URL` wird in `PG*`-Umgebung zerlegt und ambient `PG*` wird entfernt,
- stderr-Sanitizing redigiert URL, Host, User, Passwort und PG-Passwort.

## 6. Noch offen

Der tatsächliche Runtime-Audit-Lauf gegen eine konkrete Instanz bleibt ein
Operator-Schritt, weil er eine echte `DATABASE_URL` benötigt. Der Output darf als
separater Report eingecheckt werden, aber nur mit redigierter Ausgabe und ohne
Credential- oder Roh-Account-Daten.

AUTH-PG-002 bleibt bis dahin **partial**.

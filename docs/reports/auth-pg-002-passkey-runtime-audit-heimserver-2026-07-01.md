---
id: reports.auth-pg-002-passkey-runtime-audit-heimserver-2026-07-01
title: "AUTH-PG-002 Heimserver Passkey Runtime Audit 2026-07-01"
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
  Redigierter Runtime-Audit-Befund gegen die Heimserver-PostgreSQL-Instanz:
  Der read-only Passkey-FK-Audit konnte keine Counts liefern, weil die Tabelle
  passkey_credentials in der laufenden Runtime-Datenbank nicht existiert.
relations:
  - type: relates_to
    target: docs/reports/auth-pg-002-passkey-runtime-audit-plan.md
  - type: relates_to
    target: docs/reports/auth-pg-002-passkey-fk-readiness-audit.md
  - type: relates_to
    target: docs/reports/auth-pg-002-cutover-plan.md
  - type: relates_to
    target: docs/reports/auth-status-matrix.md
---

# AUTH-PG-002 Heimserver Passkey Runtime Audit 2026-07-01

## 1. Kontext

Nach Store-Slice, Runtime-Facade, Browser-Route-Proof, CI-FK-Readiness-Audit
und Runtime-Audit-Werkzeug wurde ein erster read-only Audit gegen die tatsächlich
laufende Heimserver-PostgreSQL-Instanz versucht.

Ziel war die Frage:

```text
passkey_credentials.account_id -> domain_accounts.id
```

Also: Gibt es in echten Runtime-Daten Passkey-Credentials, deren `account_id`
keine passende Account-Zeile besitzt?

## 2. Ausführung

Ziel:

```text
heimserver / laufender Docker-PostgreSQL-Container weltgewebe-db-1
```

Ausführungsprinzip:

- keine `DATABASE_URL` im Chat,
- keine Credential-Daten im Output,
- Query mit `BEGIN TRANSACTION READ ONLY`,
- Ausgabe nur redigierte Counts oder redigierte Fehlermeldung,
- keine Mutation.

Der erste Host-Lauf zeigte außerdem:

```text
psql: command not found
```

Daher wurde der Audit anschließend im laufenden PostgreSQL-Container ausgeführt.

## 3. Ergebnis

Der Audit konnte keine FK-Readiness-Counts erzeugen, weil die Tabelle in der
Runtime-Datenbank fehlt:

```text
ERROR: relation "passkey_credentials" does not exist
```

## 4. Interpretation

Dieser Befund bedeutet nicht, dass es keine Orphans gibt. Er bedeutet:

- Die produktive/laufende Heimserver-PostgreSQL-Instanz besitzt zum Auditzeitpunkt
  keine Tabelle `passkey_credentials`.
- Damit ist die Runtime nicht auf dem Schema-Stand der AUTH-PG-002
  Store-Migration.
- Ein FK-Audit über `passkey_credentials.account_id -> domain_accounts.id` ist
  gegen diese Runtime-Datenbank noch nicht auswertbar.
- Eine FK-Migration ist nicht diskutierbar, bevor die Tabelle vorhanden ist und
  ein erneuter read-only Audit Counts liefert.

## 5. Sicherheitsgrenze

Der Lauf hat keine Secret-Werte und keine Roh-Account-IDs ausgegeben. Die einzige
nicht-redigierte Datenbankinformation im Report ist der Tabellenname
`passkey_credentials`, weil genau diese Relation fehlt und der Tabellenname Teil
des Schemas ist.

## 6. Statusentscheidung

AUTH-PG-002 bleibt **partial**.

Die nächste Frage ist jetzt nicht FK-Migration, sondern Runtime-Schema-Readiness:

1. Klären, ob die Heimserver-Deployments regulär Migrationen anwenden.
2. Klären, ob der laufende PostgreSQL-Container die erwartete Datenbank für die
   API ist.
3. Erst nach vorhandener Tabelle `passkey_credentials` den Runtime-Audit erneut
   ausführen.

## 7. Nächster kleinster Slice

Empfohlen:

**AUTH-PG-002-R1: Runtime schema migration readiness**

Scope:

- read-only prüfen, welche SQLx-Migrationen in der Runtime-Datenbank angewendet
  sind,
- redigierten Report erzeugen,
- kein `sqlx migrate run`,
- keine FK-Migration,
- kein Produktions-Cutover.

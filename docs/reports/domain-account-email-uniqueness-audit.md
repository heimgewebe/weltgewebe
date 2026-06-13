---
id: reports.domain-account-email-uniqueness-audit
title: Domain Account E-Mail Uniqueness Audit
doc_type: report
status: draft
lang: de
canonicality: supporting
relations:
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
  - type: relates_to
    target: apps/api/src/auth/accounts.rs
  - type: relates_to
    target: apps/api/src/routes/accounts.rs
  - type: relates_to
    target: scripts/docmeta/audit_account_email_uniqueness.py
summary: >
  Audit- und Policy-Report zur Vorbereitung einer späteren PostgreSQL-
  E-Mail-Eindeutigkeitsregel für Domain-Accounts ohne Runtime-Code,
  Migration oder Unique-Index in diesem PR.
---

# Domain Account E-Mail Uniqueness Audit

## Ziel

Vorbereitung eines Unique-Index auf Account-E-Mails in PostgreSQL durch reproduzierbares Auditieren von vorhandenen JSONL-Daten. Ziel ist es, das aktuelle Runtime-Verhalten zu dokumentieren und Normalisierungsfragen zu klären, bevor ein Constraint Daten-Integrität bricht. Dieser Report führt noch keine DB-Migration und keinen Unique-Index ein.

## Belegter Ist-Zustand

- Der aktuelle `AccountStore` verbietet Duplikate nicht hart, sondern wählt beim Neu-Einlesen deterministisch die kleinste lexikographische Account-ID als Owner aus.
- Dieses Verhalten wurde durch eine Code-Prüfung in `apps/api/src/auth/accounts.rs` (insbesondere `rebuild_email_index`) belegt.
- Das Account-Create-Routing (`apps/api/src/routes/accounts.rs`) trimmt E-Mail-Strings und verwirft leere E-Mail-Inputs (`filter(|s| !s.is_empty())`).

## Aktuelle Runtime-Semantik

- Der Index-Schlüssel wird momentan ohne `.trim()` gebildet, lediglich durch ASCII-Lowercase-Konvertierung: `email.to_ascii_lowercase()`.
- Die Runtime lädt nur String-IDs. Account-Records mit ungültigen (z.B. Integer) IDs werden vom Audit als Fehler (`non_string_id`) markiert und in keine Gruppen aufgenommen, da das PostgreSQL-Mapping nicht-leere String-IDs verlangt.
- Die "Current-Runtime"-Gruppierung erfasst alle rohen E-Mail-Strings, einschließlich leerer (`""`) oder aus Whitespace bestehender (`"   "`) E-Mails.
- Die "Proposed-Constraint"-Gruppierung ignoriert E-Mails, die nach dem Trimmen leer sind (`empty_after_trim`).
- Bei Duplikaten (auch Bulk-Load) gewinnt die lexikographisch kleinste Account-ID.
- Das Audit-Skript implementiert als Grenze einen distinct-ID-Minimalfix: Es meldet nur dann Duplikat-Konflikte, wenn mehr als eine eindeutige Account-ID beteiligt ist.
- Das ist als Übergangsverhalten akzeptabel, aber nicht als DB-Cutover-Invariante geeignet.
- API-Create verhält sich jedoch so: `trim` + `empty` => keine E-Mail (wird nicht gespeichert).

## Audit-Schlüssel

- **raw_email**: Der gespeicherte oder gelesene Originalwert aus der JSONL.
- **current_runtime_key**: Der Schlüssel, der dem aktuellen AccountStore-Verhalten entspricht (ASCII-lowercase ohne zusätzliche Normalisierung oder Trim).
- **proposed_constraint_key**: Der Schlüssel, der für einen späteren DB-Unique-Index empfohlen wird (getrimmt, nicht-leer, ASCII-lowercase).

## Vorgeschlagene Normalisierungs-Policy

1. **Trim-Verhalten**: API-Create behält die Logik `trim + empty => keine E-Mail` bei.
2. **Index-Key**: Persistierte nicht-leere E-Mails werden für spätere Eindeutigkeit ASCII-lowercase verglichen.
3. **Datenbank-Constraint**: Für den späteren DB-Index ist `lower(email)` nur dann ausreichend, wenn gespeicherte Legacy-Werte bereits getrimmt sind. Falls Legacy-Whitespace möglich ist, muss vor E2 entweder die Datenbank bereinigt werden, oder der Index muss als `lower(btrim(email))` mit passender Policy definiert werden.
4. **Fehlende Werte**: Für die vorgeschlagene spätere Constraint-Policy werden E-Mails ignoriert, die nach dem Trimmen leer sind. Die Current-Runtime-Gruppierung bleibt davon unberührt und erfasst rohe String-E-Mails inklusive leerer und Whitespace-Werte.

## Konfliktklassen

Das Skript `scripts/docmeta/audit_account_email_uniqueness.py` unterscheidet folgende Klassifikationen für E-Mail-Prüfungen:

- `missing_email`
- `null_email`
- `empty_after_trim`
- `valid_email`
- `duplicate_current_runtime_key`
- `duplicate_proposed_constraint_key`
- `trim_changes_value`
- `case_changes_value`
- `invalid_json`
- `non_object_json`
- `missing_id`
- `non_string_id`
- `non_string_email`

## JSONL-Audit

Das Audit-Skript ermöglicht einen deterministischen Report über JSONL-Quellen:

```bash
python3 -m scripts.docmeta.audit_account_email_uniqueness \
  --accounts-jsonl <path> \
  --format json
```

Das Skript gibt Exit-Code 0 zurück, außer wenn `--fail-on-duplicates` verwendet wird und Duplikate bezüglich des vorgeschlagenen Schlüssels (`proposed_constraint_key`) vorliegen.

(Audit-Harness vorhanden; Produktions-/Runtime-Datenlauf ausstehend.)

> [!NOTE]
> Das Skript streamt JSONL-Rohzeilen und vermeidet eine vollständige Rohdatenliste. Für exakte Duplikaterkennung hält es jedoch Schlüsselzustand im Speicher. Bei sehr großen Produktions-Dumps kann ein späterer Two-Pass- oder SQLite-basierter Audit sinnvoll sein.
>
> Produktionsläufe dürfen nicht unredigiert in PRs, Issues oder Reports kopiert werden. Für Produktionsdaten sind nur aggregierte Counts, Hashes oder redigierte Beispiele zulässig.

## PostgreSQL-Audit-SQL

Aktuelle Runtime-Annäherung:

> [!NOTE]
> PostgreSQL lower(...) ist für Nicht-ASCII-Zeichen nicht identisch mit der
> aktuellen Rust-Semantik to_ascii_lowercase(). Die SQL-Queries sind daher
> Audit-Annäherungen, keine finale Constraint-Definition.

```sql
SELECT
  lower(email) AS email_key,
  count(*) AS count,
  array_agg(id ORDER BY id) AS ids
FROM domain_accounts
WHERE email IS NOT NULL
GROUP BY lower(email)
HAVING count(*) > 1
ORDER BY email_key;
```

Trim-orientierte mögliche Constraint-Policy:

> [!NOTE]
> Auch `trim(email)` bzw. `btrim(email)` ist nur eine SQL-Annäherung an die API-/Audit-Trim-Semantik in Rust. Vor PR E2 muss geprüft werden, ob Legacy-Daten nur einfache ASCII-Leerzeichen oder weitere Whitespace-Zeichen enthalten.

```sql
SELECT
  lower(btrim(email)) AS email_key,
  count(*) AS count,
  array_agg(id ORDER BY id) AS ids
FROM domain_accounts
WHERE email IS NOT NULL
  AND btrim(email) <> ''
GROUP BY lower(btrim(email))
HAVING count(*) > 1
ORDER BY email_key;
```

Zusätzliche Datenqualitäts-Prüfungen:

```sql
SELECT
  count(*) FILTER (WHERE email IS NULL) AS null_email_count,
  count(*) FILTER (WHERE email IS NOT NULL AND btrim(email) = '') AS empty_email_count,
  count(*) FILTER (WHERE email IS NOT NULL AND email <> btrim(email)) AS whitespace_changed_count
FROM domain_accounts;
```

## Ergebnis dieses PRs

- Ein reproduzierbares Audit-Paket ist vorhanden.
- Das aktuelle E-Mail-Runtime-Verhalten ist dokumentiert und auf Grundlage von Code-Prüfung belegt.
- Konfliktklassen sind definiert.
- Die Normalisierungs-Policy ist als Entscheidungsvorlage dokumentiert und vor PR E2 final zu bestätigen.
- PostgreSQL-Queries für das DB-Audit sind vorbereitet.

## Nicht-Ziele

- Keine DB-Migration.
- Kein Unique-Index eingeführt.
- Kein Runtime-Code angefasst (`apps/api/src/**`, `apps/api/migrations/**`, `contracts/**`, `configs/**` sind unberührt).
- Kein API-Error-Mapping verändert.
- Kein Step-up-E-Mail-Fix.
- Kein WebAuthn-Credential-Writeback.
- Kein PostgreSQL-Cutover-Claim.
- Keine JSONL-Demontage.

## Audit-Lauf 2026-06-13

### Quellen

- JSONL: `.gewebe/in/demo.accounts.jsonl` (generiertes Demo-Daten-Set aus `scripts/dev/generate-demo-data.sh`; kein produktiver Datenbestand)
- PostgreSQL: übersprungen — `DATABASE_URL` nicht gesetzt in dieser Ausführungsumgebung
- Source-Fingerprint:
  - JSONL sha256: `2ceaac9bfbf54aab891b96402fdc6915b7d5f5670bbe74f9ce6cfbc50b80c1b6`
  - JSONL size\_bytes: 303
  - PostgreSQL target: nicht ausgeführt

### Aggregierte Ergebnisse

| Metrik | Wert |
| --- | ---: |
| records\_total | 1 |
| records\_with\_email | 0 |
| records\_missing\_email | 1 |
| records\_null\_email | 0 |
| records\_empty\_after\_trim | 0 |
| records\_non\_string\_email | 0 |
| records\_trim\_changes\_value | 0 |
| records\_case\_changes\_value | 0 |
| duplicate\_current\_runtime\_key\_groups | 0 |
| duplicate\_proposed\_constraint\_key\_groups | 0 |

### PostgreSQL-Aggregate

| Metrik | Wert |
| --- | ---: |
| lower(email) duplicate groups | n/a — nicht ausgeführt |
| lower(btrim(email)) duplicate groups | n/a — nicht ausgeführt |
| null\_email\_count | n/a — nicht ausgeführt |
| empty\_email\_count | n/a — nicht ausgeführt |
| whitespace\_changed\_count | n/a — nicht ausgeführt |

### Redaktionsregel

Dieser Report enthält keine echten E-Mail-Adressen, keine unredigierten Account-Zeilen und keine produktionsnahen Rohdaten. Die Datenquelle ist ein generiertes Demo-Daten-Set ohne personenbezogene Daten.

### Policy-Einschätzung

Das ausgeführte Demo-Daten-Set enthält kein `email`-Feld (alle 1 Records: `missing_email`). Der Audit-Harness funktioniert korrekt und liefert deterministische Ergebnisse; Exit-Code 0 bei `--fail-on-duplicates` bestätigt, dass keine Duplikate bezüglich des vorgeschlagenen Constraint-Schlüssels vorliegen.

Da keine produktiven JSONL-Daten und keine `DATABASE_URL` in dieser Ausführungsumgebung verfügbar sind, kann die endgültige Constraint-Policy noch nicht festgelegt werden:

- `duplicate_proposed_constraint_key_groups = 0` gilt nur für das Demo-Daten-Set; keine aussagekräftige Duplikat-Prüfung gegen Produktionsdaten möglich.
- Kein `whitespace_changed_count`-Wert aus PostgreSQL verfügbar.
- Kein produktiver JSONL-Datenbestand auditiert.

TODO 2 bleibt daher blockiert bis ein echter Datenlauf gegen Runtime-/Deployment-Daten möglich ist.

### Entscheidung für nächsten Schritt

Status: `needs_real_data_run`

Begründung:

- Demo-Daten-Audit: Harness validiert — Skript startet, verarbeitet JSONL korrekt, Exit-Code 0 bei `--fail-on-duplicates`.
- Kein produktiver JSONL-Account-Datenbestand im Repo oder in dieser Ausführungsumgebung verfügbar.
- `DATABASE_URL` nicht gesetzt; PostgreSQL-Audit nicht durchführbar.
- Für TODO 2 (Unique-Index) wird ein Datenlauf gegen Deployment-Daten benötigt; der vorliegende Harness ist dafür einsatzbereit.

## Nächster PR

PR E2 kann erst nach einem echten Datenlauf gegen relevante JSONL- und/oder
PostgreSQL-Daten entscheiden, ob der spätere Constraint auf lower(email),
lower(trim(email)), physisch bereinigten Daten oder einer anderen expliziten
Policy beruhen soll.

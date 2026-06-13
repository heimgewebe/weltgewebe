---
id: reports.domain-account-email-uniqueness-audit
title: Domain Account E-Mail Uniqueness Audit
doc_type: report
status: draft
lang: de
canonicality: supporting
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
- Bei Duplikaten (auch Bulk-Load) gewinnt die lexikographisch kleinste Account-ID.
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
4. **Fehlende Werte**: E-Mails, die nach dem Trimmen leer sind, oder als `null` / abwesend in JSONL stehen, werden ignoriert und unterliegen nicht der Eindeutigkeitsprüfung.

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
- `missing_id`

## JSONL-Audit

Das Audit-Skript ermöglicht einen deterministischen Report über JSONL-Quellen:

```bash
python3 -m scripts.docmeta.audit_account_email_uniqueness \
  --accounts-jsonl <path> \
  --format json
```

Das Skript gibt Exit-Code 0 zurück, außer wenn `--fail-on-duplicates` verwendet wird und Duplikate bezüglich des vorgeschlagenen Schlüssels (`proposed_constraint_key`) vorliegen.

(Audit-Harness vorhanden; Produktions-/Runtime-Datenlauf ausstehend.)

## PostgreSQL-Audit-SQL

Aktuelle Runtime-Annäherung:

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
- Konfliktklassen und eine Normalisierungs-Policy wurden definiert.
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

## Nächster PR

PR E2 (falls das Audit keine Blockaden ergibt): Umsetzung des Unique-Constraints in PostgreSQL basierend auf den Entscheidungen dieser Normalisierungs-Policy.

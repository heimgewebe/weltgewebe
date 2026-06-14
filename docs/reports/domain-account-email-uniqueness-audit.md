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

## Runtime-Audit-Lauf 2026-06-13

### Runtime-Quellen

- PostgreSQL: ausgeführt auf dem Heimserver im Docker-Compose-Projekt `weltgewebe`, Service `db`, Tabelle `public.domain_accounts`.
- JSONL: keine Runtime-JSONL-Quelle auditiert; repo-lokal wurde nur `.gewebe/in/demo.accounts.jsonl` als `demo_or_fixture` gefunden.
- Source-Fingerprint:
  - PostgreSQL target: `weltgewebe` Compose-Projekt, Service `db`; konkrete Datenbank-URL nicht dokumentiert.
  - JSONL runtime source: n/a.

### Runtime-PostgreSQL-Aggregate

| Metrik | Wert |
| --- | ---: |
| `domain_accounts` exists | ja |
| lower(email) duplicate groups | 0 |
| lower(btrim(email)) duplicate groups | 0 |
| records_total | 0 |
| null_email_count | 0 |
| empty_email_count | 0 |
| whitespace_changed_count | 0 |

### Runtime-Redaktionsregel

Dieser Runtime-Audit-Abschnitt enthält keine echten E-Mail-Adressen, keine Account-IDs, keine Account-Zeilen und keine Datenbank-URL. Dokumentiert werden nur aggregierte Counts und ein redigiertes Ausführungsziel.

### Runtime-Policy-Einschätzung

Der aktuelle PostgreSQL-Runtime-Bestand enthält keine Account-Records. Damit liegen im aktuellen DB-Zustand keine vorhandenen E-Mail-Kollisionen vor, die einen späteren Unique-Constraint blockieren würden. Das ist keine Aussage über frühere oder externe Legacy-Datenbestände; es belegt nur den aktuell auditierten Runtime-Zustand auf dem Heimserver.

Für TODO 2 ist damit der Constraint-Design-Schritt freigegeben. Wegen der bereits dokumentierten Trim-Frage bleibt `lower(btrim(email))` gegenüber `lower(email)` der robustere Constraint-Kandidat, sofern die endgültige Policy leere bzw. nach Trim leere E-Mails weiterhin ignoriert.

### Runtime-Entscheidung für nächsten Schritt

Status: `ready_for_constraint_design`

Begründung:

- `domain_accounts` ist im PostgreSQL-Runtime-Stack vorhanden.
- Der aktuelle PostgreSQL-Bestand enthält 0 Account-Records.
- Es gibt 0 Duplicate-Gruppen für `lower(email)`.
- Es gibt 0 Duplicate-Gruppen für `lower(btrim(email))`.
- Es gibt keine gemessenen Whitespace- oder Empty-Email-Legacy-Fälle im aktuellen DB-Bestand.
- TODO 2 bleibt ein eigener PR: kein Unique-Index, keine Runtime-Änderung und kein API-Konfliktmapping in diesem Report-PR.

## Nächster PR

Nach TODO 2A bleiben weiterhin offen:

- PostgreSQL-vs-JSONL Listenparitäts-Proof
- Edge-Orphan-/Referenz-Audit
- Single-Instance-/Multi-Instance-Betriebsentscheidung
- Step-up-E-Mail-Persistenz
- WebAuthn-Credential-Writeback
- vollständiger PostgreSQL-Domain-Runtime-Smoke
- JSONL-Rolle / JSONL-Demontage

Dieser PR ist kein Runtime-Cutover.

## TODO 2A Ergebnis

Status: umgesetzt. Der unter `ready_for_constraint_design` freigegebene Constraint
ist jetzt im PostgreSQL-Account-Create-Pfad implementiert.

- Normalisierter Unique-Index eingeführt: `domain_accounts_email_normalized_unique`
- Normalisierung: `lower(btrim(email))`
- Partial Predicate: `email IS NOT NULL AND btrim(email) <> ''`
- Fehlende / NULL / nach Trim leere E-Mails: nicht unique-relevant
- Duplicate normalisierte nicht-leere E-Mail im PostgreSQL-Create-Pfad: `409 CONFLICT`
- DB-Constraint ist die Race-Sicherheitsgrenze; die App-Vorabprüfung bleibt nur Komfort
- Unique-Violation wird über den Constraint-Namen klassifiziert
  (`AccountWriteError::DuplicateEmail`), keine String-Suche im DB-Fehlertext
- Kein JSONL-Cutover, kein Step-up-E-Mail-Fix, kein WebAuthn-Credential-Cutover, kein Runtime-Smoke

### Geänderte Artefakte

- Migration up/down: `apps/api/migrations/20260613000001_domain_accounts_email_normalized_unique.up.sql` und `.down.sql`
- Fehlerklassifikation: `apps/api/src/domain_db.rs` (`ACCOUNT_EMAIL_UNIQUE_CONSTRAINT`,
  `AccountWriteError::DuplicateEmail`, `insert_account_from_jsonl_record`)
- HTTP-Mapping: `apps/api/src/routes/accounts.rs` (`create_account` → `409 CONFLICT`,
  generische Meldung ohne E-Mail-, ID- oder Constraint-Leak)
- Tests: `apps/api/tests/db_domain_schema_migrations.rs`,
  `apps/api/tests/db_domain_backfill.rs` und
  `apps/api/tests/db_domain_account_write_path.rs`

### Nicht-ASCII-Semantik (bewusste DB-Policy)

PostgreSQL `lower(...)` ist für Nicht-ASCII-Zeichen nicht byte-identisch mit der
Rust-Semantik `to_ascii_lowercase()` des In-Memory-`AccountStore`. Diese Abweichung
ist – wie in den Audit-Abschnitten oben bereits dokumentiert – bewusst akzeptiert:
Der Unique-Index ist die durable Race-Grenze des PostgreSQL-Pfades, der ASCII-Lookup
bleibt das Laufzeitverhalten des Stores. Es wurde keine zusätzliche
Normalisierungsspalte eingeführt, um den PR minimal und auf die bestehende
`domain_accounts`-Tabelle fokussiert zu halten.

### Reload-/Index-Semantik

`load_accounts_from_postgres` ruft `rebuild_email_index` auf, das bei
gleich-normalisierten E-Mails deterministisch die lexikografisch kleinste Account-ID
als Owner wählt. Nach dieser Migration kann PostgreSQL keine zwei nicht-leeren,
gleich-normalisierten E-Mails mehr persistieren. Der lexikografische Tie-Break ist
damit im PostgreSQL-Pfad unerreichbar und nur noch JSONL-/Legacy-Verhalten, nicht der
PostgreSQL-Constraint-Zustand.

### Abgelöste und erweiterte Proofs

Der Index löst die frühere Phase-B-Duplikat-Toleranz ausschließlich für
normalisierte, nicht-leere E-Mails ab.

Semantisch abgelöst wurden:

- `apps/api/tests/db_domain_schema_migrations.rs`: Der frühere
  „Duplikate erlaubt"-Test prüft jetzt, dass der normalisierte Unique-Index
  Case-Varianten ablehnt, dass nach Trim leere E-Mails DB-seitig abgelehnt werden
  und dass `NULL` erlaubt bleibt.
- `apps/api/tests/db_domain_backfill.rs`: Der Duplikat-E-Mail-Backfill-Test prüft
  jetzt Audit + Skip mit `lower(btrim(email))` statt „beide importiert".

Zusätzlich wurde erweitert:

- `apps/api/tests/db_domain_account_write_path.rs`: Der Account-Write-Path-Proof
  enthält jetzt den Route-Level-Beweis, dass eine DB-seitig erkannte normalisierte
  E-Mail-Kollision als `409 CONFLICT` ohne Cache- oder JSONL-Nebenwirkung
  zurückgegeben wird, sowie direkte Insert-Proofs.

Die drei Proofs (`db-domain-schema-migrations-proof`,
`db-domain-backfill-proof`, `db-domain-account-write-path-proof`) sind mit
CI-Evidence neu belegt:

- Run: `https://github.com/heimgewebe/weltgewebe/actions/runs/27487642549`
- Run-ID: `27487642549`
- Commit: `cc5446023417e65df1ae907cae9ad4c39612b3a0`
- Jobs:
  - `db-domain-schema-migrations-proof`
  - `db-domain-backfill-proof`
  - `db-domain-account-write-path-proof`

Die Phase-C-Backfill-Importsemantik ist sonst unverändert; es gibt keinen
Cutover, kein Dual-Write und keine Runtime-Backfill-Änderung.

### Härtung vor Review

Vor dem Review wurde der PR gezielt gehärtet (kein Scope-Zuwachs):

- **Fehlerklassifikation:** Nur `domain_accounts_email_normalized_unique`
  (→ `DuplicateEmail`) und `domain_accounts_pkey` (→ `DuplicateId`) werden
  spezifisch gemappt; jede andere – auch unbekannte – Unique-Violation bleibt
  generischer `Database`-Fehler statt fälschlich `DuplicateId`.
- **Migration-Preflight:** Vor `CREATE UNIQUE INDEX` bricht ein redigierter
  `DO`-Block mit klarer Meldung (ohne E-Mail-/ID-/Rohdaten-Ausgabe) ab, wenn
  Altbestände normalisierte Duplikate oder nach Trim leere E-Mails enthalten.
  Keine automatische Bereinigung. `IF NOT EXISTS` wurde entfernt, um Drift nicht
  zu kaschieren.
- **After-trim-empty:** `NewDomainAccountRow::from_jsonl_record` trimmt jetzt und
  bildet nach Trim leere Werte auf `None` ab; zusätzlich erzwingt der
  Check-Constraint `domain_accounts_email_not_empty_after_trim`
  (`email IS NULL OR btrim(email) <> ''`) die Invariante DB-seitig.
- **Backfill-Audit:** nutzt dieselbe Normalisierung wie der Index
  (`lower(btrim(email))`) und überspringt das Duplikat **vor** dem Insert; die
  Constraint-Ausnahme bleibt nur defensive Rückfallebene.
- **CI-Proof-Bündelung:** Der Route-409-Beweis und die direkten Insert-Proofs
  liegen jetzt in `apps/api/tests/db_domain_account_write_path.rs` (laufen im
  Job `db-domain-account-write-path-proof`); die separate Testdatei entfällt
  (siehe Abschnitt „Abgelöste und erweiterte Proofs").

### Follow-up: Login-Lookup-Normalisierung

Der bestehende nicht-eindeutige Lookup-Index `domain_accounts_email_lookup`
bleibt in diesem PR erhalten. Ein Folge-PR soll prüfen, ob Login-/Lookup-Queries
auf `lower(btrim(email))` umgestellt werden können und der alte Lookup-Index
danach entfallen kann.

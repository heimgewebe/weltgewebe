---
id: blueprints.domain-data-postgres-cutover
title: Domain Data PostgreSQL Cutover
doc_type: blueprint
status: active
lang: de
canonicality: planning
summary: >
  Planungs- und Cutover-Blaupause für OPT-ARC-001: kontrollierte Migration
  der Domänendaten von JSONL/In-Memory nach PostgreSQL ohne versteckte
  Doppelwahrheit.
relations:
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: docs/tasks/index.json
  - type: relates_to
    target: docs/reports/optimierungsstatus.md
  - type: relates_to
    target: docs/reports/domain-account-write-path-proof.md
  - type: relates_to
    target: docs/reports/optimierungsbericht.md
  - type: relates_to
    target: docs/specs/contract.md
  - type: relates_to
    target: docs/specs/list-pagination-api.md
  - type: relates_to
    target: apps/api/src/routes/nodes.rs
  - type: relates_to
    target: apps/api/src/routes/edges.rs
  - type: relates_to
    target: apps/api/src/routes/accounts.rs
  - type: relates_to
    target: apps/api/src/state.rs
---

# Domain Data PostgreSQL Cutover

## Problemstellung

OPT-ARC-001 ist nicht einfach „PostgreSQL verwenden“. Es geht um einen
kontrollierten Persistenz-Cutover für die Domänendaten `nodes`, `edges` und
`accounts`.

Der aktuell belegte Ist-Zustand ist klar:

- Die Domänendaten werden weiterhin aus JSONL-Dateien geladen und in
  In-Memory-Caches gehalten.
- PostgreSQL existiert bereits für Sessions und andere Auth-/Betriebsanteile,
  ist aber noch nicht die primäre Wahrheit für die Domänendaten.
- Eine direkte Code-Migration ohne Cutover-Plan erhöht das Risiko von
  Datenverlust, inkonsistenten Lese-/Schreibpfaden, fehlgeschlagenem Rollback
  und einer stillen Doppelwahrheit zwischen JSONL und PostgreSQL.

Diese Blaupause definiert deshalb den Migrationspfad, die Prüfregeln und die
Rückfalllogik, bevor Produktionscode verändert wird.

## Verifizierter Ist-Zustand

| Domain | Aktuelle Lesequelle | Aktuelle Schreibquelle | Runtime-Cache | PostgreSQL-Status |
|---|---|---|---|---|
| nodes | JSONL über `nodes_path()`, `BufReader::lines`, `serde_json::from_str` | JSONL-Rückschreibung über `patch_node` mit Temp-Datei + Rename | `OrderedCache<Node>` | nicht primär |
| edges | JSONL über `edges_path()`, `BufReader::lines`, `serde_json::from_str` | kein Schreibpfad im geprüften Code gefunden; aktuell nur JSONL-gestützter Lese-/Ladepfad belegt | `OrderedCache<Edge>` | nicht primär |
| accounts | `demo.accounts.jsonl` über `accounts_path()` und `BufReader::lines` | gemischt: JSONL-Append über `append_account_line` beim Anlegen; In-Memory-Mutationen in Auth-Flows, u. a. Step-up-E-Mail-Änderung und WebAuthn-User-ID-Writeback über `AccountStore` | `AccountStore` | nicht primär |

Zusatzbefund:

- `apps/api/src/state.rs` enthält weiterhin In-Memory-Caches für `accounts`,
  `nodes` und `edges` sowie einen optionalen `db_pool`, der für die
  Domänendaten noch nicht als primäre Persistenzschicht verwendet wird.
- `apps/api/migrations/` enthält derzeit nur die Session-Migrationen; es gibt
  dort noch keine PostgreSQL-Tabellen für `nodes`, `edges` oder `accounts`.
- Account-Schreibpfade sind breiter als der JSONL-Append-Pfad: Neben dem
  Anlegen von Accounts müssen spätere Auth-Mutationen wie E-Mail-Änderung
  und WebAuthn-User-ID-Writeback im Cutover explizit erfasst werden.

## Zielzustand

Der Zielzustand ist ein klarer, einziger primärer Truth-Layer für
Domänendaten:

- PostgreSQL ist die primäre Persistenzschicht für `nodes`, `edges` und
  `accounts`.
- JSONL ist entweder vollständig aus dem Runtime-Pfad entfernt oder bleibt
  nur noch explizit als Seed-, Import-, Export- oder Legacy-Artefakt erhalten.
  Es darf keine versteckte Runtime-Wahrheit mehr sein.
- Laufzeit-Caches dürfen weiter existieren, aber nur als abgeleitete oder
  read-through-Caches mit klarer Reload-/Invalidierungssemantik.
- Der Wire-Vertrag aus `docs/specs/list-pagination-api.md` bleibt stabil:
  - Legacy-Array-Antworten bleiben kompatibel.
  - Der Cursor-Envelope bleibt kompatibel.
  - Stabile ID-Sortierung im Cursor-Modus bleibt kompatibel.
  - Die `limit=0`-Validierung im Cursor-Modus bleibt unverändert.

## Vorgeschlagenes Tabellenmodell

Die folgenden Tabellen sind als Zielbild zu verstehen, nicht als fertige SQL-
Migration.

### `domain_nodes`

- Primärschlüssel: `id` als unveränderte, string-basierte Domänen-ID.
- Payload: ein flexibles `jsonb`-Dokument für nicht normalisierte Felder.
- Explizite Spalten: mindestens `kind`, `title`, eine geographisch
  indexierbare Standortrepräsentation für `location.lat`/`location.lon`,
  sowie `created_at` und `updated_at`.
- Indexe: Primärschlüssel auf `id`, geographischer Index auf der
  Standortrepräsentation (`location.lat`/`location.lon` oder spätere
  PostGIS-/bbox-Spalte), plus ggf. ein Zeitindex für Sortier-/Pflegezwecke.
- Eindeutigkeitsregeln: `id` bleibt eindeutig; zusätzliche fachliche
  Eindeutigkeiten nur dann, wenn die bestehende Domäne sie ausdrücklich verlangt.
- Migrationsprovenienz: `source_format`, `source_path`, `source_row`,
  `source_digest` und `import_batch_id` sind sinnvoll, wenn Import/Backfill
  reproduzierbar bleiben soll.

### `domain_edges`

- Primärschlüssel: `id` als unveränderte, string-basierte Domänen-ID.
- Payload: ein flexibles `jsonb`-Dokument für nicht normalisierte Felder.
- Explizite Spalten: `source_id`, `target_id`, optional ein Relationstyp oder
  Label, dazu `created_at`.
- `updated_at` ist **nicht** in der aktuellen `Edge`-Struct
  (`apps/api/src/routes/edges.rs`) und nicht im Domain-Vertrag
  (`contracts/domain/edge.schema.json`) definiert. Die Spalte wird in der
  Phase-B-Migration daher weggelassen. Falls Edge-Mutations-Semantik später
  eingeführt wird, muss eine eigene Migration `updated_at` ergänzen.
- Indexe: Primärschlüssel auf `id`, Einzelindizes auf `source_id` und
  `target_id`, plus ein zusammengesetzter Index für häufige Join-/Filterpfade.
- Eindeutigkeitsregeln: mindestens `id`; weitere Constraints nur, wenn sie aus
  dem aktuellen Domänenvertrag ableitbar sind.
- Migrationsprovenienz: analog zu `domain_nodes`.
- Foreign-Key-Entscheidung: **ausstehendes explizites Orphan-/Referenz-Audit**.
  Default-Kandidat sind strikte FKs auf `domain_nodes(id)` für `source_id`
  und `target_id`, weil sie die stärkere Integritätsgarantie liefern.
  Der spätere SQL-Migrations-PR muss diese Entscheidung aber anhand eines
  Daten-/Code-Audits treffen: Falls das aktuelle Modell externe, fehlende oder
  entitätsübergreifende Referenzen zulässt, ist alternativ eine lose
  Referenzsemantik mit explizitem Integrity-Guard oder Quarantäne-Report zu
  wählen. Der Backfill darf Orphaned Edges niemals still verwerfen,
  normalisieren oder glätten; er muss entweder laut scheitern oder die Fälle
  explizit quarantänisieren.

### `domain_accounts`

- Primärschlüssel: `id` als unveränderte, string-basierte Domänen-ID.
- Payload: getrennte Speicherung von öffentlicher Projektion und privaten/
  operativen Feldern, zum Beispiel via `public_payload jsonb` und
  `private_payload jsonb` oder über klar benannte Einzelspalten.
- Explizite Spalten: `radius_m`, `role`, `email`, `webauthn_user_id`,
  Statusfelder wie `disabled`, dazu `created_at` und `updated_at`.
- `public_pos` ist **keine gespeicherte Spalte**. Sie ist eine deterministische
  Laufzeit-Projektion aus `location_lat`, `location_lon`, `radius_m` und `id`
  via `calculate_jittered_pos` (verifiziert in `apps/api/src/routes/accounts.rs`).
  Eine spätere Migration kann eine materialisierte Spalte ergänzen, wenn der
  Lese-Aufwand das rechtfertigt; das ist aber eine explizite Folge-Entscheidung.
- Schreibpfad-Abdeckung: Der Cutover muss nicht nur Account-Erzeugung,
  sondern auch spätere Account-Mutationen abdecken, insbesondere
  Step-up-E-Mail-Änderungen und WebAuthn-User-ID-Writeback.
- Indexe: Primärschlüssel auf `id`, eindeutiger Index auf `email` oder
  `lower(email)`, falls E-Mail-Login oder Lookup das benötigen.
- Eindeutigkeitsregeln: öffentliche und private Sicht müssen getrennt bleiben;
  sensitive Felder dürfen nie über die öffentliche Projektion in die API
  leaken.
- Migrationsprovenienz: analog zu `domain_nodes`.

## Cutover-Phasen

| Phase | Inhalt | Ergebnis |
|---|---|---|
| A | Blueprint und Statusabgleich | Diese PR: Cutover-Plan, Ist-Befund und Statuspflege; kein Produktionscode, keine Migrationen |
| B | SQL-Schema-Entwurf und Migrationstests | Tabellen für Nodes, Edges und Accounts; Down-Migrationen wo sinnvoll; kein Runtime-Switch |
| C | Backfill-/Import-Pfad | Deterministischer JSONL→PostgreSQL-Import mit ID-Erhalt, Zähl- und Checksum-Prüfung, idempotent |
| D | Read-Path hinter Feature-Flag/Config | PostgreSQL-Lesepfad für alle drei Domänen; JSONL nur noch als explizite Fallback-Option |
| E | Write-Path-Cutover | Schreibpfade wechseln auf PostgreSQL; Dual-Write nur falls bewusst entschieden und reconciliation-fähig |
| F | Runtime-Smoke und CI-Beweis | API-Smoke gegen PostgreSQL-Domänendaten; Cursor- und Legacy-Listenverhalten geprüft |
| G | JSONL-Demontage | JSONL verlässt den primären Runtime-Pfad; Seed-/Export-Artefakte bleiben nur dokumentiert erhalten |

## Regeln für die Datenmigration

- IDs müssen unverändert bleiben.
- Sortier- und Cursorverhalten darf sich nicht ändern.
- Accounts müssen öffentliche und private Projektion strikt getrennt halten.
- Accounts müssen Standort- und Privacy-Radius-Semantik exakt bewahren.
- Sensible Felder wie E-Mail, WebAuthn- und Session-bezogene Daten dürfen nicht
  in öffentliche Projektionen auslaufen.
- Account-Mutationen aus Auth-Flows müssen persistent, restart-stabil und
  paritätsgetestet sein; cache-only Writebacks sind nach dem Cutover unzulässig.
- Edges müssen `source_id` und `target_id` exakt bewahren.
- Nodes müssen Standortfelder exakt bewahren.
- Der Backfill muss idempotent sein.
- Import muss bei malformed JSONL laut scheitern, sofern keine explizite
  Quarantäne-Strategie dokumentiert ist.
- Keine stillen Teilimporte.

## Rollback- und Fehlerbild

- Wenn Phase B fehlschlägt, wird die Migration verworfen.
- Wenn der Backfill fehlschlägt, dürfen Tabellen in Dev/Test neu aufgebaut
  werden; Produktion braucht dafür eine explizite Backup-/Restore-Strategie.
- Wenn die Read-Parität fehlschlägt, bleibt der Runtime-Pfad auf JSONL.
- Wenn der Write-Cutover fehlschlägt, wird nur dann auf JSONL zurückgeschaltet,
  wenn JSONL noch die autoritative Wahrheit ist; bei Dual-Write ist eine
  Reconciliation-Regel Pflicht.
- Split-Brain zwischen JSONL und PostgreSQL ist zu vermeiden, nicht zu
  kaschieren.

## CI- und Proof-Anforderungen

Für die späteren Implementierungs-PRs sind konzeptionell folgende Gates
vorzusehen:

- `cargo test --locked` für die betroffenen API-Tests.
- Migrations-Tests für Schema-Erzeugung und Rückbau.
- API-Integrations-Tests gegen PostgreSQL.
- Runtime-Smoke für `/nodes`, `/edges` und `/accounts`.
- Paritäts-Tests für Cursor-Paginierung und Legacy-Listenverhalten.
- Account-Write-Paritäts-Tests für Create, Step-up-E-Mail-Änderung und
  WebAuthn-User-ID-Writeback.
- Orphan-/Referenz-Audit vor der FK-Entscheidung: Anzahl und IDs
  potenziell verwaister Edges müssen ausgewiesen werden; das Ergebnis
  entscheidet zwischen strikten FKs und loser Referenzsemantik mit Guard oder
  Quarantäne.
- Doku-/Task-Guards wie `validate_relations`, `docs-relations-guard`,
  `generate_task_index --check` und `validate_task_index`.

Diese Gates sind hier als Zielvorgabe dokumentiert; sie werden erst in den
Implementierungsphasen relevant, wenn die jeweilige Infrastruktur existiert.

## Phase-D-Status (2026-06-03)

Phase D ist als optionaler, read-only PostgreSQL-Read-Path hinter explizitem
Config-Gate implementiert. Die `db_domain_read_path`-Suite ist als lokaler
PostgreSQL-Proof vorbereitet; der PR-CI-Beleg für
`db-domain-read-path-proof` steht aus. Mutierende Domänen-Endpunkte werden bei
`WELTGEWEBE_DOMAIN_READ_SOURCE=postgres` mit `409 CONFLICT` und
`DOMAIN_READ_SOURCE_READ_ONLY` blockiert, damit keine JSONL-only Writes nach
einem Neustart durch den PostgreSQL-Read-Path verschwinden. Das ist kein
Produktions-Cutover: JSONL bleibt im Default-/JSONL-Modus Default-Lesequelle
und Write-Truth, und Phase E bleibt offen.

## Phase-E-A-Status (2026-06-04)

Phase E-A implementiert einen bewusst engen, opt-in PostgreSQL-Schreibpfad
**ausschließlich** für die Account-Erzeugung (`POST /accounts`) hinter einem
eigenen Write-Gate `WELTGEWEBE_DOMAIN_ACCOUNT_WRITE_SOURCE`
(`domain_account_write_source`, Default `jsonl`). Der Write-Gate ist getrennt
vom Read-Gate; `postgres` erfordert hart `domain_read_source=postgres` plus
einen Pool (Config-Load- bzw. Startup-Fehler statt stillem Fallback). Es gibt
kein Dual-Write: JSONL-Modus schreibt nie PostgreSQL, PostgreSQL-Modus hängt
nie JSONL an. Der DB-Insert nutzt dasselbe semantische Mapping wie der
Phase-C-Backfill, sodass eine erzeugte Zeile mit „JSONL-Create + Backfill“
identisch ist; das In-Memory-`AccountStore` wird erst nach erfolgreichem
DB-Write aktualisiert, ein fehlgeschlagener Insert mutiert weder Cache noch
JSONL und liefert bei Primärschlüsselkollision `409 CONFLICT`.

Bewusst **nicht** Teil dieser Slice: `PATCH /nodes`-Write (im Postgres-Read-Modus
weiterhin blockiert), Edge-Writes, Step-up-E-Mail-Persistenz und
WebAuthn-User-ID-Writeback. JSONL bleibt Default und wird nicht entfernt. Belege
und Testmatrix siehe `docs/reports/domain-account-write-path-proof.md`. Der
PR-CI-Job `db-domain-account-write-path-proof` ist vorbereitet; der
PR-CI-Beleg steht aus. Das ist kein Produktions-Cutover; OPT-ARC-001 bleibt
`partial` und Phase E (Rest) bleibt offen.

## Akzeptanzkriterien für OPT-ARC-001

OPT-ARC-001 darf erst dann als erledigt gelten, wenn alles Folgende nachweisbar
ist:

- PostgreSQL-Migrationen existieren für `nodes`, `edges` und `accounts`.
- Der Runtime-Pfad kann PostgreSQL als primäre Quelle verwenden.
- JSONL ist nicht mehr die versteckte primäre Runtime-Wahrheit.
- Das API-Verhalten bleibt erhalten.
- Backfill/Import ist deterministisch und idempotent.
- CI belegt Migration und Runtime-Verhalten.
- Dokumentation und Statusartefakte werden erst nach diesem Beweis auf `done`
  gesetzt.

## Nicht-Ziele (Phase D / Read-Path-Slice)

Diese Liste beschreibt die Read-Path-Slice (Phase D). Der enge Account-Create-
Schreibpfad ist seit Phase E-A die einzige Ausnahme; alle übrigen Punkte gelten
weiter (siehe „Phase-E-A-Status“ und `docs/reports/domain-account-write-path-proof.md`).

- Kein vollständiger Write-Path-Cutover (nur `POST /accounts` ist als Phase E-A
  implementiert).
- Kein PostgreSQL-Write-Path für Nodes, Edges, Step-up-E-Mail oder
  WebAuthn-User-ID-Writeback; kein Dual-Write.
- Keine Entfernung von JSONL.
- Kein Produktions-Cutover.
- Kein Startup-Backfill.
- Keine Endpoint-Contract-Änderungen.
- Kein Claim, dass OPT-ARC-001 erledigt ist.
- Kein Auth-Redesign.
- Kein UI-Redesign.
- Kein Performance-Benchmark-Claim jenseits dieses Phase-D-Proofs.

## Einordnung

Die Phase-D-Slice ergänzte den optionalen read-only PostgreSQL-Read-Path hinter
explizitem Config-Gate. Phase E-A ergänzt darauf aufbauend genau einen engen
PostgreSQL-Schreibpfad für `POST /accounts` hinter einem getrennten Write-Gate.
Beide markieren OPT-ARC-001 bewusst noch nicht als erledigt. Phase E (Rest)
bleibt offen; JSONL bleibt im Default-/JSONL-Modus
Default-Lesequelle und Write-Truth bis Phase E/Cutover.

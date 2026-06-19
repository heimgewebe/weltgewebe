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
    target: docs/reports/domain-postgres-instance-coherence-decision.md
  - type: relates_to
    target: docs/reports/domain-node-write-path-proof.md
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

Der belegte Ist-Zustand nach Phase E-C / PR #1196:

- PostgreSQL-Domain-Tabellen und Migrationen für nodes, edges und accounts existieren.
- JSONL bleibt weiterhin Default-Wahrheit, solange kein expliziter Cutover erfolgt.
- PostgreSQL-Read-Path existiert opt-in hinter Domain-Read-Konfiguration.
- PostgreSQL-Write-Paths existieren opt-in für:
  - `POST /accounts`
  - `PATCH /nodes`
  - `POST /edges`
- `APP_CONFIG_PATH` ist fail-closed: eine explizit gesetzte,
  fehlerhafte Config fällt nicht still auf Defaults zurück.
- Neue PostgreSQL-Account-Create-Zeilen persistieren eine stabile
  `webauthn_user_id`; Cache und Reload erhalten dieselbe UUID.
- Lokale Runtime-Caches bestehen weiter.
- Produktions-Cutover ist nicht erfolgt.

Diese Blaupause ordnet deshalb den verbleibenden Cutover-Pfad, die Prüfregeln
und die Rückfalllogik, bevor PostgreSQL als primäre Domain-Wahrheit aktiviert
wird.

## Verifizierter Ist-Zustand

| Domain | Default | PostgreSQL opt-in | Status |
|---|---|---|---|
| nodes | JSONL read/write | Read-Path + `PATCH /nodes` | Nicht Default |
| edges | JSONL read/legacy | Read-Path + `POST /edges` | Nicht Default |
| accounts | JSONL read/create | Read-Path + `POST /accounts` | Nicht Default |

Zusatzdetails:

- `nodes`: Schema/Backfill/Read-Path proof-geführt; opt-in Node-Patch
  vorhanden; nicht Default.
- `edges`: Schema/Backfill/Read-Path proof-geführt; opt-in Edge-Create
  vorhanden; nicht Default.
- `accounts`: Schema/Backfill/Read-Path proof-geführt; opt-in Account-Create
  vorhanden; neue PostgreSQL-Creates persistieren `webauthn_user_id`.

Zusatzbefund:

- `ApiState` hält weiterhin prozesslokale In-Memory-Caches.
- PostgreSQL ist für Domain-Daten opt-in verfügbar, aber nicht Default-Wahrheit.
- Config-Gates müssen explizit gesetzt werden; fehlerhafte `APP_CONFIG_PATH`-Konfigurationen fail-closed.
- PostgreSQL-Write-Slices sind getrennt implementiert:
  - E-A Account-Create
  - E-B Node-Patch
  - E-C Edge-Create
- Offene Account-Mutationen bleiben:
  - Step-up-E-Mail-Persistenz
  - WebAuthn-Credential-Writeback / Passkey-Cutover
  - Legacy-Backfill und späteres `NOT NULL` für die WebAuthn-UUID-Spalte
  - E-Mail-Eindeutigkeit

## Zielzustand

Dieser Zielzustand ist noch nicht erreicht. Er definiert einen klaren, einzigen primären Truth-Layer für
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

Die folgenden Tabellen beschreiben Zielmodell und bereits teilweise implementierten Stand.
Konkrete Abweichungen und offene Constraints bleiben je Phase zu prüfen.

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
- Edge-Create existiert opt-in.
- Aktuelle Edge-Create-Semantik nutzt serialisierten PostgreSQL-Pfad
  mit Tabellenlock, Duplicate-Precheck, Cache-Limit-Check und finalem Insert.
- Performance-/Limit-Strategie bleibt offen.
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
  Step-up-E-Mail-Änderungen und WebAuthn-Credential-Writeback. Die Spalte
  `webauthn_user_id` wird bei neuen PostgreSQL-Account-Create-Zeilen persistiert.
  Legacy-Fälle ohne diese UUID bleiben vorerst erhalten.
  Backfill/Audit und späteres `NOT NULL` bleiben offen.
  Auch WebAuthn-Credential-Writeback bleibt offen.
- Indexe: Primärschlüssel auf `id`, eindeutiger Index auf `email` oder
  `lower(email)`, falls E-Mail-Login oder Lookup das benötigen.
- Eindeutigkeitsregeln: öffentliche und private Sicht müssen getrennt bleiben;
  sensitive Felder dürfen nie über die öffentliche Projektion in die API
  leaken.
- Migrationsprovenienz: analog zu `domain_nodes`.

## Cutover-Phasen

| Phase | Inhalt | Ergebnis / aktueller Stand |
|---|---|---|
| A | Blueprint und Statusabgleich | vorhanden; dieser PR aktualisiert den Blueprint auf Phase E-C + PR #1196 |
| B | SQL-Schema-Entwurf und Migrationstests | implementiert; Edge-FK-/Orphan-Gate offen |
| C | Backfill-/Import-Pfad | implementiert und proof-geführt |
| D | Read-Path hinter Config | implementiert opt-in; JSONL bleibt Default |
| E-A | Account-Create-Write-Path | implementiert opt-in; neue PostgreSQL-Creates persistieren stabile `webauthn_user_id` |
| E-B | Node-Patch-Write-Path | implementiert opt-in |
| E-C | Edge-Create-Write-Path | implementiert opt-in |
| E-Rest | Weitere Account-/Integritätsblocker | offen: Step-up-E-Mail, WebAuthn-Credential-Writeback, E-Mail-Unique, Legacy-Backfill/NOT NULL |
| F | Runtime-Smoke und Betriebsentscheidung | offen |
| G | JSONL-Demontage | offen |

## Offene Cutover-Blocker nach Phase E-C

- Produktions-Cutover nicht erfolgt; JSONL bleibt Default-Wahrheit.
- PostgreSQL-vs-JSONL-Listenparität ist offen: Legacy-`offset`/`limit`
  und Cursor-Paginierung müssen vor dem Cutover gegen den bestehenden
  API-Vertrag geprüft werden.
- Edge-Orphan-/Referenz-Audit ist offen: Vor Produktions-Cutover muss
  entschieden werden, ob `domain_edges.source_id`/`target_id` strikte
  Foreign Keys auf `domain_nodes(id)` erhalten oder ob eine lose
  Referenzsemantik mit Guard/Quarantäne-Report bewusst akzeptiert wird.
- Multi-Instance-Kohärenz ist entschieden (`DOMAIN-PG-002`, Option A):
  prozesslokale Caches sind nicht instanzübergreifend kohärent; horizontale
  API-Skalierung bleibt bis zu einer getesteten Kohärenzlösung ausgeschlossen.
  Siehe `docs/reports/domain-postgres-instance-coherence-decision.md`.
- E-Mail-Eindeutigkeit ist PostgreSQL-seitig noch nicht abgesichert.
- Step-up-E-Mail-Persistenz nach PostgreSQL ist offen.
- WebAuthn-Credential-Writeback und Passkey-Cutover sind offen.
- Legacy-Accounts ohne persistierte WebAuthn-UUID brauchen Backfill/Audit
  vor späterem `NOT NULL` auf der Spalte.
- Edge-Create funktioniert opt-in, aber Lock-/Limit-Strategie ist
  nicht performance-optimiert.
- Runtime-Smoke für vollständigen PostgreSQL-Domain-Betrieb ist offen.
- JSONL-Demontage ist offen.

## Instance Coherence Boundary

Für den aktuellen PostgreSQL-Domain-Pfad gilt `DOMAIN-PG-002`, Option A:
höchstens eine API-Instanz innerhalb dieser Kohärenzgrenze; der Normalbetrieb
erwartet eine lebende Instanz. Das ist eine Deployment-Invariante, keine
Multi-Instance-Kohärenzimplementierung und kein Verfügbarkeitsbeweis.

Operative Konsequenzen:

- `services.api.scale` darf nur das Literal `0` oder `1` sein.
- `services.api.deploy.replicas` darf nur das Literal `0` oder `1` sein.
- Ein direkter `services.api.replicas`-Key ist unzulässig. Verwende
  ausschließlich `services.api.scale` oder `services.api.deploy.replicas`,
  jeweils mit dem Literal `0` oder `1`.
- Auf ausführbaren Flächen darf `docker compose --scale api=<value>`,
  `docker compose scale api=<value>` oder die entsprechende `docker-compose`-
  Form nur mit `0` oder `1` verwendet werden; Dokumentation darf ausschließlich
  die Werte `0`, `1`, `N` oder `<value>` verwenden.
- Ein geschützter API-Upstream darf nicht zusammen mit einem weiteren Upstream
  auf derselben Caddy-`reverse_proxy`- oder `to`-Direktivzeile stehen.
- NATS gilt ohne dedizierten Invalidierungspfad und Tests nicht als
  Domain-Cache-Kohärenz.

Der statische Guard
`scripts/guard/domain-single-instance-guard.sh` und sein Test
`scripts/tests/test_domain_single_instance_guard.sh` sichern diese klar
erkennbaren Konfigurationsflächen ab. Parsergrenzen und Nicht-Beweise sind im
Decision-Report dokumentiert. Die Grenze entsperrt weder `DOMAIN-PG-001` noch
`DB-PROOF-001`, `AUTH-PG-001`, `AUTH-PG-002` oder den PostgreSQL-Cutover.

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

Bereits vorhandene Proofs:

- Schema-Migrationen
- Backfill
- Read-Path
- Account-Create-Write-Path
- Node-Patch-Write-Path
- Edge-Create-Write-Path
- OPT-ARC-001-DB-Proof-Matrix-Guard

Weiter erforderlich:

- PostgreSQL-vs-JSONL-Listenparitäts-Proof:
  - `/nodes` und `/edges` müssen im Legacy-Modus die bisherige
    Einfüge-/Dateireihenfolge bewahren.
  - `/accounts` muss im Legacy-Modus die bisherige ID-Sortierung bewahren.
  - Der Cursor-Modus muss für alle drei Domänen weiterhin stabil nach ID
    sortieren.
- Edge-Orphan-/Referenz-Audit-Proof vor der finalen Entscheidung zwischen
  Foreign Keys und bewusst loser Referenzsemantik.
- Runtime-Smoke für vollständigen PostgreSQL-Domain-Betrieb
- Multi-Instance-/Cache-Kohärenz-Proof, falls horizontale Skalierung
  erlaubt werden soll
- E-Mail-Unique-Proof
- Step-up-E-Mail-Persistenz-Proof
- WebAuthn-Credential-Writeback-Proof
- JSONL-Demontage-Proof

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
- PostgreSQL-vs-JSONL-Listenparität ist für Legacy- und Cursor-Modus
  belegt.
- Edge-Referenzintegrität ist durch Foreign Keys oder eine bewusst
  dokumentierte lose Referenzsemantik mit Guard/Quarantäne abgesichert.

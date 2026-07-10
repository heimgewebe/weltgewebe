---
id: datenmodell
title: Datenmodell
doc_type: reference
status: active
summary: Aktuelles physisches Datenmodell, Quellenumschaltung und noch nicht implementiertes Zielmodell.
relations:
  - type: relates_to
    target: architecture/overview.md
  - type: relates_to
    target: docs/domain/vocabulary.md
  - type: relates_to
    target: docs/techstack.md
  - type: relates_to
    target: docs/deploy/README.md
---

# Datenmodell

## Wichtigste Aussage

PostgreSQL ist **nicht** pauschal die alleinige Quelle der Wahrheit. Für
Domänendaten bleibt JSONL der Standard. PostgreSQL kann als Lesequelle und für
einzelne Schreibpfade ausdrücklich aktiviert werden. Auth-Sitzungen und
Passkey-Credentials besitzen eigene Persistenzentscheidungen.

## Quellenmatrix

| Domäne | Standard lesen | Standard schreiben | PostgreSQL-Option |
|---|---|---|---|
| Accounts/Garnrollen | JSONL | JSONL-Append | `domain_accounts`; Account-Create opt-in |
| Knoten | JSONL | JSONL-Rewrite | `domain_nodes`; Patch opt-in |
| Fäden | JSONL | JSONL-Append | `domain_edges`; Create opt-in |
| Sitzungen | In-Memory ohne DB | gleicher Store | `sessions` bei konfiguriertem DB-Store |
| Passkeys | In-Memory | In-Memory | `passkey_credentials` opt-in |
| Gespräche/Nachrichten | kein vollständiger produktiver Pfad | kein vollständiger produktiver Pfad | nur Contracts, keine Tabellen |

PostgreSQL-Schreiben verlangt PostgreSQL-Lesen. Die API verweigert ungültige
Mischzustände, damit Änderungen nach einem Neustart nicht unsichtbar werden.
Es gibt keinen allgemeinen Dual-Write.

## Physische PostgreSQL-Tabellen

Die folgende Übersicht wird aus den aktuellen Migrationen abgeleitet.

### `sessions`

| Spalte | Typ | Bedeutung |
|---|---|---|
| `id` | `TEXT` PK | serverseitige Session-ID |
| `account_id` | `TEXT` | zugehöriger Account |
| `device_id` | `TEXT` | Browser-/Gerätebezug |
| `created_at` | `TIMESTAMPTZ` | Erstellung |
| `last_active` | `TIMESTAMPTZ` | letzte Aktivität |
| `expires_at` | `TIMESTAMPTZ` | serverseitiger Ablauf |

Derzeit besteht kein Foreign Key auf `domain_accounts`, weil Accounts weiterhin
aus JSONL gelesen werden können.

### `domain_accounts`

| Gruppe | Spalten |
|---|---|
| Identität | `id`, `kind`, `title`, `mode` |
| Sichtbarkeit/Ort | `radius_m`, `location_lat`, `location_lon` |
| Betrieb/Auth | `disabled`, `role`, `email`, `webauthn_user_id` |
| Zeit | `created_at`, `updated_at` |
| Restfelder | `public_payload`, `private_payload` |

E-Mail-Adressen besitzen einen trim-/case-normalisierten partiellen Unique-Index.
`public_pos` wird nicht gespeichert, sondern aus privater Position, Radius und
ID deterministisch abgeleitet.

`kind` und `mode` verwenden noch Legacy-Defaults `ron`. Diese Defaults sind kein
bestätigtes Zielmodell. Ihre Ablösung braucht eine Datenmigration und kann nicht
nur dokumentarisch erfolgen.

### `domain_nodes`

| Spalte | Typ | Bedeutung |
|---|---|---|
| `id` | `TEXT` PK | Knoten-ID |
| `kind` | `TEXT` | Knotentyp |
| `title` | `TEXT` | Titel |
| `lat`, `lon` | `DOUBLE PRECISION` | optionale Position |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | Zeitangaben |
| `payload` | `JSONB` | übrige JSONL-Felder |

Es gibt derzeit keine PostGIS-Geometrie. Der Geoindex ist ein einfacher
B-Tree auf `(lat, lon)`.

### `domain_edges`

| Spalte | Typ | Bedeutung |
|---|---|---|
| `id` | `TEXT` PK | Faden-ID |
| `source_id`, `target_id` | `TEXT` | Endpunkte |
| `edge_kind` | `TEXT` | Beziehungsart |
| `created_at` | `TIMESTAMPTZ` | Erstellung |
| `payload` | `JSONB` | Typinformationen, Notiz und Restfelder |

Foreign Keys sind bewusst noch nicht gesetzt. Vor einer FK-Entscheidung ist ein
Orphan- und Referenzaudit erforderlich; bestehende Fäden dürfen nicht
stillschweigend verworfen werden.

### `passkey_credentials`

| Spalte | Typ | Bedeutung |
|---|---|---|
| `credential_id` | `TEXT` PK | hexkodierte WebAuthn-Credential-ID |
| `account_id` | `TEXT` | zugehöriger Account |
| `webauthn_user_id` | `UUID` | stabiler WebAuthn-User-Handle |
| `credential` | `JSONB` | öffentlicher Credential-Datensatz und Counter |
| Zeitfelder | `TIMESTAMPTZ` | Erstellung, Änderung, letzte Nutzung |

Die Tabelle speichert keine privaten Passkey-Schlüssel. Ein Foreign Key zu
`domain_accounts` ist bis zum vollständigen PostgreSQL-Accountcutover bewusst
ausgesetzt.

## JSONL-Modell

JSONL-Datensätze folgen den JSON-Schemas in `contracts/domain`. Die API lädt sie
beim Start in begrenzte In-Memory-Stores. Schreibpfade serialisieren
check-and-write innerhalb eines Prozesses und verwenden `fsync`; sie sind kein
Ersatz für eine transaktionale Mehrprozessdatenbank.

## Contracts ohne produktive Tabellen

`conversation.schema.json`, `message.schema.json` und `role.schema.json`
beschreiben fachliche beziehungsweise geplante Objekte. Die aktuelle
Migrationshistorie enthält keine `conversations`, `messages`, `roles`, `outbox`
oder Projektionsviews. Dokumente dürfen diese Objekte daher nicht als bereits
persistierte PostgreSQL-Fläche darstellen.

## Cutover-Regeln

Ein vollständiger PostgreSQL-Cutover ist erst belegt, wenn:

1. Backfill und Orphan-Audit grün sind,
2. die betroffene Lesequelle PostgreSQL ist,
3. alle benötigten Mutationen PostgreSQL schreiben,
4. kein restart-unsichtbarer JSONL-Pfad verbleibt,
5. Rollback und Wiederherstellung definiert sind,
6. DB- und Browser-Ende-zu-Ende-Beweise grün sind,
7. die Produktionsruntime die Schalter frisch belegt.

## Logisches Zielmodell

Das angestrebte Produktmodell besteht aus einer Garnrolle je Account,
Eigenschaften für Sichtbarkeit und Verortung, Knoten als Kollektivgüter oder
Orte sowie Fäden als Beziehungen. Dieses Zielmodell ist noch nicht vollständig
mit den Legacyfeldern `kind`, `mode`, `role` und `ron` versöhnt. Bis zur
Migration gelten die physischen Contracts und Datenintegritätsregeln vor einer
vereinfachenden Produktbeschreibung.

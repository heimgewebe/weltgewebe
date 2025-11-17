# Datenmodell

Dieses Dokument beschreibt das Datenmodell der Weltgewebe-Anwendung, das auf PostgreSQL aufbaut.
Es dient als Referenz für Entwickler, um die Kernentitäten, ihre Beziehungen und die daraus
abgeleiteten Lese-Modelle zu verstehen.

## Grundprinzipien

- **Source of Truth:** PostgreSQL ist die alleinige Quelle der Wahrheit.
- **Transaktionaler Outbox:** Alle Zustandsänderungen werden transaktional in die `outbox`-Tabelle
  geschrieben, um eine konsistente Event-Verteilung an nachgelagerte Systeme (z.B. via NATS
  JetStream) zu garantieren.
- **Normalisierung:** Das Schreib-Modell ist normalisiert, um Datenintegrität zu gewährleisten.
  Lese-Modelle (Projektionen/Views) sind für spezifische Anwendungsfälle denormalisiert und
  optimiert.
- **UUIDs:** Alle Primärschlüssel sind UUIDs (`v4`), um eine verteilte Generierung zu
  ermöglichen und Abhängigkeiten von sequenziellen IDs zu vermeiden.

---

## Tabellen (Schreib-Modell)

### `nodes`

Speichert geografische oder logische Knotenpunkte, die als Anker für Threads dienen.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | `uuid` (PK) | Eindeutiger Identifikator des Knotens. |
| `location` | `geography(Point, 4326)` | Geografischer Standort (Längen- und Breitengrad). |
| `h3_index`| `bigint` | H3-Index für schnelle geografische Abfragen. |
| `name` | `text` | Anzeigename des Knotens. |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |
| `updated_at` | `timestamptz` | Zeitstempel der letzten Änderung. |

### `roles`

Verwaltet Benutzer- oder Systemrollen, die Berechtigungen steuern.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | `uuid` (PK) | Eindeutiger Identifikator der Rolle. |
| `user_id` | `uuid` (FK) | Referenz zum Benutzer (externes System). |
| `permissions` | `jsonb` | Berechtigungen der Rolle als JSON-Objekt. |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |

### `conversations`

Repräsentiert die Gesprächsräume ("conversations"), die an Knoten gebunden sind.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | `uuid` (PK) | Eindeutiger Identifikator des Gesprächsraums. |
| `node_id` | `uuid` (FK, `nodes.id`) | Zugehöriger Knoten. |
| `author_role_id` | `uuid` (FK, `roles.id`) | Ersteller des Gesprächsraums. |
| `title` | `text` | Titel des Gesprächsraums. |
| `content` | `text` | Inhalt (z.B. erster Beitrag). |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |
| `updated_at` | `timestamptz` | Zeitstempel der letzten Änderung. |

### `outbox`

Implementiert das Transactional Outbox Pattern für zuverlässige Event-Publikation.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | `uuid` (PK) | Eindeutiger Identifikator des Events. |
| `aggregate_type` | `text` | Typ des Aggregats (z.B. "conversation"). |
| `aggregate_id` | `uuid` | ID des betroffenen Aggregats. |
| `event_type` | `text` | Typ des Events (z.B. "conversation.created"). |
| `payload` | `jsonb` | Event-Daten. |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |

---

## Projektionen (Lese-Modelle)

Diese Views sind für die Lese-Performance optimiert und fassen Daten aus mehreren Tabellen zusammen.
Sie werden von den Workern (Projektoren) asynchron aktualisiert.

### `public_role_view`

Eine denormalisierte Sicht auf Rollen, die nur öffentlich sichtbare Informationen enthält.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `role_id` | `uuid` | Identifikator der Rolle. |
| `display_name` | `text` | Öffentlich sichtbarer Name (ggf. aus einem externen User-Service). |
| `avatar_url` | `text` | URL zu einem Avatar-Bild. |

### `conversation_view`

Eine zusammengefasste Ansicht von Gesprächsräumen für die schnelle Darstellung in der Benutzeroberfläche.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `conversation_id` | `uuid` | Identifikator des Gesprächsraums. |
| `node_id` | `uuid` | Zugehöriger Knoten. |
| `node_name` | `text` | Name des zugehörigen Knotens. |
| `author_display_name` | `text` | Anzeigename des Autors. |
| `title` | `text` | Titel des Gesprächsraums. |
| `comment_count` | `integer` | Anzahl der Kommentare (wird vom Projektor berechnet). |
| `last_activity_at` | `timestamptz` | Zeitstempel der letzten Aktivität. |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |

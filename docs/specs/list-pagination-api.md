---
id: specs.list-pagination-api
title: List Pagination API Spec
doc_type: reference
status: active
lang: de
summary: Vertrag für Cursor-Paginierung, Response-Envelope und Sortierung der Listen-Endpunkte /nodes, /accounts und /edges.
relations:
  - type: relates_to
    target: docs/reports/optimierungsstatus.md
  - type: relates_to
    target: docs/specs/contract.md
---

# List Pagination API Spec

Dieser Vertrag beschreibt die Paginierung der Listen-Endpunkte der API. Er ist
die Wahrheitsquelle für den Sortierungs- und Cursor-Vertrag (OPT-API-001).

Maßgeblich für die Implementierung sind:

- `apps/api/src/routes/query.rs` (Envelope, Cursor-Kodierung, `cursor_page`)
- `apps/api/src/routes/nodes.rs`, `apps/api/src/routes/accounts.rs`,
  `apps/api/src/routes/edges.rs` (Handler)

## Betroffene Endpunkte

| Endpunkt | Zusätzliche Filter |
|---|---|
| `GET /nodes` | `bbox=min_lng,min_lat,max_lng,max_lat` |
| `GET /accounts` | – |
| `GET /edges` | `source_id`, `target_id` |

## Paginierungsmodi

Es gibt zwei Modi. Der Modus wird ausschließlich über Query-Parameter gewählt;
die Wire-Form der Antwort hängt allein davon ab.

### Legacy-Modus (Default, rückwärtskompatibel)

- Aktiv, solange **weder** `pagination=cursor` **noch** ein `cursor`-Parameter
  gesetzt ist.
- Parameter: `limit`, `offset`.
- Antwort: **rohes JSON-Array** der Elemente (unveränderte historische Form).
- Bestehende Clients und Tests, die ein Array erwarten, bleiben unverändert.

Beispiel:

```http
GET /nodes?limit=50&offset=100
```

```json
[
  { "id": "n101", "title": "…", "location": { "lat": 53.5, "lon": 10.0 } }
]
```

### Cursor-Modus (opt-in)

- Aktiv, sobald `pagination=cursor` gesetzt ist **oder** ein nicht-leerer
  `cursor`-Parameter vorliegt.
- Parameter: `limit`, `cursor` (statt `offset`).
- Antwort: **Envelope** mit `items` und `page`.

Beispiel:

```http
GET /nodes?pagination=cursor&limit=50
```

```json
{
  "items": [
    { "id": "n001", "title": "…", "location": { "lat": 53.5, "lon": 10.0 } }
  ],
  "page": {
    "limit": 50,
    "next_cursor": "6e303530",
    "has_more": true
  }
}
```

Folgeseite:

```http
GET /nodes?cursor=6e303530&limit=50
```

## Query-Parameter

| Parameter | Modus | Typ | Default | Bedeutung |
|---|---|---|---|---|
| `limit` | beide | usize | 100 (`/nodes`, `/accounts`), 250 (`/edges`) | Maximale Anzahl pro Seite. Wird auf `MAX_PAGE_SIZE` (1000) begrenzt. |
| `offset` | Legacy | usize | 0 | Anzahl übersprungener Elemente. Nur im Legacy-Modus wirksam. |
| `pagination` | Cursor | string | – | `cursor` aktiviert den Cursor-Modus. |
| `cursor` | Cursor | string (opak) | – | Positionsanker der nächsten Seite. Aktiviert ebenfalls den Cursor-Modus. |

Ein nicht-numerisches oder negatives `limit`/`offset` ergibt `400 Bad Request`
(unverändert gegenüber dem bisherigen Verhalten).

## Response-Envelope (Cursor-Modus)

```text
{
  "items": [ <Element>, … ],
  "page": {
    "limit":       <usize>,           // effektives Limit nach MAX_PAGE_SIZE-Cap
    "next_cursor": <string | null>,   // Anker der nächsten Seite, null auf der letzten Seite
    "has_more":    <bool>             // true, wenn eine weitere Seite existiert
  }
}
```

Hinweise:

- `items` trägt dieselbe Element-Form wie das Legacy-Array
  (z. B. die öffentliche Projektion eines Accounts ohne `location`).
- Ein `total`-Zähler wird bewusst **nicht** geliefert: Clients benötigen für den
  Cursor-Walk nur `has_more`. Die aktuelle In-Memory-Implementierung kann die
  gefilterten Referenzen intern materialisieren und sortieren; der API-Vertrag
  legt aber keinen `total`-Zähler fest.

## Sortierungsvertrag

- Im Cursor-Modus werden Elemente **streng nach stabiler ID aufsteigend**
  sortiert — für `/nodes`, `/accounts` und `/edges` gleichermaßen.
- Die Sortierung ist unabhängig von der Lade-/Iterationsreihenfolge der
  In-Memory-Caches. Der Cursor stützt sich nie auf eine unsortierte
  Iterator-Reihenfolge.
- Filter (`bbox`, `source_id`, `target_id`) werden **vor** der Sortierung und
  Paginierung angewendet.

> Der Legacy-Modus behält seine bisherige Reihenfolge bei: `/nodes` und
> `/edges` liefern in Einfügereihenfolge (Datei-Reihenfolge), `/accounts` nach
> ID aufsteigend (BTreeMap). Stabile, dokumentierte ID-Sortierung gilt für den
> Cursor-Modus.

## Cursor-Vertrag

- Der Cursor ist ein **opakes** Token. Clients dürfen keine Struktur annehmen.
  (Implementierung: Lowercase-Hex der UTF-8-Bytes der zuletzt gelieferten ID.)
- Der Cursor kodiert die **zuletzt zurückgegebene ID** der aktuellen Seite und
  wirkt als exklusive untere Grenze: Die Folgeseite enthält ausschließlich
  Elemente mit echt größerer ID.
- Daraus folgt: Über einen stabilen Datenbestand hinweg sind aufeinanderfolgende
  Seiten **duplikat- und lückenfrei**.
- `has_more: false` und `next_cursor: null` markieren die letzte Seite.

### Fehlerverhalten

- Ein **ungültiger** Cursor (ungerade Länge, Nicht-Hex-Zeichen oder ungültiges
  UTF-8) ergibt **`400 Bad Request`**.
- Es wird niemals still falsch paginiert: Ein nicht dekodierbarer Anker führt zu
  einem expliziten Fehler, nicht zu einem stillen Fallback.
- Ein **leerer** `cursor` (`cursor=`) ist gültig und bedeutet „von vorn
  beginnen“ im Cursor-Modus.
- Ein syntaktisch gültiger Cursor, dessen ID nicht (mehr) existiert, ist kein
  Fehler: Die Paginierung setzt deterministisch bei der nächstgrößeren ID fort.

## Kompatibilität

- Der Legacy-`offset`/`limit`-Pfad bleibt unverändert erhalten und liefert
  weiterhin rohe Arrays.
- Cursor-Paginierung ist additiv und opt-in. Bestehende Integrationen brechen
  nicht.

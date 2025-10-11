# Weltgewebe Contract – Löschkonzept (Tombstone & Key-Erase)

**Status:** Draft v0.1 · **Scope:** Beiträge, Kommentare, Artefakte

## 1. Modell

- **Event-Sourcing:** Jede Änderung ist ein Event. Historie ist unveränderlich.
- **Inhalt:** Nutzinhalte werden _verschlüsselt_ gespeichert (objektbezogener Daten-Key).
- **Identität:** Nutzer signieren Events (Ed25519). Server versieht Batches mit Transparency-Log
  (Merkle-Hash + Timestamp).

## 2. Löschen („jederzeit möglich“)

- **Semantik:** _Logisch löschen_ durch `DeleteEvent` (Tombstone). Der zugehörige **Daten-Key wird verworfen**
  (Key-Erase).
- **Effekt:**
  - UI zeigt „Gelöscht durch Autor“ (Zeitstempel, optional Grund).
  - Inhaltstext/Binary ist selbst für Admins nicht mehr rekonstruierbar.
  - Event-Spur bleibt (Minimalmetadaten: Objekt-ID, Autor-ID Hash, Zeit, Typ).
- **Unwiderruflichkeit:** Key-Erase ist irreversibel. Wiederherstellung nur möglich, wenn der Autor einen
  **lokal gesicherten Key** besitzt und freiwillig re-upploadet.

## 3. Rechts-/Moderationsbezug

- **Rechtswidrige Inhalte:** Sofortiger **Takedown-Hold**: Inhalt unzugänglich; Forensik-Snapshot (Hash + Signatur)
  intern versiegelt. Öffentlich nur Meta-Ticket.
- **DSGVO:** „Löschen“ i. S. d. Betroffenenrechte = Tombstone + Key-Erase. Historische Minimaldaten werden als
  _technische Protokollierung_ mit berechtigtem Interesse (Art. 6 (1) f) geführt.

## 4. API-Verhalten

- `GET /items/{id}`:
  - bei Tombstone: `{ status:"deleted", deleted_at, deleted_by, reason? }`
  - kein Content-Payload, keine Wiederherstellungs-Links
- `DELETE /items/{id}`:
  - idempotent; erzeugt `DeleteEvent` + triggert Key-Erase.

## 5. Migrationshinweis

- Bis zur produktiven Verschlüsselung gilt: _Soft-Delete + Scrub_: Inhalt wird überschrieben (z. B. mit
  Zufallsbytes), Backups erhalten Löschmarker, Replikate werden re-keyed.

## 6. Telemetrie/Transparenz

- Wöchentliche Veröffentlichung eines **Transparency-Anchors** (Root-Hash der Woche).
- Öffentliche Statistik: Anzahl Tombstones, Takedown-Holds, mediane Löschzeit.

---

**Kurzfassung:** Löschen = _Tombstone_ (sichtbar) + _Key-Erase_ (Inhalt weg).
Historie bleibt integer, Privatsphäre bleibt gewahrt.

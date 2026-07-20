---
id: domain.vocabulary
title: Domänenvokabular
doc_type: reference
status: active
summary: Aktuelle Zuordnung der Produktbegriffe Garnrolle, Knoten und Faden zu den vorhandenen API- und Datenbegriffen.
relations:
  - type: relates_to
    target: docs/domain/modules.md
  - type: relates_to
    target: docs/datenmodell.md
  - type: relates_to
    target: docs/specs/contract.md
---

# Domänenvokabular

| Produktbegriff | Technik/API | Bedeutung | Aktueller Status |
|---|---|---|---|
| Garnrolle | Account, `/accounts` | genau ein persönlicher Ausgangspunkt je Account | produktiver PostgreSQL-Pfad belegt |
| Kartenstatus | `map_state` | `not_on_map`, `exact` oder `radius`; Eigenschaft der Garnrolle, kein Kontotyp | produktiv migriert; Legacy-`mode` bleibt Rollbackbrücke |
| Knoten | Node, `/nodes` | Ort, Kollektivgut, Ressource oder Vorhaben | API- und Browser-Schreibpfad produktiv belegt |
| Faden | Edge, `/edges` | serverseitig abgeleitete Beziehung zwischen Garnrollen und/oder Knoten | öffentliche Leseprojektion; Erzeugung durch fachliche Webungsaktionen |
| Gesprächsraum | Conversation, `/conversations` | Öffentlicher Diskussionsraum eines Knotens; weitere Gesprächstypen geplant | Knotengespräch produktiv |
| Beitrag | Message, `/conversations/{id}/messages` | Klartextbeitrag mit Autoren-Snapshot und Tombstone | Knotengespräch produktiv |
| Berechtigungsrolle | `role` (`gast`, `weber`, `admin`) | Gast webt eigene Inhalte; Weber pflegt zusätzlich gemeinschaftliche Inhalte; Admin moderiert | implementiert |

## Legacybegriffe

`RoN`, `mode=ron`, `mode=verortet` und `ron_flag` sind keine aktuellen
Produktbegriffe. Sie werden ausschließlich beim Lesen alter Daten interpretiert:
Jede RoN-Markierung ergibt privacy-sicher `map_state=not_on_map`. Neue Contracts,
API-Antworten und Schreibpfade erzeugen diese Felder nicht mehr.

Die nullable PostgreSQL-Spalte `mode` bleibt vorübergehend als Rollbackbrücke.
Sie darf erst nach einem eigenen Post-Cutover-Daten- und Rückfallbeleg entfernt werden.

`role` bedeutet nur Berechtigungsrolle. Historische Dokumente, die `role` als
Identitätsobjekt verwenden, sind nicht die aktuelle Fachsprache.

**`thread` ist als technischer Sammelbegriff verboten; eine Beziehung ist ein
`edge`, ein Diskussionsraum eine `conversation`.**

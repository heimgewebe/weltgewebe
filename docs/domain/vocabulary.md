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
| Garnrolle | Account, `/accounts` | genau ein persönlicher Ausgangspunkt je Account | Code und Migration implementiert; Produktionscutover offen |
| Kartenstatus | `map_state` | `not_on_map`, `exact` oder `radius`; Eigenschaft der Garnrolle, kein Kontotyp | Code und Migration implementiert; Produktionscutover offen |
| Knoten | Node, `/nodes` | Ort, Kollektivgut, Ressource oder Vorhaben | API implementiert; Browserpfad offen |
| Faden | Edge, `/edges` | Beziehung zwischen Garnrollen und/oder Knoten | API implementiert; Browserpfad offen |
| Gesprächsraum | Conversation, `/conversations` | Diskussions- oder Entscheidungsraum | Contract vorhanden, kein vollständiger Produktpfad |
| Beitrag | Message, `/conversations/{id}/messages` | Inhalt in einem Gesprächsraum | Contract vorhanden, kein vollständiger Produktpfad |
| Berechtigungsrolle | `role` (`gast`, `weber`, `admin`) | technische Autorisierung, nicht die Identität der Person | implementiert |

## Legacybegriffe

`RoN`, `mode=ron`, `mode=verortet` und `ron_flag` sind keine aktuellen
Produktbegriffe. Sie werden ausschließlich beim Lesen alter Daten interpretiert:
Jede RoN-Markierung ergibt privacy-sicher `map_state=not_on_map`. Neue Contracts,
API-Antworten und Schreibpfade erzeugen diese Felder nicht mehr.

Die nullable PostgreSQL-Spalte `mode` bleibt vorübergehend als Rollbackbrücke.
Sie darf erst nach einem belegten Produktionscutover entfernt werden.

`role` bedeutet nur Berechtigungsrolle. Historische Dokumente, die `role` als
Identitätsobjekt verwenden, sind nicht die aktuelle Fachsprache.

**`thread` ist als technischer Sammelbegriff verboten; eine Beziehung ist ein
`edge`, ein Diskussionsraum eine `conversation`.**

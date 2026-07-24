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
  - type: relates_to
    target: docs/reports/garnrolle-identity-cutover-proof.md
---

# Domänenvokabular

| Produktbegriff | Technik/API | Bedeutung | Aktueller Status |
|---|---|---|---|
| Garnrolle | Account, `/accounts` | genau ein persönlicher Ausgangspunkt je Account | produktiver PostgreSQL-Pfad belegt |
| Kartenstatus | `map_state` | `not_on_map`, `exact` oder `radius`; Eigenschaft der Garnrolle, kein Kontotyp | produktiv |
| Knoten | Node, `/nodes` | Ort, Kollektivgut, Ressource oder Vorhaben | API- und Browser-Schreibpfad produktiv belegt |
| Faden | Edge, `/edges` | serverseitig abgeleitete Beziehung zwischen Garnrollen und/oder Knoten | öffentliche Leseprojektion; Erzeugung durch fachliche Webungsaktionen |
| Gesprächsraum | Conversation, `/conversations` | Öffentlicher Diskussionsraum eines Knotens; weitere Gesprächstypen geplant | Knotengespräch produktiv |
| Beitrag | Message, `/conversations/{id}/messages` | Klartextbeitrag mit Autoren-Snapshot und Tombstone | Knotengespräch produktiv |
| Berechtigungsrolle | `role` (`gast`, `weber`, `admin`) | Gast webt und spricht mit; Weber pflegt zusätzlich fremde gemeinschaftliche Inhalte und besitzt formale Veto-/Stimmrechte; Admin moderiert | implementiert |

## Entfernte Begriffe

Die frühere Identität „Rolle ohne Namen“ und ihre technischen Felder wurden nach
belegtem Produktionscutover entfernt. Eine nicht öffentlich verortete Person ist
weiterhin eine Garnrolle mit `map_state=not_on_map`.

`role` bedeutet nur Berechtigungsrolle. Historische Dokumente, die `role` als
Identitätsobjekt verwenden, sind nicht die aktuelle Fachsprache.

**`thread` ist als technischer Sammelbegriff verboten; eine Beziehung ist ein
`edge`, ein Diskussionsraum eine `conversation`.**

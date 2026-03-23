---
id: domain.vocabulary
title: Domänenvokabular
doc_type: reference
status: active
canonicality: derived
summary: Zuordnung von Domänenbegriffen zu technischen API-Konzepten (node, role, edge, conversation, message).
related_docs:
  - docs/domain/modules.md
  - docs/datenmodell.md
  - docs/specs/contract.md
---
|Domäne|Deutsch|Technik/API|Bedeutung|
|---|---|---|---|
|node|Knoten|/nodes|Orte, Ideen, Ressourcen|
|role|Rolle|/roles|Berechtigungs- und Identitätskontext für Aktionen im Gewebe|
|edge|Faden|/edges|Graph-Beziehungen zwischen node/role (siehe [ADR-0043](../adr/0043-edge-vs-conversation.md))|
|conversation|Gesprächsraum|/conversations|Diskussions- / Entscheidungsräume (siehe [ADR-0043](../adr/0043-edge-vs-conversation.md))|
|message|Beitrag|/conversations/{id}/messages|Einzelner Inhalt in einer conversation|

---

**`thread` ist vollständig verboten; jede frühere Verwendung muss in `edge` oder `conversation` überführt werden.**

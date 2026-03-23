---
id: adr.0043-edge-vs-conversation
title: ADR-0043 — Edge vs. Conversation
doc_type: reference
status: active
summary: Entscheidung zur Abgrenzung von Edge- und Conversation-Entitäten im Domänenmodell.
relates_to:
  - docs/domain/vocabulary.md
  - docs/datenmodell.md
---
# ADR 0043: Begriffsvereinheitlichung edge vs conversation

## Status

accepted

## Problem

Der Begriff „thread“ war doppeldeutig (Graph ↔ Kommunikation) und erzeugte semantische Konflikte in Code, UI und API.

## Entscheidung

- Graph-Beziehungen heißen ausschließlich **edge** (DE: Faden).
- Gesprächsräume heißen ausschließlich **conversation** (DE: Gespräch / Gesprächsraum).
- **thread** ist im gesamten Weltgewebe verboten.
- Offizielle Domänenfamilie: `node`, `edge`, `conversation`, `message`.

## Konsequenzen

- **APIs**: `/edges`, `/conversations`, `/conversations/{id}/messages`, `/nodes`
- **Schemas** müssen die neuen Begriffe nutzen. Diese Entscheidung ist im Schema-Verzeichnis
  `contracts/domain/*.schema.json` konkretisiert.
- **Spätere DB-Migration**: `threads` → `conversations`
- **CI** wird künftig prüfen, dass „thread“ nicht mehr vorkommt.
- Alle **Dokumentationen** müssen perspektivisch auf die neue Domäne umgestellt werden.

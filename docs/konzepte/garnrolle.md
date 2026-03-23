---
id: konzepte.garnrolle
title: Garnrolle
doc_type: reference
status: deprecated
canonicality: derived
summary: Veraltetes Dokument. Bitte docs/konzepte/garnrolle-und-verortung.md nutzen.
related_docs:
  - docs/konzepte/garnrolle-und-verortung.md
---
# Garnrolle (Veraltet)

> **Hinweis:** Dieses Dokument ist **veraltet**. Das Modell wurde grundlegend vereinfacht.
> Bitte konsumiere ausschließlich das neue kanonische Konzept unter:
> [Weltgewebe – Garnrolle, Verortung und Rolle ohne Namen](./garnrolle-und-verortung.md)

Die alte Logik von `visibility` (public/private/approximate) und dem nachträglichen `ron_flag` (Rolle ohne Namen als Toggle) wurde durch ein striktes Zwei-Modi-Modell abgelöst:

- **Verortete Garnrolle** (mit exakter interner Adresse und einem Ungenauigkeitsradius für die öffentliche Anzeige)
- **Rolle ohne Namen (RoN)** (kanonischer Einstiegsmodus ohne Personenangaben und ohne individuelle Verortung/`location`)

Für die aktuellen technischen Schnittstellen und Entscheidungen siehe [ADR-0003](../adr/ADR-0003__privacy-ungenauigkeitsradius-ron.md).

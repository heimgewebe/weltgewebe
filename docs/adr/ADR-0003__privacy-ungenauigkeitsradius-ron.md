---
id: adr.ADR-0003__privacy-ungenauigkeitsradius-ron
title: ADR-0003 — Historisches Privacy- und Startzustandsmodell
doc_type: reference
status: superseded
summary: >
  Historische Entscheidung zum früheren Privacy- und Startzustandsmodell. Als
  Zielmodell abgelöst durch ADR-0009.
relations:
  - type: relates_to
    target: docs/konzepte/garnrolle-und-verortung.md
  - type: relates_to
    target: docs/adr/ADR-0009__garnrolle-verortung-sichtbarkeit.md
---

# ADR-0003 — Historisches Privacy- und Startzustandsmodell

Datum: 2025-09-13
Status: Superseded durch [ADR-0009](ADR-0009__garnrolle-verortung-sichtbarkeit.md)

## Revisionsentscheidung 2026-07-09

Diese Entscheidung ist als Zielmodell abgelöst.

Die frühere Modellierung trennte zu stark zwischen einem unverorteten
Startzustand und einer verorteten Garnrolle. Diese Trennung führte in Konzept,
UI und Contract zu einer unnötigen Identitätsmodus-Semantik.

Das neue Zielmodell ist einfacher:

> Jeder Account hat genau eine Garnrolle.

Verortung und öffentliche Sichtbarkeit sind Eigenschaften dieser Garnrolle. Sie
sind kein eigener Identitätsmodus.

## Historischer Nutzen

ADR-0003 bleibt nur relevant, um alte Codepfade, Fixture-Daten oder
Migrationslogik zu verstehen. Neue Produktarbeit, neue UI-Sprache und neue
Architekturentscheidungen folgen ADR-0009.

## Nicht mehr gültig als Zielmodell

Nicht mehr als Zielsemantik verwenden:

- getrennte Identitätsmodi für dasselbe Konto
- Privacy-Toggle als Account-Ontologie
- Startzustand als eigenständige Rollenart
- ungefähre Sichtbarkeit als impliziter Default

## Gültige Nachfolge

Siehe:

- [ADR-0009 — Garnrolle, Verortung und Sichtbarkeit](ADR-0009__garnrolle-verortung-sichtbarkeit.md)
- [Weltgewebe — Garnrolle, Verortung und Sichtbarkeit](../konzepte/garnrolle-und-verortung.md)

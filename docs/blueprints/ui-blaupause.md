---
id: ui-blaupause
title: Weltgewebe UI-Blaupause
doc_type: blueprint
status: canonical
canonicality: This document is the canonical source of truth for the UI architecture.
summary: Defines the core principles, layout, and interaction model for the Weltgewebe mobile-first UI.
related_docs:
  - docs/blueprints/ui-state-machine.md
  - docs/blueprints/ui-roadmap.md
---

# Weltgewebe – UI-Blaupause

⸻

## 1 Grundprinzip

Die UI besteht aus drei Hauptflächen:

* Karte
* Kontextpanel
* Aktionsleiste

Alle Funktionen entstehen aus Zuständen dieser drei Flächen.

⸻

## 2 Layout (Mobile-First)

Standardlayout

┌─────────────────────┐
│                     │
│                     │
│        KARTE        │
│                     │
│                     │
│                     │
├─────────────────────┤
│     Aktionsleiste   │
└─────────────────────┘

Kontextpanel erscheint als Bottom-Sheet.

⸻

## 3 Karte

Rolle

Die Karte ist die primäre Bühne des Gewebes.

Sie zeigt:
  •  Knoten
  •  Fäden
  •  Aktivität
  •  räumliche Struktur

⸻

Interaktionen

Navigation
  •  Drag → Karte verschieben
  •  Pinch → Zoom

Fokus

Tap → Objekt fokussieren

Kontextpanel öffnet sich.

⸻

Vorschau

Longpress → Kurzinfo


⸻

Neuer Knoten

Longpress auf Karte → Kompositionsmodus


⸻

## 4 Kontextpanel

Rolle

Das Kontextpanel ist der einzige Detailraum der UI.

Mobile:

Bottom-Sheet

Desktop:

rechte Seitenleiste


⸻

## 5 Objektmodi des Kontextpanels

⸻

### Modus A — Knoten

Ein Knoten ist ein Ort oder Anlass im Gewebe.

Struktur

Titel
Typ
Ort
Beschreibung

Tabs:

* Übersicht
* Gespräch
* Anträge
* Verlauf

⸻

Übersicht

Zeigt:
  •  Beschreibung
  •  beteiligte Garnrollen
  •  Aktivität

⸻

Gespräch

Gesprächsraum des Knotens.

⸻

Anträge

Bereich für:
  •  Vorschläge
  •  Abstimmungen
  •  Entscheidungen

⸻

Verlauf

Zeitliche Entwicklung des Knotens.

⸻

Regel

Knoten besitzen keine ausgehenden Fäden.

Nur Garnrollen können weben.

⸻

### Modus B — Garnrolle

Eine Garnrolle ist ein handelnder Akteur im Gewebe.

⸻

Struktur

Name
Kurzbeschreibung

Tabs:

* Profil
* Aktivität
* Knoten

⸻

Profil

Enthält:

* Beschreibung
* Kompetenzen
* Interessen
* vergemeinschaftete Güter

⸻

Vergemeinschaftete Güter

Ressourcen, die der Akteur der Gemeinschaft bereitstellt.

Beispiele:

* Werkzeuge
* Räume
* Wissen
* Zeit
* Material
* Infrastruktur

⸻

Aktivität

Liste:

* geknüpfte Knoten
* Beiträge
* Anträge
* Teilnahmen

⸻

Knoten

Knoten, an denen diese Garnrolle beteiligt ist.

⸻

Regel

Keine Fädenliste zwischen Garnrollen.

Fäden sind Handlungen im Gewebe.

⸻

### Modus C — Faden

Ein Faden ist eine konkrete Handlung oder Verbindung.

⸻

Struktur

Typ
Beschreibung

Abschnitte:

* Ursprung
* Ziel
* beteiligte Garnrollen
* Zeitlichkeit

⸻

## 6 Aktionsleiste

Position:

untere Bildschirmkante

⸻

Elemente

* Suche
* Neuer Knoten
* Filter

Hinweis: Der persönliche Kontoeinstieg befindet sich oben rechts über die Garnrolle, welche als Dropdown-Menü für alle Kontofunktionen (Einstellungen, Login, Logout) dient.

⸻

## 7 Kompositionsmodus

Start über:

Neuer Knoten
oder
Longpress auf Karte

⸻

Ablauf

1 Ort wählen
2 Knotentyp wählen
3 Beschreibung
4 veröffentlichen

Kontextpanel wird zum Editor.

⸻

## 8 Suche

Suche arbeitet gewebeweit.

Ergebnisse erscheinen:
  •  auf Karte
  •  im Kontextpanel

⸻

## 9 Systemzustände

Das System kennt drei globale Zustände.

Navigation
Fokus
Komposition

⸻

Navigation

Karte bewegen.

⸻

Fokus

Objekt ausgewählt.

Kontextpanel zeigt Details.

⸻

Komposition

Nutzer erstellt neuen Inhalt.

⸻

## 10 Desktop-Layout

┌───────────────┬───────────────┐
│               │               │
│               │ Kontextpanel  │
│               │               │
│     Karte     │               │
│               │               │
│               │               │
└───────────────┴───────────────┘

⸻

## Kernregeln der UI

* Mobile-first
* Karte ist primäre Bühne
* Kontextpanel ist einziger Detailraum
* nur Garnrollen können weben
* Knoten besitzen keine ausgehenden Fäden
* Garnrollen besitzen vergemeinschaftete Güter
* Fäden sind Handlungen, keine dauerhaften Beziehungen

⸻

## Weiterführende Dokumente

* [Weltgewebe UI State Machine](ui-state-machine.md)
* [Weltgewebe UI Roadmap](ui-roadmap.md)

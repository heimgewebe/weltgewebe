---
id: specs.governance-antraege
title: Anträge, Konsent, Veto und Abstimmung
summary: Kanonischer Produkt- und Ausführungsvertrag für die allgemeine Antragsmechanik und die Aufnahme von Gästen als Weber.
doc_type: specification
status: canonical
canonicality: normative
lifecycle_state: active
role: norm
organ: governance
owner: governance
last_reviewed: 2026-07-14
review_after: 2026-10-12
depends_on:
  - specs.garnrolle-knoten-faden
relations:
  - type: relates_to
    target: docs/domain/vocabulary.md
verifies_with:
  - apps/api/tests/api_governance_guards.rs
  - apps/api/tests/db_governance.rs
  - apps/web/src/lib/api/governance.test.ts
  - apps/web/tests/governance.spec.ts
---

# Anträge, Konsent, Veto und Abstimmung

## Grundsatz

Alles, was im Weltgewebe gemeinschaftlich verändert werden kann, soll grundsätzlich über denselben transparenten Antragsmechanismus disponibel sein. Der Antrag besitzt eine Informationsseite, einen Gesprächsraum, eine eindeutige Frist und eine dauerhaft nachvollziehbare Zustandsfolge.

Der erste produktive Antragstyp ist der **Weberantrag**. Er überführt einen Gast nach gemeinschaftlicher Prüfung in den Weberstatus und aktiviert damit genau eine Garnrolle.

## Gast und Weber

Ein neu registrierter Account beginnt als `gast`.

Ein Gast darf:

- das gesamte öffentliche Weltgewebe ansehen;
- suchen und filtern;
- Anträge, Vetos, Ergebnisse und Gesprächsräume lesen;
- den eigenen Weberstatus beantragen;
- den eigenen Gaststatus auflösen und das Weltgewebe vollständig verlassen.

Ein Gast darf keine Webungsaktion ausführen und hinterlässt daher keine reguläre Spur im Gewebe. Insbesondere darf er keine Knoten knüpfen, Gesprächsbeiträge verfassen, Vetos einlegen oder abstimmen.

Der Weberantrag und der selbst initiierte Gast-Austritt sind eng begrenzte Eintritts- beziehungsweise Austrittspfade. Sie verleihen keine weiteren Schreibrechte.

Ein Weber darf Webungsaktionen ausführen. Dazu gehören insbesondere:

- Knoten knüpfen;
- kommunizieren;
- Anträge stellen;
- begründete Vetos einlegen;
- abstimmen.

## Weberantrag

Der Gast löst die Aktion **Weberstatus beantragen** aus. Pro Gast darf höchstens ein offener Weberantrag bestehen. Der Antrag enthält:

- Antragsteller und Anzeigename;
- optionale Vorstellung oder Begründung;
- Status und vollständige Fristen;
- öffentliche Vetos;
- Stimmenzählung;
- Gesprächsraum;
- Ergebnis und Ausführungsstatus.

## Erste Phase: sieben Tage Konsent

Nach dem Stellen befindet sich der Antrag exakt sieben Tage im Status `consent`.

Bestehende Weber und Administratoren können in dieser Zeit ein begründetes Veto einlegen. Das Veto ist selbst eine Webungsaktion und muss einen nichtleeren Einwand enthalten.

Nach Ablauf gilt:

- **kein Veto:** Antrag wird angenommen;
- **mindestens ein Veto:** Antrag wechselt in die Abstimmungsphase.

Ein Veto lehnt den Antrag nicht ab. Es erzwingt Beratung und eine ausdrückliche Abstimmung.

## Zweite Phase: sieben Tage Gespräch und Abstimmung

Die zweite Phase schließt unmittelbar an das Ende der ersten Phase an und dauert exakt weitere sieben Tage. Die maximale reguläre Verfahrensdauer beträgt daher vierzehn Tage.

Jeder Weber und Administrator besitzt pro Antrag genau eine aktuelle Stimme. Diese Stimme kann bis zum Fristende geändert werden. Mögliche Werte sind:

- `ja`;
- `nein`;
- `enthaltung`.

Es gibt kein Quorum und keine Mindestbeteiligung.

Die einzige Entscheidungsregel lautet:

```text
Ja-Stimmen > Nein-Stimmen
```

Daraus folgt:

- mehr Ja als Nein: angenommen;
- Gleichstand: abgelehnt;
- 0:0: abgelehnt;
- Enthaltungen verändern den Vergleich nicht.

## Ausführung eines angenommenen Weberantrags

Die Annahme und die Aktivierung des Weberstatus sind ein einziger Datenbankvorgang. Innerhalb derselben PostgreSQL-Transaktion:

1. wechselt der Account von `gast` zu `weber`;
2. wird seine bisher ruhende Accountidentität als genau eine Garnrolle aktiviert;
3. wechselt der Antrag auf `accepted`.

Es darf weder ein angenommener Antrag ohne Weberstatus noch eine doppelte Garnrolle entstehen. Wiederholte Fristenauswertung muss idempotent sein.

Die Garnrolle beginnt im Zustand `not_on_map`. Der neue Weber entscheidet anschließend selbst, ob und wie er sie beschreibt und auf der Karte sichtbar macht.

## Fristenauswertung

Fristen werden serverseitig ausgewertet. Ein Browser ist weder Uhr noch Ausführungsinstanz.

Die API wertet fällige Anträge bei relevanten Zugriffen aus. Zusätzlich läuft im API-Prozess ein regelmäßiger Sweeper. Beide Wege benutzen dieselben gesperrten und idempotenten Datenbankübergänge.

Governance ist nur aktiv, wenn Account-Lesen und Account-Schreiben kanonisch aus PostgreSQL erfolgen. Fehlt diese Voraussetzung, antworten die Governance-Endpunkte fail-closed statt auf eine zweite Wahrheit auszuweichen.

## Gesprächsraum

Jeder Antrag besitzt einen öffentlichen, lesbaren Gesprächsraum.

- Gäste dürfen lesen.
- Weber und Administratoren dürfen während einer offenen Phase Beiträge verfassen.
- Nach Abschluss bleibt der Gesprächsraum als Verfahrensnachweis lesbar, aber geschlossen.

## Gast-Austritt

Ein Gast kann den eigenen Status vollständig auflösen. Der Gast-Austritt entfernt in einer Transaktion:

- die Gastidentität;
- eigene Weberanträge samt abhängigen Vetos, Stimmen und Gesprächsbeiträgen;
- Passkeys;
- Sitzungen.

Der Sonderpfad ist für Weber und Administratoren gesperrt. Deren Austritt berührt bereits entstandene gemeinschaftliche Spuren und benötigt daher einen eigenen, später zu spezifizierenden Governance- und Datenschutzprozess.

## Anträge-Oberfläche

Der Wurzelknopf **Gemeinsam** befindet sich im Kartenkopf oben mittig. Er fächert ausschließlich reale Governance-Sichten nach unten auf: alle Anträge, offene Konsentverfahren und laufende Abstimmungen. Das Stellen eines Antrags ist davon getrennt und erscheint als eigene Webungsaktion im unteren Werkzeugfächer. Die Oberfläche bietet:

- Liste aller Anträge;
- Status und verbleibende Zeit;
- Informationsseite;
- Vetos und Stimmenzahlen;
- ein aus den belegten Aktionen abgeleitetes Antragsgewebe mit nicht bearbeitbaren Fadenbündeln;
- Gesprächsraum;
- kontextabhängige Veto- und Abstimmungsaktionen;
- für Gäste den Weberantrag und den Gast-Austritt;
- einen direkten Einstieg `Antrag stellen` aus der Webungsebene des unteren Werkzeugfächers.

Die Oberfläche darf keine Rechte simulieren. Nicht erlaubte Aktionen sind serverseitig gesperrt, auch wenn ein Client manipuliert wird.

Das Antragsgewebe ist eine reine Leseprojektion auf der Informationsseite. Es zeigt den Antrag im Zentrum sowie Fadenbündel für Antragstellung, Vetos, Gesprächsbeiträge und Stimmen. Die exakten Zahlen stammen aus den Governance-Datensätzen; es werden weder öffentliche Faden-Schreibwege noch zusätzliche `domain_edges` erzeugt. Da Anträge keinen geografischen Ort besitzen, erscheint diese Projektion nicht auf der Karte.

## Erweiterung auf weitere Antragstypen

Das Zustandsmodell und die Fristen sind allgemein angelegt. Weitere Antragstypen dürfen später dieselbe Mechanik verwenden. Der aktuelle Datenbankvertrag lässt zunächst ausschließlich `weberantrag` zu, damit nicht spezifizierte Antragstypen nicht versehentlich produktiv werden.

## Nicht-Ziele dieses Schnitts

- kein Quorum;
- keine Mindestbeteiligung;
- keine gewichteten Stimmen;
- keine automatische Beförderung nach Zeit oder Aktivität;
- keine direkte Vergabe des Weberstatus durch einzelne Administratoren;
- keine zweite Governance-Wahrheit außerhalb PostgreSQL;
- noch kein allgemeiner Austrittsprozess für Weber.

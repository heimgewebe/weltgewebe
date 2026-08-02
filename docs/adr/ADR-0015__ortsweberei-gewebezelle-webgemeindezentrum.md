---
id: adr.ADR-0015__ortsweberei-gewebezelle-webgemeindezentrum
title: ADR-0015 — Ortsweberei, Gewebezelle und Webgemeindezentrum
doc_type: reference
status: active
summary: Entscheidet die Ortsweberei als soziale Gewebezelle mit genau einem bewusst verorteten Webgemeindezentrum als Karten-, Begegnungs- und Governance-Anker.
relations:
  - type: relates_to
    target: docs/adr/ADR-0011__foederierte-gewebezellen.md
  - type: relates_to
    target: docs/specs/ortsweberei-webgemeindezentrum.md
  - type: relates_to
    target: docs/specs/map-experience.md
  - type: relates_to
    target: docs/specs/governance-antraege.md
---

# ADR-0015 — Ortsweberei, Gewebezelle und Webgemeindezentrum

Datum: 2026-08-02
Status: accepted

## Kontext

Weltgewebe braucht einen verständlichen lokalen Mittelpunkt, an dem digitale
Selbstverwaltung, gemeinschaftliche Vorhaben und reale Begegnung zusammenfinden.
Die bisherige Antragsoberfläche versuchte Governance-Aktivitäten als eigenes
abgeleitetes Fadendiagramm darzustellen. Antragstellung, Vetos, Stimmen und
Gesprächsbeiträge sind jedoch Verfahrensdaten und keine räumlichen Beziehungen.
Die Darstellung wiederholte Zähler, ohne Zuständigkeit, Frist und nächsten
Verfahrensschritt klar zu machen.

Gleichzeitig entscheidet ADR-0011 autonome Gewebezellen als langfristiges
Skalierungsmodell. Es fehlte die fachliche Zuordnung zwischen lokaler
Gemeinschaft, betrieblicher Zelle und sichtbarem Kartenort.

## Entscheidung

### Begriffe

- Die **Ortsweberei** ist die lokale Gemeinschaft mit Mitgliedern, Regeln,
  Governance, Vorhaben und gemeinschaftlichen Mitteln.
- Die **Gewebezelle** ist ihre betriebliche und föderative Heimat mit eigener
  Primärwahrheit oder klarer Mandantenisolation.
- Das **Webgemeindezentrum** ist ihr sichtbarer Karten-, Zugangs- und
  Begegnungsanker.

Jede aktive Ortsweberei entspricht logisch genau einer Gewebezelle und besitzt
genau ein aktives Webgemeindezentrum. Ein Betreiber darf mehrere Gewebezellen
hosten; dadurch werden ihre fachlichen Identitäten nicht zusammengelegt.

### Standort

Das Webgemeindezentrum liegt nicht automatisch im geografischen Mittelpunkt.
Die Ortsweberei bestimmt bewusst einen Ort, an dem sie sich physisch treffen
kann oder künftig treffen möchte. Der Ort darf als gewünscht, vorläufig,
bestätigt oder vorübergehend nicht verfügbar ausgewiesen werden.

Private Wohnadressen werden nicht ohne ausdrückliche Zustimmung und klare
Zugangsbedingungen als Webgemeindezentrum veröffentlicht.

### Karten- und Governance-Semantik

Das Webgemeindezentrum ist ein dauerhafter Strukturknoten der Karte. Webrat,
Gewebekonto, örtlicher Gesprächsraum und lokale Vorhaben werden von dort aus
zugänglich, erhalten aber nicht automatisch konkurrierende Mittelpunktmarker.

Anträge bleiben eigenständige Entscheidungsobjekte. Ihre Informationsseite
zeigt Verfahrensart, Phase, Frist, nächsten möglichen Ausgang, Vetos,
Gesprächsbeiträge und erst in einer Abstimmungsphase die Stimmen. Kategorien und
Zähler werden nicht als Fäden gezeichnet.

Ein Faden darf Governance nur dann darstellen, wenn eine ausdrücklich
spezifizierte fachliche Handlung zwei echte, typisierte Endpunkte verbindet.
Eine bloße Antragstellung, ein Zähler oder eine Verfahrensphase erzeugt keine
Kartenbeziehung durch Interpretation der Benutzeroberfläche.

### Veränderung

Das Zentrum wird bei einem Ortswechsel nicht gelöscht und neu erfunden. Eine
Governance-Entscheidung verändert seine aktive Verortung; Identität, URLs und
Chronik bleiben stabil. Eine aktive Ortsweberei darf nicht ohne aktives Zentrum
bestehen. Bei Auflösung wird das Zentrum gemeinsam mit der Ortsweberei
archiviert.


## Fortschreibung: erste Instanz

Am 2. August 2026 wird die bisherige einzelne Gewebezelle als
`Ortsweberei Hamm` mit der stabilen Zellen-ID `hamm.weltgewebe.net` und dem
`Webgemeindezentrum Hammer Park` umgesetzt. Der erste Kartenanker liegt
ungefähr bei `53.5585, 10.0580` auf einer Grünfläche im Hammer Park. Die
fachliche Absicht ist ein tatsächlich nutzbarer gemeinsamer Treffpunkt; der
Runtimezustand bleibt zunächst `desired`.

Diese Fortschreibung entscheidet also Ort, Identitäten und Ausgangszustand. Sie
entscheidet ausdrücklich noch keine Reservierung, Genehmigung,
Barrierefreiheit, regelmäßige Nutzungszeit oder endgültige Feinposition. Eine
spätere Präzisierung oder Bestätigung erfolgt als chronologisch erhaltene
Governance-Änderung unter derselben Zentrum-ID.

## Alternativen

### Nur globale Antragslisten

Verworfen als Zielmodell. Eine globale Liste ist als zusätzliche Sicht sinnvoll,
würde aber die lokale Zuständigkeit und den realen Begegnungsort unsichtbar
machen.

### Webrat als eigener Kartenmittelpunkt

Verworfen. Der Webrat ist eine Funktion der Ortsweberei, kein zweites Zentrum
neben dem Webgemeindezentrum.

### Automatischer geografischer Mittelpunkt

Verworfen. Er könnte auf einem unzugänglichen oder sozial bedeutungslosen Ort
liegen und würde eine gemeinschaftliche Entscheidung vortäuschen.

### Antragsgewebe als Detailgrafik

Verworfen. Es setzt Verfahrenskategorien mit Beziehungen gleich und erzeugt
eine dekorative zweite Semantik neben den echten Fäden.

## Folgen

- Ortswebereien erhalten eine klare soziale, technische und räumliche Identität.
- Der Kartenmittelpunkt dient Orientierung und Begegnung, nicht Hierarchie.
- Die Antragsoberfläche wird prozessorientiert statt graphisch-abstrakt.
- Für die Runtime werden ein eigenes Ortsweberei-/Zentrum-Modell,
  Eindeutigkeitsregeln, Standortstatus, Governance-Zuordnung und Migrationen
  benötigt.
- Bestehende Gewebezellen-Verträge bleiben gültig; dieses ADR konkretisiert ihre
  lokale Produktgestalt.

## Nicht entschieden

- das endgültige Kartensymbol;
- Neben- oder temporäre Trefforte zusätzlich zum einen aktiven Zentrum;
- die technische Betreiberzuordnung einer später selbst gehosteten Zelle.

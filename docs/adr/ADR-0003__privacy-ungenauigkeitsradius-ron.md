---
id: adr.ADR-0003__privacy-ungenauigkeitsradius-ron
title: Adr 0003__Privacy Ungenauigkeitsradius Ron
doc_type: reference
status: active
canonicality: derived
summary: Automatisch hinzugefügtes Frontmatter.
---
# ADR-0003 — Privacy: Ungenauigkeitsradius & RoN-Identitätsmodus (v2)

Datum: 2025-09-13
Status: Accepted

## Kontext

Die Garnrolle ist am Wohnsitz verortet (Residence-Lock). Die Karte und die Fäden sollen ortsbasierte
Sichtbarkeit ermöglichen, ohne den exakten Wohnsitz preiszugeben - sofern dies explizit vom Nutzer gewünscht
ist.

Bisher wurde die Rolle ohne Namen (RoN) teilweise als nachträglicher Privacy-Toggle behandelt. Dies führte zu
ontologischen Widersprüchen (z. B. wenn eine Adresse vorhanden war, der Toggle aber umgelegt wurde) und einem
zu komplexen Modell mit halbgaren Zuständen.

## Entscheidung

Das Konzept wird vereinfacht und kanonisiert. Es gibt nun genau zwei klare Identitätsmodi:

1) **Verortete Garnrolle**
   Wer seine genaue Adresse und Personenangaben ergänzt, vollzieht den Übergang zur verorteten Garnrolle.
   Der Nutzer kann die öffentliche Genauigkeit seiner Garnrolle über einen **Ungenauigkeitsradius** (Meter) selbst
   einstellen. Die **öffentliche Anzeige** nutzt eine **ungenaue Position innerhalb dieses Radius**.
   Der Ungenauigkeitsradius steuert *nur* die öffentliche Anzeige, nicht die interne Verortungswahrheit.

2) **Rolle ohne Namen (RoN) als kanonischer Startzustand und Identitätsmodus**
   Alle neu erstellten Nutzerkonten starten im System im RoN-Modus als sicherem Initialzustand.
   Dieser Startzustand ist nicht als bewusste Entscheidung oder alternativer Einstiegsweg zu interpretieren, sondern als vorläufiger Zustand.
   RoN ist *kein* bloßer nachträglicher Privacy-Toggle für verortete Garnrollen, sondern ein eigenständiger, kanonischer Identitätsmodus.
   Wer keine Verortung vornimmt, verbleibt dauerhaft im RoN-Zustand.

- Die Verortung ist ein expliziter späterer Übergang, kein impliziter Default und keine gleichrangige Anfangswahl.

## Alternativen

Weitere Modi (z. B. "nur Stadtteil", "ohne Hausnummer") werden **nicht** eingeführt, da diese Zwischenstufen zu viele Grenzfälle und Widersprüche in der Dokumentation und Implementierung erzeugen.
Auch Vertrauensbewertungen, Trust-Scores oder Pflichtverifikationen als Grundvoraussetzung werden verworfen, da Vertrauen ausschließlich sozial entstehen soll.

## Konsequenzen

- Die UI darf keinen verpflichtenden Zwei-Wege-Onboarding-Screen erzwingen.
- Stattdessen muss der aktuelle Identitätszustand sichtbar gemacht werden.
- Der Übergang zu einer verorteten Garnrolle muss als bewusste Handlung gestaltet werden.
- **Einfaches UI**: Alle neu erstellten Nutzerkonten starten im RoN-Startzustand. Die UI macht den aktuellen Zustand sichtbar. Die Verortung wird als bewusster Übergang angeboten. Für verortete Garnrollen existiert ein **Slider** (Meter) für den Ungenauigkeitsradius.
- **Konsistente Darstellung**: Verortete Garnrollen werden am exakten oder (bei Radius > 0) verfremdeten Ort angezeigt. RoN-Zuordnungen haben keine individuelle öffentliche Verortung (`public_pos = None`), sind aber nicht ortlos. Ihre öffentliche Wirksamkeit (das Weben von Fäden) erfolgt kollektiv über die Rolle ohne Namen des jeweiligen Stadtteils (technisch eine spätere Gruppierungs-/Darstellungsoption im Zentrum).
- **Einfacher Contract**: Der Contract trägt nur noch die Modusunterscheidung (Verortet vs. RoN) und den Ungenauigkeitsradius.

- **Legacy-Kompatibilität:** Alte Datensätze mit `visibility = "private"` werden sicher in das neue System projiziert. Sie werden auf `mode = "verortet"` gemappt (behalten ihre individuelle Identität und interne Adresse), erhalten aber strikt keine öffentliche Position (`public_pos = None`), um nicht versehentlich ihre alte Privatsphäre-Stufe zu verletzen.
- **Runtime-Mapping vs. Zielzustand:** Die Schema-Invarianten (`type="garnrolle" => mode="verortet"`) definieren den strikten kanonischen Zielzustand. Das API-Runtime-Mapping toleriert Legacy-Daten und projiziert diese sicher in diesen Zielzustand.

## Schnittstellen

- **API/Modell**
  - Accounts haben ein Modus-Feld (`mode`: `verortet` oder `ron`).
  - `location` existiert intern nur für `verortete` Rollen.
  - `radius_m` steuert die öffentliche Anzeige für verortete Rollen.
- **Views**
  - intern: exakte Position (nur für verortete Rollen).
  - öffentlich: public view zeigt bei `mode=verortet` die Position gemäß Radius, und bei `mode=ron` keine individuelle Position (`public_pos` ist leer), sondern eine kollektive Stellvertretung über den Stadtteil.

## Rollout

- **Web**: Start-UI anpassen (RoN als kanonischer Startzustand), Zwei-Wege-Screen entfernen, RoN-Toggle aus den nachträglichen Privatsphäre-Einstellungen entfernen, Slider für verortete Rollen beibehalten.
- **API**: Schema-Anpassung, Ersetzung von `visibility` und dem RoN-Toggle durch ein modusbasiertes Modell (`mode: "verortet" | "ron"`).

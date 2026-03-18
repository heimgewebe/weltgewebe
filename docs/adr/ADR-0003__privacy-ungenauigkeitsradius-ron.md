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

Das Konzept wird vereinfacht und kanonisiert. Es gibt nun genau zwei klare Identitätsmodi, die direkt aus der Accounterstellung folgen:

1) **Verortete Garnrolle**
   Wer eine genaue Adresse angibt, erhält eine verortete Garnrolle.
   Der Nutzer kann die öffentliche Genauigkeit seiner Garnrolle über einen **Ungenauigkeitsradius** (Meter) selbst
   einstellen. Die **öffentliche Anzeige** nutzt eine **ungenaue Position innerhalb dieses Radius**.
   Der Ungenauigkeitsradius steuert *nur* die öffentliche Anzeige, nicht die interne Verortungswahrheit.

2) **Rolle ohne Namen (RoN) als kanonischer Identitätsmodus**
   Wer keine Personenangaben macht, wird vorab informiert, dass er der Rolle ohne Namen zugeordnet wird.
   RoN ist *kein* bloßer nachträglicher Privacy-Toggle für verortete Garnrollen, sondern ein eigenständiger, kanonischer Identitätsmodus, der aus fehlenden Personenangaben folgt.

## Alternativen

Weitere Modi (z. B. "nur Stadtteil", "ohne Hausnummer") werden **nicht** eingeführt, da diese Zwischenstufen zu viele Grenzfälle und Widersprüche in der Dokumentation und Implementierung erzeugen.
Auch Vertrauensbewertungen, Trust-Scores oder Pflichtverifikationen als Grundvoraussetzung werden verworfen, da Vertrauen ausschließlich sozial entstehen soll.

## Konsequenzen

- **Einfaches UI**: Zwei Wege bei der Accounterstellung ("genaue Adresse" vs. "keine Angaben"). Für verortete Garnrollen existiert ein **Slider** (Meter) für den Ungenauigkeitsradius.
- **Konsistente Darstellung**: Verortete Garnrollen werden am exakten oder (bei Radius > 0) verfremdeten Ort angezeigt. RoN-Zuordnungen haben keine individuelle öffentliche Position (`public_pos = None`). Eine Gruppierung im Zentrum des jeweiligen Stadtteils ist eine spätere Darstellungsoption (noch nicht implementiert).
- **Einfacher Contract**: Der Contract trägt nur noch die Modusunterscheidung (Verortet vs. RoN) und den Ungenauigkeitsradius.

## Schnittstellen

- **API/Modell**
  - Accounts haben ein Modus-Feld (`mode`: `verortet` oder `ron`).
  - `location` existiert intern nur für `verortete` Rollen.
  - `radius_m` steuert die öffentliche Anzeige für verortete Rollen.
- **Views**
  - intern: exakte Position (nur für verortete Rollen).
  - öffentlich: public view zeigt bei `mode=verortet` die Position gemäß Radius, und bei `mode=ron` keine individuelle Position (`public_pos` ist leer).

## Rollout

- **Web**: Accounterstellung anpassen, RoN-Toggle aus den nachträglichen Privatsphäre-Einstellungen entfernen, Slider beibehalten.
- **API**: Schema-Anpassung, Ersetzung von `visibility` und dem RoN-Toggle durch ein modusbasiertes Modell (`mode: "verortet" | "ron"`).

---
id: konzepte.garnrolle-und-verortung
title: "Weltgewebe – Garnrolle, Verortung und Rolle ohne Namen"
doc_type: concept
status: active
canonicality: canonical
summary: "Kanonisches Konzept für Garnrolle, Verortung, Ungenauigkeitsradius und Rolle ohne Namen bei der Accounterstellung im Weltgewebe."
---

# Weltgewebe – Garnrolle, Verortung und Rolle ohne Namen

## 1. Dialektische Grundlegung

### These

Vertrauen im Weltgewebe entsteht sozial:
durch Zeit, Wiedererkennung und tatsächliche Nachbarschaftsinteraktion.
Das System darf dieses Vertrauen weder berechnen noch simulieren.

### Antithese

Ohne jede formale Struktur drohen Unklarheit, Täuschung und ein Mangel an lokaler Anschlussfähigkeit.
Ein rein offenes System ohne Verortungslogik würde den nachbarschaftlichen Kern des Weltgewebes schwächen.

### Synthese

Das Weltgewebe setzt weder auf Vertrauensbewertung noch auf Verifikationszwang,
sondern auf eine einfache Identitäts- und Verortungsordnung:

- genaue Adresse angegeben → verortete Garnrolle
- keine Personenangaben gemacht → Zuordnung zur Rolle ohne Namen
- Ungenauigkeitsradius → steuert nur die öffentliche Darstellung

So bleibt die Logik einfach, sichtbar und sozial verständlich.

---

## 2. Begriffe

### Garnrolle

**Garnrolle** ist die persistente Rolle eines Akteurs im Weltgewebe.

Im Weltgewebe ist die Garnrolle die Spule, von der Fäden ausgehen.

Eigenschaften:

- persistent
- wiedererkennbar
- handlungsfähig
- entweder verortet oder der Rolle ohne Namen zugeordnet

---

### Verortung

**Verortung** bezeichnet die Bindung einer Garnrolle an einen konkreten Wohnsitz.

Im Weltgewebe bedeutet Verortung:
> Eine Garnrolle ist intern an einen realen Wohnsitz gebunden.

---

### Rolle ohne Namen (RoN)

**RoN** bedeutet **Rolle ohne Namen**.

RoN ist kein bloßer Tarnmodus, sondern ein eigenständiger Identitätsmodus für Nutzer,
die keine Personenangaben machen.

---

### Ungenauigkeitsradius

**Ungenauigkeitsradius** bezeichnet den Radius in Metern, innerhalb dessen die öffentliche
Position einer verorteten Garnrolle angezeigt wird.

Er betrifft nur die **öffentliche Anzeige**, nicht die interne Verortung.

---

## 3. Ontologischer Kern

Grundsatz:

> Eine Garnrolle ist entweder
>
> 1. an einen konkreten Wohnsitz verortet
> oder
> 2. der Rolle ohne Namen zugeordnet.

Diese Unterscheidung ergibt sich aus den Angaben bei der Accounterstellung.

Das Weltgewebe kennt damit zwei klare Grundmodi:

- **verortete Garnrolle**
- **Rolle ohne Namen**

Teilmodelle mit halber Adressschärfe werden bewusst verworfen.

---

## 4. Accounterstellung

Bei der Accounterstellung entscheidet die Eingabe des Nutzers über den Modus.

### 4.1 Verortete Garnrolle

Wenn ein Nutzer die erforderlichen Personen- und Adressangaben macht, erhält er eine verortete Garnrolle.

Minimal dafür erforderlich:

- Personenangaben
- genaue Adresse

Zusätzlich einstellbar:

- Ungenauigkeitsradius

Default:

- Ungenauigkeitsradius = 0 m

Bedeutung:

- intern: exakte Verortung am Wohnsitz
- öffentlich: Anzeige gemäß Ungenauigkeitsradius

---

### 4.2 Rolle ohne Namen (RoN)

Wenn ein Nutzer **keine Angaben zur Person** macht, wird er der **Rolle ohne Namen** zugeordnet.

Dabei gilt:

- kein Name
- keine Personenangaben
- keine Adresse
- keine individuelle Verortung

Vor Abschluss der Accounterstellung wird der Nutzer explizit informiert:

> Wenn du keine Angaben zu deiner Person machst, wirst du der Rolle ohne Namen zugeordnet.
> Deine Identität erscheint dann nicht als individuell verortete Garnrolle, sondern als Teil der
> Rolle ohne Namen im Zentrum deines Stadtteils.

RoN ist damit:

- ein bewusster Einstiegsmodus
- keine Strafe
- keine verdeckte Anonymisierung
- keine bloße nachträgliche Privacy-Einstellung

---

## 5. Anzeige-Logik

Die Anzeige folgt aus den gemachten Angaben.

### Fall A: Genaue Adresse angegeben

Ergebnis:

- verortete Garnrolle
- öffentliche Anzeige:
  - exakt bei 0 m
  - ungenauer bei Radius > 0 m

### Fall B: Keine Personenangaben gemacht

Ergebnis:

- Zuordnung zur Rolle ohne Namen
- öffentliche Anzeige:
  - nicht individuelle Adresse
  - stattdessen Rolle ohne Namen im Zentrum des Stadtteils

---

## 6. Sichtbarkeit und Wahrheit

Zentrale Trennung:

| Ebene | Bedeutung |
|---|---|
| interne Verortung | exakte Wohnsitzbindung einer verorteten Garnrolle |
| öffentliche Anzeige | sichtbare Position gemäß Ungenauigkeitsradius oder RoN-Zentrum |

Prinzip:

> Die Wahrheit der Verortung ist intern.
> Die Sichtbarkeit ist öffentlich gestaltet.

Für RoN gilt:

- keine individuelle interne Wohnsitzverortung im Sinne einer öffentlichen Rolle
- öffentliche Darstellung über die Rolle ohne Namen

---

## 7. Vertrauen

Vertrauen ist kein Systemwert.

Es entsteht durch:

1. Wiedererkennbarkeit
2. Ko-Präsenz
3. Interaktion
4. Zeit

Das Weltgewebe:

- berechnet kein Vertrauen
- speichert keine Reputation
- vergibt keine Scores

Stattdessen erzeugt es eine soziale Asymmetrie:

- verortete Garnrollen haben höhere lokale Anschlussfähigkeit
- RoN erlaubt Teilnahme ohne individuelle Verortung, aber mit geringerer persönlicher Wiedererkennbarkeit

Diese Differenz ist keine Sanktion, sondern Folge der gewählten Sichtbarkeit.

---

## 8. Architekturprinzip

Das Weltgewebe implementiert bewusst nicht:

- keine algorithmische Vertrauensbewertung
- keine soziale Punktelogik
- keine automatische Verdachtslogik
- keine Pflichtverifikation als Grundvoraussetzung

Es implementiert stattdessen:

- klare Modusunterscheidung
- klare Anzeige-Logik
- klare soziale Konsequenzen ohne Systemstrafe

---

## 9. Risiken und Grenzen

### Risiken

- Täuschung bleibt möglich
- RoN kann persönliche Wiedererkennbarkeit reduzieren
- geringe Aktivität verhindert Vertrauensbildung unabhängig vom Modell

### Nutzen

- einfache Logik
- klare Accounterstellung
- keine versteckte Bewertung
- Wahrung des nachbarschaftlichen Kerns
- Privacy ohne Ontologiebruch

---

## 10. Implikationen für UI und API

### UI

Die UI der Accounterstellung muss klar zwischen zwei Wegen unterscheiden:

1. **Verortete Garnrolle erstellen**
   - Personenangaben
   - genaue Adresse
   - Ungenauigkeitsradius einstellen

2. **Ohne Personenangaben fortfahren**
   - Hinweis vor Abschluss:
     Zuordnung zur Rolle ohne Namen im Zentrum des Stadtteils

Die UI darf RoN nicht mehr primär als bloßen Privacy-Toggle erklären.

---

### API

Die API muss diese Unterscheidung ausdrücken können:

- verortete Garnrolle
- RoN-Zuordnung

Der Ungenauigkeitsradius bleibt ein eigener Parameter der öffentlichen Anzeige.

---

## 11. Basale Contract-Folgen

Der Contract soll basal bleiben.

Er muss nur die Kernunterscheidung tragen:

- ob eine Rolle verortet ist
- ob sie der Rolle ohne Namen zugeordnet ist
- welcher Ungenauigkeitsradius für die öffentliche Anzeige gilt

Nicht in den basalen Contract gehören:

- Vertrauenswert
- Bewertungslogik
- komplexe Zwischenstufen der Adressgranularität

---

## 12. Essenz

Das Weltgewebe kennt künftig zwei klare Modi:

- **verortete Garnrolle**
- **Rolle ohne Namen**

Die Entscheidung ergibt sich aus den Angaben bei der Accounterstellung.

Der Ungenauigkeitsradius verfeinert nur die öffentliche Anzeige verorteter Garnrollen.
Vertrauen entsteht nicht durch das System, sondern durch die Nachbarschaft.

---

## 13. Unsicherheitsgrad

0.12

Ursachen:

- empirische soziale Dynamiken bleiben offen
- spätere technische Umsetzung kann neue Randfälle sichtbar machen

---

## 14. Interpolationsgrad

0.14

Annahmen:

- RoN wird als eigenständiger Einstiegsmodus kanonisiert
- Stadtteilzentrum bleibt die öffentliche Raumlogik für RoN

---

## 15. Schlussbemerkung

Das Weltgewebe fragt nicht:
„Wie vertrauenswürdig bist du?“

Es fragt:
„Willst du hier als verortete Person erscheinen oder ohne Namen teilnehmen?“

Und die Nachbarschaft beantwortet den Rest mit der einzigen Währung, die dafür taugt:
Zeit.

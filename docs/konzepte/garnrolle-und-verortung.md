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

Das Weltgewebe kennt damit zwei klare Grundmodi:

- **verortete Garnrolle**
- **Rolle ohne Namen**

Teilmodelle mit halber Adressschärfe werden bewusst verworfen.

---

## 4. Startzustand und Übergang (kanonisch)

Alle neu erstellten Accounts beginnen im System im **Startmodus**.

Technisch entspricht dieser dem Modus **Rolle ohne Namen (RoN)**.

Wichtig:
Dieser Zustand ist **keine bewusste Entscheidung**, sondern ein
vorläufiger, sicherer Initialzustand ohne personenbezogene Angaben.

Der Startmodus dient dazu:

- Einstiegshürden zu minimieren
- sofortige Teilnahme zu ermöglichen
- keine impliziten Entscheidungen zu erzwingen

### Übergang zu verorteter Garnrolle

Die Erstellung einer verorteten Garnrolle ist ein
**bewusster Transformationsschritt**.

Er erfordert zwingend:

- Personenangaben
- eine genaue Adresse

Optional:

- Ungenauigkeitsradius für die öffentliche Anzeige

Der Übergang ist:

- jederzeit möglich
- explizit
- nicht ohne semantische Verschiebung reversibel

### Semantische Klarstellung

RoN ist:

- kein „anonymer Modus“
- keine reduzierte Version der verorteten Garnrolle

RoN ist:
→ eine eigenständige Rolle im System ohne individuelle räumliche Verankerung

---

## 5. Start und Ergänzung von Angaben

Der Account beginnt im Startzustand RoN.

### 5.1 Rolle ohne Namen (RoN) als Startzustand

Alle starten in der Rolle ohne Namen. Wer keine Verortung ergänzt, bleibt dauerhaft dort.

Im Startzustand gilt für RoN:

- noch kein Name hinterlegt
- noch keine Personenangaben ergänzt
- noch keine Adresse angegeben
- noch keine individuelle Verortung

Wird dies nicht geändert, wird RoN zum dauerhaften Modus.

RoN ist damit:

- der kanonische Startmodus
- ein valider Dauerzustand, keine Strafe
- keine verdeckte Anonymisierung
- keine bloße nachträgliche Privacy-Einstellung

---

### 5.2 Übergang zur verorteten Garnrolle

Wenn Personen- und Adressangaben ergänzt werden, erfolgt ein expliziter Übergang zur verorteten Garnrolle.

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

## 6. Anzeige-Logik

Die Anzeige folgt aus dem aktuellen Modus der Garnrolle.

### Fall A: Verortung vorgenommen

Ergebnis:

- verortete Garnrolle
- öffentliche Anzeige:
  - exakt bei 0 m
  - ungenauer bei Radius > 0 m

### Fall B: Keine Verortung vorgenommen (im RoN-Startmodus verblieben)

Ergebnis:

- Verbleib in der Rolle ohne Namen
- öffentliche Anzeige:
  - nicht individuelle Adresse
  - stattdessen Rolle ohne Namen. Keine individuelle öffentliche Verortung, sondern kollektive Stellvertretung (Weben von der RoN des Stadtteils aus).

---

## 7. Sichtbarkeit und Wahrheit

### 7.1 Kanonisches Modell vs. Legacy-Kompatibilität

Das oben beschriebene Zwei-Modi-Modell (verortet vs. RoN) ist der kanonische Zielzustand.
Für bestehende Datensätze aus dem alten `visibility`-Modell gilt eine sichere Kompatibilitätsregel:
Alte `private`-Accounts werden **nicht** ontologisch zu RoN umgedeutet. Sie behalten ihre individuelle Garnrollen-Semantik und interne Verortung (mode = `verortet`), jedoch wird ihre öffentliche individuelle Position strikt unterdrückt (`public_pos = None`), um ihren alten Privatsphäre-Wunsch zu respektieren, bis der Nutzer explizit in das neue Modell migriert.


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

## 8. Vertrauen

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

## 9. Architekturprinzip

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

## 10. Risiken und Grenzen

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

## 11. Implikationen für UI und API

### UI

Die UI darf keinen Zwei-Wege-Onboarding-Screen erzwingen.

- Der Startzustand (RoN) wird sichtbar kommuniziert.
- Die Verortung (Eingabe von Personenangaben, genauer Adresse und Ungenauigkeitsradius) wird als bewusster späterer Transformationsschritt angeboten.

Die UI darf RoN nicht mehr primär als bloßen Privacy-Toggle erklären, sondern als den sicheren Initialzustand.

---

### API

Die API muss diese Unterscheidung ausdrücken können:

- verortete Garnrolle
- RoN-Zuordnung

Der Ungenauigkeitsradius bleibt ein eigener Parameter der öffentlichen Anzeige.

---

## 12. Basale Contract-Folgen

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

## 13. Essenz

Das Weltgewebe kennt zwei klare Modi:

- **verortete Garnrolle**
- **Rolle ohne Namen**

Alle beginnen in der Rolle ohne Namen. Die Verortung ist ein expliziter Übergang durch Ergänzung der Angaben.

Der Ungenauigkeitsradius verfeinert nur die öffentliche Anzeige verorteter Garnrollen.
Vertrauen entsteht nicht durch das System, sondern durch die Nachbarschaft.

---

## 14. Unsicherheitsgrad

0.12

Ursachen:

- empirische soziale Dynamiken bleiben offen
- spätere technische Umsetzung kann neue Randfälle sichtbar machen

---

## 15. Interpolationsgrad

0.14

Annahmen:

- RoN wird als eigenständiger Einstiegsmodus kanonisiert
- Stadtteilzentrum bleibt die öffentliche Raumlogik für RoN

---

## 16. Schlussbemerkung

Das Weltgewebe fragt nicht:
„Wie vertrauenswürdig bist du?“

Es bietet an:
„Du kannst hier als verortete Person erscheinen, oder sicher in der Rolle ohne Namen bleiben.“

Und die Nachbarschaft beantwortet den Rest mit der einzigen Währung, die dafür taugt:
Zeit.

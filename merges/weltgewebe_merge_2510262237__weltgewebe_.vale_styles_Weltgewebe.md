### 📄 weltgewebe/.vale/styles/Weltgewebe/GermanComments.yml

**Größe:** 167 B | **md5:** `649b1c9d66791244009507d8cc6307ba`

```yaml
extends: existence
message: "TODO/FIXME gefunden: Ergänze Kontext oder verlinke ein Ticket."
level: suggestion
ignorecase: true
scope: raw
tokens:
  - TODO
  - FIXME
```

### 📄 weltgewebe/.vale/styles/Weltgewebe/GermanProse.yml

**Größe:** 189 B | **md5:** `4767fb769bf96c61801a9496667b15f9`

```yaml
extends: substitution
level: suggestion
ignorecase: true
message: "Begriff prüfen: '%s' – konsistente Schreibweise wählen."
swap:
  "z.B.": "z. B."
  "bspw.": "z. B."
  "u.a.": "u. a."
```

### 📄 weltgewebe/.vale/styles/Weltgewebe/WeltgewebeStyle.yml

**Größe:** 1 KB | **md5:** `e4ea56a6673b4c7536ea8fdadc31f264`

```yaml
extends: existence
level: warning
scope: text
ignorecase: false
description: "Weltgewebe-Redaktionsstil: neutrale Sprache, konsistente Begriffe und Zahlenschreibweisen."
tokens:
  - pattern: "\\b[\u00C0-\u024F\w]+(?:\\*|:|_)innen\\b"
    message: "Vermeide Gender-Stern/-Gap – wähle eine neutrale Formulierung."
  - pattern: "\\b[\u00C0-\u024F\w]+/[\u00C0-\u024F\w]+innen\\b"
    message: "Vermeide Slash-Genderformen – nutze eine neutrale Bezeichnung."
  - pattern: "\\bRolle[nr]?/(?:und|oder)?Funktion\\b"
    message: "Begriffe nicht vermischen: 'Rolle' und 'Funktion' haben unterschiedliche Bedeutungen."
  - pattern: "\\bFunktion(en)?\\b"
    message: "Prüfe den Begriff: Meinst du die Glossar-'Rolle'? Rolle ≠ Funktion."
  - pattern: "\\bThread(s)?\\b"
    message: "Glossarbegriff verwenden: Statt 'Thread' bitte 'Faden'."
  - pattern: "\\bNode(s)?\\b"
    message: "Glossarbegriff verwenden: Statt 'Node' bitte 'Knoten'."
  - pattern: "\\bYarn\\b"
    message: "Glossarbegriff verwenden: Statt 'Yarn' bitte 'Faden' oder 'Garn'."
  - pattern: "\\bGarn\\b"
    message: "Prüfe den Kontext: 'Faden' ist der Standardbegriff, 'Garn' nur bei Verzwirnung."
  - pattern: "\\bKnotenpunkt\\b"
    message: "Glossarbegriff verwenden: Statt 'Knotenpunkt' bitte 'Knoten'."
  - pattern: "\\b\\d{4,}\\b"
    message: "Zahlenschreibweise prüfen: Tausender trennen (z. B. 10 000) oder Zahl ausschreiben."
  - pattern: "\\b\\d+[kK]\\b"
    message: "Zahl abkürzungen vermeiden: Schreibe z. B. '1 000' statt '1k'."
```


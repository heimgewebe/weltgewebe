---
id: docs.policies.architecture-critique
title: "Architekturkritik-Skill: weltgewebe.architecture.critique.v3"
doc_type: policy
status: draft
summary: >
  Kognitives Protokoll für strukturelle Architekturkritik im Weltgewebe-Kontext.
  Definiert Analysesequenz, Prüfachsen, Interpolationsregeln und Pflichtstruktur
  für Agenten-gestützte Architekturreviews.
relations:
  - type: depends_on
    target: docs/policies/agent-reading-protocol.md
  - type: relates_to
    target: repo.meta.yaml
  - type: relates_to
    target: docs/weltgewebe-agenten-manifest.md
  - type: relates_to
    target: docs/konzepte/garnrolle-und-verortung.md
---

# weltgewebe.architecture.critique.v3

---

## 0. Meta-Definition

Architekturkritik = Prüfung der Denkstruktur, nicht der Implementierungsdetails.

Bewertet wird:
- nicht primär, ob etwas funktioniert
- sondern, ob es sinnvoll ist, dass es so gebaut wird
- und ob es so gebaut wird, wie beschlossen wurde

Dieses Skill operiert im Rahmen des Truth-Modells aus `repo.meta.yaml`:

```
domain_contracts
  > canonical_policies
  > runtime_configs_and_code
  > normative_specifications
  > diagnostic_reports
  > navigational_indices
  > generated_diagnostics
```

Jede Diagnose muss einer dieser Klassen zugeordnet sein.
Aussagen über „das System tut X" → verankert in `runtime_configs_and_code`.
Aussagen über „das System soll X" → verankert in `normative_specifications` oder `canonical_policies`.
Verwechslung dieser Klassen ist der häufigste epistemische Fehler — muss explizit sichtbar gemacht werden.

---

## 0.1 Geltungsbereich (Pflicht, vor jeder Analyse deklarieren)

| Wert | Bedeutung | Typische Kritiktiefe |
|------|-----------|---------------------|
| `System` | Gesamtes Weltgewebe-System | Vollständig |
| `Modul` | Einzelnes Subsystem (API, Web, Auth, Map, Identity) | Strukturell |
| `Entscheidung` | Einzelner ADR oder Blueprint | Strukturell |
| `PR/Diff` | Konkrete Implementierungsänderung | Essenziell |

---

## 0.2 Kritiktiefe (Pflicht, automatisch bestimmt und deklariert)

| Tiefe | Aktive Sektionen | Einsatz |
|-------|-----------------|---------|
| `Vollständig` | Alle 9 | Systemweite Fragen, ADR-Entwürfe, systemübergreifende Reviews |
| `Strukturell` | 1, 2, 5, 6, 9 | Modul- und Konzeptkritiken, Blueprint-Reviews |
| `Essenziell` | 2, 9 | Einzelentscheidungen, PR-Diffs, Drift-Checks |

Die Kritiktiefe wird vom Agenten zu Beginn bestimmt und in der Antwort deklariert.
Sektionen, die bei der gewählten Tiefe nicht aktiv sind, werden weggelassen — ohne Erklärung.

---

## 1. Zweck

Dieser Skill erzwingt:
- strukturelle Architekturkritik
- Aufdeckung impliziter Annahmen
- Identifikation systemischer Schwächen
- Prüfung der Kohärenz zwischen Truth Model / Semantik / Runtime

Ziel: Selbsttäuschung verhindern.

ADR-gebundene Entscheidungen: Implementierungstreue prüfen, nicht Entscheidungsqualität neu bewerten.
Wiederöffnung eines `accepted` ADR erfordert expliziten Vermerk:
„ADR-[Nr] wird zur Revision vorgeschlagen, weil [konkreter Befund]."

---

## 2. Diagnose-Gate (zweistufig)

### Stufe 1 — Harter Abbruch

Wenn zwingend notwendige (nicht nur hilfreiche) Quellen fehlen:
→ Abbruch mit: „X fehlt, nötig für Y"
Kein Fortschreiten. Keine Interpolation.

### Stufe 2 — Weiche Unsicherheit

Wenn Daten vorhanden aber unvollständig sind, oder wenn strukturelle Ableitung möglich ist:
→ Fortschreiten mit explizitem Interpolationsgrad in Sektion 9.
→ Wenn Interpolationsgrad > 0,5: Warnung in Sektion 2 ("Diagnose auf unzureichender Datenbasis — Schlussfolgerungen vorläufig").

---

## 3. Interpolationsregeln

Es gelten drei Typen, nicht ein pauschales Verbot:

| Typ | Definition | Status |
|-----|-----------|--------|
| **Faktisch** | Implementierungsdetail erfinden, das durch Lesen vorhandener Dateien abrufbar wäre | VERBOTEN — Abbruch (Diagnose-Gate Stufe 1) |
| **Strukturell-plausibel** | Ableitung aus vorhandener Evidenz (Muster A + B impliziert C) | ERLAUBT — Interpolationsgrad ≤ 0,5, Quelle nennen |
| **Konzeptuell-annahmebasiert** | Annahme über Systemziel oder -absicht aus normativen Docs | ERLAUBT MIT WARNUNG wenn Interpolationsgrad > 0,5 |

Jede Interpolation in Sektion 9 muss:
1. Typ deklarieren (strukturell / konzeptuell)
2. Quellen der Ableitung nennen (Dateipfad oder Verhaltensbeschreibung)
3. Interpolationsgrad (0–1) angeben
4. Bei Grad > 0,5: Schlussfolgerungen in Sektion 2 als vorläufig markieren

---

## 4. Analysesequenz (drei Ebenen, sequenziell aufbauend)

Reihenfolge bindend. Ebene 3 darf nicht ohne Ebene 1 und 2 einsetzen.

**Ebene 1 — Evidenz (belegt)**
Was ist nachweisbar vorhanden?
Belegpflicht: jede Aussage mit Dateipfad oder Verhaltensbeschreibung verankern.
Truth-Klasse benennen.

**Ebene 2 — Modellierung (plausibel)**
Wie ist das System gedacht?
Nur Ableitungen aus vorhandener Evidenz — keine freien Hypothesen.

**Ebene 3 — Urteil (kritisch)**
Ist diese Modellierung tragfähig?
Darf und soll widersprechen.
Unsicherheitsgrad explizit machen.

---

## 5. Prüfachsen

Achsen A–D und G sind immer aktiv.
Achsen E und F sind konditioniert — wenn inaktiv, explizit als „nicht anwendbar für diese Abfrage" deklarieren.

**A. Truth Model**
- Mehrere Wahrheitsquellen im Widerspruch?
- Implizite statt explizite Wahrheit?
- Verwechslung von `normative_specifications` und `runtime_configs_and_code`?
→ Output in Sektion 2 (Diagnose) und Sektion 5 (Architekturkritik)

**B. Contracts**
- Fehlend, zu schwach oder zu strikt?
- Werden sie umgangen?
- ADR-Status prüfen: `accepted` → nur Fidelity-Check; kein ADR → offene Frage markieren; `superseded` → Treue zum Nachfolger-ADR prüfen
→ Output in Sektion 2 (Diagnose) und Sektion 5 (Architekturkritik)

**C. Semantik**
- Begriff ≠ Verhalten?
- Bedeutungsdrift zwischen Docs und Code?
→ Output in Sektion 1 (Dialektik) und Sektion 4 (Versteckte Annahmen)

**D. Runtime vs. Dokumentation**
- Behauptung ≠ Implementierung?
- Tote Dokumentation?
- Ist `docs/_generated/architecture-drift.md` relevant?
→ Output in Sektion 2 (Diagnose) und Sektion 7 (Risikoanalyse: epistemisch)

**E. Kartenarchitektur** *(aktiv nur bei: Kartenrendering, Basemap-Pipeline, Overlay-Architektur, räumliche Semantik)*
- Rendering oder semantischer Kern?
- Repräsentation vs. Realität?
- Basemap = Infrastruktur, Overlay = Weltgewebe-Semantik — korrekt getrennt?
→ Output in Sektion 5 (Architekturkritik) und Sektion 8 (Alternative Sinnachse)

**F. Identitätssystem** *(aktiv nur bei: Garnrolle, RoN, Verortung, Vertrauen, Auth-Identität, Sichtbarkeitslogik)*
- Garnrolle-Modi konsistent (verortet vs. RoN)?
- Versteckte Trust-Mechaniken?
- Ist Vertrauen als Systemwert modelliert (verboten im Weltgewebe)?
→ Output in Sektion 5 (Architekturkritik) und Sektion 8 (Alternative Sinnachse)

**G. Komplexität**
- Notwendig vs. künstlich?
- Overengineering?
- Ist die Komplexität durch Systemgrenzen gerechtfertigt?
→ Output in Sektion 3 (Kontrastprüfung) und Sektion 6 (Alternativpfad)

---

## 6. Pflichtstruktur (je nach Kritiktiefe)

### 1. Dialektik *(Vollständig, Strukturell)*

- **These:** Stärkste wohlwollende Lesart
- **Antithese:** Stärkste kritische Lesart
- **Synthese:** Tragfähige Einordnung

---

### 2. Diagnose *(immer aktiv)*

Beginnt mit **Befundklasse** (Pflicht):

| Klasse | Bedeutung |
|--------|-----------|
| **A** | Kritisch: strukturelle Fehler gefunden, Tragfähigkeit in Frage |
| **B** | Warnung: potenzielle Schwächen, abhängig von Kontext oder Annahmen |
| **C** | Bedingt sound: gefundene Schwächen sind bekannt und bewusst akzeptiert |
| **D** | Sound: keine tragfähigkeitsgefährdenden Befunde — Begründung warum (Belegpflicht) |

Dann dreistufige Evidenzgradierung:
- **Belegt** (mit Quellenangabe)
- **Plausibel** (strukturelle Ableitung, Interpolationstyp nennen)
- **Spekulativ** (konzeptuelle Annahme, Interpolationsgrad hoch)

Bei Befundklasse D: Soundness muss earned sein — „X ist sound, weil Y nachweisbar ist."
Keine blanken Zertifikate.

---

### 3. Kontrastprüfung *(Vollständig)*

- **Lesart A:** System funktioniert — warum?
- **Lesart B:** System ist grundlegend fehlerhaft — warum?

---

### 4. Versteckte Annahmen *(Vollständig)*

- Welche Prämissen werden still angenommen?
- Welche könnten falsch sein?

---

### 5. Architekturkritik *(Vollständig, Strukturell)*

Mit Achsenzuordnung (A–G):
- Strukturelle Schwächen
- Semantische Brüche
- Unnötige Komplexität
- Mögliche Sackgassen

---

### 6. Alternativpfad *(Vollständig, Strukturell)*

Grundlegend andere Denkweise — kein Variantenwechsel.
Nur wenn Befundklasse A oder B.

---

### 7. Risikoanalyse *(Vollständig)*

- technisch
- semantisch
- epistemisch
- organisatorisch

Inkl. Folgenabschätzung.

---

### 8. Alternative Sinnachse *(Vollständig)*

Pflicht: Mindestens eine der folgenden Fragen beantworten:
- Ist die Karte das falsche Zentrum?
- Ist Identität falsch modelliert?
- Ist Vertrauen falsch gedacht?
- Wird Komplexität mit Tiefe verwechselt?

---

### 9. Essenz + Folgepfad *(immer aktiv)*

**Essenz:**
- Hebel
- Entscheidung
- Nächste Aktion

**Folgepfad (Pflicht):**

| Befundklasse | Aktion |
|-------------|--------|
| A | ADR-Entwurf vorschlagen oder bestehenden ADR zur Revision markieren |
| B | Blueprint-Ergänzung oder Spec-Update vorschlagen |
| C | Drift-Befund in `docs/_generated/` adressierbar? Markieren. |
| D | Keine Aktion. Befundklasse D und Begründung dokumentieren. |

**Unsicherheits- & Interpolationsangaben (Pflicht):**
- Unsicherheitsgrad (0–1) + Ursachen
- Interpolationsgrad (0–1) + Typ (strukturell / konzeptuell) + Quellen
- Wenn Interpolationsgrad > 0,5: Schlussfolgerungen als vorläufig markieren

---

## 7. Anti-Fehler-Regeln

Claude darf NICHT:
- glätten
- implizit zustimmen
- faktisch fehlende Daten ergänzen (→ Abbruch)
- nur Code reviewen
- accepted ADRs ohne expliziten Vermerk zur Revision vorschlagen
- Befundklasse D vergeben ohne Belegpflicht zu erfüllen

Claude MUSS:
- widersprechen können
- Unsicherheit sichtbar machen
- alternative Deutungen liefern
- Denkfehler korrigieren
- zwischen Diagnose und Entscheidung unterscheiden

---

## 8. Eskalationslogik

Bei folgenden Fällen:
- widersprüchliche Architektur
- fragile Kernprämissen
- erkennbare Sackgasse

→ Explizit formulieren:

„Dieses System ist in seiner aktuellen Form wahrscheinlich nicht tragfähig, weil …"

**Klarstellung:** Eskalation ist Diagnose (Befundklasse A), kein Governance-Beschluss.
Die Aussage ist ein diagnostischer Befund, kein Auftrag.
Welche Konsequenz gezogen wird, liegt ausschließlich beim menschlichen Projekt-Collective.
Der Agent markiert und begründet — er entscheidet nicht.

---

## 9. Prämissencheck *(Vollständig)*

Was müsste wahr sein, damit das System so funktioniert?
Welche dieser Prämissen sind belegt, welche sind Annahmen?

---

## 10. Unsicherheitsgrad

Dieses Dokument selbst:

**0.08**

Ursachen:
- Die Achsen-zu-Sektionen-Zuordnung ist normativ, nicht empirisch validiert
- Kritiktiefe-Schwellen könnten in der Praxis anders kalibriert werden müssen

---

## 11. Interpolationsgrad

**0.11**

Typ: konzeptuell-annahmebasiert

Annahmen:
- LLMs befolgen sequentielle Analysesequenzen kohärenter als parallele Anweisungen
- Befundklasse D wird in der Praxis nicht als Ausrede für oberflächliche Analyse missbraucht
- Kritiktiefe `Essenziell` reicht für PR-Diffs aus ohne kritische Befunde zu unterdrücken

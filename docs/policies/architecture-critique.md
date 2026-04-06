---
id: docs.policies.architecture-critique
title: "Architekturkritik-Skill: weltgewebe.architecture.critique.v4"
doc_type: policy
status: canonical
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

# weltgewebe.architecture.critique.v4

Status: canonical — maßgebliches kognitives Protokoll für Architekturkritik im Weltgewebe.

Begründung der Kanonisierung:
Dieser Skill wird als canonical geführt, da Architekturkritik als verbindliches kognitives Protokoll für Agenten im Weltgewebe etabliert wird. Ziel ist die systematische Aufdeckung struktureller Schwächen, semantischer Brüche und epistemischer Inkonsistenzen über alle Module hinweg. Der Skill ersetzt keine fachlichen Entscheidungen, sondern standardisiert deren kritische Prüfung.

---

## 0. Meta-Definition

Architekturkritik = Prüfung der Denkstruktur, nicht der Implementierungsdetails.

Bewertet wird:

- nicht primär, ob etwas funktioniert
- sondern, ob es sinnvoll ist, dass es so gebaut wird
- und ob es so gebaut wird, wie beschlossen wurde

Dieses Skill operiert im Rahmen des Truth-Modells aus `repo.meta.yaml`:

```text
domain_contracts
  > canonical_policies
  > runtime_configs_and_code
  > normative_specifications
  > diagnostic_reports
  > navigational_indices
  > generated_diagnostics
```

Jede Aussage muss einer dieser Klassen zugeordnet sein.
„Das System tut X" → belegt in `runtime_configs_and_code`.
„Das System soll X" → belegt in `normative_specifications` oder `canonical_policies`.
Klassenverwechslung ist der häufigste epistemische Fehler — muss explizit sichtbar gemacht werden.

---

## 0.1 Geltungsbereich (Pflicht, vor jeder Analyse deklarieren)

| Wert | Bedeutung | Kritiktiefe |
|------|-----------|-------------|
| `System` | Gesamtes Weltgewebe-System | Vollständig |
| `Modul` | Einzelnes Subsystem (API, Web, Auth, Map, Identity) | Strukturell |
| `Entscheidung` | Einzelner ADR oder Blueprint | Strukturell |
| `PR/Diff` | Konkrete Implementierungsänderung | Essenziell |

---

## 0.2 Kritiktiefe (Pflicht, automatisch bestimmt und deklariert)

| Tiefe | Aktive Sektionen |
|-------|-----------------|
| `Vollständig` | 1–9 |
| `Strukturell` | 1, 2, 5, 6, 9 |
| `Essenziell` | 2, 9 |

Sektionen außerhalb der gewählten Tiefe werden weggelassen — ohne Erklärung.

---

## 1. Zweck

Erzwingt:

- strukturelle Architekturkritik
- Aufdeckung impliziter Annahmen
- Identifikation systemischer Schwächen
- Kohärenzprüfung: Truth Model / Semantik / Runtime

Ziel: Selbsttäuschung verhindern.

ADR-gebundene Entscheidungen: Implementierungstreue prüfen, nicht Entscheidungsqualität neu bewerten.
Wiederöffnung eines `accepted` ADR erfordert expliziten Vermerk:
„ADR-[Nr] wird zur Revision vorgeschlagen, weil [konkreter Befund]."

---

## 2. Diagnose-Gate

Wenn zwingend notwendige (nicht nur hilfreiche) Quellen fehlen:
→ Abbruch: „X fehlt, nötig für Y"

Wenn Daten vorhanden, aber unvollständig — strukturelle Ableitung möglich:
→ Analyse erlaubt, Interpolationsgrad in Sektion 9 deklarieren
→ Wenn Interpolationsgrad > 0,5: Ergebnis in Sektion 2 als vorläufig markieren

---

## 3. Interpolationsregeln

| Typ | Definition | Status |
|-----|-----------|--------|
| **Faktisch** | Implementierungsdetail erfinden, das durch Lesen vorhandener Dateien abrufbar wäre | VERBOTEN → Abbruch |
| **Strukturell** | Ableitung aus vorhandener Evidenz (Muster A + B impliziert C) | ERLAUBT, Grad ≤ 0,5 |
| **Konzeptuell** | Annahme über Systemziel aus normativen Docs | ERLAUBT, Warnung wenn Grad > 0,5 |

Jede Interpolation in Sektion 9 muss Typ, Quelle und Grad (0–1) benennen.

---

## 4. Analysesequenz (verpflichtend, sequenziell)

Reihenfolge bindend. Ebene 3 darf nicht ohne Ebene 1 und 2 einsetzen.

### Ebene 1 — Evidenz (belegt)

Was ist nachweisbar vorhanden? Jede Aussage mit Dateipfad oder Verhaltensbeschreibung verankern. Truth-Klasse benennen.

### Ebene 2 — Modellierung (plausibel)

Wie ist das System gedacht? Nur Ableitungen aus vorhandener Evidenz — keine freien Hypothesen.

### Ebene 3 — Urteil (kritisch)

Ist diese Modellierung tragfähig? Darf und soll widersprechen. Unsicherheitsgrad explizit machen.

---

## 5. Prüfachsen

Achsen A–D und G: immer aktiv.
Achsen E und F: konditioniert — wenn inaktiv, explizit als „nicht anwendbar" deklarieren.

### A. Truth Model

- Widersprüche zwischen Wahrheitsquellen?
- Implizite statt explizite Wahrheit?
- Klassenverwechslung (`normative_specifications` vs. `runtime_configs_and_code`)?

→ Sektion 2 (Diagnose) + Sektion 5 (Architekturkritik)

### B. Contracts

- Fehlend, zu schwach, zu strikt oder umgangen?
- ADR-Status: `accepted` → nur Fidelity-Check; kein ADR → offene Frage markieren; `superseded` → Treue zum Nachfolger-ADR prüfen

→ Sektion 2 (Diagnose) + Sektion 5 (Architekturkritik)

### C. Semantik

- Begriff ≠ Verhalten?
- Bedeutungsdrift zwischen Docs und Code?

→ Sektion 1 (Dialektik) + Sektion 4 (Versteckte Annahmen)

### D. Runtime vs. Dokumentation

- Behauptung ≠ Implementierung? Tote Dokumentation?
- Ist `docs/_generated/architecture-drift.md` relevant?

→ Sektion 2 (Diagnose) + Sektion 7 (Risikoanalyse: epistemisch)

### E. Kartenarchitektur *(aktiv nur bei: Kartenrendering, Basemap-Pipeline, Overlay-Architektur, räumliche Semantik)*

- Rendering oder semantischer Kern?
- Basemap = Infrastruktur, Overlay = Weltgewebe-Semantik — korrekt getrennt?

→ Sektion 5 (Architekturkritik) + Sektion 8 (Alternative Sinnachse)

### F. Identitätssystem *(aktiv nur bei: Garnrolle, RoN, Verortung, Auth-Identität, Sichtbarkeitslogik)*

- Garnrolle-Modi konsistent (verortet vs. RoN)?
- Vertrauen als Systemwert modelliert? (im Weltgewebe verboten)

→ Sektion 5 (Architekturkritik) + Sektion 8 (Alternative Sinnachse)

### G. Komplexität

- Notwendig vs. künstlich? Overengineering?
- Durch Systemgrenzen gerechtfertigt?

→ Sektion 3 (Kontrastprüfung) + Sektion 6 (Alternativpfad)

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
| **A** | Kritisch: strukturelle Fehler, Tragfähigkeit in Frage |
| **B** | Warnung: potenzielle Schwächen, kontextabhängig |
| **C** | Bedingt sound: Schwächen bekannt und bewusst akzeptiert |
| **D** | Sound: keine tragfähigkeitsgefährdenden Befunde (Belegpflicht) |

Befundklasse D: Soundness muss earned sein — „X ist sound, weil Y nachweisbar ist."
Keine blanken Zertifikate.

Dann Evidenzgradierung:

- **Belegt** (mit Quellenangabe)
- **Plausibel** (strukturelle Ableitung, Interpolationstyp nennen)
- **Spekulativ** (konzeptuelle Annahme, Interpolationsgrad hoch)

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

Mit Achsenzuordnung (A–G, nur aktive Achsen):

- Strukturelle Schwächen
- Semantische Brüche
- Unnötige Komplexität
- Mögliche Sackgassen

---

### 6. Alternativpfad *(Vollständig, Strukturell — nur bei Befundklasse A oder B)*

Grundlegend andere Denkweise — kein Variantenwechsel.

---

### 7. Risikoanalyse *(Vollständig)*

- technisch
- semantisch
- epistemisch
- organisatorisch

Inkl. Folgenabschätzung.

---

### 8. Alternative Sinnachse *(Vollständig)*

Mindestens eine der folgenden Fragen beantworten:

- Ist die Karte das falsche Zentrum?
- Ist Identität falsch modelliert?
- Ist Vertrauen falsch gedacht?
- Wird Komplexität mit Tiefe verwechselt?

---

### 9. Essenz + Folgepfad *(immer aktiv)*

**Essenz:** Hebel — Entscheidung — nächste Aktion

#### Folgepfad

| Befundklasse | Aktion |
|-------------|--------|
| A | ADR-Entwurf vorschlagen oder zur Revision markieren |
| B | Blueprint-Ergänzung oder Spec-Update vorschlagen |
| C | Drift in `docs/_generated/` adressierbar? Markieren. |
| D | Keine Aktion. Befundklasse D und Begründung dokumentieren. |

#### Unsicherheit & Interpolation

- Unsicherheitsgrad (0–1) + Ursachen
- Interpolationsgrad (0–1) + Typ (strukturell / konzeptuell) + Quellen
- Wenn Interpolationsgrad > 0,5: Schlussfolgerungen als vorläufig markieren

---

## 7. Anti-Fehler-Regeln

Darf NICHT:

- glätten
- implizit zustimmen
- faktisch fehlende Daten ergänzen (→ Abbruch)
- nur Code reviewen
- `accepted` ADRs ohne expliziten Vermerk zur Revision vorschlagen
- Befundklasse D ohne Belegpflicht vergeben

Muss:

- widersprechen können
- Unsicherheit sichtbar machen
- alternative Deutungen liefern
- Denkfehler korrigieren
- zwischen Diagnose und Entscheidung unterscheiden

---

## 8. Eskalation

Bei widersprüchlicher Architektur, fragilen Kernprämissen oder erkennbarer Sackgasse:

→ „Dieses System ist in seiner aktuellen Form wahrscheinlich nicht tragfähig, weil …"

Eskalation ist Diagnose (Befundklasse A), kein Governance-Beschluss.
Welche Konsequenz gezogen wird, liegt beim menschlichen Projekt-Collective.
Der Agent markiert und begründet — er entscheidet nicht.

---

## 9. Prämissencheck *(Vollständig)*

Was müsste wahr sein, damit das System so funktioniert?
Was ist belegt — was ist Annahme?

---

## Essenz des Skills

Kritik vor Lösung.
Struktur vor Detail.
Wahrheit vor Komfort.

---

## Unsicherheitsgrad

0.08

Ursachen:

- Achsen-zu-Sektionen-Zuordnung ist normativ, nicht empirisch validiert
- Kritiktiefe-Schwellen könnten in der Praxis anders kalibriert werden müssen

---

## Interpolationsgrad

**0.11** · Typ: konzeptuell

Annahmen:

- LLMs befolgen sequentielle Analysesequenzen kohärenter als parallele Anweisungen
- Befundklasse D wird nicht als Ausrede für oberflächliche Analyse missbraucht
- Kritiktiefe `Essenziell` reicht für PR-Diffs ohne kritische Befunde zu unterdrücken

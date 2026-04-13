---
id: docs.policies.agent-operability-assertions
title: Agent Operability Assertions
doc_type: policy
status: active
scope: global
summary: "Prüfbare Invarianten für deterministische Agenten-Ausführung. Grundlage für Task-Validierung und spätere Formalisierung des Agent-Operability-Kerns."
relations:
  - type: relates_to
    target: docs/blueprints/agent-operability-blaupause.md
  - type: relates_to
    target: docs/policies/agent-reading-protocol.md
  - type: relates_to
    target: AGENTS.md
  - type: relates_to
    target: agent-policy.yaml
---

# Agent Operability Assertions

## Zweck

Dieses Dokument definiert vier prüfbare Invarianten (A0–A3), die jeder Agent-Task erfüllen
muss, bevor er formalisiert oder ausgeführt wird. Sie sind keine Guidelines, sondern
Abbruchbedingungen: ein Task, der eine Assertion verletzt, darf nicht ausgeführt werden.

Die Assertions beschreiben, wann Entscheidungen im Agent-Loop deterministische Wahrheit
erzeugen – und wann nicht.

---

## Voraussetzung: Discovery-Prädikat (A0.1)

Jeder Task muss vor der Ausführung explizit definieren, **was als Fundstelle gilt**.

Ohne explizites Discovery-Prädikat ist A0 nicht prüfbar, weil `read_context` keine
definierte Vollständigkeitsgrenze hat.

**Formale Anforderung:**

```
task.discovery_predicate:
  scope: <Verzeichnis oder Muster>
  counts_as_usage:
    - <explizite Auflistung, z. B. "TypeScript-Typreferenz">
  does_not_count:
    - <explizite Ausschlüsse, z. B. "Kommentar", "String-Literal">
```

**Beispiel (Task: `MapPoint` entfernen):**

```
scope: apps/web/src/
counts_as_usage:
  - TypeScript-Typreferenz (Import oder Typannotation)
does_not_count:
  - Kommentare
  - String-Literale
  - JSDoc-Kommentare (außer in der Typdefinition selbst)
```

**Failure Mode:** Wenn das Discovery-Prädikat fehlt, kann `read_context` formal vollständig
wirken, aber operativ Fundstellen übersehen oder falsch einschließen. Das System wird
deterministisch falsch.

---

## A0 — Kontext-Vollständigkeit

> `read_context` ist ausreichend, wenn jede Entscheidung im `decide`-Schritt ohne
> externe Information getroffen werden kann.

**Testprädikat:**
Nimm alle Artefakte aus `read_context`. Gibt es eine Entscheidung, für die du etwas
nachschlagen müsstest, das nicht drin ist? Wenn ja: `read_context` unvollständig.

**Positivbeispiel (Task B: `MapPoint` entfernen):**
`read_context` liefert: Typdefinition in `types.ts` + Kommentarreferenz in
`NodePanel.svelte`. Beide Entscheidungen (`in scope?`, `abort?`) sind aus diesen
Artefakten allein begründbar. A0 erfüllt.

**Negativbeispiel (Task D: unklares Discovery-Prädikat):**
`read_context` liefert: 0 TypeScript-Typverwendungen. Zusätzlich existiert ein
dynamischer String `"MapPoint"` in einer Konfigurationsdatei. Ohne explizites
Discovery-Prädikat (A0.1) ist unklar, ob das eine Fundstelle ist. Die Entscheidung
erfordert externe Klärung. A0 verletzt.

**Failure Mode:** Das System trifft eine deterministische Entscheidung auf unvollständiger
Basis. Das Ergebnis ist formal korrekt, inhaltlich falsch. Dieser Fehler ist unsichtbar
ohne A0.1.

---

## A1 — Kausalkette

> Eine Scope-Erweiterung ist erlaubt, wenn eine kausale Kette vom Ziel zum neuen
> Artefakt vollständig aus A0-vollständigem Kontext rekonstruierbar ist.

**Testprädikat:**
Kann jeder Link der Kette (Ziel → Artefakt N → Artefakt N+1) aus dem A0-vollständigen
Kontext abgeleitet werden, ohne externe Annahme? Wenn ein Link extern begründet werden
muss: Kette gebrochen, Erweiterung nicht erlaubt.

**Was als gültiger Link zählt:**
Ein Link ist gültig, wenn das entdeckte Artefakt ohne die Kernänderung in einem
inkonsistenten, misleadenden oder funktional falschen Zustand verbleibt.

**Positivbeispiel (Task B):**
Kette: `MapPoint` entfernen → Kommentar in `NodePanel.svelte` referenziert `MapPoint`
→ Kommentar wird misleading → Kommentar muss mitgeändert werden.
Drei Links, alle aus lokalem Kontext rekonstruierbar. A1 erfüllt.

**Negativbeispiel (Task C):**
Ziel: `MapPoint` entfernen. Zusätzlich entdeckt: `NodePanel.svelte` hat ein allgemeines
Refactoring-Potenzial. Das Refactoring ist nicht durch die Entfernung von `MapPoint`
verursacht. Kein gültiger Link. A1 nicht anwendbar → A2 prüfen → Abort.

**Failure Mode:** Scope wird auf kausal nicht verbundene Artefakte ausgeweitet. Der Task
bleibt scheinbar kohärent, führt aber Multiple-Change-Probleme ein, die unabhängig
reviewt werden müssten.

---

## A2 — Unabhängigkeitstest

> Abort, wenn ein entdecktes Artefakt unabhängig vom Kernziel geändert werden
> könnte und die Änderung trotzdem sinnvoll wäre.

**Testprädikat:**
Entferne das Kernziel aus dem Plan. Macht die Artefaktänderung als eigenständiger Task
noch Sinn? Wenn ja: unabhängig → Abort.

**Formale Definition operativer Unabhängigkeit:**
Artefakt B ist unabhängig von Kernziel A, wenn:
(a) B in einem anderen PR ohne A sinnvoll und vollständig wäre, **und**
(b) die Entscheidung für B keine Fakten aus der A-Änderung benötigt.

**Positivbeispiel (A2 korrekt negativ, Task B):**
NodePanel-Kommentar-Update ohne `MapPoint`-Entfernung sinnvoll? Nein – der Kommentar
ist nur misleading, wenn `MapPoint` entfernt wird. Nicht unabhängig. A2 nicht getriggert.

**Negativbeispiel (Task C):**
`NodePanel.svelte`-Refactoring ohne `MapPoint`-Entfernung sinnvoll? Ja – es ist ein
eigenständiger Qualitätsgewinn. Unabhängig. A2 getriggert → Abort.

**Failure Mode:** Zwei unabhängige Veränderungen werden in einem Task gebündelt. Review
wird erschwert, Rollback schwierig, Kausalität im Changelog unklar.

---

## A3 — Lokalität

> Ein Task ist deterministisch, wenn alle Entscheidungen aus lokalem Kontext allein
> begründbar sind.

**Testprädikat:**
Gibt es einen Entscheidungspunkt, bei dem ein außerhalb des Kontexts liegender Fakt
das Ergebnis verändern würde? Wenn ja: nicht deterministisch, Task neu schneiden.

**Lokalität ist kein Datenmengenlimit, sondern ein Entscheidungseinheit-Konzept:**
Eine Entscheidung ist lokal, wenn sie vollständig in einem einzigen Entscheidungskontext
haltbar ist – unabhängig davon, wie viele Artefakte dieser Kontext enthält.

**Positivbeispiel (Task B):**
Alle Entscheidungen (scope erweitern?, abort?) wurden aus dem Ergebnis von
`read_context` allein getroffen. Kein externes Wissen nötig. A3 erfüllt.

**Negativbeispiel (Task E, lange Kette):**
Kette umspannt 5 Artefakte. Zwischen Artefakt 3 und 4 ist eine Zwischenentscheidung
nötig, die einen neuen `read_context`-Lauf erfordern würde (z. B. ob Artefakt 4 überhaupt
existiert, was in A0 nicht erfasst wurde). Diese Entscheidung ist nicht mehr lokal.
A3 verletzt → Task neu schneiden, nicht erweitern.

**Failure Mode:** System produziert formal korrekte Entscheidungen, die auf
unvollständigen Prämissen beruhen. Unterschiedliche Agents würden zu unterschiedlichen
Ergebnissen kommen. Reproduzierbarkeit gebrochen.

---

## Fuzzer-Suite

Referenzfälle für Assertion-Validierung. Jeder neue Task sollte gegen diese Suite
geprüft werden, bevor er formalisiert wird.

### Task A – Trivial (1 Datei, kein Entscheidungsbedarf)

**Task:** Korrigiere irreführenden Kommentar in `apps/web/src/routes/map/+page.svelte`
Z. 269–272 (behauptet `remote-style`, Code nutzt `local-sovereign` in lokalem Kontext).

| Assertion | Ergebnis | Begründung |
| :--- | :--- | :--- |
| A0.1 | ✓ | Discovery-Prädikat: Kommentarblock Z. 269–272, ein File |
| A0 | ✓ | Kommentar vollständig sichtbar, keine externe Info nötig |
| A1 | ✓ | Kette: Code widerspricht Kommentar → Kommentar korrigieren |
| A2 | ✓ | Ohne Code-Widerspruch kein Anlass zur Änderung: nicht unabhängig |
| A3 | ✓ | Einzige Entscheidung lokal entscheidbar |

**Erwartetes Verhalten:** Gültig. Scope: 1 Datei, 4 Zeilen.

---

### Task B – Kausal erweitert (2 Dateien, 1 Entscheidung)

**Task:** Entferne `@deprecated MapPoint`-Interface aus `apps/web/src/lib/map/types.ts`.

| Assertion | Ergebnis | Begründung |
| :--- | :--- | :--- |
| A0.1 | ✓ | Discovery: TypeScript-Typreferenzen in `apps/web/src/`, keine Kommentare |
| A0 | ✓ | 0 Typverwendungen + 1 Kommentarreferenz: vollständig |
| A1 | ✓ | Kette: Typ weg → Kommentar referenziert weg → Kommentar misleading → update |
| A2 | ✓ | NodePanel-Kommentar ohne MapPoint-Entfernung nicht änderungswürdig |
| A3 | ✓ | Alle Entscheidungen aus read_context-Ergebnis begründbar |

**Erwartetes Verhalten:** Gültig. Scope-Erweiterung auf `NodePanel.svelte` korrekt.

---

### Task C – Abort (unabhängige Änderung)

**Task:** Entferne `MapPoint` + refactore `NodePanel.svelte`.

| Assertion | Ergebnis | Begründung |
| :--- | :--- | :--- |
| A2 | **✗** | NodePanel-Refactoring ohne MapPoint-Entfernung sinnvoll → unabhängig |

**Erwartetes Verhalten:** Abort. Task in zwei separate Tasks aufteilen.

---

### Task D – A0-Verletzung durch fehlendes Discovery-Prädikat

**Task:** Entferne `MapPoint` wenn ungenutzt – ohne Definition von „Verwendung".

| Assertion | Ergebnis | Begründung |
| :--- | :--- | :--- |
| A0.1 | **✗** | Discovery-Prädikat fehlt. Was zählt als Verwendung? |

**Erwartetes Verhalten:** Abort vor Ausführung. Task-Definition um A0.1 ergänzen, dann neu prüfen.

---

### Task E – Grenzfall lange Kausalkette

**Task:** Entferne Typ X, dessen Entfernung eine 5-Link-Kette über 5 Dateien auslöst.
Zwischen Link 3 und 4 ist ein zusätzlicher `read_context`-Lauf nötig.

| Assertion | Ergebnis | Begründung |
| :--- | :--- | :--- |
| A3 | **✗** | Zwischenentscheidung benötigt externen Lauf → nicht mehr lokal |

**Erwartetes Verhalten:** Abort. Task an der Grenze zwischen Link 3 und 4 aufteilen.
Kein Zahlen-Limit, aber: Eine Entscheidungseinheit = ein Kontext.

---

## Entscheidungslogik (Zusammenfassung)

```
Task definiert Discovery-Prädikat?  →  Nein: Abort (A0.1)
                                         Ja: weiter

read_context vollständig?            →  Nein: read_context erweitern
                                         Ja: weiter

Neue Artefakte entdeckt?             →  Nein: write_change ausführen
                                         Ja: A1 prüfen

A1 (Kausalkette gültig)?            →  Nein: A2 prüfen
                                         Ja: Scope erweitern, weiter

A2 (Artefakt unabhängig)?           →  Ja: Abort
                                         Nein: Scope erweitern, weiter

A3 (Entscheidung lokal)?            →  Nein: Abort, Task neu schneiden
                                         Ja: write_change ausführen
```

---

## Nicht-Ziel dieses Dokuments

Dieses Dokument definiert **keine** Implementierungsstruktur.

Es legt fest:
- **nicht**: wie Commands implementiert werden
- **nicht**: wie der Runner aufgebaut ist
- **nicht**: welche Verzeichnisstruktur verwendet wird

Es legt fest:
- **ja**: wann ein Task gültig ist
- **ja**: wann abgebrochen werden muss
- **ja**: was Deterministik im Agent-Loop bedeutet

Die Implementierung des Runners und der Command-Struktur folgt aus diesen Invarianten –
nicht umgekehrt.

# Blueprint: Replace personal ownership with architectural ownership model

## Ziel

Die bestehende Blaupause zum Thema `owner` / `CODEOWNERS` soll überarbeitet werden.

Grundannahme:
Das Repository wird primär solo betrieben. Personale Ownership und `CODEOWNERS` sind daher nicht zielführend.

Stattdessen soll ein architektonisch sinnvolles Ownership-Modell definiert werden,
das maschinell auswertbar ist und die Selbstorganisation des Repos stärkt.

Wichtig:

- Kein reines Entfernen.
- Konzeptionell sauber neu denken.
- Nur implementieren, wenn es maschinellen Mehrwert erzeugt.

---

## 1. Entferne personale Ownership aus der Blaupause

Personale Ownership wird aus dem System entfernt. Dies bedeutet konkret:

- Keine Annahmen wie „Team“, „Person“, „Verantwortlicher“.
- `CODEOWNERS` wird nicht in die priorisierte Planung aufgenommen.
- **Begründung:** Governance ohne verteilte Verantwortung ist formale Redundanz.
  Im Solo-Setup führt personale Ownership lediglich zu Governance-Ballast ohne funktionalen Wert.

---

## 2. Ersetze Owner durch Architektur-Semantik

Stattdessen wird ein neues, rein optionales Frontmatter-Feld eingeführt:

`organ`

Beispiele für Ausprägungen von `organ`:

- `organ: governance`
- `organ: runtime`
- `organ: contracts`
- `organ: docmeta`
- `organ: deploy`

**Wichtig:**

- Das Feld ist strikt optional.
- Es wird nur eingeführt, da es auch maschinell genutzt wird.

---

## 3. Maschinelle Nutzung definieren

Das neue Feld `organ` generiert sofortigen maschinellen Mehrwert:

- `generate_system_map.py` wertet `organ` aus und nimmt es als strukturelles Feld in die
  System Map auf, was die Gruppierung von Dokumenten nach funktionaler Systemintelligenz ermöglicht.

Da diese Nutzung implementiert ist, ist das Feld zulässig.

---

## 4. CODEOWNERS explizit zurückstellen

- `CODEOWNERS` wird nicht implementiert.
- GitHub Review-Routing ist aktuell nicht Teil des Zielsystems.
- **Ausnahmefall:** Sollte das Repository kollaborativ werden, wird `CODEOWNERS` neu evaluiert.
  Bis dahin bleibt es ausgesetzt.

---

## 5. Strukturelle Einordnung der Blaupause

Diese Blaupause stellt sicher, dass:

- Klar zwischen sozialer Governance (nicht benötigt im Solo-Repo) und Architektur-Semantik unterschieden wird.
- Ownership als System-Navigation definiert wird, nicht als Verantwortlichkeit.
- Das neue Modell nahtlos in die bestehende Phasenstruktur und CI-Härte (`Docs-Guard`) integrierbar ist.

---

## Risiko-/Nutzenanalyse

- **Risiko:** Zusätzliches Pflegefeld in Metadaten.
- **Nutzen:** Strukturierte Impact-Cluster, System-Heatmap, und eine Architekturintelligenz,
  die Systeme miteinander sprechen lässt.

**Metakriterium:** Dieser PR darf das System nicht schwerer machen. Er macht es klarer und
intelligenter. Ownership ist sinnvoll, wenn jemand anderes da ist. Architektur-Semantik ist
sinnvoll, wenn Systeme miteinander sprechen. Hier sprechen Systeme – nicht Menschen.

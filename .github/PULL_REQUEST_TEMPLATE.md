## Task

<!-- Natürlichsprachliche Beschreibung der Aufgabe. Kein YAML, kein Code. -->

**Ziel:** <!-- Was soll nachher anders sein? -->

**Scope:** <!-- Welche Dateien/Bereiche sind betroffen – und welche ausdrücklich nicht? -->

**Erfolgsnachweis:** <!-- Woran erkennt man objektiv, dass der Task gelungen ist? -->

---

## Assertion-Check

<!-- Pflicht für agent-generierte Änderungen. Für manuelle PRs optional, aber empfohlen. -->
<!-- Vollständige Definition: docs/policies/agent-operability-assertions.md -->

**A0.1 – Discovery-Prädikat** *(Gate: Pflicht vor A0 — ohne diesen Eintrag ist der Task nicht gültig definierbar)*
- counts_as_usage:
- does_not_count:

**A0 – Kontext vollständig?**
- [ ] Alle Entscheidungen waren aus read_context allein begründbar.

**A1 – Kausalkette vorhanden?**
- [ ] Jede geänderte Datei hat eine rekonstruierbare kausale Kette vom Ziel.

**A2 – Unabhängige Änderungen ausgeschlossen?**
- [ ] Keine entdeckte Änderung wäre als eigenständiger Task sinnvoll.

**A3 – Entscheidung lokal?**
- [ ] Keine Entscheidung erforderte externe Information, die nicht in A0 vorlag.

---

## Nicht-Ziel

<!-- Was wurde bewusst nicht geändert? -->

### 📄 weltgewebe/docs/overview/inhalt.md

**Größe:** 2 KB | **md5:** `6f065ff394abd87be4043025db5fc89b`

```markdown
# Einführung: Ethik- & UX-First-Startpunkt

Die Weltgewebe-Initiative stellt Menschen und ihre Lebensrealität in den Mittelpunkt.
Die technische Plattform – SvelteKit für das Web-Frontend, Axum als Rust-API sowie Postgres
und JetStream im Daten- und Event-Backbone – ist Mittel zum Zweck: Sie schafft Transparenz,
Handlungssicherheit und nachhaltige Teilhabe.
Dieses Dokument bietet Außenstehenden einen klaren Einstieg in die inhaltliche Stoßrichtung
des Projekts.

## Leitplanken & Prinzipien

- **Ethik vor Feature-Liste:** Entscheidungen werden entlang von Wirkungszielen und Schutzbedarfen
  priorisiert.
  UX-Entscheidungen orientieren sich an Barrierefreiheit, Datenschutz und erklärbaren Abläufen.
- **Partizipation sichern:** Stakeholder:innen aus Zivilgesellschaft, Verwaltung und Forschung
  erhalten früh Zugang zu Prototypen, um Risiken zu erkennen und gemeinsam zu mitigieren.
- **Transparenz herstellen:** Dokumentation, Policies und öffentlich nachvollziehbare
  Entscheidungen haben Vorrang vor reinem Feature-Output.

## Projektumfang (Docs-only, Gate-Strategie)

Das Repository befindet sich in Phase ADR-0001 „Docs-only“.
Technische Re-Entry-Pfade sind über Gates A–D definiert.
So bleiben Experimente nachvollziehbar und können schrittweise in den Produktionskontext
überführt werden.

## Weitere Orientierung

- **Systematik & Struktur:** Siehe `docs/overview/zusammenstellung.md`.
- **Architektur-Details:** `architekturstruktur.md` fasst Domänen, Boundaries und Kommunikationspfade zusammen.
- **Fahrplan & Prozesse:** `docs/process/fahrplan.md` beschreibt Freigaben, Gates und Quality-Gates.

> _Stand:_ Docs-only, Fokus auf Ethik, UX und transparente Entscheidungsprozesse.
> Mit dem Startpunkt hier und der Systematik im Schwesterdokument erhalten Außenstehende in
> zwei Klicks den vollständigen Projektkontext.
```

### 📄 weltgewebe/docs/overview/zusammenstellung.md

**Größe:** 2 KB | **md5:** `ab6cbff930700676b08bb59271a33fbc`

```markdown
# Systematik & Strukturüberblick

Diese Zusammenstellung führt durch die zentralen Orientierungspunkte der Weltgewebe-Dokumentation.
Sie ergänzt die inhaltliche Einführung (`docs/overview/inhalt.md`) und macht deutlich,
wie Ethik & UX entlang des gesamten Vorhabens abgesichert werden.

## Kernartefakte

| Bereich | Zweck | Primäre Ressourcen |
| --- | --- | --- |
| **Ethik & Wirkung** | Leitplanken, Risiken, Schutzbedarfe | `policies/`, `docs/ethik/`, `docs/process/fahrplan.md` |
| **User Experience** | UX-Guidelines, Prototypen, Feedback-Loops | `apps/web/README.md`, `docs/ux/`, `docs/runbooks/` |
| **Architektur** | Technische Boundaries, Integrationen | `architekturstruktur.md`, `docs/architecture/` |
|                 | Datenflüsse                          | `contracts/` |
| **Betrieb & Qualität** | Gates, CI/CD, Observability, Budgets | `docs/process/`, `ci/`, `policies/limits.yaml` |

## Navigationspfad für Außenstehende

1. **Einführung lesen:** `docs/overview/inhalt.md` liefert Vision, Prinzipien und Scope.
2. **Systematik prüfen:** Dieses Dokument zeigt, wo welche Detailtiefe zu finden ist.
3. **Architektur & Fahrplan vertiefen:**
   - `architekturstruktur.md` für Domänen & Komponenten.
   - `docs/process/fahrplan.md` für Timeline, Gates und Verantwortlichkeiten.
4. **Ethik & UX-Vertiefung:**
   - `docs/ethik/` für Entscheidungskriterien und Risikokataloge.
   - `docs/ux/` und `apps/web/README.md` für Prototypen und Research-Ansätze.

## Rollen & Verantwortlichkeiten

- **Ethik/Governance:** Kuratiert Policies, überprüft Releases gegen Schutzbedarfe.
- **UX-Research & Design:** Verantwortet Tests, Insights und Accessibility-Guidelines.
- **Tech Leads:** Halten Architekturdokumentation und Verträge aktuell.
- **Ops & QA:** Betreiben Gates, Observability und Budget-Checks in CI.

## Verbindung zu den Gates

Jedes Gate (A–D) besitzt eine eigene Dokumentation in `docs/process/`.
Die Gates stellen sicher, dass neue Funktionen den Ethik- und UX-Anforderungen
entsprechen, bevor sie in den produktiven Stack überführt werden.
Die Zusammenstellung dient als Index, um die passenden Unterlagen pro Gate rasch
zu finden.

> _Hinweis:_ Ergänzende Artefakte (z. B. Workshops, Entscheidungen, ADRs)
> werden im jeweiligen Ordner verlinkt, sobald sie vorliegen. Diese Systematik
> wird fortlaufend gepflegt und bildet den verbindlichen Einstiegspunkt für neue
> Teammitglieder ebenso wie externe Auditor:innen.
```


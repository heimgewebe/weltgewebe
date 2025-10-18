# Systematik & Strukturüberblick

Diese Zusammenstellung führt durch die zentralen Orientierungspunkte der Weltgewebe-Dokumentation. Sie ergänzt die inhaltliche Einführung (`docs/overview/inhalt.md`) und macht deutlich, wie Ethik & UX entlang des gesamten Vorhabens abgesichert werden.

## Kernartefakte

| Bereich | Zweck | Primäre Ressourcen |
| --- | --- | --- |
| **Ethik & Wirkung** | Leitplanken, Risiken, Schutzbedarfe | `policies/`, `docs/ethik/`, `docs/process/fahrplan.md` |
| **User Experience** | UX-Guidelines, Prototypen, Feedback-Loops | `apps/web/README.md`, `docs/ux/`, `docs/runbooks/` |
| **Architektur** | Technische Boundaries, Integrationen, Datenflüsse | `architekturstruktur.md`, `docs/architecture/`, `contracts/` |
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

Jedes Gate (A–D) besitzt eine eigene Dokumentation in `docs/process/`. Die Gates stellen sicher, dass neue Funktionen den Ethik- und UX-Anforderungen entsprechen, bevor sie in den produktiven Stack überführt werden. Die Zusammenstellung dient als Index, um die passenden Unterlagen pro Gate rasch zu finden.

> _Hinweis:_ Ergänzende Artefakte (z. B. Workshops, Entscheidungen, ADRs) werden im jeweiligen Ordner verlinkt, sobald sie vorliegen. Diese Systematik wird fortlaufend gepflegt und bildet den verbindlichen Einstiegspunkt für neue Teammitglieder ebenso wie externe Auditor:innen.

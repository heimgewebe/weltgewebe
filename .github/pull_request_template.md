## Ziel

Kurz: Was wird erreicht?

## Motivation / Kontext

Warum ist das nötig? Welche Symptome / Tickets / Logs?

## Änderungen

- [ ] Code
- [ ] Config / Compose
- [ ] Docs / Runbook

## Compose / Deploy-Check (Pflicht bei infra/compose Änderungen)

- [ ] `docker compose -f infra/compose/compose.prod.yml config` ist grün
- [ ] Keine neuen relativen host volume paths (Guard; Ausnahmen werden vom Guard explizit ausgegeben)
- [ ] Health:
  - [ ] `/health/live` ok
  - [ ] `/health/ready` ok (alle checks true)

## Risikoabschätzung

Was kann schiefgehen? Rollback-Weg?

## Verifikation

Wie getestet? Logs / Screenshots / Kommandos.

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

## Follow-ups

Was bleibt offen, was kommt in einen Folge-PR?

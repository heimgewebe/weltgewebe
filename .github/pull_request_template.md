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
- [ ] Keine neuen relativen host volume paths in compose.prod.yml
- [ ] Health:
  - [ ] `/health/live` ok
  - [ ] `/health/ready` ok (alle checks true)

## Risikoabschätzung

Was kann schiefgehen? Rollback-Weg?

## Verifikation

Wie getestet? Logs / Screenshots / Kommandos.

## Follow-ups

Was bleibt offen, was kommt in einen Folge-PR?

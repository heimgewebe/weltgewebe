# CI – Roadmap

- prose (vale)
- web (budgets)
- api (clippy/tests)
- security (trivy)

## CI (Platzhalter)

Diese Repo-Phase ist Docs-only. `ci/budget.json` dient als Referenz für spätere Gates.

### Frontend

- `npm run ci` im Web-Paket prüft das Performance-Budget per
  `ci/scripts/assert-web-budget.mjs` und lässt Linting sowie
  `svelte-check --fail-on-warnings` laufen. Der Budget-Assert erwartet die
  Schlüssel `js_kb_max`, `tti_ms_p95_max` und `inp_ms_p75_max` unter
  `budgets.web`.
- Ein dedizierter GitHub-Actions-Job `e2e` baut das Frontend, startet einen
  Preview-Server unter `127.0.0.1:4173`, führt die Playwright-Suite via
  `npm run test:ci` aus und lädt den HTML-Report als Artefakt hoch.

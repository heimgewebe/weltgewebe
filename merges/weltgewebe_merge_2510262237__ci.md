### 📄 ci/README.md

**Größe:** 200 B | **md5:** `d5d468659276cd627ef5d0055a942b75`

```markdown
# CI – Roadmap

- prose (vale)
- web (budgets)
- api (clippy/tests)
- security (trivy)

## CI (Platzhalter)

Diese Repo-Phase ist Docs-only. `ci/budget.json` dient als Referenz für spätere Gates.
```

### 📄 ci/budget.json

**Größe:** 123 B | **md5:** `d1377d85d1cc1645b5f2440bb0d08f25`

```json
{
  "budgets": {
    "web": {
      "js_kb_max": 60,
      "tti_ms_p95_max": 2000,
      "inp_ms_p75_max": 200
    }
  }
}
```


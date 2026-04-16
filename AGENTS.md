---
id: repo.agents
title: AGENTS
doc_type: policy
status: active
canonicality: canonical
summary: Agent configuration and operational boundaries for Weltgewebe.
---

# AGENTS

## Binding Reading Protocol

All agents MUST follow the [Agent Reading Protocol](docs/policies/agent-reading-protocol.md).

**Core Rules (Strictly Binding):**

1. **Reading Order:** `repo.meta.yaml` -> `AGENTS.md` -> `agent-policy.yaml` -> `docs/policies/agent-reading-protocol.md`
2. **Conflict Resolution:** Kanonisch und vollständig definiert in `repo.meta.yaml` (`truth_model.precedence`).
3. **No Interpolation:** Silent interpolation is FORBIDDEN. Explicitly name missing gaps.
4. **Abort Rule:** Agents MUST abort if contradictions are unresolvable, necessary files are missing, or target proof is impossible.
5. **Navigation vs Truth:** `docs/index.md` is strictly navigation (`navigational_indices`). `docs/_generated/*` is strictly diagnostic (`generated_diagnostics`).

These core rules derive from the canonical definitions in `repo.meta.yaml` and the `Agent Reading Protocol`. They override implicit interpretation.

## Purpose

Agent configuration, operational boundaries, and strict coding guidelines for Weltgewebe. This document defines how agents navigate the repository, canonical files, and the rules for CI-ready code contributions.

## Read This First

1. Begin with `repo.meta.yaml` and `docs/policies/agent-reading-protocol.md` to understand the truth structure. Navigation can be found in `docs/index.md`.
2. Read the "Coding Guidelines" below. Sie definieren, wie Code-Snippets syntaktisch korrekt, ausführbar und CI-tauglich vorgeschlagen werden müssen – statt nur „so ungefähr“ zu passen.

## Canonical Sources

- `repo.meta.yaml`
- `AGENTS.md`
- `agent-policy.yaml`
- `docs/policies/agent-reading-protocol.md`
- `docs/policies/architecture-critique.md` (cognitive module; canonical, but excluded from default reading order; activated via protocol rules)

## Discovery Rules

Scan `.github/workflows/`, `apps/`, `contracts/`, `docs/`, `infra/`, `scripts/`, `src/`, and `tests/` for changes.

## Generated Files

Files in `docs/_generated/` are automatically generated and protected.

## Safe Read Paths

- `README.md`
- `AGENTS.md`
- `docs/`

## Guarded / Risky Paths

- `.github/workflows/`
- `apps/`
- `contracts/`
- `docs/`
- `infra/`
- `scripts/`
- `src/`

## Required Checks

- `repo-structure-guard`
- `docs-relations-guard`
- `generated-files-guard`
- `coverage-guard`

## Common Traps

Do not manually edit `docs/_generated/` files. Ensure new code or docs are linked.

## Open Gaps

Ensure that critical infrastructure changes are added to `audit/impl-registry.yaml`.

## Coding Guidelines

### 1. Allgemeine Arbeitsweise

- Immer echte Dateien bevorzugen: Bevor du Code vorschlägst oder analysierst, musst du nach der realen Datei im Repo suchen und von dort aus arbeiten. Rate nicht frei, wenn die Datei existiert.
- Keine „stilisierten“ Snippets: Verwende keine verkürzten Schreibweisen wie SECONDS end oder zerstückelte Redirections (devtcpHOSTPORT). Alles, was du zeigst, muss so in einer echten Datei kompilierbar bzw. ausführbar sein.
- Vollständige Blöcke: Wenn du Funktionen oder Skripte änderst, zeige immer den ganzen betroffenen Block (z.B. komplette Funktion, komplettes Skript), nicht nur einzelne zerhackte Zeilen.
- Kennzeichnung von Auslassungen: Wenn du Teile weglässt, markiere das explizit mit Kommentaren wie // ... oder # ... ohne die Syntax zu zerstören.

### 2. Regeln für Node-/JS-Snippets (z.B. assert-web-budget.mjs)

- Erfolgsmeldungen nur bei tatsächlichem Erfolg:
  `console.log('Frontend performance budget matches expected thresholds')` oder ähnliche Erfolgsmeldungen dürfen nur ausgeführt werden, wenn vorher kein Fehler geworfen wurde.
- Wenn du throw verwendest, achte darauf, dass die Logik so strukturiert ist, dass bei Fehlern kein „Alles ok“ im CI-Log erscheint.
- Saubere Fehlermeldungen: Keine überflüssigen Zeichen am Ende von Template Strings, z.B. kein abschließendes Komma nach ${actual}.
- Fehlermeldungen müssen klar, einzeilig und ohne überflüssige Interpunktion sein.
- Strikte Typprüfungen: Wenn du Performance-Budgets oder Konfigwerte prüfst, nutze Muster wie:

```javascript
if (typeof actual !== 'number' || Number.isNaN(actual)) {
  throw new Error(`Performance budget value ${key} must be a number`)
}
```

- Vergleiche erwartete und tatsächliche Werte explizit und wirf Fehler mit verständlicher Botschaft:

```javascript
if (actual !== expectedValue) {
  throw new Error(
    `Performance budget key ${key} expected ${expectedValue} but found ${actual}`
  )
}
```

### 3. Regeln für Shell-Skripte (z.B. db-wait.sh)

- POSIX- oder Bash-Syntax niemals „optisch vereinfachen“.
- [ und ] brauchen immer Leerzeichen:

```bash
while [ "$SECONDS" -lt "$end" ]; do
```

- Redirections brauchen echte Pfade und Slashes:

```bash
echo >"/dev/tcp/$HOST/$PORT" 2>/dev/null
```

- Keine pseudo-kompakten, zusammengeklebten Tokens (z.B. SECONDS end, devtcpHOSTPORT, devnull).
- Variablen und Defaults: Verwende klare Standardwerte mit ${VAR:-default} und weise sie oben zu, z.B.:

```bash
HOST=${PGHOST:-localhost}
PORT=${PGPORT:-5432}
TIMEOUT=${DB_WAIT_TIMEOUT:-60}
INTERVAL=${DB_WAIT_INTERVAL:-2}
```

- Zeit-Logik korrekt schreiben. Integer-Deklaration sauber:

```bash
declare -i end=$SECONDS+$TIMEOUT
```

- Timeout-Schleife:

```bash
while [ "$SECONDS" -lt "$end" ]; do
  if echo >"/dev/tcp/$HOST/$PORT" 2>/dev/null; then
    printf 'Postgres is available at %s:%s\n' "$HOST" "$PORT"
    exit 0
  fi
  sleep "$INTERVAL"
done

printf 'Timed out waiting for Postgres at %s:%s after %s seconds\n' \
  "$HOST" "$PORT" "$TIMEOUT" >&2
exit 1
```

- Kein Pseudocode in echten Skripten: Wenn du ein Snippet als Beispiel zeigst, das nicht 1:1 lauffähig ist, musst du das ausdrücklich als Pseudocode markieren. In echten Dateien darfst du nur ausführbaren Code vorschlagen.

### 4. Verhalten bei Unsicherheit

- Wenn du dir bei einer Datei, Syntax oder Semantik nicht sicher bist, sage das explizit und schlage eine mögliche Variante vor.
- Bitte darum, den realen Build- oder Lint-Fehler zu posten, statt so zu tun, als wäre alles sicher.
- Bevor du Änderungen an CI-relevanten Skripten vorschlägst (Node, Bash, YAML), simuliere gedanklich mindestens:
  - Läuft das Skript von set -e / errexit umgeben sauber durch?
  - Sind alle Erfolgsmeldungen wirklich nur im Erfolgsfall sichtbar?

### 5. Zielbild

- Code-Vorschläge aus dieser Umgebung sollen direkt lauffähig, syntaktisch korrekt und CI-tauglich sein – ohne händische Nachkorrekturen von offensichtlichen Tipp- und Syntaxfehlern.

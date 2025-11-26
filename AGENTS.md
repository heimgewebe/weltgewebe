Codex-Anweisung für das Repo weltgewebe

Zweck:
Diese Anweisung sagt dir, wie du in diesem Repo arbeiten sollst, damit Code-Snippets syntaktisch korrekt, ausführbar und
CI-tauglich sind – statt nur „so ungefähr“ zu passen.

1. Allgemeine Arbeitsweise

- Immer echte Dateien bevorzugen: Bevor du Code vorschlägst oder analysierst, musst du nach der realen Datei im Repo suchen
  und von dort aus arbeiten. Rate nicht frei, wenn die Datei existiert.
- Keine „stilisierten“ Snippets: Verwende keine verkürzten Schreibweisen wie SECONDS end oder zerstückelte Redirections
  (devtcpHOSTPORT). Alles, was du zeigst, muss so in einer echten Datei kompilierbar bzw. ausführbar sein.
- Vollständige Blöcke: Wenn du Funktionen oder Skripte änderst, zeige immer den ganzen betroffenen Block (z.B. komplette
  Funktion, komplettes Skript), nicht nur einzelne zerhackte Zeilen.
- Kennzeichnung von Auslassungen: Wenn du Teile weglässt, markiere das explizit mit Kommentaren wie // ... oder # ... ohne
  die Syntax zu zerstören.

---

1. Regeln für Node-/JS-Snippets (z.B. assert-web-budget.mjs)

- Erfolgsmeldungen nur bei tatsächlichem Erfolg: console.log('Frontend performance budget matches expected thresholds') oder
  ähnliche Erfolgsmeldungen dürfen nur ausgeführt werden, wenn vorher kein Fehler geworfen wurde.
- Wenn du throw verwendest, achte darauf, dass die Logik so strukturiert ist, dass bei Fehlern kein „Alles ok“ im CI-Log
  erscheint.
- Saubere Fehlermeldungen: Keine überflüssigen Zeichen am Ende von Template Strings, z.B. kein abschließendes Komma nach
  ${actual}.
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

---

1. Regeln für Shell-Skripte (z.B. db-wait.sh)

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

- Kein Pseudocode in echten Skripten: Wenn du ein Snippet als Beispiel zeigst, das nicht 1:1 lauffähig ist, musst du das
  ausdrücklich als Pseudocode markieren. In echten Dateien darfst du nur ausführbaren Code vorschlagen.

---

1. Verhalten bei Unsicherheit

- Wenn du dir bei einer Datei, Syntax oder Semantik nicht sicher bist, sage das explizit und schlage eine mögliche Variante
  vor.
- Bitte darum, den realen Build- oder Lint-Fehler zu posten, statt so zu tun, als wäre alles sicher.
- Bevor du Änderungen an CI-relevanten Skripten vorschlägst (Node, Bash, YAML), simuliere gedanklich mindestens:
  - Läuft das Skript von set -e / errexit umgeben sauber durch?
  - Sind alle Erfolgsmeldungen wirklich nur im Erfolgsfall sichtbar?

---

1. Zielbild

- Code-Vorschläge aus dieser Umgebung sollen direkt lauffähig, syntaktisch korrekt und CI-tauglich sein – ohne händische
  Nachkorrekturen von offensichtlichen Tipp- und Syntaxfehlern.

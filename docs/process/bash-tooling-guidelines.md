# Bash Tooling Guidelines

Diese Richtlinie sammelt Best Practices für Bash-Utilities im Weltgewebe-Projekt.
Sie basiert auf Erfahrungen aus der Arbeit an unserem Entwicklungscontainer,
CLI-Hilfsprogrammen und Modultests. Die Beispiele orientieren sich an
Prototypen, die wir für die zukünftige Code Re-Entry Phase entworfen haben.

## Devcontainer-Setup

- **Bash-Version dokumentieren:** Skripte, die `nameref` nutzen, benötigen Bash
  ≥ 4.3. Ein kurzer Hinweis direkt unter der Shebang macht zukünftigen
  Mitwirkenden klar, welche Shell-Funktionen erwartet werden.
- **Paketsammlungen per Referenz füllen:** Statt Arrays per Subshell zu
  erzeugen, können Installationslisten über `local -n` an den Aufrufer
  übergeben werden. Dadurch werden unnötige Kopien vermieden und die Funktion
  kann Fehler (`return 1`) signalisieren, ohne das komplette Skript zu
  beenden.
- **`check`-Ziel aus Installationen ausklammern:** Hygiene-Checks sollten
  separat laufen. Wenn jemand `./setup.sh check` aus Versehen mit angibt,
  weisen wir darauf hin und ignorieren das Ziel, damit keine Pakete doppelt
  installiert werden.

## CLI-Bootstrap (`wgx`)

- **Debug-Ausgabe optional machen:** Über eine Umgebungsvariable wie
  `WGX_DEBUG=1` kann zusätzliche Diagnose aktiviert werden. Standardmäßig bleibt
  der CLI-Start leise, um Skriptausgaben nicht zu verwässern.
- **Subcommands validieren:** Ohne Argument soll der Dispatcher die Usage
  anzeigen und mit `exit 1` abbrechen. Unbekannte Befehle melden wir auf
  Englisch, damit Fehlermeldungen auch in CI-Logs international lesbar sind.
  Gleichzeitig geben wir die Usage-Hilfe auf `stderr` aus, um sofortige
  Selbsthilfe zu ermöglichen.

## SemVer-Caret-Ranges

- **`^0.0.x` strikt behandeln:** Für doppelt-nullte Versionen erlauben wir nur
  Patch-Updates. Tests stellen sicher, dass `^0.0.3` nicht auf `0.0.4`
  hochrutscht.
- **Major-Sprünge blockieren:** Ein zusätzlicher Testfall prüft, dass `^1.2.3`
  nicht auf `2.0.0` erweitert. So bleiben unsere Module kompatibel, bis wir
  explizit eine neue Major-Version freigeben.
- **Automatisierte Tests:** Bats-Tests dokumentieren das gewünschte Verhalten
  und verhindern Regressionen, sobald wir die Shell-Module produktiv setzen.

Diese Leitlinien werden zum Gate-C-Übergang erneut evaluiert und bei Bedarf in
konkrete Skripte überführt.

# Konfigurationsdefaults

`configs/app.defaults.yml` liefert die Basiswerte für die API. Zur Laufzeit können
Deployments eine alternative YAML-Datei via `APP_CONFIG_PATH` angeben oder einzelne
Felder mit `HA_*`-Variablen überschreiben (`HA_ANONYMIZE_OPT_IN`,
`HA_DELEGATION_EXPIRE_DAYS`).

`fade_days: 7` und der Kompatibilitätswert `HA_FADE_DAYS=7` spiegeln nur die
verfassungsfeste Lebensdauer neu abgeleiteter, unverzwirnter Fäden. Andere oder
syntaktisch ungültige Werte sind keine Konfiguration und verhindern den API-Start
fail-closed.

`ron_days` und `HA_RON_DAYS` wurden entfernt und werden ebenfalls fail-closed
abgewiesen. Für diese Oberfläche existiert kein Runtime-Verbraucher, der eine
RON-Aufbewahrungswirkung umsetzt; ein ladbarer Wert wäre daher Scheinsteuerbarkeit.

# Konfigurationsdefaults

`configs/app.defaults.yml` liefert die Basiswerte für die API. Zur Laufzeit können
Deployments eine alternative YAML-Datei via `APP_CONFIG_PATH` angeben oder einzelne
Felder mit `HA_*`-Variablen überschreiben (`HA_RON_DAYS`,
`HA_ANONYMIZE_OPT_IN`, `HA_DELEGATION_EXPIRE_DAYS`).

`fade_days: 7` und der Kompatibilitätswert `HA_FADE_DAYS=7` spiegeln nur die
verfassungsfeste Lebensdauer neu abgeleiteter, unverzwirnter Fäden. Andere oder
syntaktisch ungültige Werte sind keine Konfiguration und verhindern den API-Start
fail-closed.

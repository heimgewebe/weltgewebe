# Konfigurationsdefaults

`configs/app.defaults.yml` liefert die Basiswerte für die API. Zur Laufzeit können
Deployments eine alternative YAML-Datei via `APP_CONFIG_PATH` angeben oder einzelne
Felder mit `HA_*`-Variablen überschreiben (`HA_FADE_DAYS`, `HA_RON_DAYS`,
`HA_ANONYMIZE_OPT_IN`, `HA_DELEGATION_EXPIRE_DAYS`).

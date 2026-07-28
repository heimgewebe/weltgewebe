# Konfigurationsdefaults

`configs/app.defaults.yml` liefert die Basiswerte für die API. Zur Laufzeit können
Deployments eine alternative YAML-Datei via `APP_CONFIG_PATH` angeben oder einzelne
Felder mit `HA_*`-Variablen überschreiben (`HA_RON_DAYS`,
`HA_ANONYMIZE_OPT_IN`, `HA_DELEGATION_EXPIRE_DAYS`).

Die Lebensdauer neu abgeleiteter, unverzwirnter Fäden ist verfassungsfest auf
sieben Tage gebunden und deshalb kein Runtime-Feld. Die entfernten Oberflächen
`fade_days` und `HA_FADE_DAYS` werden fail-closed abgewiesen, damit alte
Deployment-Konfiguration keine Scheinsteuerbarkeit erzeugt.

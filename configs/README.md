# Konfigurationsdefaults

`configs/app.defaults.yml` liefert die Basiswerte für die API. Zur Laufzeit können
Deployments eine alternative YAML-Datei via `APP_CONFIG_PATH` angeben oder einzelne
Felder mit dokumentierten Umgebungsvariablen überschreiben, etwa
`HA_ANONYMIZE_OPT_IN`.

Die Lebensdauer neu abgeleiteter, unverzwirnter Fäden ist verfassungsfest auf
sieben Tage gebunden und deshalb kein Runtime-Feld. Die entfernten Oberflächen
`fade_days` und `HA_FADE_DAYS` werden fail-closed abgewiesen, damit alte
Deployment-Konfiguration keine Scheinsteuerbarkeit erzeugt.

`ron_days` und `HA_RON_DAYS` wurden ebenfalls entfernt und werden fail-closed
abgewiesen. Für diese Oberfläche existiert kein Runtime-Verbraucher, der eine
RON-Aufbewahrungswirkung umsetzt; ein ladbarer Wert wäre daher Scheinsteuerbarkeit.

`delegation_expire_days` und `HA_DELEGATION_EXPIRE_DAYS` wurden entfernt und
werden fail-closed abgewiesen. Es existiert kein Runtime-Verbraucher, der eine
Delegationsablaufwirkung umsetzt; ein ladbarer Wert wäre daher Scheinsteuerbarkeit.

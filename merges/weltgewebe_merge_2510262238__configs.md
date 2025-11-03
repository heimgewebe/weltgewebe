### 📄 configs/README.md

**Größe:** 323 B | **md5:** `5f291886a54691e71197bd288d398c5f`

```markdown
# Konfigurationsdefaults

`configs/app.defaults.yml` liefert die Basiswerte für die API. Zur Laufzeit können
Deployments eine alternative YAML-Datei via `APP_CONFIG_PATH` angeben oder einzelne
Felder mit `HA_*`-Variablen überschreiben (`HA_FADE_DAYS`, `HA_RON_DAYS`,
`HA_ANONYMIZE_OPT_IN`, `HA_DELEGATION_EXPIRE_DAYS`).
```

### 📄 configs/app.defaults.yml

**Größe:** 76 B | **md5:** `2e2703e5a92b04e9d68b1ab93b336039`

```yaml
fade_days: 7
ron_days: 84
anonymize_opt_in: true
delegation_expire_days: 28
```


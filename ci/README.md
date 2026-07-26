# CI – aktive Prüfpfade

- Prosa und Dokumentation
- Web-Build, Routenbudgets und Browserprüfungen
- API-, Rust- und PostgreSQL-Prüfungen
- Sicherheits- und Lieferkettenprüfungen

## Performancewahrheit

`policies/performance.v1.json` ist die einzige kanonische Quelle für
Performance-Metriken, Szenarien, Profile, Grenzwerte und deren Geltungsstatus.

- `ci/scripts/assert-web-budget.mjs` prüft den Vertrag und verhindert die
  Rückkehr ersetzter Parallelquellen.
- `apps/web/scripts/assert-route-performance-budget.mjs` misst beim Build die
  tatsächlich erzeugten initialen JavaScript- und CSS-Artefakte je Route und
  setzt den blockierenden `measurements.web_build`-Abschnitt durch.
- Browser-, API- und Ressourcenprofile tragen zunächst den Status
  `calibration_required`. Ihre eingetragenen Grenzwerte sind damit sichtbar,
  aber noch kein Freibrief für Produktionskapazität und kein blockierendes Gate.
- PostgreSQL-Planprüfungen bleiben als `blocking_plan_shape` gekennzeichnet;
  sie belegen keine Ende-zu-Ende-Latenz.

Ein Performancebericht ohne exakte Quellrevision weist ausdrücklich aus, dass
er keine revisionsgebundene Evidenz begründet.

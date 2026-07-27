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
- `apps/web/playwright.performance.config.ts` führt die kanonischen
  Browserprofile aus. Je Profil entstehen fünf frische Chromium-Läufe mit LCP,
  Interaction-to-Next-Paint und dem Zeitpunkt, an dem Karte, Marker und
  Werkzeugfächer benutzbar sind.
- `apps/web/scripts/assert-web-runtime-evidence.mjs` liest das erzeugte
  JSON-Artefakt unabhängig zurück. Der Required-Merge-Gate-Job scheitert bei
  fehlender Commitbindung, falscher Laufzahl, manipulierten Perzentilen oder
  unvollständigen Geltungsgrenzen.
- Browser-, API- und Ressourcenprofile tragen zunächst den Status
  `calibration_required`. Zielwertüberschreitungen werden deshalb im Artefakt
  ausgewiesen, blockieren aber noch nicht. Blockierend ist nur die Integrität
  der tatsächlich gemessenen Evidenz.
- PostgreSQL-Planprüfungen bleiben als `blocking_plan_shape` gekennzeichnet;
  sie belegen keine Ende-zu-Ende-Latenz.

Das Browserartefakt verwendet deterministische API- und Basemap-Fixtures. Es
belegt reproduzierbare synthetische Frontendmessungen für einen exakten Commit,
aber weder Produktionsfeldleistung noch API- oder Datenbankkapazität.

Ein Performancebericht ohne exakte Quellrevision weist ausdrücklich aus, dass
er keine revisionsgebundene Evidenz begründet.

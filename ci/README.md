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
- `.github/workflows/ci.yml` erkennt Änderungen an den tatsächlichen
  API-/Performance-Eingaben und ruft `.github/workflows/domain-scale.yml` genau
  einmal als wiederverwendbaren Beweis auf. Für solche Änderungen akzeptiert
  der `Required merge gate` ausschließlich einen erfolgreichen Runtime-Beweis;
  ein fehlgeschlagener oder fälschlich übersprungener Lastlauf blockiert den
  Merge. Der wiederverwendbare Workflow baut die API mit der exakten
  Checkout-Revision, lädt das validierte `domain-scale-ci`-Fixture vollständig
  in eine migrierte PostgreSQL-Instanz und führt das in der kanonischen Policy
  deklarierte Szenario gegen den echten `/search`-Repositorypfad aus.
  Vorher-/Nachher-Scrapes, k6-Perzentile und Fehlerrate,
  Docker-CPU/-Speicher sowie ein
  `pg_stat_activity`-Verbindungspunkt werden zu einem revisionsgebundenen
  Artefakt zusammengeführt, unabhängig verifiziert und hochgeladen. Derselbe
  Job verlangt außerdem für das Regression-Fixture einen revisionsgebundenen
  Bericht mit konkreten Grenzwertverletzungen und den spezifischen
  fail-closed Verifikationsgrund.
- Browser-, API- und Ressourcenprofile tragen zunächst den Status
  `calibration_required`. Das exakt revisionsgebundene API-Artefakt setzt die
  kanonischen Latenz- und Fehlerratengrenzen durch; für Browser- und
  Ressourcenprofile werden Zielwertüberschreitungen zunächst nur ausgewiesen.
  Die Integritäts- und Revisionsbindung bleibt in allen Fällen blockierend.
- PostgreSQL-Planprüfungen bleiben als `blocking_plan_shape` gekennzeichnet;
  sie belegen keine Ende-zu-Ende-Latenz.

Das Browserartefakt verwendet deterministische API- und Basemap-Fixtures. Es
belegt reproduzierbare synthetische Frontendmessungen für einen exakten Commit,
aber weder Produktionsfeldleistung noch API- oder Datenbankkapazität.

Auch das API-Artefakt ist synthetische CI-Evidenz: Die Manifestbindung belegt
das verwendete deterministische Fixture, nicht den Inhalt einer
Produktionsdatenbank, ihre Datenverteilung oder dauerhafte Live-Kapazität.

Ein Performancebericht ohne exakte Quellrevision weist ausdrücklich aus, dass
er keine revisionsgebundene Evidenz begründet.

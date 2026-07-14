<!--
Weltgewebe is the primary project. Replace R? with exactly one class:
R0 = Markdown-only, at most 50 changed lines
R1 = bounded low-risk change
R2 = application code, API, tests, scripts or dependencies
R3 = auth, privacy, security, concurrency, migration, workflow, deploy or operations
The gate rejects a class below the path-derived minimum.
-->
<!-- weltgewebe-risk: R? -->

## Ziel

<!-- Was soll sich für Nutzer oder Betrieb konkret ändern? -->

## Nicht-Ziele

<!-- Was ist ausdrücklich nicht Teil dieses PR? -->

## Zu bewahrende Invarianten

<!-- Welche Regeln dürfen trotz der Änderung nicht verletzt werden? -->

## Fehlerszenarien und Rückfallweg

<!-- Wie kann die Änderung scheitern, wie wird der Fehler erkannt und wie wird zurückgerollt? -->

## Prüfungen

<!-- Ausgeführte Tests und noch fehlende praktische Nachweise. Keine pauschalen Aussagen. -->

## Reviewevidenz

Der Workflow **Review Evidence Gate** erzeugt ein herunterladbares Paket mit:

- vollständigem `.diff` und anwendbarem `.patch`;
- Basis-, Head-, Merge-Basis- und Diff-SHA-256;
- Reviewauftrag und maschinenlesbarem Manifest;
- aktuellem Ergebnis der hashgebundenen Fremdreviews.

Reviewbelege gehören als PR-Kommentar in das Format aus der erzeugten
`*.review-request.md`. Jeder neue Push oder Basiswechsel entwertet frühere Belege.

## Veröffentlichung und Liveprüfung

<!-- Welche Produktionsoberfläche wird geprüft? Woran ist die exakte Version erkennbar? -->

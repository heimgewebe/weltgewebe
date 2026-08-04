---
id: deploy.germany-basemap-rollout
title: Deutschlandweite PMTiles-Basemap ausrollen
summary: Runbook für Vorbereitung, Aktivierung und sicheren Rückbau der deutschlandweiten PMTiles-Basemap.
doc_type: runbook
status: active
owner: product-map
relations:
  - type: implements
    target: docs/specs/map-experience.md
---
# Deutschlandweite PMTiles-Basemap ausrollen

## Ziel und Sicherheitsgrenze

Die Deutschland-Basemap wird als eigenständiges, versioniertes PMTiles-Artefakt
vorbereitet. Der bestehende Regionalpfad mit Hamburg und Schleswig-Holstein
bleibt Standard und Rückfallpfad.

Der Vorbereitungslauf veröffentlicht ausschließlich unveränderliche
Versionsdateien. Er verändert weder `basemap-germany.pmtiles` noch
`basemap-germany.meta.json`. Die stabilen Aliase werden erst innerhalb der
getrennten Aktivierungstransaktion umgestellt.

Die Clientaktivierung erfordert einen bewusst neu gebauten Frontend-Build mit:

- `PUBLIC_BASEMAP_MODE=local-sovereign`
- `PUBLIC_BASEMAP_VARIANT=germany`

Ohne `PUBLIC_BASEMAP_VARIANT` bleibt `regional` aktiv.

## Voraussetzungen

- sauberer, aktueller Checkout;
- Docker, Git, Node und pnpm;
- mindestens 64 GiB freier Arbeitsraum, sofern der Grenzwert nicht bewusst
  über `BASEMAP_MIN_FREE_BYTES` angepasst wurde;
- gepinnter OSM-Snapshot mit bekannter SHA256-Prüfsumme;
- vollständige, nicht leere Provenienz aus Dateiname, HTTPS-URL, SHA256 und
  einem realen, nicht zukünftigen Kalenderdatum;
- keine gleichzeitige Veröffentlichung in dasselbe Zielverzeichnis;
- keine parallele Aktivierung desselben Compose-Projekts. Der Aktivierungspfad
  erzwingt dies zusätzlich durch einen checkout-übergreifenden Prozess-Lock.

Versionierte Artefakte sind unveränderlich. Existiert eine Version bereits im
Build- oder Zielverzeichnis, muss eine neue `BASEMAP_VERSION` verwendet werden.
Ein Austausch unter demselben Versionsnamen ist nicht zulässig.

Planetiler läuft unter einer eindeutigen Containeridentität. Während des Builds
werden Container-CPU, Container-RAM, Arbeitsverzeichniswachstum und der maximale
Verbrauch des zugrunde liegenden Dateisystems gemessen. Der resultierende
`basemap-germany-v<version>.build.json`-Beleg bindet Quelle, Planetiler-Digest,
Artefakthash, Dauer und Spitzenwerte. Vorbereitung und Aktivierung weisen ein
Artefakt ohne diesen Beleg zurück.

## Phase 1: Version herstellen und veröffentlichen

`scripts/basemap/prepare-germany-rollout.sh` führt in dieser Reihenfolge aus:

1. reproduzierbaren Build durch `build-germany-pmtiles.sh` im isolierten
   Staging-Verzeichnis `build/basemap-staging/germany`;
2. Sentinel-, Hash- und Größenprüfung gegen das gebaute Artefakt;
3. vollständige Traversierung aller erreichbaren PMTiles-Verzeichnisse;
4. deterministische Stichprobe realer MVT-Kacheln gegen
   `map-style/style-germany.json`;
5. Erzeugung eines Validierungsumschlags, der den Validatorbericht an
   Artefaktname, SHA256 und Größe bindet, nicht an den früheren Staging-Pfad;
6. unveränderliche Veröffentlichung genau dieser vier Versionsdateien:
   - `basemap-germany-v<version>.pmtiles`
   - `basemap-germany-v<version>.meta.json`
   - `basemap-germany-v<version>.build.json`
   - `basemap-germany-v<version>.validation.json`
7. Readback, dass beide stabilen Germany-Aliase unverändert geblieben sind.

Die Metadaten tragen bis zur getrennten Aktivierung
`"activation": "opt-in"`.

## Phase 2: Runtime- und Gerätebeweis

Vor der Aktivierung müssen mindestens belegt sein:

- aktueller OSM-Snapshot; der Aktivierungsoperator akzeptiert standardmäßig
  höchstens 45 Tage alte Quelldaten;
- HTTP 200 und 206 über einen staginggebundenen echten Caddy-Pfad;
- `application/octet-stream`, `Accept-Ranges: bytes` und korrektes
  `Content-Range`;
- PMTiles-Signatur, Größe und SHA256 des geprüften Artefakts;
- dekodierte und sichtbare Kacheln aus Nord, Süd, Ost, West und Mitte;
- Browserabnahme mit MapLibre auf iPad und Desktop;
- keine Requests an externe Kartenanbieter;
- exakter Frontend-Commit und SHA256 des Germany-Stils;
- zeitlich begrenzter Beleg, standardmäßig höchstens 24 Stunden alt.

Die Belege werden als JSON-Datei an Artefakt, Frontend und Stil gebunden:

```json
{
  "schema_version": 1,
  "verdict": "PROVEN",
  "proofed_at": "2026-08-01T14:00:00+00:00",
  "basemap_version": "1.0.0",
  "artifact_sha256": "<64 hex>",
  "artifact_size_bytes": 123,
  "frontend_commit": "<40 hex>",
  "style_sha256": "<64 hex>",
  "proofs": [
    "desktop-maplibre",
    "ipad-maplibre",
    "five-region-visual",
    "no-external-map-requests",
    "staging-caddy-range"
  ]
}
```

Der Desktop-Beleg wird mit dem bewusst getrennten Deutschland-Lauf erzeugt:

```bash
GERMANY_BASEMAP_PROOF_ARTIFACT="$PWD/build/basemap-staging/germany/basemap-germany-v1.0.1.pmtiles" \
GERMANY_BASEMAP_PROOF_METADATA="$PWD/build/basemap-staging/germany/basemap-germany-v1.0.1.meta.json" \
pnpm -C apps/web test:proof:basemap-germany
```

Dieser Lauf prüft Hamburg, Berlin, Köln, Dresden und München mit derselben
versionierten Deutschland-PMTiles-Datei. Die beiden privaten Beweisvariablen
werden nur vom lokalen Vite-Dateiserver ausgewertet: Die HTTP-Aliasnamen bleiben
für MapLibre gleich, werden im Beweislauf aber direkt auf das benannte
Versionspaar abgebildet. Die stabilen Dateien in `build/basemap` werden dadurch
weder angelegt noch verändert. Beide Variablen müssen gemeinsam gesetzt sein,
auf reguläre Dateien ohne Symlink-Komponenten zeigen und dasselbe Verzeichnis
verwenden.

Für jede Region müssen dekodierte und sichtbare Features, ein eigener Screenshot
und eine lokale HTTP-206-Lieferung belegt sein. Die normale regionale Basemap-CI
führt diesen großen Beweis nicht implizit aus. Der Artefakthash wird dabei
gestreamt; die mehrere Gigabyte große Datei wird nicht vollständig in den
Node-Arbeitsspeicher geladen.

Der Caddy-Vertrag wird getrennt vom Entwicklungsserver bewiesen. Ein privater
Staging-Caddy muss die stabile Alias-URL bereitstellen; anschließend erzeugt der
Operator einen HTTP-200/206-, Header-, Signatur- und Vollhashbeleg:

```bash
python3 scripts/basemap/prove-germany-staging-caddy.py \
  --origin http://127.0.0.1:8787 \
  --artifact build/basemap-staging/germany/basemap-germany-v1.0.1.pmtiles \
  --output build/proofs/basemap-germany-caddy/proof.json
```

Der physische iPad-Beleg muss aus einer nativen `WKWebView` stammen und dieselbe
Artefakt-, Frontend- und Stilidentität tragen. Erst anschließend erzeugt
`scripts/basemap/assemble-germany-release-proof.py` aus Desktop-, iPad- und
Caddy-Rohbeleg den vom Aktivierer akzeptierten Umschlag. Der Assembler weist
fehlende Regionen,
Fremdanbieter-Anfragen, emulierte Geräte, veraltete Belege, Symlink-Artefakte
und abweichende Hashbindungen fail-closed zurück.

Der Pfad wird über `GERMANY_BASEMAP_RELEASE_PROOF_PATH` übergeben. Das
zulässige Belegalter kann über
`GERMANY_BASEMAP_RELEASE_PROOF_MAX_AGE_HOURS` enger gesetzt werden.

## Phase 3: Aktivierungstransaktion

`scripts/basemap/activate-germany-basemap.sh` ist der einzige vorgesehene
Aktivierungspfad. Er verlangt
`GERMANY_BASEMAP_ACTIVATION_CONFIRM=deploy-germany-pmtiles` und arbeitet
fail-closed. Ein separater Aktivierungs-Lock umfasst die vollständige
Transaktion vom ersten Alias-Readback bis zum bestätigten Receipt. Sein
Standardpfad folgt dem Compose-Projekt und – sofern gesetzt – dem bestehenden
`WELTGEWEBE_DEPLOY_LOCK_FILE`; ein abweichender Pfad kann explizit über
`GERMANY_BASEMAP_ACTIVATION_LOCK_FILE` gesetzt werden. Ein paralleler Lauf
bricht ab, bevor Aliase oder Receipt verändert werden:

1. ausgewählte Versionsdateien, Sentinel, Buildmessung und beide Validierungsberichte werden
   gegen Name, Hash, Größe, Region und Version geprüft;
2. die PMTiles-Tiefenvalidierung wird gegen die aktuellen Bytes wiederholt;
3. Gerätebeleg, Frontend-Commit, Stilhash und Belegalter werden geprüft;
4. unmittelbar vor der ersten sichtbaren Wirkung wird das OSM-Alter erneut
   gegen die aktuelle UTC-Zeit geprüft;
5. der bisherige Zustand beider stabilen Aliase wird erfasst;
6. beide Aliase werden auf das ausgewählte Versionspaar umgestellt und sofort
   zurückgelesen;
7. ein frischer Germany-Frontend-Build wird erzwungen;
8. lokaler und öffentlicher `/_app/basemap-build.json` müssen Variante,
   Frontend-Commit und Stilhash exakt ausweisen;
9. öffentlicher Stil, Sentinel und HTTP-206-Vertrag werden mit explizitem
   Verbindungs- und Gesamtzeitlimit gelesen;
10. das vollständige öffentliche PMTiles-Archiv wird innerhalb derselben
    Zeitgrenze gestreamt und gegen den vorbereiteten SHA256 gehasht;
11. erst danach wird `.ops/germany-basemap-activation.json` atomar geschrieben.

Die HTTP-Grenzen werden über
`GERMANY_BASEMAP_HTTP_CONNECT_TIMEOUT_SECONDS` und
`GERMANY_BASEMAP_HTTP_MAX_TIME_SECONDS` konfiguriert. Die Defaults sind 10
beziehungsweise 900 Sekunden.

## Rückfall

Jeder Fehler ab dem ersten Aliasversuch bis einschließlich Receipt-Schreiben
führt durch denselben Rückfallpfad:

1. beide Germany-Aliase werden gemeinsam auf ihren vorherigen Zustand
   zurückgestellt oder entfernt, falls sie vorher nicht existierten;
2. das Frontend wird mit `PUBLIC_BASEMAP_VARIANT=regional` neu gebaut;
3. der Aktivierungslauf endet fehlgeschlagen und schreibt keinen Erfolgsbeleg.

Das gilt auch für einen teilweise fehlgeschlagenen Aliaswechsel, einen
nichtnulligen Deploy-Abschluss, einen hängenden oder zu langsamen öffentlichen
Archivreadback und ein nicht beschreibbares State-Verzeichnis.

## Noch nicht automatisch erfüllt

- aktuellerer OSM-Snapshot als der eingebaute reproduzierbare Teststand vom
  1. Januar 2026;
- realer Deutschland-Buildbeleg auf dem Heim-PC;
- staginggebundener Caddy-Readback mit dem großen Artefakt;
- bundesweite visuelle Abnahme auf Desktop und iPad;
- gemessene Artefaktgröße, Builddauer, Spitzenlast und Bandbreite;
- physische iPad-Ausführung und Erzeugung des artefakt-, commit- und
  stilgebundenen Gerätefreigabebelegs; der Assembler selbst ist automatisiert.

Diese Punkte sind Freigabebedingungen, keine stillschweigend als erfüllt
geltenden Annahmen.

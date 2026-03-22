---
id: map-roadmap
title: Basemap-Umsetzungsroadmap
doc_type: roadmap
status: draft
canonicality: canonical
summary: >
  Roadmap zur schrittweisen operativen Umsetzung der souveränen Basemap-Architektur.
---

# Basemap-Umsetzungsroadmap

> **Hinweis:** Dieses Dokument ist der exekutive Pfad zur Umsetzung der
> [Basemap-Architektur-Blaupause](map-blaupause.md). Blueprint und Roadmap sind als Paket zu verstehen: Die Blaupause
> definiert das Zielbild (normativ), diese Roadmap definiert den Inkrementpfad (exekutiv).

## Phase 1 — Souveräne Basemap-Grundlage

**Ziel:** Die erste funktionale Pipeline zur Generierung und Bereitstellung eines Artefakts steht.

- [x] Zielregion für ersten Build festlegen (Entscheidung: Hamburg für schnelle Iteration)
- [x] Tile-Generator festlegen (Entscheidung: planetiler)
- [x] Artefaktformat festlegen (Entscheidung: PMTiles)
- [x] Hosting-Ziel festlegen (Entscheidung: Heimserver/Caddy für Produktion, Vite für Dev-Hosting)
- [x] Deterministische Build-Basis für Basemap-Artefakt herstellen (Tool-Basis gepinnt)
- [x] OSM-Input-Pin herstellen (historischer Snapshot mit SHA256-Prüfung statt "latest")

**Abnahmekriterium:** Ein lokal generiertes `.pmtiles`-Artefakt kann über einen HTTP-Endpunkt aufgerufen und gerendert
werden. **Nicht-Ziele:** Perfektes Styling, automatisierte CI-Pipeline für Artefakte.

## Phase 2 — Style-Souveränität

**Ziel:** Vollständige Kontrolle über die visuelle Präsentation der Basemap im eigenen Repository.

- [x] Eigenes `style.json` im `map-style`-Verzeichnis anlegen
- [x] Glyph- und Sprite-Strategie festlegen
  - _Umgesetzt (für das aktuelle MVP abgeschlossen): Lokales Asset-Hosting für Glyphs ist per reproduzierbarem Download-Skript (`fetch-glyphs.sh`) vorbereitet und best-effort in den `weltgewebe-up` Deployment-Guard eingebunden. Sprites sind im aktuellen Architekturziel bewusst nicht Teil der Basemap, da sie in einer beruhigten Infrastruktur-Basemap nicht benötigt werden._
- [x] Lizenz-/Asset-Manifest für Glyphs, Sprites und Fonts dokumentieren
  - _Umgesetzt: OFL-Lizenz und Herkunft für Noto Sans Glyphs im ASSETS.md dokumentiert. Das Fehlen der Sprites ist dort explizit architekturell begründet._
- [x] Basemap visuell beruhigen (Fokus auf Infrastruktur)
  - _Erledigt: Style ist minimalistisch und enthält keine POI-Icons. Visuelle Semantik liegt im Overlay._
- [ ] Overlay-Lesbarkeit gegen Basemap prüfen

**Abnahmekriterium:** Ein eigenes `style.json` wird geladen und Schriften (Glyphs) werden lokal/souverän serviert und sind
lizenzrechtlich dokumentiert. Die Basemap ist bewusst sprite-frei (keine Icons), da die visuelle Semantik vollständig in den Overlays (Nodes/Edges) liegt. **Nicht-Ziele:** Finale Farbpalette für alle Layer; dynamische Theming-Umschaltung
(Light/Dark).

## Phase 3 — Runtime-Integration

**Ziel:** MapLibre nutzt ausschließlich das eigene, souveräne PMTiles-Artefakt. _(Update: Dev-Infrastruktur im Vite-Server bereitet vor; Prod-Hosting in Caddy für Style und PMTiles unter `/local-basemap/` vorbereitet; produktiver Rollout steht noch aus.)_

- [x] PMTiles-Protokoll in MapLibre registrieren
- [x] Externe Style-Abhängigkeiten im Dev-Betrieb entfernen
  - _Hinweis: Der lokale Dev-Server nutzt nun die souveräne Struktur (`local-sovereign`)
    als Standard. CDN-Abhängigkeiten sind im Dev-Betrieb aufgelöst._
- [ ] Lokales bzw. selbst gehostetes Basemap-Artefakt in MapLibre anbinden
  - _Teilweise umgesetzt: Das Frontend-Flag (`PUBLIC_BASEMAP_MODE`) ermöglicht nun die produktive Freischaltung der \`local-sovereign\` Infrastruktur in Zielumgebungen wie \`weltgewebe.home.arpa\`. Der tatsächliche operative Rollout inkl. E2E-Nachweis und durchgängigem Deploy-Contract für die Produktions-Caddyfile bleibt ausstehend._
- [x] OSM-/ODbL-Attribution im MapLibre-Client sichtbar verankern
- [x] MapLibre Layer-Reihenfolge (Basemap vs. Overlays) final absichern (siehe `apps/web/src/lib/map/overlay/edges.ts`)

**Abnahmekriterium:** Die Weltgewebe-Anwendung lädt die Karte erfolgreich im Offline-/Intranet-Szenario ohne externe
Requests. **Nicht-Ziele:** Integration von nutzergenerierten Overlays (Fäden/Knoten) auf Datenbankebene.

## Phase 4 — Betrieb und Versionierung

**Ziel:** Die Basemap wird dauerhaft, vorhersehbar und sicher als Version gepflegt.

- [x] Versioniertes Artefakt-Schema definieren (z. B. `basemap-vX.pmtiles`)
- [x] Stabiler Alias-/Current-Pfad für das versionierte Artefakt bereitstellen
- [ ] Update-Zyklus definieren (z. B. monatliche OSM-Updates)
- [ ] Publish- und Rollback-Strategie festlegen
- [x] Basemap-Metadaten dokumentieren

**Abnahmekriterium:** Ein reproduzierbarer Cronjob oder CI-Workflow kann eine neue Version bauen und bereitstellen, ohne
Clients zu brechen. **Nicht-Ziele:** Real-Time OSM-Updates; vollautomatisches Deployment ohne Review.

## Phase 5 — Ausbau

**Ziel:** Erweiterung der souveränen Kartengrundlage um spezifische Sichten und Leistungsmerkmale.

- [ ] Regionale Tilesets ergänzen (Large Scale vs. Local Scale)
- [ ] Offline-Modus-Konzepte prüfen
- [ ] Heatmap- und Activity-Layer auf Basis der eigenen Infrastruktur ergänzen
- [ ] Mehrskalige Projektionen prüfen

**Abnahmekriterium:** Mindestens ein spezifisches Zusatzfeature (z. B. Heatmap oder regionales Tileset) ist in der
Architektur verankert und abrufbar. **Nicht-Ziele:** Implementierung einer komplett neuen Render-Engine.

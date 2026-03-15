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

> **Hinweis:** Dieses Dokument ist der exekutive Pfad zur Umsetzung der [Basemap-Architektur-Blaupause](map-blaupause.md). Blueprint und Roadmap sind als Paket zu verstehen: Die Blaupause definiert das Zielbild (normativ), diese Roadmap definiert den Inkrementpfad (exekutiv).

## Phase 1 — Souveräne Basemap-Grundlage

**Ziel:** Die erste funktionale Pipeline zur Generierung und Bereitstellung eines Artefakts steht.

- [ ] Zielregion für ersten Build festlegen (z. B. Hamburg / Germany / Europe)
- [ ] Tile-Generator festlegen (Standard: planetiler)
- [ ] Artefaktformat festlegen (PMTiles)
- [ ] Hosting-Ziel festlegen (z. B. Heimserver / S3 / R2)
- [ ] Basemap-Artefakt erstmals reproduzierbar bauen

**Abnahmekriterium:** Ein lokal generiertes `.pmtiles`-Artefakt kann über einen HTTP-Endpunkt aufgerufen und gerendert werden.
**Nicht-Ziele:** Perfektes Styling, automatisierte CI-Pipeline für Artefakte.

## Phase 2 — Style-Souveränität

**Ziel:** Vollständige Kontrolle über die visuelle Präsentation der Basemap im eigenen Repository.

- [ ] Eigenes `style.json` im `map-style` Repository anlegen
- [ ] Glyph- und Sprite-Strategie festlegen
- [ ] Lizenz-/Asset-Manifest für Glyphs, Sprites und Fonts dokumentieren
- [ ] Basemap visuell beruhigen (Fokus auf Infrastruktur)
- [ ] Overlay-Lesbarkeit gegen Basemap prüfen

**Abnahmekriterium:** Ein eigenes `style.json` wird geladen, Schriften und Icons werden lokal/souverän serviert und sind lizenzrechtlich dokumentiert.
**Nicht-Ziele:** Finale Farbpalette für alle Layer; dynamische Theming-Umschaltung (Light/Dark).

## Phase 3 — Runtime-Integration

**Ziel:** MapLibre nutzt ausschließlich das eigene, souveräne PMTiles-Artefakt.

- [ ] PMTiles-Protokoll in MapLibre registrieren
- [ ] Externe Style-Abhängigkeiten entfernen
- [ ] Lokales bzw. selbst gehostetes Basemap-Artefakt in MapLibre anbinden
- [ ] OSM-/ODbL-Attribution im MapLibre-Client sichtbar verankern
- [ ] MapLibre Layer-Reihenfolge (Basemap vs. Overlays) final absichern

**Abnahmekriterium:** Die Weltgewebe-Anwendung lädt die Karte erfolgreich im Offline-/Intranet-Szenario ohne externe Requests.
**Nicht-Ziele:** Integration von nutzergenerierten Overlays (Fäden/Knoten) auf Datenbankebene.

## Phase 4 — Betrieb und Versionierung

**Ziel:** Die Basemap wird dauerhaft, vorhersehbar und sicher als Version gepflegt.

- [ ] Versioniertes Artefakt-Schema definieren (z. B. `basemap-vX.pmtiles`)
- [ ] Update-Zyklus definieren (z. B. monatliche OSM-Updates)
- [ ] Publish- und Rollback-Strategie festlegen
- [ ] Basemap-Metadaten dokumentieren

**Abnahmekriterium:** Ein reproduzierbarer Cronjob oder CI-Workflow kann eine neue Version bauen und bereitstellen, ohne Clients zu brechen.
**Nicht-Ziele:** Real-Time OSM-Updates; vollautomatisches Deployment ohne Review.

## Phase 5 — Ausbau

**Ziel:** Erweiterung der souveränen Kartengrundlage um spezifische Sichten und Leistungsmerkmale.

- [ ] Regionale Tilesets ergänzen (Large Scale vs. Local Scale)
- [ ] Offline-Modus-Konzepte prüfen
- [ ] Heatmap- und Activity-Layer auf Basis der eigenen Infrastruktur ergänzen
- [ ] Mehrskalige Projektionen prüfen

**Abnahmekriterium:** Mindestens ein spezifisches Zusatzfeature (z. B. Heatmap oder regionales Tileset) ist in der Architektur verankert und abrufbar.
**Nicht-Ziele:** Implementierung einer komplett neuen Render-Engine.

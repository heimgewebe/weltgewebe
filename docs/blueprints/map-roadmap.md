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
- [ ] Hosting-Ziel festlegen (z. B. Heimserver / S3 / R2) _(Teilweise: Vite Dev-Server implementiert, Prod-Hosting in
      Caddy/Heimserver auf Infra-Ebene vorbereitet, echter End-to-End-Nachweis in Produktion fehlt)_
- [x] Deterministische Build-Basis für Basemap-Artefakt herstellen (Tool-Basis gepinnt)
- [ ] OSM-Input-Pin für volle Reproduzierbarkeit des Artefakts noch offen

**Abnahmekriterium:** Ein lokal generiertes `.pmtiles`-Artefakt kann über einen HTTP-Endpunkt aufgerufen und gerendert
werden. **Nicht-Ziele:** Perfektes Styling, automatisierte CI-Pipeline für Artefakte.

## Phase 2 — Style-Souveränität

**Ziel:** Vollständige Kontrolle über die visuelle Präsentation der Basemap im eigenen Repository.

- [x] Eigenes `style.json` im `map-style`-Verzeichnis anlegen
- [ ] Glyph- und Sprite-Strategie festlegen
  - _Teilweise dokumentiert: lokale Auslieferung über Repo-Pfade vorgesehen; konkrete Reproduktions- und Lieferkette
    noch zu finalisieren._
- [ ] Lizenz-/Asset-Manifest für Glyphs, Sprites und Fonts dokumentieren
  - _Teilweise dokumentiert: Font-Richtung beschrieben; Sprite-Lizenz und konkrete Asset-Bestückung noch offen (siehe
    `map-style/ASSETS.md`)._
- [ ] Basemap visuell beruhigen (Fokus auf Infrastruktur)
- [ ] Overlay-Lesbarkeit gegen Basemap prüfen

**Abnahmekriterium:** Ein eigenes `style.json` wird geladen, Schriften und Icons werden lokal/souverän serviert und sind
lizenzrechtlich dokumentiert. **Nicht-Ziele:** Finale Farbpalette für alle Layer; dynamische Theming-Umschaltung
(Light/Dark).

## Phase 3 — Runtime-Integration

**Ziel:** MapLibre nutzt ausschließlich das eigene, souveräne PMTiles-Artefakt.

- [x] PMTiles-Protokoll in MapLibre registrieren
- [x] Externe Style-Abhängigkeiten entfernen
  - _Hinweis: Der lokale Dev-Server nutzt nun die lokale souveräne Struktur (`local-sovereign`) als Standard._
- [x] Lokales bzw. selbst gehostetes Basemap-Artefakt in MapLibre anbinden
  - _Erreicht durch die Aktivierung von `local-sovereign` im Frontend und das Dev-Hosting über Vite. Ein vollautomatisches Produktion-Hosting-Setup auf dem Heimserver steht in Phase 1 und 4 weiterhin teilweise aus, die Laufzeitanbindung im Client ist jedoch nun bewiesen._
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

---
id: reports.map-status
title: Kartenstatus
summary: Kurzer, überprüfbarer Ist-Stand der Kartenimplementierung mit ausdrücklich begrenzten Runtimeaussagen.
doc_type: report
status: active
canonicality: diagnostic
lifecycle_state: active
lifecycle: audit
owner: product-map
owner_task: DOCMETA-REPORT-LIFECYCLE-001
review_after: 2026-08-11
relations:
  - type: supersedes
    target: docs/reports/map-status-matrix.md
  - type: verifies
    target: docs/specs/map-experience.md
---
# Kartenstatus

Stand: 11.07.2026. Dieses Dokument ist ein zeitgebundener Diagnosebericht. Der dauerhafte Produktvertrag steht in [`docs/specs/map-experience.md`](../specs/map-experience.md).

## Belegt im Repository

| Bereich | Ist-Stand | Beleg |
|---|---|---|
| Datenladung | `ok`, `partial` und `failed` werden getrennt | `apps/web/src/routes/map/+page.ts`, `map-load-fallback.spec.ts` |
| Szenenmodell | Rohdaten werden vor dem Rendering in eine explizite Szene übersetzt | `apps/web/src/lib/map/scene.ts`, `scene.test.ts` |
| Entitäten | Knoten und Garnrollen besitzen typisierte Kartenmodelle | `apps/web/src/lib/map/types.ts` |
| Interaktion | Auswahl öffnet das Fokuspanel; Schließen und Fokuswiederherstellung sind getestet | `map-interaction.spec.ts` |
| Suche und Filter | getrennte, gegenseitig ausschließende Kartenlinsen | `overlayManager.ts`, `ui-filter.spec.ts` |
| URL-Einstieg | `focus`, `lens` und `compose` werden typisiert ausgewertet | `urlState.ts`, `map-url-state.spec.ts` |
| Garnrolle | `not_on_map`, `exact` und `radius` sind im Browserpfad vorhanden | `garnrolle-self-service.spec.ts` |
| Knoten und Faden | Komposition erzeugt Knoten und den zugehörigen Faden | `KompositionPanel.svelte`, `komposition.spec.ts` |

## Bewusst nicht als vollständig bewiesen geführt

- produktiver Persistenzpfad des gesamten Flusses Anmeldung → Garnrolle → Knoten → Faden;
- endgültiger produktiver Basemap-Modus;
- echte Vector-Tile-Payload-Lieferung im produktionsnahen Caddy-Pfad;
- visuelle Korrektheit über repräsentative Zoomstufen und Geräte;
- URL-Bindung lokaler Panel-Tabs;
- dauerhaft gemessene Kartenleistung mit real wachsendem Gewebe.

## Betriebsgrenze

Grüne Unit- und Browsertests belegen die Repository- und Testumgebung. Sie belegen weder den aktuellen Zustand von `wg-prod-1` noch die dort aktive Datenquelle, Migration oder Basemap. Dafür ist eine frische Runtimeprüfung nötig.

## Nächster Beweis

Der nächste fachliche Integrationsbeweis ist der dauerhafte vertikale Schnitt:

1. anmelden;
2. Garnrolle beschreiben und verorten;
3. Knoten weben;
4. automatisch erzeugten Faden lesen;
5. nach Neuladen alle drei Objekte wiederfinden.

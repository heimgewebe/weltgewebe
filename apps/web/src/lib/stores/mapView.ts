/**
 * Map View Store (Kartenklarheit Phase 2)
 *
 * Owns the *presentation* derivations of the map: which entities are shown,
 * how they are filtered, which markers match the current search, and which
 * edges remain visible. Previously these derivations lived inline in
 * `routes/map/+page.svelte`, which made the route the sole owner of marker
 * description and panel-feeding state.
 *
 * This module decouples three concerns out of the route:
 *  - Auswahlzustand (selection)   -> `selectMapEntity()` delegates to uiView.
 *  - Markerbeschreibung (markers) -> `filteredMarkers`, `availableFilterTypes`,
 *                                    `searchMatchIds`, `visibleEdges`.
 *  - Paneldaten (panel feed)      -> the selected entity travels via uiView's
 *                                    `selection.data`; this store only feeds it.
 *
 * Ownership boundary:
 *  - This store owns *derived presentation* of the scene. It does NOT own the
 *    raw scene transformation (that is `lib/map/scene.ts`) nor the imperative
 *    map/overlay lifecycle (that stays in the route).
 *
 * URL query-parameter state vs. map state:
 *  - Map runtime state (center, zoom, bearing, pitch, selection, systemState,
 *    active filters, search query) is ephemeral and lives in stores / MapLibre.
 *    It is intentionally NOT mirrored into the URL.
 *  - The deep-link contract `l` / `r` / `t` (left drawer, right drawer, active
 *    tab) is a *separate*, URL-owned layer. It is documented in
 *    `docs/reports/map-status-matrix.md` and is deliberately kept out of this
 *    store so map runtime state and URL state never blur into each other.
 */
import { derived, writable } from "svelte/store";
import type { MapSceneModel } from "$lib/map/scene";
import type { Edge, MapEntityViewModel } from "$lib/map/types";
import { isRecord } from "$lib/utils/guards";
import { activeFilters } from "./filterStore";
import { isSearchOpen, searchQuery } from "./searchStore";
import { enterFokus, type Selection } from "./uiView";

const EMPTY_SCENE: MapSceneModel = {
  entities: [],
  edges: [],
  loadState: "ok",
  resourceStatus: [],
  diagnostics: {
    apiMode: "local",
    basemapMode: "local-sovereign",
    degraded: false,
  },
};

/**
 * The current scene. The route is the single writer (it builds the scene from
 * route data via `buildMapScene`) and pushes it here so the presentation
 * derivations can react without the route re-implementing them.
 */
export const mapScene = writable<MapSceneModel>(EMPTY_SCENE);

export function setMapScene(scene: MapSceneModel): void {
  mapScene.set(scene);
}

/** Explicit load state, mirrored from the scene. */
export const mapLoadState = derived(mapScene, ($scene) => $scene.loadState);

/** Diagnostics (api mode, basemap mode, degraded), mirrored from the scene. */
export const mapDiagnostics = derived(mapScene, ($scene) => $scene.diagnostics);

const RESOURCE_LABELS: Record<string, string> = {
  nodes: "Knoten",
  accounts: "Garnrollen",
  edges: "Fäden",
};

/** Human-readable labels for resources that failed to load. */
export const failedResourceLabels = derived(mapScene, ($scene) =>
  $scene.resourceStatus
    .filter((r) => r.status === "failed")
    .map((r) => RESOURCE_LABELS[r.resource] ?? r.resource),
);

/** All renderable entities of the current scene. */
export const markers = derived(mapScene, ($scene) => $scene.entities);

/** Diagnostic counts for the debug badge (nodes vs. accounts). */
export const markerCounts = derived(markers, ($markers) => ({
  nodes: $markers.filter((e) => e.type === "node").length,
  accounts: $markers.filter((e) => e.type !== "node").length,
}));

/** The filter bucket an entity belongs to (node kind, or "Garnrolle"). */
export function getFilterTypeKey(m: MapEntityViewModel): string {
  return m.type === "node" ? m.kind || "Knoten" : "Garnrolle";
}

/** Filterable type buckets with counts, sorted by label. */
export const availableFilterTypes = derived(markers, ($markers) => {
  const counts = new Map<string, number>();
  for (const m of $markers) {
    const typeKey = getFilterTypeKey(m);
    counts.set(typeKey, (counts.get(typeKey) || 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([id, count]) => ({
      id,
      label: id.charAt(0).toUpperCase() + id.slice(1),
      count,
    }))
    .sort((a, b) => a.label.localeCompare(b.label));
});

/** Markers visible under the active filter set. */
export const filteredMarkers = derived(
  [markers, activeFilters],
  ([$markers, $activeFilters]) =>
    $activeFilters.size === 0
      ? $markers
      : $markers.filter((m) => $activeFilters.has(getFilterTypeKey(m))),
);

/**
 * Search operates strictly on currently visible markers: the full set when no
 * filter is active, otherwise the filtered set.
 */
const searchBaseData = derived(
  [markers, filteredMarkers, activeFilters],
  ([$markers, $filteredMarkers, $activeFilters]) =>
    $activeFilters.size === 0 ? $markers : $filteredMarkers,
);

/** Up to 10 search matches for the current query, scoped to visible markers. */
export const searchResults = derived(
  [isSearchOpen, searchQuery, searchBaseData],
  ([$isSearchOpen, $searchQuery, $searchBaseData]) => {
    if ($isSearchOpen && $searchQuery.trim().length > 0) {
      const q = $searchQuery.toLowerCase();
      return $searchBaseData
        .filter((m) => {
          const titleMatch = m.title?.toLowerCase().includes(q);
          const summaryMatch = m.summary?.toLowerCase().includes(q);
          return titleMatch || summaryMatch;
        })
        .slice(0, 10);
    }
    return [] as MapEntityViewModel[];
  },
);

/** Ids of the current search matches, for marker highlighting. */
export const searchMatchIds = derived(
  searchResults,
  ($searchResults) => new Set($searchResults.map((r) => r.id)),
);

function isEdge(e: unknown): e is Edge {
  if (!isRecord(e)) return false;
  return (
    typeof e.id === "string" &&
    typeof e.source_id === "string" &&
    typeof e.target_id === "string" &&
    typeof e.edge_kind === "string"
  );
}

/** Edges whose endpoints are both currently visible markers. */
export const visibleEdges = derived(
  [mapScene, filteredMarkers],
  ([$scene, $filteredMarkers]) => {
    const validEdges = $scene.edges.filter(isEdge);
    const visibleIds = new Set($filteredMarkers.map((p) => p.id));
    return validEdges.filter(
      (e) => visibleIds.has(e.source_id) && visibleIds.has(e.target_id),
    );
  },
);

function normalizeSelectionType(
  type: MapEntityViewModel["type"],
): "node" | "garnrolle" {
  return type === "garnrolle" ? "garnrolle" : "node";
}

/**
 * Selection-state decoupling: turn a map entity into a focus selection.
 * This carries the panel data (`data: item`) into uiView's `selection`, which
 * the ContextPanel reads. The map-side concern (flyTo) stays in the route.
 */
export function selectMapEntity(item: MapEntityViewModel): void {
  const selection: NonNullable<Selection> = {
    type: normalizeSelectionType(item.type),
    id: item.id,
    data: item,
  };
  enterFokus(selection);
}

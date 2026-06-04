/**
 * Map View presentation helpers (Kartenklarheit Phase 2)
 *
 * Owns the *presentation* derivations of the map: which entities are shown,
 * how they are filtered, which markers match the current search, and which
 * edges remain visible. Previously these derivations lived inline in
 * `routes/map/+page.svelte`, which made the route the sole owner of marker
 * description and panel-feeding state.
 *
 * This module decouples three concerns out of the route:
 *  - Auswahlzustand (selection)   -> `selectMapEntity()` delegates to uiView.
 *  - Markerbeschreibung (markers) -> `deriveFilteredMarkers`,
 *                                    `deriveAvailableFilterTypes`,
 *                                    `deriveSearchMatchIds`, `deriveVisibleEdges`.
 *  - Paneldaten (panel feed)      -> the selected entity travels via uiView's
 *                                    `selection.data`; this module only feeds it
 *                                    through `toMapSelection` / `selectMapEntity`.
 *
 * Why pure functions instead of a module-level scene store:
 *  - The scene is *request-specific* data (it is built from the route's
 *    `load`-provided `data`). Holding it in a module-level `writable` would put
 *    request data into shared module state. Even though this app ships as a
 *    static SPA (adapter-static, no runtime SSR server), keeping the scene
 *    request-scoped in the component instance avoids that coupling entirely and
 *    keeps these derivations trivially unit-testable as pure transformations.
 *  - The route computes the scene locally (via `buildMapScene`) and feeds it,
 *    together with the ephemeral UI state (active filters, search query), into
 *    these pure functions. This module therefore owns no scene state of its own.
 *
 * Ownership boundary:
 *  - This module owns *derived presentation* of the scene as pure functions. It
 *    does NOT own the raw scene transformation (that is `lib/map/scene.ts`) nor
 *    the imperative map/overlay lifecycle (that stays in the route).
 *
 * URL query-parameter state vs. map state:
 *  - Map runtime state (center, zoom, bearing, pitch, selection, systemState,
 *    active filters, search query) is ephemeral and lives in stores / MapLibre.
 *    It is intentionally NOT mirrored into the URL.
 *  - The deep-link contract `l` / `r` / `t` (left drawer, right drawer, active
 *    tab) is a *separate*, URL-owned layer. It is documented in
 *    `docs/reports/map-status-matrix.md`. Its actual wiring remains Phase 4 and
 *    is deliberately kept out of this module so map runtime state and URL state
 *    never blur into each other.
 */
import type { MapSceneModel } from "$lib/map/scene";
import type { Edge, MapEntityViewModel } from "$lib/map/types";
import { isRecord } from "$lib/utils/guards";
import { enterFokus, type Selection } from "./uiView";

const RESOURCE_LABELS: Record<string, string> = {
  nodes: "Knoten",
  accounts: "Garnrollen",
  edges: "Fäden",
};

/** Human-readable labels for resources that failed to load. */
export function deriveFailedResourceLabels(scene: MapSceneModel): string[] {
  return scene.resourceStatus
    .filter((r) => r.status === "failed")
    .map((r) => RESOURCE_LABELS[r.resource] ?? r.resource);
}

/** Diagnostic counts for the debug badge (nodes vs. accounts). */
export function deriveMarkerCounts(markers: MapEntityViewModel[]): {
  nodes: number;
  accounts: number;
} {
  return {
    nodes: markers.filter((e) => e.type === "node").length,
    accounts: markers.filter((e) => e.type !== "node").length,
  };
}

/** The filter bucket an entity belongs to (node kind, or "Garnrolle"). */
export function getFilterTypeKey(m: MapEntityViewModel): string {
  return m.type === "node" ? m.kind || "Knoten" : "Garnrolle";
}

export type FilterType = { id: string; label: string; count: number };

/** Filterable type buckets with counts, sorted by label. */
export function deriveAvailableFilterTypes(
  markers: MapEntityViewModel[],
): FilterType[] {
  const counts = new Map<string, number>();
  for (const m of markers) {
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
}

/** Markers visible under the active filter set. */
export function deriveFilteredMarkers(
  markers: MapEntityViewModel[],
  activeFilters: Set<string>,
): MapEntityViewModel[] {
  return activeFilters.size === 0
    ? markers
    : markers.filter((m) => activeFilters.has(getFilterTypeKey(m)));
}

/**
 * Up to 10 search matches for the current query.
 *
 * Search operates strictly on the markers it is handed: callers pass the
 * currently *visible* markers (the full set when no filter is active, otherwise
 * the filtered set) so search never reaches hidden entities.
 */
export function deriveSearchResults(
  visibleMarkers: MapEntityViewModel[],
  query: string,
  isOpen: boolean,
): MapEntityViewModel[] {
  if (!isOpen || query.trim().length === 0) {
    return [];
  }
  const q = query.toLowerCase();
  return visibleMarkers
    .filter((m) => {
      const titleMatch = m.title?.toLowerCase().includes(q);
      const summaryMatch = m.summary?.toLowerCase().includes(q);
      return titleMatch || summaryMatch;
    })
    .slice(0, 10);
}

/** Ids of the current search matches, for marker highlighting. */
export function deriveSearchMatchIds(
  results: MapEntityViewModel[],
): Set<string> {
  return new Set(results.map((r) => r.id));
}

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
export function deriveVisibleEdges(
  edges: Edge[],
  filteredMarkers: MapEntityViewModel[],
): Edge[] {
  const validEdges = edges.filter(isEdge);
  const visibleIds = new Set(filteredMarkers.map((p) => p.id));
  return validEdges.filter(
    (e) => visibleIds.has(e.source_id) && visibleIds.has(e.target_id),
  );
}

function normalizeSelectionType(
  type: MapEntityViewModel["type"],
): "node" | "garnrolle" {
  return type === "garnrolle" ? "garnrolle" : "node";
}

/**
 * Pure selection adapter: turn a map entity into a uiView focus selection.
 * Carries the panel data (`data: item`) that the ContextPanel reads.
 */
export function toMapSelection(
  item: MapEntityViewModel,
): NonNullable<Selection> {
  return {
    type: normalizeSelectionType(item.type),
    id: item.id,
    data: item,
  };
}

/**
 * Selection-state decoupling: focus a map entity by delegating to uiView.
 * The map-side concern (flyTo) stays in the route. This is the one effectful
 * helper here; it mutates only ephemeral UI state (uiView), never scene data.
 */
export function selectMapEntity(item: MapEntityViewModel): void {
  enterFokus(toMapSelection(item));
}

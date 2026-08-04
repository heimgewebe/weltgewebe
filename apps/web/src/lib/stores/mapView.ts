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
 *  - The semantic deep-link contract (`focus`, `tab`, `lens`, `compose`) is a
 *    separate, URL-owned layer documented in `docs/specs/ui-interaction.md`.
 *    It is deliberately kept out of this module so map runtime state and URL
 *    state never blur into each other.
 */
import {
  getMapSearchTermsNormalized,
  normalizeMapSearchTerm,
} from "$lib/map/searchIndex";
import type { Edge, MapEntityViewModel } from "$lib/map/types";
import { isRecord } from "$lib/utils/guards";
import { enterFokus, type Selection } from "./uiView";

/** Diagnostic counts for the debug badge (nodes vs. accounts). */
export function deriveMarkerCounts(markers: MapEntityViewModel[]): {
  nodes: number;
  accounts: number;
  webgemeindezentren: number;
} {
  return {
    nodes: markers.filter((entity) => entity.type === "node").length,
    accounts: markers.filter((entity) => entity.type === "garnrolle").length,
    webgemeindezentren: markers.filter(
      (entity) => entity.type === "webgemeindezentrum",
    ).length,
  };
}

/** The filter bucket an entity belongs to (node kind, or "Garnrolle"). */
export function getFilterTypeKey(m: MapEntityViewModel): string {
  if (m.type === "node") return m.kind || "Knoten";
  if (m.type === "webgemeindezentrum") return "Webgemeindezentrum";
  return "Garnrolle";
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
  const q = normalizeMapSearchTerm(query.trim());
  const results: MapEntityViewModel[] = [];
  for (const marker of visibleMarkers) {
    const searchableTerms = getMapSearchTermsNormalized(marker);
    if (!searchableTerms.some((term) => term.includes(q))) continue;

    results.push(marker);
    if (results.length === 10) break;
  }
  return results;
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
export function deriveVisibleEdges<T extends Edge>(
  edges: T[],
  filteredMarkers: MapEntityViewModel[],
): T[] {
  const validEdges = edges.filter(isEdge);
  const visibleIds = new Set<string>();
  for (const marker of filteredMarkers) {
    visibleIds.add(marker.id);
    if (marker.type === "webgemeindezentrum") {
      visibleIds.add(marker.faden_endpoint_id);
    }
  }
  return validEdges.filter(
    (e) => visibleIds.has(e.source_id) && visibleIds.has(e.target_id),
  );
}

function normalizeSelectionType(
  type: MapEntityViewModel["type"],
): "node" | "garnrolle" | "webgemeindezentrum" {
  return type;
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

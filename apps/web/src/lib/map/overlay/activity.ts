import type { Map as MapLibreMap } from "maplibre-gl";

/**
 * Architectural Stub: Activity & Highlight Layer
 *
 * Responsibility:
 * This module is reserved for rendering node/account activity (e.g., recent updates,
 * high-density clusters, user status highlights) without bloating the main routing logic.
 *
 * Current state:
 * A no-op hook to establish the architectural boundary.
 *
 * Future implementations could include:
 * - Adding a heatmap layer for activity density.
 * - Adding pulse animations around active nodes.
 * - Managing highlighting states for specific nodes/edges.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function setupActivityInteraction(map: MapLibreMap) {
  // Setup logic would go here: e.g. map.addSource(), map.addLayer()

  return () => {
    // Teardown logic here
  };
}

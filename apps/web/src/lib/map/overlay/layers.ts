/**
 * Map Layer Ordering & Orchestration
 *
 * Architecture Note:
 * - Basemap = Orientierung (Provides orientation, roads, parks, rivers)
 * - Overlay = Weltgewebe-Bedeutung (Nodes, Edges, Activity, interactions)
 *
 * This file defines the canonical z-index / rendering order for all overlays.
 * Target Order (Bottom to Top):
 * 1. Basemap (vector tiles)
 * 2. Activity / Density (MapLibre heatmap layer, inserted before edge layers so edges stay readable)
 * 3. Edges (MapLibre 'line' layer)
 * 4. Nodes / Accounts (DOM Markers, so they sit above WebGL canvas)
 * 5. Focus / Highlight (DOM interaction via setupFocusInteraction)
 * 6. Komposition (DOM interaction via setupKompositionInteraction)
 */

export const LAYERS = {
  // 1. Basemap is handled by map.setStyle()

  // 2. Activity density heatmap — inserted before edge layers (see activity.ts ensureActivityLayer)
  ACTIVITY_SOURCE: "activity-source",
  ACTIVITY_LAYER: "activity-layer",

  // 3. Edges
  EDGES_SOURCE: "edges-source",
  EDGES_LAYER: "edges-layer",
  EDGES_HALO_LAYER: "edges-halo-layer",

  // 4. Nodes are HTML markers, so they inherently sit above WebGL.

  // 5. Focus / Highlight — DOM-based, see overlay/focus.ts

  // 6. Komposition — DOM-based, see overlay/komposition.ts
} as const;

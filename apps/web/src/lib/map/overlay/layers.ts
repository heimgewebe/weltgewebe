/**
 * Map Layer Ordering & Orchestration
 *
 * Architecture Note:
 * - Basemap = Orientierung (Provides orientation, roads, parks, rivers)
 * - Overlay = Weltgewebe-Bedeutung (Nodes, Edges, interactions)
 *
 * This file defines the canonical z-index / rendering order for all overlays.
 * Target Order (Bottom to Top):
 * 1. Basemap (vector tiles)
 * 2. Edges (MapLibre 'line' layer)
 * 4. Nodes / Accounts (DOM Markers, so they sit above WebGL canvas)
 * 5. Focus / Highlight (DOM elements or top-level layers)
 * 6. Komposition (Temporary interaction aides)
 */

export const LAYERS = {
  // 1. Basemap is handled by map.setStyle()

  // 2. Edges
  EDGES_SOURCE: "edges-source",
  EDGES_LAYER: "edges-layer",
  EDGES_HALO_LAYER: "edges-halo-layer",


  // 4. Nodes are HTML markers, so they inherently sit above WebGL.

  // 5. Focus / Highlight (planned, could be source/layer or DOM)

  // 6. Komposition (planned, could be source/layer or DOM)
} as const;

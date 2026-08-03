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
 * 2. Edges (MapLibre 'line' layers)
 * 3. Nodes / Accounts (DOM Markers, so they sit above WebGL canvas)
 * 4. Focus / Highlight (DOM elements or top-level layers)
 * 5. Komposition (Temporary interaction aides)
 */

export const LAYERS = {
  // 1. Basemap is handled by map.setStyle()

  // 2. Edges. MapLibre does not support data expressions for line-dasharray,
  // so every textile Faden pattern owns one fixed halo/main layer pair.
  EDGES_SOURCE: "edges-source",
  EDGES_LAYER: "edges-layer",
  EDGES_HALO_LAYER: "edges-halo-layer",
  EDGES_CONVERSATION_LAYER: "edges-conversation-layer",
  EDGES_CONVERSATION_HALO_LAYER: "edges-conversation-halo-layer",
  EDGES_PROPOSAL_LAYER: "edges-proposal-layer",
  EDGES_PROPOSAL_HALO_LAYER: "edges-proposal-halo-layer",
  EDGES_KNOTTING_LAYER: "edges-knotting-layer",
  EDGES_KNOTTING_HALO_LAYER: "edges-knotting-halo-layer",
  EDGES_VOTE_LAYER: "edges-vote-layer",
  EDGES_VOTE_HALO_LAYER: "edges-vote-halo-layer",

  // 3. Nodes are HTML markers, so they inherently sit above WebGL.

  // 4. Focus / Highlight (planned, could be source/layer or DOM)

  // 5. Komposition (planned, could be source/layer or DOM)
} as const;

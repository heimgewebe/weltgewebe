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
  // so every textile Faden pattern owns one fixed shadow/body/highlight triple.
  EDGES_SOURCE: "edges-source",
  EDGES_SHADOW_LAYER: "edges-shadow-layer",
  EDGES_LAYER: "edges-layer",
  EDGES_HIGHLIGHT_LAYER: "edges-highlight-layer",
  /** @deprecated Prefer EDGES_SHADOW_LAYER; kept as alias for older probes. */
  EDGES_HALO_LAYER: "edges-shadow-layer",
  EDGES_CONVERSATION_SHADOW_LAYER: "edges-conversation-shadow-layer",
  EDGES_CONVERSATION_LAYER: "edges-conversation-layer",
  EDGES_CONVERSATION_HIGHLIGHT_LAYER: "edges-conversation-highlight-layer",
  /** @deprecated Prefer EDGES_CONVERSATION_SHADOW_LAYER. */
  EDGES_CONVERSATION_HALO_LAYER: "edges-conversation-shadow-layer",
  EDGES_PROPOSAL_SHADOW_LAYER: "edges-proposal-shadow-layer",
  EDGES_PROPOSAL_LAYER: "edges-proposal-layer",
  EDGES_PROPOSAL_HIGHLIGHT_LAYER: "edges-proposal-highlight-layer",
  /** @deprecated Prefer EDGES_PROPOSAL_SHADOW_LAYER. */
  EDGES_PROPOSAL_HALO_LAYER: "edges-proposal-shadow-layer",
  EDGES_KNOTTING_SHADOW_LAYER: "edges-knotting-shadow-layer",
  EDGES_KNOTTING_LAYER: "edges-knotting-layer",
  EDGES_KNOTTING_HIGHLIGHT_LAYER: "edges-knotting-highlight-layer",
  /** @deprecated Prefer EDGES_KNOTTING_SHADOW_LAYER. */
  EDGES_KNOTTING_HALO_LAYER: "edges-knotting-shadow-layer",
  EDGES_VOTE_SHADOW_LAYER: "edges-vote-shadow-layer",
  EDGES_VOTE_LAYER: "edges-vote-layer",
  EDGES_VOTE_HIGHLIGHT_LAYER: "edges-vote-highlight-layer",
  /** @deprecated Prefer EDGES_VOTE_SHADOW_LAYER. */
  EDGES_VOTE_HALO_LAYER: "edges-vote-shadow-layer",

  // 3. Nodes are HTML markers, so they inherently sit above WebGL.

  // 4. Focus / Highlight (planned, could be source/layer or DOM)

  // 5. Komposition (planned, could be source/layer or DOM)
} as const;

export const LAYERS = {
  EDGES_SOURCE: 'edges-source',
  EDGES_LAYER: 'edges-layer',
} as const;

// We could add logic for dynamically determining layer order or enforcing it.
// Nodes are HTML markers in the current implementation, so they don't have a WebGL layer ID.

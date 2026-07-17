export interface Location {
  lat: number;
  lon: number;
}

export interface Module {
  id: string;
  label: string;
  locked: boolean;
  type: string;
}

export interface Node {
  id: string;
  kind: string;
  title: string;
  created_at: string;
  updated_at: string;
  summary?: string | null;
  info?: string | null;
  tags: string[];
  /** Human-readable address. Optional for nodes persisted before this field existed. */
  address?: string | null;
  location: Location;
  modules?: Module[];
}

export interface AccountBase {
  id: string;
  title: string;
  summary?: string | null;
  created_at: string;
  tags: string[];
  modules?: Module[];
}

export type GarnrolleMapState = "not_on_map" | "exact" | "radius";

export interface Account extends AccountBase {
  type: "garnrolle";
  location?: Location; // internal when available to trusted/local code
  public_pos?: Location; // public projection used by the map
  radius_m?: number;
  map_state?: GarnrolleMapState;
}

/**
 * @deprecated MapPoint uses lat/lng (inconsistent with domain's lat/lon).
 * Not used in the overlay pipeline. Retained only for potential external consumers.
 * See MapEntityViewModel for the canonical map entity type.
 */
export interface MapPoint {
  id: string;
  lat: number;
  lng: number;
  kind: string; // 'node' | 'account'
  data: Node | Account | unknown;
}

export interface Edge {
  id: string;
  source_id: string;
  source_type?: string;
  target_id: string;
  target_type?: string;
  edge_kind: string;
  created_at?: string | null;
  expires_at?: string | null;
}

export type EdgeLifecycle =
  | { kind: "legacy" }
  | { kind: "invalid" }
  | { kind: "faden"; createdAtMs: number; expiresAtMs: number };

/** Map-only edge model with lifecycle timestamps parsed exactly once. */
export interface MapEdge extends Edge {
  lifecycle: EdgeLifecycle;
}

// Phase 3: Discriminated union for map entities – eliminates semantic guesswork

/** A node entity rendered on the map. */
export interface MapEntityNode {
  type: "node";
  id: string;
  title: string;
  lat: number;
  lon: number;
  summary?: string | null;
  info?: string | null;
  kind: string;
  tags: string[];
  modules?: Module[];
  created_at: string;
  updated_at?: string;
  weight?: number;
}

/** A Garnrolle entity rendered on the map when it has a public position. */
export interface MapEntityGarnrolle {
  type: "garnrolle";
  id: string;
  title: string;
  lat: number;
  lon: number;
  summary?: string | null;
  modules?: Module[];
  created_at: string;
  tags?: string[];
  weight?: number;
}

/**
 * Discriminated union of all map-renderable entities.
 * The `type` field is the discriminant – it is always present and determines the variant.
 * Garnrollen without a public position are excluded from map rendering.
 */
export type MapEntityViewModel = MapEntityNode | MapEntityGarnrolle;

/**
 * @deprecated Use MapEntityViewModel for new code.
 * Retained as structural compatibility alias during migration.
 * The key difference: MapEntityViewModel requires `type` as a discriminant.
 */
export interface RenderableMapPoint {
  id: string;
  title: string;
  lat: number;
  lon: number;
  summary?: string | null;
  info?: string | null;
  type?: string;
  modules?: Module[];
  created_at?: string;
  updated_at?: string;
  kind?: string;
  tags?: string[];
  weight?: number;
}

// Phase 1: Explicit load state – replaces silent fallback-to-empty semantics
export type MapLoadState = "ok" | "partial" | "failed";

export type MapResourceStatus = {
  resource: "nodes" | "accounts" | "edges";
  status: "ok" | "failed";
  error?: string;
};

// Phase 4: Diagnostics – separates API mode from basemap mode
export type MapDiagnostics = {
  apiMode: "remote" | "local";
  basemapMode: "local-sovereign" | "remote-style";
  degraded: boolean;
};

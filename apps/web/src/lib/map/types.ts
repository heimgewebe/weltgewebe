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

export interface AccountVerortet extends AccountBase {
  type: "garnrolle";
  mode: "verortet";
  location?: Location; // internal (omitted in public API responses)
  public_pos?: Location; // projected
  radius_m: number;
}

export interface AccountRon extends AccountBase {
  type: "ron";
  mode: "ron";
  location?: never;
  public_pos?: never;
  radius_m: number;
}

export type Account = AccountVerortet | AccountRon;

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
  target_id: string;
  edge_kind: string;
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

/** A garnrolle (located account) entity rendered on the map. */
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
 * Ron accounts are excluded because they have no position.
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

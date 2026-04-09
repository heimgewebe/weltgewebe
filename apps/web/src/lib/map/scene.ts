import type {
  Node,
  Account,
  Edge,
  RenderableMapPoint,
  MapLoadState,
  MapResourceStatus,
  MapDiagnostics,
} from "$lib/map/types";
import type { BasemapMode } from "$lib/map/config/basemap.current";

/**
 * MapSceneModel: the single source of truth for what the map should display.
 * Transforms raw route data into a structured representation.
 */
export type MapSceneModel = {
  entities: RenderableMapPoint[];
  edges: Edge[];
  loadState: MapLoadState;
  resourceStatus: MapResourceStatus[];
  diagnostics: MapDiagnostics;
};

export type MapSceneInput = {
  nodes: Node[];
  accounts: Account[];
  edges: Edge[];
  loadState: MapLoadState;
  resourceStatus: MapResourceStatus[];
  apiBase: string | undefined;
  basemapMode: BasemapMode;
};

/**
 * Resolves the API mode from the API base URL.
 * A configured PUBLIC_GEWEBE_API_BASE means remote; absent means local/demo.
 */
export function resolveApiMode(
  apiBase: string | undefined,
): "remote" | "local" {
  return apiBase ? "remote" : "local";
}

/**
 * Transforms nodes into RenderableMapPoint[].
 */
function mapNodesToEntities(nodes: Node[]): RenderableMapPoint[] {
  return nodes.map((n) => ({
    id: n.id,
    title: n.title,
    lat: n.location.lat,
    lon: n.location.lon,
    summary: n.summary,
    info: n.info,
    type: "node",
    modules: n.modules,
    created_at: n.created_at,
    updated_at: n.updated_at,
    kind: n.kind,
    tags: n.tags,
  }));
}

/**
 * Transforms accounts into RenderableMapPoint[].
 * Only accounts with a public_pos are renderable on the map.
 */
function mapAccountsToEntities(accounts: Account[]): RenderableMapPoint[] {
  const result: RenderableMapPoint[] = [];
  for (const a of accounts) {
    if (a.public_pos) {
      result.push({
        id: a.id,
        title: a.title,
        lat: a.public_pos.lat,
        lon: a.public_pos.lon,
        summary: a.summary,
        type: a.type,
        modules: a.modules,
        created_at: a.created_at,
      });
    }
  }
  return result;
}

/**
 * Builds the complete map scene from raw route data.
 * This is the single transformation point between data loading and map rendering.
 */
export function buildMapScene(input: MapSceneInput): MapSceneModel {
  const nodeEntities = mapNodesToEntities(input.nodes);
  const accountEntities = mapAccountsToEntities(input.accounts);

  const apiMode = resolveApiMode(input.apiBase);
  const degraded = input.loadState !== "ok";

  return {
    entities: [...nodeEntities, ...accountEntities],
    edges: input.edges,
    loadState: input.loadState,
    resourceStatus: input.resourceStatus,
    diagnostics: {
      apiMode,
      basemapMode: input.basemapMode,
      degraded,
    },
  };
}

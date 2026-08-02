/**
 * Map Scene Module
 *
 * Ownership: This module owns the transformation from raw route data
 * (nodes, accounts, edges, loadState) into the MapSceneModel.
 *
 * It is the single transformation point between data loading (+page.ts)
 * and map rendering (+page.svelte). No other module should duplicate
 * the node→entity or account→entity mapping logic.
 *
 * The scene is stateless and pure – it has no side effects.
 */
import type {
  Node,
  Account,
  Edge,
  Webgemeindezentrum,
  MapEdge,
  MapEntityViewModel,
  MapEntityNode,
  MapEntityGarnrolle,
  MapEntityWebgemeindezentrum,
  MapLoadState,
  MapResourceStatus,
  MapDiagnostics,
} from "$lib/map/types";
import type { BasemapMode } from "$lib/map/config/basemap.current";
import { normalizeEdgeLifecycle } from "$lib/map/edgeLifecycle";

/**
 * MapSceneModel: the single source of truth for what the map should display.
 * Transforms raw route data into a structured representation.
 */
export type MapSceneModel = {
  entities: MapEntityViewModel[];
  edges: MapEdge[];
  loadState: MapLoadState;
  resourceStatus: MapResourceStatus[];
  diagnostics: MapDiagnostics;
};

export type MapSceneInput = {
  nodes: Node[];
  accounts: Account[];
  edges: Edge[];
  webgemeindezentren: Webgemeindezentrum[];
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
 * Transforms nodes into MapEntityNode[].
 */
function mapNodesToEntities(nodes: Node[]): MapEntityNode[] {
  return nodes.map((n) => ({
    type: "node" as const,
    id: n.id,
    title: n.title,
    lat: n.location.lat,
    lon: n.location.lon,
    summary: n.summary,
    info: n.info,
    kind: n.kind,
    tags: n.tags,
    modules: n.modules,
    created_at: n.created_at,
    updated_at: n.updated_at,
  }));
}

/**
 * Transforms accounts into MapEntityGarnrolle[].
 * Only accounts with a public_pos are renderable on the map.
 */
function mapAccountsToEntities(accounts: Account[]): MapEntityGarnrolle[] {
  const result: MapEntityGarnrolle[] = [];
  for (const a of accounts) {
    if (a.public_pos) {
      result.push({
        type: "garnrolle" as const,
        id: a.id,
        title: a.title,
        lat: a.public_pos.lat,
        lon: a.public_pos.lon,
        summary: a.summary,
        tags: a.tags,
        modules: a.modules,
        created_at: a.created_at,
      });
    }
  }
  return result;
}

function mapWebgemeindezentrenToEntities(
  centers: Webgemeindezentrum[],
): MapEntityWebgemeindezentrum[] {
  return centers.map((center) => ({
    type: "webgemeindezentrum" as const,
    id: center.id,
    title: center.title,
    lat: center.location.lat,
    lon: center.location.lon,
    summary: center.meeting_note,
    tags: [
      "Webgemeindezentrum",
      center.ortsweberei.name,
      center.location_state_label,
      center.location_label,
    ],
    created_at: center.created_at,
    updated_at: center.updated_at,
    location_state: center.location_state,
    location_state_label: center.location_state_label,
    location_label: center.location_label,
    meeting_note: center.meeting_note,
    access_note: center.access_note,
    ortsweberei: center.ortsweberei,
  }));
}

/**
 * Builds the complete map scene from raw route data.
 * This is the single transformation point between data loading and map rendering.
 */
export function buildMapScene(input: MapSceneInput): MapSceneModel {
  const nodeEntities = mapNodesToEntities(input.nodes);
  const accountEntities = mapAccountsToEntities(input.accounts);
  const centerEntities = mapWebgemeindezentrenToEntities(
    input.webgemeindezentren,
  );

  const apiMode = resolveApiMode(input.apiBase);
  const degraded = input.loadState !== "ok";

  return {
    entities: [...nodeEntities, ...accountEntities, ...centerEntities],
    edges: input.edges.map(normalizeEdgeLifecycle),
    loadState: input.loadState,
    resourceStatus: input.resourceStatus,
    diagnostics: {
      apiMode,
      basemapMode: input.basemapMode,
      degraded,
    },
  };
}

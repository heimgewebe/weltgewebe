import { describe, it, expect, beforeEach } from "vitest";
import { get } from "svelte/store";
import { buildMapScene, type MapSceneModel } from "$lib/map/scene";
import type { Account, Edge, MapEntityViewModel, Node } from "$lib/map/types";
import {
  deriveFailedResourceLabels,
  deriveMarkerCounts,
  deriveAvailableFilterTypes,
  deriveFilteredMarkers,
  deriveSearchResults,
  deriveSearchMatchIds,
  deriveVisibleEdges,
  getFilterTypeKey,
  toMapSelection,
  selectMapEntity,
} from "./mapView";
import { selection, systemState, leaveToNavigation } from "./uiView";

const makeNode = (overrides: Partial<Node> = {}): Node => ({
  id: "node-1",
  kind: "Werkstatt",
  title: "Hammer Park",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
  tags: [],
  location: { lat: 53.5, lon: 10.0 },
  ...overrides,
});

const makeAccount = (overrides: Partial<Account> = {}): Account => ({
  id: "acc-1",
  type: "garnrolle",
  title: "Eine Garnrolle",
  created_at: "2025-01-01T00:00:00Z",
  tags: [],
  radius_m: 0,
  map_state: "exact",
  public_pos: { lat: 53.56, lon: 10.06 },
  ...overrides,
});

function sceneFrom(
  nodes: Node[],
  accounts: Account[],
  edges: Edge[] = [],
): MapSceneModel {
  return buildMapScene({
    nodes,
    accounts,
    edges,
    loadState: "ok",
    resourceStatus: [],
    apiBase: undefined,
    basemapMode: "local-sovereign",
  });
}

describe("mapView presentation helpers", () => {
  beforeEach(() => {
    // Only uiView carries effectful state (via selectMapEntity); reset it.
    leaveToNavigation();
  });

  it("can build an empty, non-degraded scene as the starting point", () => {
    const scene = sceneFrom([], []);
    expect(scene.entities).toHaveLength(0);
    expect(scene.diagnostics.degraded).toBe(false);
    expect(deriveFailedResourceLabels(scene)).toEqual([]);
  });

  it("derives failed resource labels from the scene", () => {
    const scene = buildMapScene({
      nodes: [],
      accounts: [],
      edges: [],
      loadState: "partial",
      resourceStatus: [
        { resource: "nodes", status: "ok" },
        { resource: "edges", status: "failed", error: "HTTP 500" },
      ],
      apiBase: undefined,
      basemapMode: "local-sovereign",
    });

    expect(scene.loadState).toBe("partial");
    expect(deriveFailedResourceLabels(scene)).toEqual(["Fäden"]);
  });

  it("exposes markers and diagnostic counts", () => {
    const scene = sceneFrom([makeNode()], [makeAccount()]);

    expect(scene.entities).toHaveLength(2);
    expect(deriveMarkerCounts(scene.entities)).toEqual({
      nodes: 1,
      accounts: 1,
    });
  });

  it("derives filterable types with counts and labels", () => {
    const scene = sceneFrom(
      [
        makeNode({ id: "n1", kind: "werkstatt" }),
        makeNode({ id: "n2", kind: "werkstatt" }),
      ],
      [makeAccount()],
    );

    expect(deriveAvailableFilterTypes(scene.entities)).toEqual([
      { id: "Garnrolle", label: "Garnrolle", count: 1 },
      { id: "werkstatt", label: "Werkstatt", count: 2 },
    ]);
  });

  it("filters markers by the active filter set", () => {
    const scene = sceneFrom([makeNode({ kind: "Werkstatt" })], [makeAccount()]);

    expect(deriveFilteredMarkers(scene.entities, new Set())).toHaveLength(2);

    const filtered = deriveFilteredMarkers(
      scene.entities,
      new Set(["Garnrolle"]),
    );
    expect(filtered).toHaveLength(1);
    expect(filtered[0].type).toBe("garnrolle");
  });

  it("returns search matches only when search is open with a query", () => {
    const scene = sceneFrom(
      [makeNode({ title: "Hammer Park" })],
      [makeAccount({ title: "Garn" })],
    );

    expect(deriveSearchResults(scene.entities, "hammer", false)).toHaveLength(
      0,
    );
    expect(deriveSearchResults(scene.entities, "", true)).toHaveLength(0);

    const results = deriveSearchResults(scene.entities, "hammer", true);
    expect(results).toHaveLength(1);
    expect(results[0].id).toBe("node-1");
    expect(deriveSearchMatchIds(results).has("node-1")).toBe(true);
  });

  it("stops scanning once the ten-result search limit is satisfied", () => {
    const matches: MapEntityViewModel[] = Array.from(
      { length: 10 },
      (_, index) => ({
        type: "node",
        id: `node-${index}`,
        title: `Needle ${index}`,
        kind: "Werkstatt",
        tags: [],
        created_at: "2025-01-01T00:00:00Z",
        lat: 53.5 + index * 0.001,
        lon: 10 + index * 0.001,
      }),
    );
    const sentinel = {
      ...matches[0],
      id: "must-not-be-scanned",
      title: "placeholder",
    };
    Object.defineProperty(sentinel, "title", {
      get() {
        throw new Error("search scanned beyond its ten-result limit");
      },
    });

    const results = deriveSearchResults([...matches, sentinel], "needle", true);
    expect(results).toHaveLength(10);
    expect(results.map((item) => item.id)).toEqual(
      matches.map((item) => item.id),
    );
  });

  it("finds Garnrollen by semantic type, plural and profile tags", () => {
    const scene = sceneFrom(
      [],
      [
        makeAccount({
          title: "Alexander Mohr",
          summary: "schaunmermal",
          tags: ["interest:Commons"],
        }),
      ],
    );

    for (const query of ["Garnrolle", "Garnrollen", "Commons"]) {
      const results = deriveSearchResults(scene.entities, query, true);
      expect(results).toHaveLength(1);
      expect(results[0].id).toBe("acc-1");
    }
  });

  it("finds Knoten by semantic type and kind", () => {
    const scene = sceneFrom(
      [makeNode({ title: "Fairschenkbox", kind: "Resource" })],
      [],
    );

    expect(deriveSearchResults(scene.entities, "Knoten", true)).toHaveLength(1);
    expect(deriveSearchResults(scene.entities, "Resource", true)).toHaveLength(
      1,
    );
  });

  it("scopes search to the visible markers it is handed", () => {
    const scene = sceneFrom(
      [makeNode({ title: "Findbar", kind: "Werkstatt" })],
      [makeAccount({ title: "Findbar" })],
    );

    // No filter: search sees the full marker set.
    expect(deriveSearchResults(scene.entities, "findbar", true)).toHaveLength(
      2,
    );

    // With a filter active, the caller hands search only the visible markers.
    const visible = deriveFilteredMarkers(
      scene.entities,
      new Set(["Garnrolle"]),
    );
    const results = deriveSearchResults(visible, "findbar", true);
    expect(results).toHaveLength(1);
    expect(results[0].type).toBe("garnrolle");
  });

  it("keeps only edges whose endpoints are both visible", () => {
    const scene = sceneFrom([makeNode()], [makeAccount()]);
    const edges: Edge[] = [
      {
        id: "e1",
        source_id: "node-1",
        target_id: "acc-1",
        edge_kind: "reference",
      },
      {
        id: "e2",
        source_id: "node-1",
        target_id: "missing",
        edge_kind: "reference",
      },
    ];

    const allVisible = deriveFilteredMarkers(scene.entities, new Set());
    expect(deriveVisibleEdges(edges, allVisible).map((e) => e.id)).toEqual([
      "e1",
    ]);

    // Filtering out the garnrolle removes the edge that needs it.
    const onlyNodes = deriveFilteredMarkers(
      scene.entities,
      new Set(["Werkstatt"]),
    );
    expect(deriveVisibleEdges(edges, onlyNodes)).toHaveLength(0);
  });

  it("getFilterTypeKey distinguishes nodes from garnrollen", () => {
    const nodeEntity: MapEntityViewModel = {
      type: "node",
      id: "node-1",
      title: "Test Node",
      lat: 53.5,
      lon: 10.0,
      kind: "Werkstatt",
      tags: [],
      created_at: "2025-01-01T00:00:00Z",
    };

    const garnrolleEntity: MapEntityViewModel = {
      type: "garnrolle",
      id: "acc-1",
      title: "Test Garnrolle",
      lat: 53.56,
      lon: 10.06,
      tags: [],
      created_at: "2025-01-01T00:00:00Z",
    };

    expect(getFilterTypeKey(nodeEntity)).toBe("Werkstatt");
    expect(getFilterTypeKey(garnrolleEntity)).toBe("Garnrolle");
  });

  it("toMapSelection carries panel data and normalizes the type", () => {
    const node: MapEntityViewModel = {
      type: "node",
      id: "node-1",
      title: "Hammer Park",
      lat: 53.5,
      lon: 10.0,
      kind: "Werkstatt",
      tags: [],
      created_at: "2025-01-01T00:00:00Z",
    };

    const sel = toMapSelection(node);
    expect(sel).toEqual({ type: "node", id: "node-1", data: node });
  });

  it("selectMapEntity moves selection into fokus with panel data", () => {
    const node: MapEntityViewModel = {
      type: "node",
      id: "node-1",
      title: "Hammer Park",
      lat: 53.5,
      lon: 10.0,
      kind: "Werkstatt",
      tags: [],
      created_at: "2025-01-01T00:00:00Z",
    };

    selectMapEntity(node);

    expect(get(systemState)).toBe("fokus");
    const sel = get(selection);
    expect(sel?.type).toBe("node");
    expect(sel?.id).toBe("node-1");
    expect(sel?.data).toBe(node);
  });
});

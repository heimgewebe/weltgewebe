import { describe, it, expect, beforeEach } from "vitest";
import { get } from "svelte/store";
import { buildMapScene, type MapSceneModel } from "$lib/map/scene";
import type { Account, Node } from "$lib/map/types";
import {
  setMapScene,
  mapScene,
  mapLoadState,
  failedResourceLabels,
  markers,
  markerCounts,
  availableFilterTypes,
  filteredMarkers,
  searchResults,
  searchMatchIds,
  visibleEdges,
  getFilterTypeKey,
  selectMapEntity,
} from "./mapView";
import { activeFilters } from "./filterStore";
import { isSearchOpen, searchQuery } from "./searchStore";
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

const makeAccount = (overrides: Partial<Account> = {}): Account =>
  ({
    id: "acc-1",
    type: "garnrolle",
    mode: "verortet",
    title: "Eine Garnrolle",
    created_at: "2025-01-01T00:00:00Z",
    tags: [],
    radius_m: 0,
    public_pos: { lat: 53.56, lon: 10.06 },
    ...overrides,
  }) as Account;

function sceneFrom(
  nodes: Node[],
  accounts: Account[],
  edges = [],
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

describe("mapView store", () => {
  beforeEach(() => {
    // Reset all shared store state between tests.
    setMapScene(sceneFrom([], []));
    activeFilters.set(new Set());
    isSearchOpen.set(false);
    searchQuery.set("");
    leaveToNavigation();
  });

  it("mirrors load state and failed resource labels from the scene", () => {
    setMapScene(
      buildMapScene({
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
      }),
    );

    expect(get(mapLoadState)).toBe("partial");
    expect(get(failedResourceLabels)).toEqual(["Fäden"]);
  });

  it("exposes markers and diagnostic counts", () => {
    setMapScene(sceneFrom([makeNode()], [makeAccount()]));

    expect(get(markers)).toHaveLength(2);
    expect(get(markerCounts)).toEqual({ nodes: 1, accounts: 1 });
  });

  it("derives filterable types with counts and labels", () => {
    setMapScene(
      sceneFrom(
        [
          makeNode({ id: "n1", kind: "werkstatt" }),
          makeNode({ id: "n2", kind: "werkstatt" }),
        ],
        [makeAccount()],
      ),
    );

    const types = get(availableFilterTypes);
    expect(types).toEqual([
      { id: "Garnrolle", label: "Garnrolle", count: 1 },
      { id: "werkstatt", label: "Werkstatt", count: 2 },
    ]);
  });

  it("filters markers by the active filter set", () => {
    setMapScene(sceneFrom([makeNode({ kind: "Werkstatt" })], [makeAccount()]));

    expect(get(filteredMarkers)).toHaveLength(2);

    activeFilters.set(new Set(["Garnrolle"]));
    const filtered = get(filteredMarkers);
    expect(filtered).toHaveLength(1);
    expect(filtered[0].type).toBe("garnrolle");
  });

  it("returns search matches only when search is open with a query", () => {
    setMapScene(
      sceneFrom(
        [makeNode({ title: "Hammer Park" })],
        [makeAccount({ title: "Garn" })],
      ),
    );

    expect(get(searchResults)).toHaveLength(0);

    isSearchOpen.set(true);
    searchQuery.set("hammer");

    const results = get(searchResults);
    expect(results).toHaveLength(1);
    expect(results[0].id).toBe("node-1");
    expect(get(searchMatchIds).has("node-1")).toBe(true);
  });

  it("scopes search to visible markers when a filter is active", () => {
    setMapScene(
      sceneFrom(
        [makeNode({ title: "Findbar", kind: "Werkstatt" })],
        [makeAccount({ title: "Findbar" })],
      ),
    );

    isSearchOpen.set(true);
    searchQuery.set("findbar");
    expect(get(searchResults)).toHaveLength(2);

    // Hide nodes via filter: only the garnrolle remains searchable.
    activeFilters.set(new Set(["Garnrolle"]));
    const results = get(searchResults);
    expect(results).toHaveLength(1);
    expect(results[0].type).toBe("garnrolle");
  });

  it("keeps only edges whose endpoints are both visible", () => {
    const edges = [
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
    setMapScene(sceneFrom([makeNode()], [makeAccount()], edges as never));

    expect(get(visibleEdges).map((e) => e.id)).toEqual(["e1"]);

    // Filtering out the garnrolle removes the edge that needs it.
    activeFilters.set(new Set(["Werkstatt"]));
    expect(get(visibleEdges)).toHaveLength(0);
  });

  it("getFilterTypeKey distinguishes nodes from garnrollen", () => {
    expect(getFilterTypeKey({ type: "node", kind: "Werkstatt" } as never)).toBe(
      "Werkstatt",
    );
    expect(getFilterTypeKey({ type: "garnrolle" } as never)).toBe("Garnrolle");
  });

  it("selectMapEntity moves selection into fokus with panel data", () => {
    const node = {
      type: "node" as const,
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

  it("mapScene starts from an empty, non-degraded scene", () => {
    setMapScene(sceneFrom([], []));
    const s = get(mapScene);
    expect(s.entities).toHaveLength(0);
    expect(s.diagnostics.degraded).toBe(false);
  });
});

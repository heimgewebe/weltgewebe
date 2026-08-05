import { describe, expect, it, vi } from "vitest";
import type { Map as MapLibreMap } from "maplibre-gl";
import type { MapEdge, MapEntityViewModel } from "$lib/map/types";
import { NodesOverlay, type MarkerConstructor } from "./nodes";
import { deriveWeaveEdges } from "$lib/stores/mapView";
import { weaveRuntime } from "./weaveRuntime";

function relation(id: string, sourceId: string, targetId: string): MapEdge {
  return {
    id,
    source_id: sourceId,
    target_id: targetId,
    edge_kind: "reference",
  } as MapEdge;
}

describe("NodesOverlay visibility and zoom ownership", () => {
  it("keeps relations for visible weave targets when source markers are filtered out", () => {
    const centerEndpoint = "22222222-2222-5222-8222-222222222222";
    const points = [
      { type: "node", id: "source" },
      {
        type: "webgemeindezentrum",
        id: "center",
        faden_endpoint_id: centerEndpoint,
      },
    ] as MapEntityViewModel[];
    const edges = [
      relation("visible-source", "source", centerEndpoint),
      relation("filtered-source", "missing", centerEndpoint),
      relation("hidden-target", "source", "missing"),
    ];
    const visibleEdgeIds = deriveWeaveEdges(edges, points).map(
      (edge) => edge.id,
    );

    expect(visibleEdgeIds).toEqual(["visible-source", "filtered-source"]);
  });

  it("owns and releases its MapLibre zoom listener", () => {
    const on = vi.fn();
    const off = vi.fn();
    const map = {
      getZoom: () => 12,
      on,
      off,
    } as unknown as MapLibreMap;
    const MarkerClass = class {} as unknown as MarkerConstructor;

    const overlay = new NodesOverlay(map, MarkerClass, weaveRuntime);
    expect(on).toHaveBeenCalledWith("zoom", expect.any(Function));

    overlay.destroy();
    expect(off).toHaveBeenCalledWith("zoom", expect.any(Function));
  });
});

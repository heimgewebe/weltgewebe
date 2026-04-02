import { describe, it, expect, vi } from "vitest";
import { updateActivity } from "./activity";
import type { RenderableMapPoint } from "$lib/map/types";

function makePoint(overrides: Partial<RenderableMapPoint> = {}): RenderableMapPoint {
  return { id: "p1", title: "P1", lat: 1, lon: 2, ...overrides };
}

function makeMap(sourceData?: object) {
  const source = sourceData
    ? { setData: vi.fn() }
    : undefined;

  return {
    getSource: vi.fn().mockReturnValue(source),
    addSource: vi.fn(),
    getLayer: vi.fn().mockReturnValue(undefined),
    getStyle: vi.fn().mockReturnValue({ layers: [] }),
    addLayer: vi.fn(),
  };
}

describe("updateActivity", () => {
  describe("showActivity = false", () => {
    it("does not add a new source when no source exists", () => {
      const map = makeMap();
      updateActivity(map as any, [makePoint()], false);
      expect(map.addSource).not.toHaveBeenCalled();
    });

    it("clears existing source data with an empty FeatureCollection", () => {
      const map = makeMap({});
      updateActivity(map as any, [makePoint()], false);
      const source = map.getSource.mock.results[0].value;
      expect(source.setData).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "FeatureCollection",
          features: [],
        }),
      );
      expect(map.addSource).not.toHaveBeenCalled();
    });

    it("does not add a layer when no source was touched", () => {
      const map = makeMap();
      updateActivity(map as any, [makePoint()], false);
      expect(map.addLayer).not.toHaveBeenCalled();
    });
  });

  describe("showActivity = true", () => {
    it("does not add a source when points is empty", () => {
      const map = makeMap();
      updateActivity(map as any, [], true);
      expect(map.addSource).not.toHaveBeenCalled();
    });

    it("adds a new source with non-empty FeatureCollection when points are present", () => {
      const map = makeMap();
      updateActivity(map as any, [makePoint()], true);
      expect(map.addSource).toHaveBeenCalledWith(
        "activity-source",
        expect.objectContaining({
          type: "geojson",
          data: expect.objectContaining({
            type: "FeatureCollection",
            features: expect.arrayContaining([
              expect.objectContaining({
                type: "Feature",
                geometry: expect.objectContaining({ type: "Point" }),
              }),
            ]),
          }),
        }),
      );
    });

    it("updates existing source data with features", () => {
      const map = makeMap({});
      updateActivity(map as any, [makePoint({ lat: 10, lon: 20 })], true);
      const source = map.getSource.mock.results[0].value;
      expect(source.setData).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "FeatureCollection",
          features: [
            expect.objectContaining({
              geometry: { type: "Point", coordinates: [20, 10] },
            }),
          ],
        }),
      );
    });

    it("defaults weight to 1 when not provided", () => {
      const map = makeMap();
      updateActivity(map as any, [makePoint()], true);
      const callArg = map.addSource.mock.calls[0][1];
      expect(callArg.data.features[0].properties.weight).toBe(1);
    });

    it("uses provided weight when it is a finite number", () => {
      const map = makeMap();
      updateActivity(map as any, [makePoint({ weight: 0.7 })], true);
      const callArg = map.addSource.mock.calls[0][1];
      expect(callArg.data.features[0].properties.weight).toBe(0.7);
    });
  });
});

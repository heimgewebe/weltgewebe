import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Edge visibility on load", () => {
  test("edges are rendered after map load without filter toggle", async ({
    page,
  }) => {
    await mockApiResponses(page);

    await page.goto("/map");

    // Wait for the map to fully load (including style)
    await page.waitForFunction(
      () => {
        const m = (window as any).__TEST_MAP__;
        return m && typeof m.isStyleLoaded === "function" && m.isStyleLoaded();
      },
      undefined,
      { timeout: 15000 },
    );

    // Wait for the edges layer to appear – this is the rendering layer, not just the data source
    await page.waitForFunction(
      () => {
        const m = (window as any).__TEST_MAP__;
        return (
          m &&
          m.getLayer("edges-layer") !== undefined &&
          m.getLayer("edges-halo-layer") !== undefined
        );
      },
      undefined,
      { timeout: 5000 },
    );

    // Verify the full rendering pipeline: source exists, layer exists, features are populated
    const edgeState = await page.evaluate(() => {
      const m = (window as any).__TEST_MAP__;
      if (!m)
        return {
          source: false,
          layer: false,
          haloLayer: false,
          featureCount: 0,
        };

      const source = m.getSource("edges-source");
      const layer = m.getLayer("edges-layer");
      const haloLayer = m.getLayer("edges-halo-layer");

      // Access GeoJSON data via the public serialize() API to avoid relying on internal _data
      let featureCount = 0;
      if (source && typeof source.serialize === "function") {
        const serialized = source.serialize();
        featureCount = serialized?.data?.features?.length ?? 0;
      }

      return {
        source: source !== undefined,
        layer: layer !== undefined,
        haloLayer: haloLayer !== undefined,
        featureCount,
      };
    });

    expect(edgeState.source).toBe(true);
    expect(edgeState.layer).toBe(true);
    expect(edgeState.haloLayer).toBe(true);
    expect(edgeState.featureCount).toBeGreaterThan(0);
  });
});

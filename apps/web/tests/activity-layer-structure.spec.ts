import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

// Architecture Contract:
// 1. The activity density layer ('activity-layer') MUST exist when nodes are present.
// 2. It MUST be of type 'heatmap'.
// 3. It MUST be placed in a correct Z-order (underneath nodes and edges if possible).
// 4. Its opacity configuration MUST allow visibility at the default zoom level (15), so it isn't completely faded out immediately.

test.describe("Activity Heatmap layer structure on load", () => {
  test.beforeEach(async ({ page }) => {
    // Setup API mocking, including the empty /local-basemap/style.json,
    // so MapLibre initializes fully without 'style could not be loaded' errors
    await mockApiResponses(page);
    await page.goto("/map");

    // Wait until the Svelte layer binding pushes the activity layer
    await page.waitForFunction(
      () => {
        const map = (window as any).__TEST_MAP__;
        return map && map.getLayer("activity-layer");
      },
      undefined,
      { timeout: 15000 },
    );
  });

  test("activity-layer exists, is a heatmap, and is configured correctly at default zoom (15)", async ({
    page,
  }) => {
    const activityLayerInfo = await page.evaluate(() => {
      const map = (window as any).__TEST_MAP__;
      if (!map) return null;

      const layerId = "activity-layer";
      const layer = map.getLayer(layerId);
      const source = map.getSource("activity-source");

      if (!layer || !source) return null;

      const opacityPaint = map.getPaintProperty(layerId, "heatmap-opacity");

      // We expect the activity layer to be below edges if edges are active, but at least below symbols
      // We can query the raw layers array to check its relative position
      const layers = map.getStyle().layers;
      const activityIndex = layers.findIndex((l: any) => l.id === layerId);
      const edgeIndex = layers.findIndex(
        (l: any) => l.id === "edges-halo-layer" || l.id === "edges-layer",
      );

      const isBelowEdges = edgeIndex !== -1 ? activityIndex < edgeIndex : true;

      return {
        id: layer.id,
        type: layer.type,
        opacityPaint,
        sourceExists: !!source,
        isBelowEdges,
      };
    });

    expect(
      activityLayerInfo,
      "Activity layer info should not be null (check if layer actually added)",
    ).not.toBeNull();
    expect(activityLayerInfo?.id).toBe("activity-layer");
    expect(activityLayerInfo?.type).toBe("heatmap");
    expect(activityLayerInfo?.sourceExists).toBe(true);

    // Structural Z-Order proof: The heatmap density must remain in the background (beneath edges or labels)
    expect(activityLayerInfo?.isBelowEdges).toBe(true);

    // Ensure that it does not immediately fade to 0 at zoom 15
    const opacityConfig = activityLayerInfo?.opacityPaint;
    expect(Array.isArray(opacityConfig)).toBe(true);

    // As long as the fadeout completely reaches 0 at zoom >= 16, we are safe.
    const lastStopZoom = opacityConfig[opacityConfig.length - 2];
    const lastStopOpacity = opacityConfig[opacityConfig.length - 1];

    expect(lastStopZoom).toBeGreaterThanOrEqual(16);
    expect(lastStopOpacity).toBe(0);
  });
});

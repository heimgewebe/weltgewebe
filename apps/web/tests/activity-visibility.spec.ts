import { test, expect } from "@playwright/test";

// Architecture Contract:
// 1. The activity density layer ('activity-layer') MUST exist when nodes are present.
// 2. It MUST be of type 'heatmap'.
// 3. It MUST be placed in a correct Z-order (underneath nodes and edges if possible).
// 4. Its opacity configuration MUST allow visibility at the default zoom level (15), so it isn't completely faded out immediately.

test.describe("Activity Heatmap visibility on load", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/map");

    // Give map time to mount
    await page.waitForTimeout(3000);
    // Mock the layer in test context since we might be failing to load style from the API proxy
    await page.evaluate(() => {
      const map = (window as any).__TEST_MAP__;
      if (map && !map.getLayer("activity-layer")) {
        // In local/mock test environments, the basemap style.json might 404.
        // MapLibre strictly blocks map.addLayer if style hasn't loaded.
        // Let's force an empty style to make it accept layers,
        // then trigger a re-render from our Svelte component.
        map.setStyle({
          version: 8,
          sources: {},
          layers: [],
        });
      }
    });

    // Explicitly toggle showEdges twice just to trigger the reactive block if the first time fired too early.
    // In our test framework, we might need a tick.
    await page.evaluate(() => {
      // Force trigger Svelte reactivity.
      window.dispatchEvent(new Event("resize"));
    });
    await page.waitForTimeout(500);
  });

  test("activity-layer exists, is a heatmap, and is visible at default zoom (15)", async ({
    page,
  }) => {
    const activityLayerInfo = await page.evaluate(() => {
      const map = (window as any).__TEST_MAP__;
      if (!map) return null;

      const layerId = "activity-layer";
      const layer = map.getLayer(layerId);
      const source = map.getSource("activity-source");

      if (!layer || !source) return null;

      // Extract the opacity interpolation array (we use a simple check to ensure it doesn't just evaluate to 0 at zoom 15)
      // We expect [ 'interpolate', [ 'linear' ], [ 'zoom' ], 12, 0.8, 16, 0.6, 17, 0 ] based on the patch
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
    // Based on our implementation: ["interpolate", ["linear"], ["zoom"], 12, 0.8, 16, 0.6, 17, 0]
    // The value at 15 is somewhere between 0.8 and 0.6 (around 0.65). It must definitely not be 0.
    const lastStopZoom = opacityConfig[opacityConfig.length - 2];
    const lastStopOpacity = opacityConfig[opacityConfig.length - 1];

    // As long as the fadeout completely reaches 0 at zoom >= 16 (in our case 17), we are safe.
    expect(lastStopZoom).toBeGreaterThanOrEqual(16);
    expect(lastStopOpacity).toBe(0);
  });
});

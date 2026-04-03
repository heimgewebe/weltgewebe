import { test, expect } from "@playwright/test";

test.describe("Activity Heatmap Removal Guard", () => {
  test("activity-layer and heatmap layers should not exist on the map", async ({
    page,
  }) => {
    await page.goto("/map");

    // Wait until the map is loaded and exposed on the window
    await page.waitForFunction(
      () => !!(window as any).__TEST_MAP__,
      undefined,
      { timeout: 10000 },
    );
    await page.waitForFunction(
      () => (window as any).__TEST_MAP__.isStyleLoaded(),
      undefined,
      { timeout: 10000 },
    );

    const result = await page.evaluate(() => {
      const map = (window as any).__TEST_MAP__ as maplibregl.Map;
      const layers = map.getStyle().layers;

      const hasActivityLayer = layers.some(
        (layer) => layer.id === "activity-layer",
      );
      const hasActivitySource = !!map.getSource("activity-source");
      const heatmapLayers = layers.filter((layer) => layer.type === "heatmap");

      return {
        hasActivityLayer,
        hasActivitySource,
        heatmapLayerCount: heatmapLayers.length,
      };
    });

    expect(result.hasActivityLayer).toBe(false);
    expect(result.hasActivitySource).toBe(false);
    expect(result.heatmapLayerCount).toBe(0);
  });
});

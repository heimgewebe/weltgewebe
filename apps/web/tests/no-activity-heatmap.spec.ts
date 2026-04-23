import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Activity Heatmap Removal Guard", () => {
  test("activity-layer and heatmap layers should not exist on the map", async ({
    page,
  }) => {
    // Setup API mocking, including the empty /local-basemap/style.json,
    // so MapLibre initializes fully without 'style could not be loaded' errors
    await mockApiResponses(page);
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
      const map = (window as any).__TEST_MAP__ as {
        getStyle(): { layers?: Array<{ id: string; type?: string }> };
        getSource(id: string): unknown;
      };
      const layers = map.getStyle().layers || [];

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

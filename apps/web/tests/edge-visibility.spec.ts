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

    // Wait briefly for the reactive edge update to propagate
    await page.waitForTimeout(500);

    // Verify that the edges GeoJSON source exists on the map
    const hasEdgeSource = await page.evaluate(() => {
      const m = (window as any).__TEST_MAP__;
      if (!m) return false;
      const source = m.getSource("edges-source");
      return source !== undefined;
    });

    expect(hasEdgeSource).toBe(true);
  });
});

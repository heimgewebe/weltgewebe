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

    // Wait for the edges GeoJSON source to appear on the map
    await page.waitForFunction(
      () => {
        const m = (window as any).__TEST_MAP__;
        return m && m.getSource("edges-source") !== undefined;
      },
      undefined,
      { timeout: 5000 },
    );

    const hasEdgeSource = await page.evaluate(() => {
      const m = (window as any).__TEST_MAP__;
      return m?.getSource("edges-source") !== undefined;
    });

    expect(hasEdgeSource).toBe(true);
  });
});

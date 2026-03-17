import { test, expect } from "@playwright/test";
import { mockApiResponses } from "./fixtures/mockApi";

test.describe("Search mode", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiResponses(page);

    await page.route("**/api/nodes", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "mock-node-1",
            title: "Abendliches Stricken",
            summary: "Wir stricken gemeinsam",
            kind: "Treffen",
            location: { lat: 51, lon: 10 },
            modules: [],
            created_at: new Date().toISOString(),
          },
        ]),
      });
    });

    await page.route("**/api/node/mock-node-1", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "mock-node-1",
          title: "Abendliches Stricken",
          summary: "Wir stricken gemeinsam",
          kind: "Treffen",
          location: { lat: 51, lon: 10 },
          modules: [],
          created_at: new Date().toISOString(),
        }),
      });
    });
  });

  test("toggles search overlay, highlights markers, and supports keyboard navigation with map centering", async ({
    page,
  }) => {
    // Navigate to map
    await page.goto("/map");

    // Click search button
    const searchBtn = page.locator('.action-bar button[aria-label="Suche"]');
    await searchBtn.click();

    // Verify search overlay appears
    const searchOverlay = page.locator('[data-testid="search-overlay"]');
    await expect(searchOverlay).toBeVisible();

    // Type query
    const searchInput = page.locator(".search-box input");
    await searchInput.fill("Strick");

    // Wait for results to render
    const resultItem = page.locator("li[role='option']").first();
    await expect(resultItem).toBeVisible({ timeout: 10000 });

    // Validate that the result type bubble is rendered
    await expect(resultItem.locator(".result-type")).toBeVisible();
    await expect(resultItem.locator(".result-title")).toContainText("Stricken");

    // Verify the map marker gets highlighted
    const highlightedMarker = page.locator(
      '.map-marker[data-search-match="true"]',
    );
    await expect(highlightedMarker).toBeVisible();
    await expect(highlightedMarker).toHaveAttribute("data-id", "mock-node-1");

    // Clear search and verify highlight is removed
    await searchInput.fill("");
    await expect(
      page.locator('.map-marker[data-search-match="true"]'),
    ).toHaveCount(0);

    // Refill and proceed to test keyboard navigation
    await searchInput.fill("Strick");
    await expect(resultItem).toBeVisible();

    // Focus is still on input. Press ArrowDown to highlight first result
    await searchInput.press("ArrowDown");

    // Verify ARIA activedescendant is set
    const firstResultId = `search-result-mock-node-1`;
    await expect(searchInput).toHaveAttribute(
      "aria-activedescendant",
      firstResultId,
    );

    // Check that the item has active class
    const activeItem = page.locator(`li#${firstResultId}.active`);
    await expect(activeItem).toBeVisible();

    // Press Enter to select
    await searchInput.press("Enter");

    // Verify search overlay is closed and ContextPanel is open (Fokus state)
    await expect(searchOverlay).not.toBeVisible();
    const contextPanel = page.locator('[data-testid="context-panel"]');
    await expect(contextPanel).toBeVisible();
    await expect(page.locator(".context-panel .panel-header h2")).toContainText(
      /Knoten/,
    );

    // Verify map is centered on the selected node (lon: 10, lat: 51)
    await page.waitForFunction(
      () => {
        const map = (window as any).__TEST_MAP__;
        if (!map) return false;
        const center = map.getCenter();
        // Allow slight epsilon for floating point math
        return (
          Math.abs(center.lng - 10) < 0.0001 &&
          Math.abs(center.lat - 51) < 0.0001
        );
      },
      { timeout: 10000 },
    );

    // Also verify search field was cleared
    await searchBtn.click();
    await expect(searchInput).toHaveValue("");
  });
});

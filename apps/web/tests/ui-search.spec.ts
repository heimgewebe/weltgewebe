import { test, expect } from "@playwright/test";

test.describe("Search mode", () => {
  // Use mock data to ensure we have results instead of relying on the backend
  test.beforeEach(async ({ page }) => {
    // Override the API response for nodes to guarantee data
    await page.route("/api/nodes", async (route) => {
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

    await page.route("/api/accounts", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.route("/api/edges", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "[]",
      });
    });
    await page.route("/api/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: '{"authenticated": false}',
      });
    });
  });

  test("toggles search overlay from action bar and filters results", async ({
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
    const resultItem = page.locator(".result-btn").first();
    await expect(resultItem).toBeVisible({ timeout: 10000 });

    // Validate that the result type bubble is rendered
    await expect(resultItem.locator(".result-type")).toBeVisible();
    await expect(resultItem.locator(".result-title")).toContainText("Stricken");

    // Click result
    await resultItem.click();

    // Verify search overlay is closed and ContextPanel is open (Fokus state)
    await expect(searchOverlay).not.toBeVisible();
    const contextPanel = page.locator('[data-testid="context-panel"]');
    await expect(contextPanel).toBeVisible();
    await expect(page.locator(".context-panel .panel-header h2")).toContainText(
      /Knoten|Garnrolle/,
    );
  });
});
